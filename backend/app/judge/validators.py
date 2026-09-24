"""The two semantic validators of spec 011: `judge_chapter` and `judge_novel` (K3).

Both call the read-only `judge` role through `traced_complete` (K2), apply the D11 pass rule
of `rubric.evaluate`, send one Langfuse score per criterion (`judge:<criterion>`, 1-5, the
justification as comment) and return a `ValidationResult` whose evidence lines
`"<criterion>: <n>/5 — <justification>"` are what `compare.py` reads back. `run_point`
persists the result and scores `validator:<name>`.

Inputs are kept cheap: the chapter judge reads the chapter, its plan entry, the *summaries*
of the previous chapters and a brief summary; the novel judge reads the summaries, the
opening of chapter 1 and the ending of the last chapter.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from app.bible import ChapterVersion
from app.commons.llm.protocol import Document, ModelClient
from app.commons.observability import CallScope, load_prompt, traced_complete
from app.commons.permissions import AgentRole
from app.judge.models import ChapterJudgement, CriterionScore, Issue, NovelJudgement
from app.judge.rubric import evaluate, render_markdown
from app.validators import ValidationContext, ValidationPoint, ValidationResult

JUDGE_SCORE_PREFIX: Final[str] = "judge:"
OPENING_WORDS: Final[int] = 300
ENDING_WORDS: Final[int] = 400
SUMMARY_FALLBACK_WORDS: Final[int] = 60
EVIDENCE_LINE: Final = re.compile(r"^(?P<key>[a-z_]+): (?P<score>[1-5])/5\b")
"""Parses the per-criterion evidence lines back (`compare.py`)."""

_default_client: ModelClient | None = None

SPECULATIVE: Final = re.compile(
    r"\b(posibles?|posiblemente|parecen?|podr[ií]a[n]?|quiz[aá]s?|tal vez|sugiere|sugiriendo|"
    r"revisar si|no queda claro si)\b",
    re.IGNORECASE,
)


def is_blocking(issue: Issue) -> bool:
    """Tuning 1: only a concrete issue blocks — severity `alta`, at least one chapter named,
    and no speculative wording. Everything else is feedback for the editor."""
    return (
        issue.severidad == "alta"
        and bool(issue.capitulos)
        and SPECULATIVE.search(issue.descripcion) is None
    )


def describe(issue: Issue) -> str:
    chapters = ", ".join(str(n) for n in issue.capitulos) or "sin capítulo"
    return f"[{issue.severidad}; cap. {chapters}] {issue.descripcion}"


def _client(ctx: ValidationContext) -> ModelClient:
    given = ctx.extra.get("client")
    if given is not None and hasattr(given, "complete"):
        return cast("ModelClient", given)
    global _default_client  # one live client per process, built lazily
    if _default_client is None:
        from app.commons.llm import ClaudeCodeModelClient

        _default_client = ClaudeCodeModelClient()
    return _default_client


def first_words(text: str, count: int) -> str:
    return " ".join(text.split()[:count])


def last_words(text: str, count: int) -> str:
    return " ".join(text.split()[-count:])


def brief_summary(ctx: ValidationContext) -> str:
    """The brief fields the judge needs, as compact JSON."""
    raw = ctx.extra.get("brief")
    if not isinstance(raw, Mapping):
        stored = ctx.repo.get_brief(ctx.novel_id)
        raw = stored.data if stored is not None else {}
    data = cast("Mapping[str, object]", raw)
    keep = (
        "recipient",
        "occasion",
        "genre",
        "tone",
        "people",
        "pets",
        "places",
        "memories",
        "mandatory_elements",
    )  # never `free_text`: raw untrusted text; its extracted facts are in the bible (R2)
    return json.dumps({k: data[k] for k in keep if k in data}, ensure_ascii=False)


def plan_entry(plan: object, chapter: int) -> object | None:
    """The plan entry of `chapter`, whatever reasonable shape the planner (B3) used."""
    if not isinstance(plan, Mapping):
        return None
    chapters = plan.get("chapters")
    if not isinstance(chapters, Sequence) or isinstance(chapters, str):
        return None
    for index, entry in enumerate(chapters, start=1):
        if isinstance(entry, Mapping):
            number = entry.get("number", entry.get("chapter", entry.get("index", index)))
            if number == chapter:
                return cast("object", entry)
        elif index == chapter:
            return cast("object", entry)
    return None


def _summary_lines(rows: Sequence[ChapterVersion]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        summary = row.summary.strip() or (
            f"{first_words(row.text, SUMMARY_FALLBACK_WORDS)} […] "
            f"{last_words(row.text, SUMMARY_FALLBACK_WORDS)}"
        )
        title = f" — {row.title}" if row.title else ""
        lines.append(f"Capítulo {row.chapter}{title}: {summary}")
    return lines


def _score_criteria(ctx: ValidationContext, scores: Mapping[str, CriterionScore]) -> None:
    trace_id = ctx.trace_id or ctx.observer.current_trace_id()
    for key, value in scores.items():
        ctx.observer.score(
            f"{JUDGE_SCORE_PREFIX}{key}",
            float(value.score),
            comment=value.justification[:1000],
            trace_id=trace_id,
        )


def _result(
    name: str,
    judgement: ChapterJudgement,
    extra_evidence: Sequence[str] = (),
    extra_issues: Sequence[tuple[str, Issue]] = (),
) -> ValidationResult:
    scores = judgement.scores()
    issues = [("", issue) for issue in judgement.blocking_issues] + list(extra_issues)
    blocking = [prefix + describe(issue) for prefix, issue in issues if is_blocking(issue)]
    advisory = [prefix + describe(issue) for prefix, issue in issues if not is_blocking(issue)]
    verdict = evaluate({key: value.score for key, value in scores.items()}, blocking)
    evidence = [f"{key}: {value.score}/5 — {value.justification}" for key, value in scores.items()]
    evidence += [f"bloqueante: {issue}" for issue in blocking]
    evidence += [f"observación (no bloquea): {issue}" for issue in advisory]
    evidence += list(extra_evidence)
    if verdict.passed:
        explanation = f"Aprobado (media {verdict.mean:.2f}). {judgement.comentario_general}"
    else:
        weak = [
            f"{key} ({scores[key].score}/5): {scores[key].justification}" for key in verdict.failing
        ]
        explanation = " ".join(
            [
                f"Suspende ({'; '.join(verdict.reasons)}).",
                *(f"Corregir {item}" for item in weak),
                f"Para el editor: {judgement.comentario_general}",
            ]
        )
    return ValidationResult(
        name=name,
        passed=verdict.passed,
        score=round(verdict.mean / 5, 4),
        evidence=evidence,
        explanation=explanation,
    )


def _skipped(ctx: ValidationContext, name: str) -> ValidationResult | None:
    if ctx.extra.get("judge_enabled") is False:
        return ValidationResult(
            name=name, passed=True, score=None, explanation="judge disabled (judge_enabled=False)"
        )
    return None


@dataclass(frozen=True, slots=True)
class JudgeChapter:
    name: str = "judge_chapter"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        skipped = _skipped(ctx, self.name)
        if skipped is not None:
            return skipped
        chapter = ctx.chapter or 0
        previous = _summary_lines(
            [
                row
                for row in ctx.repo.list_chapters(ctx.novel_id, ctx.version)
                if row.chapter < chapter
            ]
        )
        documents = [
            Document(path="brief/summary.json", text=brief_summary(ctx)),
            Document(
                path="chapters/previous-summaries.md",
                text="\n".join(previous) or "(Es el primer capítulo.)",
            ),
        ]
        entry = plan_entry(ctx.extra.get("plan"), chapter)
        if entry is not None:
            documents.append(
                Document(
                    path=f"plan/chapter-{chapter}.json",
                    text=json.dumps(entry, ensure_ascii=False, default=str),
                )
            )
        documents.append(Document(path=f"chapters/{chapter}.md", text=ctx.text))
        prompt = load_prompt("judge_chapter", ctx.observer)
        completion = traced_complete(
            _client(ctx),
            role=AgentRole.JUDGE,
            system=f"{prompt.text}\n\n{render_markdown(novel=False)}",
            documents=documents,
            instruction=f"Evalúa el capítulo {chapter} con la rúbrica y devuelve el JSON.",
            output_schema=ChapterJudgement,
            observer=ctx.observer,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            sink=ctx.repo,
            scope=CallScope(ctx.novel_id, ctx.version, chapter=ctx.chapter),
        )
        judgement = completion.output
        _score_criteria(ctx, judgement.scores())
        return _result(self.name, judgement)


@dataclass(frozen=True, slots=True)
class JudgeNovel:
    name: str = "judge_novel"
    point: ValidationPoint = ValidationPoint.PRE_PUBLISH

    def run(self, ctx: ValidationContext) -> ValidationResult:
        skipped = _skipped(ctx, self.name)
        if skipped is not None:
            return skipped
        rows = ctx.repo.list_chapters(ctx.novel_id, ctx.version)
        if not rows:
            return ValidationResult(
                name=self.name,
                passed=False,
                score=0.0,
                evidence=["no chapters in this version"],
                explanation="No hay capítulos que evaluar.",
            )
        documents = [
            Document(path="brief/summary.json", text=brief_summary(ctx)),
            Document(
                path="chapters/summaries.md",
                text="\n".join(_summary_lines(rows)),
            ),
            Document(
                path=f"chapters/{rows[0].chapter}-opening.md",
                text=first_words(rows[0].text, OPENING_WORDS),
            ),
            Document(
                path=f"chapters/{rows[-1].chapter}-ending.md",
                text=last_words(rows[-1].text, ENDING_WORDS),
            ),
        ]
        prompt = load_prompt("judge_novel", ctx.observer)
        completion = traced_complete(
            _client(ctx),
            role=AgentRole.JUDGE,
            system=f"{prompt.text}\n\n{render_markdown(novel=True)}",
            documents=documents,
            instruction=(
                f"Evalúa la novela completa ({len(rows)} capítulos) con la rúbrica y "
                "devuelve el JSON."
            ),
            output_schema=NovelJudgement,
            observer=ctx.observer,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            sink=ctx.repo,
            scope=CallScope(ctx.novel_id, ctx.version),
        )
        judgement = completion.output
        _score_criteria(ctx, judgement.scores())
        repair = sorted(set(judgement.capitulos_a_reparar))
        extra = ["capítulos a reparar: " + ", ".join(str(n) for n in repair)] if repair else []
        return _result(
            self.name,
            judgement,
            extra_evidence=extra,
            extra_issues=[("contradicción: ", item) for item in judgement.contradicciones],
        )


__all__ = [
    "EVIDENCE_LINE",
    "JUDGE_SCORE_PREFIX",
    "JudgeChapter",
    "JudgeNovel",
    "brief_summary",
    "describe",
    "first_words",
    "is_blocking",
    "last_words",
    "plan_entry",
]
