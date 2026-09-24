"""The gift-novel generation pipeline (spec 007, contract K4; docs Figure 5).

Public entry points: `generate` (also resumes) and `change_fact`. The functions below are
named after the TLA+ actions of `formal/tla/GiftNovelHarness.tla`:

| TLA+ action          | function                                         |
|----------------------|--------------------------------------------------|
| Plan                 | `plan_novel` (+ `persist_plan`, `_open_version`) |
| NextChapter / Resume | `_chapter_loop` (`first_incomplete_chapter`)     |
| WriteScene           | `write_scene` → `before_scene_accept`            |
| Editor               | `write_chapter` (editor pass)                    |
| CloseChapter         | `close_chapter` → `before_chapter_close`         |
| Checkpoint           | `checkpoint` → `save_chapter_and_checkpoint`     |
| PrePublish / Publish | `publish_version` → `before_publish`             |
| ChangeFact           | `change_fact` → `create_version_from`            |

The four TLC rules (formal/tla/COUNTEREXAMPLES.md) hold here:

* CE1 — `checkpoint` writes the chapter text and its checkpoint in one transaction.
* CE2 — the chapter retry budget is read from persisted `chapter_close` validator runs
  (`count_chapter_attempts`), counting only runs since the chapter was last reopened.
* CE3 — chapters are upserted on (version, chapter); a published version is never written.
* CE4 — the repair round is stored on `novel_version` in the same transaction that sets
  `blocked` and reopens the chapters; `publish_version` reads it.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from app.bible import BibleRepository, ChapterVersion, Fact, NovelVersion, word_count
from app.commons.db.connection import transaction
from app.commons.llm import ClaudeCodeModelClient, Document, ModelClient
from app.commons.observability import Observer, get_observer
from app.novel import context as cx
from app.novel._bible_ext import load_plan, rename_cast, store_plan
from app.novel.chronology import chronology_problems, normalise_events, plan_births
from app.novel.models import (
    ChangeResult,
    ChapterEdit,
    NovelPlan,
    RunResult,
    RunStatus,
    SceneDraft,
)
from app.novel.plan_check import check_plan
from app.novel.roles import Roles
from app.novel.setup import register_all, register_lean_for
from app.validators import (
    ValidationContext,
    ValidationPoint,
    ValidationResult,
    all_passed,
    run_point,
)

MAX_SCENE_RETRIES: Final[int] = 2
MAX_CHAPTER_RETRIES: Final[int] = 2
MAX_REPAIR_ROUNDS: Final[int] = 1
MAX_REPLANS: Final[int] = 1
DEFAULT_CHAPTERS: Final[int] = 10

Progress = Callable[[str], None]


class StopRunError(Exception):
    """A bounded budget is exhausted: the run ends in `stopped_error` with `reason`."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(slots=True)
class Run:
    repo: BibleRepository
    novel_id: str
    roles: Roles
    observer: Observer
    brief: dict[str, JsonValue]
    progress: Progress
    trace_id: str | None = None
    plan: NovelPlan | None = None
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def lengths(self) -> cx.Lengths:
        return cx.brief_lengths(self.brief)

    def require_plan(self) -> NovelPlan:
        if self.plan is None:  # pragma: no cover - set before any chapter work
            message = "no plan"
            raise RuntimeError(message)
        return self.plan

    def facts(self) -> list[Fact]:
        return [f for f in self.repo.list_facts(self.novel_id) if f.kind != "plan"]

    def forbidden(self) -> list[str]:
        return [t.term for t in self.repo.list_forbidden_terms(self.novel_id)]

    def names(self) -> list[str]:
        return cx.exact_names(self.brief)


# --------------------------------------------------------------------------------------
# Hook points (K4)
# --------------------------------------------------------------------------------------


def _ctx(
    run: Run,
    version: int,
    chapter: int | None,
    scene: int | None,
    text: str,
    **extra: object,
) -> ValidationContext:
    payload: dict[str, object] = {
        "brief": run.brief,
        "plan": plan_for_validators(run.plan) if run.plan is not None else {},
        "client": run.roles.client,
    }
    payload.update(extra)
    return ValidationContext(
        novel_id=run.novel_id,
        version=version,
        chapter=chapter,
        scene=scene,
        text=text,
        repo=run.repo,
        observer=run.observer,
        extra=payload,
        trace_id=run.trace_id,
    )


def plan_for_validators(plan: NovelPlan) -> dict[str, object]:
    """The plan as `ctx.extra["plan"]`: each `chapters[i]` also carries its scenes and the
    fact keys they use, so coverage evidence can name the chapter a fact was planned for."""
    data: dict[str, object] = plan.model_dump(mode="json")
    chapters: list[dict[str, object]] = []
    for chapter in plan.chapters:
        scenes = plan.scenes_of(chapter.number)
        chapters.append(
            {
                **chapter.model_dump(mode="json"),
                "facts_used": sorted({k for s in scenes for k in s.facts_used}),
                "scenes": [s.model_dump(mode="json") for s in scenes],
            }
        )
    data["chapters"] = chapters
    return data


def before_scene_accept(
    run: Run, version: int, chapter: int, scene: int, text: str
) -> list[ValidationResult]:
    return run_point(
        ValidationPoint.SCENE_ACCEPT,
        _ctx(
            run,
            version,
            chapter,
            scene,
            text,
            feedback_role="writer",
            role_output=SceneDraft(text=text),
            role_output_model=SceneDraft,
        ),
    )


def before_chapter_close(
    run: Run, version: int, chapter: int, edit: ChapterEdit, scene_texts: Sequence[str]
) -> list[ValidationResult]:
    return run_point(
        ValidationPoint.CHAPTER_CLOSE,
        _ctx(
            run,
            version,
            chapter,
            None,
            edit.text,
            scene_texts=list(scene_texts),
            chapter_title=edit.title,
            feedback_role="editor",
        ),
    )


def before_publish(run: Run, version: int) -> list[ValidationResult]:
    chapters = run.repo.list_chapters(run.novel_id, version)
    text = "\n\n".join(f"{c.title}\n\n{c.text}" for c in chapters)
    return run_point(
        ValidationPoint.PRE_PUBLISH,
        _ctx(run, version, None, None, text, feedback_role="editor"),
    )


def _feedback(results: Sequence[ValidationResult]) -> str:
    lines = []
    for r in results:
        if r.passed:
            continue
        evidence = "; ".join(r.evidence[:8])
        lines.append(
            f"- {r.name}: {r.explanation} {('Evidencia: ' + evidence) if evidence else ''}"
        )
    return "\n".join(lines)


def _stop_reason(results: Sequence[ValidationResult], default: str) -> str:
    failed = [r.name for r in results if not r.passed]
    if any("forbidden" in name for name in failed):
        return "forbidden_word_limit"
    if any("schema" in name for name in failed):
        return "schema_limit"
    return default


# --------------------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------------------


def plan_novel(run: Run, chapters: int) -> NovelPlan:
    """TLA+ `Plan`. One planner call, a programmatic check, at most one replan."""
    facts = run.facts()
    documents = [
        cx.brief_document(run.brief),
        cx.facts_document(facts),
        cx.forbidden_document(run.forbidden()),
        cx.names_document(run.names()),
    ]
    mandatory = [f.key for f in facts if f.mandatory]
    known = [f.key for f in facts]
    known_births = {c.name: c.birth_date for c in run.repo.list_characters(run.novel_id)}
    feedback: list[str] = []
    for attempt in range(MAX_REPLANS + 1):
        plan = run.roles.plan(documents, chapters=chapters, feedback=feedback)
        plan = _repair_plan(plan, chapters, known)
        births = plan_births(plan, known_births)
        plan = normalise_events(plan, births)
        feedback = check_plan(
            plan,
            chapters=chapters,
            mandatory_keys=mandatory,
            known_keys=known,
            exact_names=run.names(),
        ) + chronology_problems(plan, births)
        run.progress(
            f"plan attempt {attempt + 1}: '{plan.title}', {len(plan.chapters)} chapters, "
            f"{len(plan.scenes)} scenes, {len(plan.events)} events, {len(feedback)} problems"
        )
        for problem in feedback[:10]:
            run.progress(f"  plan problem: {problem[:200]}")
        if not feedback:
            return plan
    raise StopRunError("plan_limit", "; ".join(feedback)[:1000])


def _repair_plan(plan: NovelPlan, chapters: int, known: Sequence[str]) -> NovelPlan:
    """Deterministic fixes that need no model: drop unknown fact keys, rescale scene budgets
    into range. Structural problems (missing chapters or scenes) are left to the replan."""
    known_set = set(known)
    scenes = []
    for number in range(1, chapters + 1):
        own = plan.scenes_of(number)
        total = sum(max(s.word_budget, 1) for s in own) or 1
        for s in own:
            budget = s.word_budget
            if not 1100 <= total <= 1350:
                budget = round(max(s.word_budget, 1) * 1200 / total)
            scenes.append(
                s.model_copy(
                    update={
                        "word_budget": budget,
                        "facts_used": [k for k in s.facts_used if k in known_set],
                    }
                )
            )
    scenes += [s for s in plan.scenes if not 1 <= s.chapter <= chapters]
    return plan.model_copy(update={"scenes": scenes})


def persist_plan(run: Run, plan: NovelPlan, version: int) -> None:
    """Idempotent: the plan fact, then cast, places, events and fact usage for `version`.
    Characters and places already ingested from the brief are matched by name."""
    repo, novel_id = run.repo, run.novel_id
    store_plan(repo, novel_id, plan)
    novel = repo.get_novel(novel_id)
    if not novel.title:
        repo.update_novel(novel_id, title=plan.title)
    characters = {c.name: c for c in repo.list_characters(novel_id)}
    for pc in plan.characters:
        existing = characters.get(pc.name)
        if existing is None:
            characters[pc.name] = repo.add_character(
                novel_id,
                name=pc.name,
                role=pc.role,
                birth_date=pc.birth_date if cx.parse_iso(pc.birth_date) else None,
                description=pc.description,
            )
    places = {p.name: p for p in repo.list_places(novel_id)}
    for pp in plan.places:
        if pp.name not in places:
            places[pp.name] = repo.add_place(novel_id, name=pp.name, description=pp.description)
    existing_events = {e.id for e in repo.list_events(novel_id)}
    for event in sorted(plan.events, key=lambda e: e.seq):
        if f"e{event.seq}" in existing_events:
            continue
        ages = {a.name: a.age for a in event.declared_ages}
        participants: dict[str, int | None] = {}
        for name in event.participants:
            character = characters.get(name)
            if character is not None:
                participants[character.id] = ages.get(name)
        place = places.get(event.place)
        repo.add_event(
            novel_id,
            seq=event.seq,
            description=event.description,
            story_date=event.story_date if cx.parse_iso(event.story_date) else None,
            place_id=place.id if place is not None else None,
            participants=participants,
            chapter=event.chapter,
            scene=event.scene,
            kind=event.kind,
        )
        existing_events.add(f"e{event.seq}")
    record_plan_usage(run, plan, version)


def record_plan_usage(run: Run, plan: NovelPlan, version: int) -> None:
    facts = {f.key: f for f in run.facts()}
    for scene in plan.scenes:
        for key in scene.facts_used:
            fact = facts.get(key)
            if fact is not None:
                run.repo.record_fact_usage(
                    fact.id, chapter=scene.chapter, scene=scene.scene, version=version
                )


# --------------------------------------------------------------------------------------
# Scenes and chapters
# --------------------------------------------------------------------------------------


def _previous_chapter(run: Run, version: int, chapter: int) -> ChapterVersion | None:
    return run.repo.get_chapter(run.novel_id, version, chapter - 1) if chapter > 1 else None


def write_scene(run: Run, version: int, chapter: int, scene: int, written: dict[int, str]) -> str:
    """TLA+ `WriteScene`. Writer call, then `scene_accept`; at most MAX_SCENE_RETRIES
    rewrites (volatile counter: an interrupted chapter restarts from its first scene)."""
    plan = run.require_plan()
    scenes = plan.scenes_of(chapter)
    current = next(s for s in scenes if s.scene == scene)
    previous = _previous_chapter(run, version, chapter)
    tail = cx.previous_scene_tail(scenes, written, current, previous.text if previous else "")
    facts = run.facts()
    base_docs = [
        cx.brief_summary_document(run.brief),
        cx.synopsis_document(plan),
        cx.summaries_document(
            cx.summaries_via_tools(run.repo, run.novel_id, version, chapter, observer=run.observer)
        ),
        cx.character_sheet_document(run.repo, run.novel_id, observer=run.observer),
        cx.chapter_plan_document(plan, chapter, facts),
        cx.text_document("manuscript/previous-tail.txt", tail or "(inicio de la novela)"),
        cx.forbidden_document(run.forbidden()),
        cx.names_document(run.names()),
    ]
    feedback = ""
    last: list[ValidationResult] = []
    for _attempt in range(MAX_SCENE_RETRIES + 1):
        documents = list(base_docs)
        if feedback:
            documents.append(cx.text_document("manuscript/feedback.txt", feedback))
        draft = run.roles.write_scene(
            documents,
            version=version,
            chapter=chapter,
            scene=scene,
            words=current.word_budget,
            feedback=feedback,
        )
        text = _clean(draft.text)
        last = before_scene_accept(run, version, chapter, scene, text)
        if all_passed(last):
            return text
        feedback = _feedback(last)
        run.progress(f"  chapter {chapter} scene {scene}: scene_accept failed, rewriting")
    raise StopRunError(
        _stop_reason(last, "scene_retry_limit"),
        f"chapter {chapter} scene {scene}: {_feedback(last)}"[:1000],
    )


_HEADING = re.compile(r"^\s*(#+\s.*|cap[ií]tulo\s+\d+.*|escena\s+\d+.*)$", re.IGNORECASE)


def _clean(text: str) -> str:
    """Drop heading lines a model may add despite the prompt."""
    lines = [line for line in text.strip().splitlines() if not _HEADING.match(line)]
    return "\n".join(lines).strip()


def _editor_docs(run: Run, version: int, chapter: int) -> list[Document]:
    plan = run.require_plan()
    return [
        cx.brief_summary_document(run.brief),
        cx.chapter_plan_document(plan, chapter, run.facts()),
        cx.character_sheet_document(run.repo, run.novel_id, observer=run.observer),
        cx.text_document(
            "manuscript/previous-chapter-summary.txt",
            cx.previous_summary_via_tool(
                run.repo, run.novel_id, version, chapter, observer=run.observer
            ),
        ),
        cx.forbidden_document(run.forbidden()),
        cx.names_document(run.names()),
    ]


def _edit(
    run: Run, version: int, chapter: int, text_docs: Sequence[Document], task: str
) -> ChapterEdit:
    lengths = run.lengths
    edit = run.roles.edit_chapter(
        [*_editor_docs(run, version, chapter), *text_docs],
        version=version,
        chapter=chapter,
        words_min=lengths.words_min,
        words_max=lengths.words_max,
        task=task,
    )
    edit = edit.model_copy(update={"text": _clean(edit.text)})
    words = word_count(edit.text)
    if not lengths.words_min <= words <= lengths.words_max:
        # One bounded length adjustment before chapter_close (spec 007 plan, risks).
        verb = "Amplía" if words < lengths.words_min else "Recorta"
        run.progress(f"  chapter {chapter}: editor gave {words} words, adjusting length")
        edit = run.roles.edit_chapter(
            [
                *_editor_docs(run, version, chapter),
                cx.text_document("manuscript/chapter-draft.txt", edit.text),
            ],
            version=version,
            chapter=chapter,
            words_min=lengths.words_min,
            words_max=lengths.words_max,
            task=(
                f"{verb} el capítulo de manuscript/chapter-draft.txt: ahora tiene {words} "
                "palabras y debe quedar dentro del rango. "
                + (
                    "Amplía con escena, diálogo y detalle sensorial, sin relleno ni repetir."
                    if words < lengths.words_min
                    else "Recorta sin perder hechos ni nombres."
                )
                + " Conserva el título y el contenido."
            ),
        )
        edit = edit.model_copy(update={"text": _clean(edit.text)})
    return edit


def _rewrite_task(feedback: str) -> str:
    return (
        "Reescribe el capítulo de manuscript/chapter-draft.txt corrigiendo exactamente lo que "
        "señala manuscript/feedback.txt (validadores). Mantén lo que funciona. Si el problema "
        "es la longitud, amplía o recorta. Si aparece un término prohibido, elimínalo."
        if feedback
        else "Pule el capítulo de manuscript/chapter-draft.txt."
    )


def write_chapter(run: Run, version: NovelVersion, chapter: int) -> None:
    """TLA+ `NextChapter` body: scenes → `Editor` → `CloseChapter` → `Checkpoint`.

    Three modes: a fresh chapter (3 scenes); a chapter reopened by the repair round (the
    stored text is repaired with the failed `pre_publish` feedback); a chapter affected by a
    `change_fact` (the parent version's text is rewritten with the new value)."""
    v = version.version
    existing = run.repo.get_chapter(run.novel_id, v, chapter)
    change = _change_note(version)
    scene_texts: list[str]
    if existing is not None:
        feedback = _last_prepublish_feedback(run, v)
        scene_texts = [existing.text]
        edit = _edit(
            run,
            v,
            chapter,
            [
                cx.text_document("manuscript/chapter-draft.txt", existing.text),
                cx.text_document("manuscript/feedback.txt", feedback or "(sin detalle)"),
            ],
            "Repara el capítulo de manuscript/chapter-draft.txt según manuscript/feedback.txt "
            "(validadores de publicación): si falta un hecho del brief asignado a este "
            "capítulo, intégralo con naturalidad; si hay una incoherencia temporal, corrígela. "
            "Mantén todo lo demás.",
        )
    elif (
        change is not None
        and version.parent_version is not None
        and (parent := run.repo.get_chapter(run.novel_id, version.parent_version, chapter))
        is not None
    ):
        scene_texts = [parent.text]
        edit = _edit(
            run,
            v,
            chapter,
            [
                cx.text_document("manuscript/chapter-draft.txt", parent.text),
                cx.text_document(
                    "manuscript/change.txt",
                    f"Dato cambiado ({change['key']}): antes «{change['old']}», "
                    f"ahora «{change['new']}».",
                ),
            ],
            "Un dato de la novela ha cambiado (manuscript/change.txt). Reescribe el capítulo "
            "de manuscript/chapter-draft.txt aplicando el nuevo valor en todas partes y "
            "ajustando solo lo necesario para que siga siendo coherente y natural. Conserva "
            "todo lo demás: trama, estructura, estilo y longitud.",
        )
    else:
        written: dict[int, str] = {}
        plan = run.require_plan()
        for scene in plan.scenes_of(chapter):
            written[scene.scene] = write_scene(run, v, chapter, scene.scene, written)
            run.progress(
                f"  chapter {chapter} scene {scene.scene}: {word_count(written[scene.scene])} words"
            )
        scene_texts = [written[k] for k in sorted(written)]
        joined = "\n\n".join(scene_texts)
        edit = _edit(
            run,
            v,
            chapter,
            [cx.text_document("manuscript/chapter-draft.txt", joined)],
            "Une las tres escenas de manuscript/chapter-draft.txt en un capítulo continuo y "
            "pulido (transiciones, repeticiones, clichés), y haz tu autocrítica. No resumas ni "
            f"condenses: las escenas suman {word_count(joined)} palabras y el capítulo final "
            "debe conservar prácticamente todo su contenido.",
        )
    close_chapter(run, v, chapter, edit, scene_texts)


def _chapter_close_runs(run: Run, version: int, chapter: int) -> int:
    """CE2: `chapter_close` runs of this chapter since it was last reopened, from persisted
    `validator_result` rows. A repair round reopens the budget: runs recorded before the
    version's last `pre_publish` failure do not count."""
    total = run.repo.count_chapter_attempts(run.novel_id, version, chapter)
    marker = _last_prepublish_failure_id(run, version)
    if marker is None:
        return total
    before = {
        r.run_id or str(r.id)
        for r in run.repo.list_validator_results(
            run.novel_id, version=version, chapter=chapter, point="chapter_close"
        )
        if r.id < marker
    }
    return total - len(before)


def _last_prepublish_failure_id(run: Run, version: int) -> int | None:
    failed = [
        r.id
        for r in run.repo.list_validator_results(run.novel_id, version=version, point="pre_publish")
        if not r.passed
    ]
    return max(failed) if failed else None


def _last_prepublish_feedback(run: Run, version: int) -> str:
    rows = run.repo.list_validator_results(run.novel_id, version=version, point="pre_publish")
    if not rows:
        return ""
    last_run = rows[-1].run_id
    return "\n".join(
        f"- {r.name}: {r.explanation} Evidencia: {'; '.join(r.evidence[:8])}"
        for r in rows
        if r.run_id == last_run and not r.passed
    )


def close_chapter(
    run: Run, version: int, chapter: int, edit: ChapterEdit, scene_texts: Sequence[str]
) -> None:
    """TLA+ `CloseChapter`. `chapter_close` pass → `checkpoint`; fail → keep the rejected
    text, editor rewrite with the evidence, bounded by MAX_CHAPTER_RETRIES read from the
    database (CE2). A forbidden-word failure takes the same rewrite path (G03)."""
    while True:
        if _chapter_close_runs(run, version, chapter) > MAX_CHAPTER_RETRIES:
            raise StopRunError("chapter_retry_limit", f"chapter {chapter}: budget used")
        results = before_chapter_close(run, version, chapter, edit, scene_texts)
        if all_passed(results):
            checkpoint(run, version, chapter, edit)
            return
        feedback = _feedback(results)
        run.repo.record_chapter_attempt(
            run.novel_id, version, chapter, text=edit.text, reason=feedback[:2000]
        )
        used = _chapter_close_runs(run, version, chapter)
        if used > MAX_CHAPTER_RETRIES:
            raise StopRunError(
                _stop_reason(results, "chapter_retry_limit"),
                f"chapter {chapter}: {feedback}"[:1000],
            )
        run.progress(f"  chapter {chapter}: chapter_close failed ({used}), editor rewrite")
        edit = _edit(
            run,
            version,
            chapter,
            [
                cx.text_document("manuscript/chapter-draft.txt", edit.text),
                cx.text_document("manuscript/feedback.txt", feedback),
            ],
            _rewrite_task(feedback),
        )


def checkpoint(run: Run, version: int, chapter: int, edit: ChapterEdit) -> None:
    """TLA+ `Checkpoint`: text + checkpoint in one transaction (CE1), upsert (CE3)."""
    run.repo.save_chapter_and_checkpoint(
        run.novel_id,
        version,
        chapter,
        text=edit.text,
        title=edit.title,
        summary=edit.summary,
        detail=json.dumps({"issues": edit.issues}, ensure_ascii=False)[:2000],
    )
    run.progress(f"chapter {chapter} done: {word_count(edit.text)} words — {edit.title}")


# --------------------------------------------------------------------------------------
# Publish
# --------------------------------------------------------------------------------------


_CHAPTER_REF = re.compile(r"(?:cap[ií]tulo|chapter|ch\.?|cap\.?)\s*[:#]?\s*(\d+)", re.IGNORECASE)
_EVENT_REF = re.compile(r"\be(\d+)\b")


def chapters_named(results: Sequence[ValidationResult], plan: NovelPlan, total: int) -> list[int]:
    """Which chapters a failed `pre_publish` points at: explicit chapter numbers, event ids
    (Lean), or fact keys (coverage → the chapters planned to use them). None found → all."""
    found: set[int] = set()
    event_chapter = {e.seq: e.chapter for e in plan.events}
    for result in results:
        if result.passed:
            continue
        for blob in [result.explanation, *result.evidence]:
            found |= {int(n) for n in _CHAPTER_REF.findall(blob)}
            found |= {
                event_chapter[int(n)] for n in _EVENT_REF.findall(blob) if int(n) in event_chapter
            }
            for scene in plan.scenes:
                if any(key in blob for key in scene.facts_used):
                    found.add(scene.chapter)
    chosen = sorted(c for c in found if 1 <= c <= total)
    return chosen or list(range(1, total + 1))


def publish_version(run: Run, version: int, total: int) -> RunResult | None:
    """TLA+ `PrePublish` / `Publish`. Returns the final result, or None when a repair round
    reopened chapters and the chapter loop must run again."""
    results = before_publish(run, version)
    if all_passed(results):
        run.repo.set_version_status(run.novel_id, version, "published")
        run.repo.update_novel(run.novel_id, status="published")
        run.progress(f"version {version} published")
        return RunResult(run.novel_id, version, "published")
    current = run.repo.get_version(run.novel_id, version)
    feedback = _feedback(results)
    if current.repair_rounds >= MAX_REPAIR_ROUNDS:
        # Version stays blocked; earlier published versions are untouched.
        _stop(run, current, "repair_limit", feedback, status="blocked")
        return RunResult(run.novel_id, version, "stopped_error", f"repair_limit: {feedback}"[:2000])
    reopened = chapters_named(results, run.require_plan(), total)
    with transaction(run.repo.connection):  # CE4: blocked + round + reopened, atomically
        run.repo.block_version(
            run.novel_id,
            version,
            repair_rounds=current.repair_rounds + 1,
            note=current.note,
        )
        for chapter in reopened:
            run.repo.set_checkpoint(
                run.novel_id, version, chapter, "pending", detail="reopened by repair round"
            )
    run.progress(f"pre_publish failed; repair round on chapters {reopened}")
    return None


def _stop(
    run: Run,
    version: NovelVersion,
    reason: str,
    detail: str,
    *,
    status: str | None = None,
) -> None:
    note = _note_dict(version)
    note["stop_reason"] = f"{reason}: {detail}"[:2000]
    run.repo.set_version_status(
        run.novel_id,
        version.version,
        "blocked" if status == "blocked" else version.status,
        note=json.dumps(note, ensure_ascii=False),
    )
    run.repo.update_novel(run.novel_id, status="stopped_error")
    run.progress(f"STOPPED: {reason} {detail[:300]}")


def _note_dict(version: NovelVersion) -> dict[str, object]:
    """The version note is a JSON object (`change`, `stop_reason`); free text is kept."""
    try:
        data = json.loads(version.note) if version.note else {}
    except json.JSONDecodeError:
        return {"text": version.note}
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else {}


def _change_note(version: NovelVersion) -> dict[str, str] | None:
    try:
        data = json.loads(version.note) if version.note else {}
    except json.JSONDecodeError:
        return None
    change = data.get("change") if isinstance(data, dict) else None
    if isinstance(change, dict) and {"key", "old", "new"} <= change.keys():
        return {k: str(change[k]) for k in ("key", "old", "new")}
    return None


# --------------------------------------------------------------------------------------
# The loop, generate, change_fact
# --------------------------------------------------------------------------------------


def _chapter_loop(run: Run, version: int) -> RunResult:
    """TLA+ `NextChapter` / `Resume`: the lowest chapter without a complete checkpoint;
    none left → pre-publish (at most MAX_REPAIR_ROUNDS + 1 times)."""
    total = len(run.require_plan().chapters)
    for _round in range(MAX_REPAIR_ROUNDS + 2):
        while (
            chapter := run.repo.first_incomplete_chapter(
                run.novel_id, version, total_chapters=total
            )
        ) is not None:
            with run.observer.span(f"chapter:{chapter}", metadata={"version": version}):
                write_chapter(run, run.repo.get_version(run.novel_id, version), chapter)
        with run.observer.span("phase:publish", metadata={"version": version}):
            result = publish_version(run, version, total)
        if result is not None:
            return result
    raise StopRunError("repair_limit", "loop bound")  # pragma: no cover - CE4 bound


def _make_run(
    repo: BibleRepository,
    novel_id: str,
    client: ModelClient | None,
    observer: Observer | None,
    progress: Progress | None,
) -> Run:
    brief = repo.get_brief(novel_id)
    if brief is None:
        message = f"novel {novel_id!r} has no brief"
        raise ValueError(message)
    obs = observer or get_observer()
    return Run(
        repo=repo,
        novel_id=novel_id,
        roles=Roles(client or ClaudeCodeModelClient(), obs, repo, novel_id),
        observer=obs,
        brief=dict(brief.data),
        progress=progress or (lambda _line: None),
    )


def _finish(run: Run, version: int | None) -> None:
    summary = run.repo.cost_summary(run.novel_id)
    run.observer.score("novel_cost_usd", summary.cost_usd, trace_id=run.trace_id)
    run.observer.score(
        "novel_tokens",
        float(summary.input_tokens + summary.output_tokens + summary.cache_read),
        trace_id=run.trace_id,
    )
    run.progress(
        f"cost so far: ${summary.cost_usd:.4f}, {summary.calls} calls, "
        f"{summary.latency_s:.0f}s model time (version {version})"
    )
    run.observer.flush()


def _run_guarded(run: Run, version: NovelVersion, body: Callable[[], RunResult]) -> RunResult:
    try:
        return body()
    except StopRunError as stop:
        latest = run.repo.get_version(run.novel_id, version.version)
        _stop(run, latest, stop.reason, stop.detail)
        return RunResult(run.novel_id, version.version, "stopped_error", str(stop))


def generate(
    repo: BibleRepository,
    novel_id: str,
    *,
    client: ModelClient | None = None,
    observer: Observer | None = None,
    chapters: int | None = None,
    progress: Progress | None = None,
    register: bool = True,
) -> RunResult:
    """K4. Plan (once), write every incomplete chapter of the latest non-published version,
    pre-publish, publish. Resumes automatically from `first_incomplete_chapter`.
    `register=False` leaves the validator registry as the caller set it (tests)."""
    if register:
        setup_validators(repo, novel_id)
    run = _make_run(repo, novel_id, client, observer, progress)
    session = run.observer.start_session(novel_id)
    version: NovelVersion | None = None
    with run.observer.trace(
        "generate", session_id=session, metadata={"novel_id": novel_id}
    ) as trace:
        run.trace_id = trace.id
        try:
            run.plan = load_plan(repo, novel_id)
            if run.plan is None:
                total = chapters or cx.brief_chapters(run.brief, DEFAULT_CHAPTERS)
                with run.observer.span("phase:plan", metadata={"chapters": total}):
                    try:
                        run.plan = plan_novel(run, total)
                    except StopRunError as stop:
                        repo.update_novel(novel_id, status="stopped_error")
                        return RunResult(novel_id, 0, "stopped_error", str(stop))
            version = _open_version(run)
            if version.status == "published":
                return RunResult(novel_id, version.version, "published", "already published")
            persist_plan(run, run.plan, version.version)
            repo.update_novel(novel_id, status="generating")
            v = version
            return _run_guarded(run, v, lambda: _chapter_loop(run, v.version))
        finally:
            _finish(run, version.version if version else None)


def setup_validators(repo: BibleRepository, novel_id: str) -> None:
    """Register every block's validators (guarded) and this novel's own Lean project."""
    register_all()
    row = repo.connection.execute("pragma database_list").fetchone()
    db_file = str(row[2]) if row is not None and row[2] else ""
    base = Path(db_file).parent if db_file else Path(tempfile.gettempdir()) / "harness"
    register_lean_for(novel_id, base)


def _open_version(run: Run) -> NovelVersion:
    latest = run.repo.latest_version(run.novel_id)
    if latest is None:
        return run.repo.create_version(run.novel_id, note="", trace_id=run.trace_id)
    return latest


_NAME_KINDS: Final[frozenset[str]] = frozenset({"recipient", "person", "pet", "place"})


def _replace_values(data: JsonValue, pattern: re.Pattern[str], new: str) -> JsonValue:
    """Every string value of the brief with the old name replaced as a whole word."""
    if isinstance(data, str):
        return pattern.sub(new, data)
    if isinstance(data, list):
        return [_replace_values(item, pattern, new) for item in data]
    if isinstance(data, dict):
        return {k: _replace_values(v, pattern, new) for k, v in data.items()}
    return data


def _name_pattern(old: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(old)}(?!\w)")


def change_fact(
    repo: BibleRepository,
    novel_id: str,
    fact_key: str,
    new_value: str,
    *,
    client: ModelClient | None = None,
    observer: Observer | None = None,
    progress: Progress | None = None,
    register: bool = True,
) -> ChangeResult:
    """K4 / R05 / TLA+ `ChangeFact`. Update the fact, create version v+1 from the latest
    published one copying every chapter that does not use the fact, rewrite only those
    chapters (editor over the existing text), then chapter_close, pre_publish, publish.
    The previous version is never touched."""
    if register:
        setup_validators(repo, novel_id)
    run = _make_run(repo, novel_id, client, observer, progress)
    fact = repo.find_fact(novel_id, fact_key)
    if fact is None:
        message = f"novel {novel_id!r} has no fact {fact_key!r}"
        raise ValueError(message)
    published = repo.latest_version(novel_id, status="published")
    if published is None:
        message = f"novel {novel_id!r} has no published version to change"
        raise ValueError(message)
    plan = load_plan(repo, novel_id)
    if plan is None:
        message = f"novel {novel_id!r} has no plan"
        raise ValueError(message)
    old = fact.value
    affected = set(repo.chapters_using_fact(fact.id, version=published.version))
    affected |= {s.chapter for s in plan.scenes if fact_key in s.facts_used}
    is_name = fact_key.endswith(".name") or fact.kind in _NAME_KINDS
    pattern = _name_pattern(old)
    derived: list[Fact] = []
    if is_name and old:
        # A name also lives inside other facts ("El rescate de Toby") and in the prose of
        # chapters that never "used" the name fact: all of them change with it.
        derived = [
            f for f in run.facts() if f.id != fact.id and pattern.search(f.value) is not None
        ]
        for other in derived:
            affected |= set(repo.chapters_using_fact(other.id, version=published.version))
        affected |= {
            c.chapter
            for c in repo.list_chapters(novel_id, published.version)
            if pattern.search(c.text) is not None
        }
    affected = {c for c in affected if 1 <= c <= len(plan.chapters)}
    session = run.observer.start_session(novel_id)
    new_version: NovelVersion | None = None
    with run.observer.trace(
        "change_fact",
        session_id=session,
        metadata={"novel_id": novel_id, "fact": fact_key, "parent": published.version},
    ) as trace:
        run.trace_id = trace.id
        try:
            repo.update_fact_value(fact.id, new_value)
            if is_name and old:
                rename_cast(repo, novel_id, old, new_value)
                for other in derived:
                    repo.update_fact_value(other.id, pattern.sub(new_value, other.value))
                plan = NovelPlan.model_validate_json(pattern.sub(new_value, plan.model_dump_json()))
                store_plan(repo, novel_id, plan)
                brief = repo.get_brief(novel_id)
                if brief is not None:
                    updated = _replace_values(dict(brief.data), pattern, new_value)
                    if isinstance(updated, dict):
                        repo.save_brief(novel_id, updated, valid=brief.valid)
                        run.brief = updated
                if fact_key == "recipient.name":
                    repo.update_novel(novel_id, recipient_name=new_value)
            run.plan = plan
            note = {"change": {"key": fact_key, "old": old, "new": new_value}}
            new_version = repo.create_version_from(
                novel_id,
                published.version,
                copy_chapters_except=affected,
                note=json.dumps(note, ensure_ascii=False),
                trace_id=trace.id,
            )
            record_plan_usage(run, plan, new_version.version)
            run.progress(
                f"change_fact {fact_key}: version {new_version.version} from "
                f"{published.version}, chapters {sorted(affected)}"
            )
            nv = new_version
            result = _run_guarded(run, nv, lambda: _chapter_loop(run, nv.version))
            status: RunStatus = result.status
            changed = repo.changed_chapters(novel_id, nv.version)
            return ChangeResult(nv.version, changed, status, result.detail)
        finally:
            _finish(run, new_version.version if new_version else None)


def resume(
    repo: BibleRepository,
    novel_id: str,
    *,
    client: ModelClient | None = None,
    observer: Observer | None = None,
    progress: Progress | None = None,
    register: bool = True,
) -> RunResult:
    """TLA+ `Resume`: the same as `generate` on an existing novel."""
    return generate(
        repo, novel_id, client=client, observer=observer, progress=progress, register=register
    )


__all__ = [
    "MAX_CHAPTER_RETRIES",
    "MAX_REPAIR_ROUNDS",
    "MAX_SCENE_RETRIES",
    "StopRunError",
    "before_chapter_close",
    "before_publish",
    "before_scene_accept",
    "change_fact",
    "chapters_named",
    "checkpoint",
    "close_chapter",
    "generate",
    "persist_plan",
    "plan_novel",
    "publish_version",
    "resume",
    "write_chapter",
    "write_scene",
]
