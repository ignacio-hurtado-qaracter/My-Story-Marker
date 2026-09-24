"""What each role reads (spec 007). Everything from the brief, the bible or an earlier model
output is handed over as a `Document` (data), never spliced into a system prompt; the
instructions are fixed text written here, carrying only numbers and the plan's structure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import JsonValue

from app.bible import Fact
from app.commons.llm import Document
from app.novel.models import NovelPlan, PlanScene
from app.novel.plan_check import parse_iso

TAIL_WORDS = 250
DEFAULT_WORDS_MIN = 1000
DEFAULT_WORDS_MAX = 1500


@dataclass(frozen=True, slots=True)
class Lengths:
    words_min: int = DEFAULT_WORDS_MIN
    words_max: int = DEFAULT_WORDS_MAX


def brief_lengths(brief: Mapping[str, JsonValue]) -> Lengths:
    raw = brief.get("length")
    if isinstance(raw, Mapping):
        low, high = raw.get("words_min"), raw.get("words_max")
        if isinstance(low, int) and isinstance(high, int) and 0 < low < high:
            return Lengths(low, high)
    return Lengths()


def brief_chapters(brief: Mapping[str, JsonValue], default: int) -> int:
    raw = brief.get("length")
    if isinstance(raw, Mapping):
        chapters = raw.get("chapters")
        if isinstance(chapters, int) and chapters > 0:
            return chapters
    return default


def recipient_name(brief: Mapping[str, JsonValue]) -> str:
    recipient = brief.get("recipient")
    if isinstance(recipient, Mapping):
        name = recipient.get("name")
        if isinstance(name, str):
            return name
    return ""


def exact_names(brief: Mapping[str, JsonValue]) -> list[str]:
    """Names that must be spelled exactly: recipient, people, pets."""
    names = [recipient_name(brief)]
    for group in ("people", "pets"):
        items = brief.get(group)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                    names.append(str(item["name"]))
    return [n for n in names if n]


def brief_document(brief: Mapping[str, JsonValue]) -> Document:
    return Document(
        path="bible/brief.json", text=json.dumps(dict(brief), ensure_ascii=False, indent=1)
    )


def brief_summary_document(brief: Mapping[str, JsonValue]) -> Document:
    """The brief without the free text and memories' long descriptions: the writer's view."""
    keep = {
        k: v
        for k, v in brief.items()
        if k in {"recipient", "occasion", "people", "pets", "places", "genre", "tone", "dedication"}
    }
    return Document(
        path="bible/brief-summary.json", text=json.dumps(keep, ensure_ascii=False, indent=1)
    )


def facts_document(facts: Sequence[Fact]) -> Document:
    lines = [
        f"{f.key} | kind={f.kind} | mandatory={str(f.mandatory).lower()} | {f.value}" for f in facts
    ]
    return Document(path="bible/facts.txt", text="\n".join(lines) or "(none)")


def forbidden_document(terms: Sequence[str]) -> Document:
    return Document(
        path="bible/forbidden-terms.txt", text="\n".join(terms) or "(no forbidden terms)"
    )


def names_document(names: Sequence[str]) -> Document:
    return Document(
        path="bible/exact-names.txt",
        text="Nombres que deben escribirse exactamente así:\n" + "\n".join(names),
    )


def synopsis_document(plan: NovelPlan) -> Document:
    return Document(
        path="plan/synopsis.txt",
        text=f"Título: {plan.title}\n\n{plan.synopsis}\n\nFinal: {plan.ending_note}",
    )


def chapter_plan_document(plan: NovelPlan, chapter: int, facts: Sequence[Fact]) -> Document:
    by_key = {f.key: f.value for f in facts}
    chap = plan.chapter(chapter)
    lines = [
        f"Capítulo {chap.number} de {len(plan.chapters)}: {chap.title} (arco: {chap.arc_role})",
        f"Sinopsis: {chap.synopsis}",
        "",
    ]
    for scene in plan.scenes_of(chapter):
        used = "; ".join(f"{k} = {by_key.get(k, '?')}" for k in scene.facts_used)
        lines += [
            (
                f"Escena {scene.scene} — fecha {scene.story_date} — lugar {scene.place} — "
                f"~{scene.word_budget} palabras"
            ),
            f"  Personajes: {', '.join(scene.characters)}",
            f"  Resumen: {scene.summary}",
            f"  Hechos a integrar: {used or 'ninguno'}",
        ]
        for event in plan.events:
            if event.chapter == chapter and event.scene == scene.scene:
                ages = ", ".join(f"{a.name} tiene {a.age} años" for a in event.declared_ages)
                lines.append(
                    f"  Evento ({event.story_date}, {event.place}): {event.description}"
                    + (f" [{ages}]" if ages else "")
                )
    return Document(path=f"plan/chapter-{chapter}.txt", text="\n".join(lines))


def summaries_document(summaries: Sequence[tuple[int, str]]) -> Document:
    text = "\n\n".join(f"Capítulo {n}: {s}" for n, s in summaries) or "(es el primer capítulo)"
    return Document(path="manuscript/previous-summaries.txt", text=text)


def tail(text: str, words: int = TAIL_WORDS) -> str:
    parts = text.split()
    return " ".join(parts[-words:])


def previous_scene_tail(
    scenes: Sequence[PlanScene], written: Mapping[int, str], current: PlanScene, fallback: str
) -> str:
    """The last ~250 words of the scene that precedes `current` in **story** order within the
    chapter (spec 004 § 1 row on `literal_tail`); a flashback that has no earlier-dated
    scene written falls back to the scene just before it on the page, and scene 1 to the
    previous chapter's ending."""
    here = parse_iso(current.story_date)
    candidates = [
        s
        for s in scenes
        if s.scene in written
        and s.scene != current.scene
        and here is not None
        and (d := parse_iso(s.story_date)) is not None
        and d <= here
    ]
    if candidates:
        best = max(candidates, key=lambda s: (s.story_date, s.scene))
        return tail(written[best.scene])
    before = [s.scene for s in scenes if s.scene in written and s.scene < current.scene]
    if before:
        return tail(written[max(before)])
    return tail(fallback)


def text_document(path: str, text: str) -> Document:
    return Document(path=path, text=text or "(vacío)")


__all__ = [
    "Lengths",
    "brief_chapters",
    "brief_document",
    "brief_lengths",
    "brief_summary_document",
    "chapter_plan_document",
    "exact_names",
    "facts_document",
    "forbidden_document",
    "names_document",
    "parse_iso",
    "previous_scene_tail",
    "recipient_name",
    "summaries_document",
    "synopsis_document",
    "tail",
    "text_document",
]
