"""`fact_usage_recorder` and `brief_coverage` — invariant 13, V03, M01 (spec 008 / AC 3).

**fact_usage_recorder** (``chapter_close``) detects which facts of the bible the chapter
renders and records one ``fact_usage(fact, version, chapter, scene=0)`` row per fact
through the repository (K1). This is what keeps "chapters using each fact" truthful for
the reader and for ``change_fact``. It always passes; its evidence reports the facts found
and the mandatory coverage so far. Matching (``fact_values`` + ``text.fact_rendered``):

- name facts (key ``*.name`` or kind recipient/person/pet) match when any token of the
  name (≥ 3 letters, not a particle) appears as a word — "Lucía" renders "Lucía Pérez";
- memories match on their **title** (from the brief when available) by the key-term rule
  of ``text``: ≥ 50 % of the title's key terms in the chapter;
- every other value: ≤ 3 words as a phrase, longer by the key-term rule.

Non-mandatory ``trait`` and ``occasion`` facts are not tracked (they are adjectives, not
elements a chapter "uses").

**brief_coverage** (``pre_publish``, brief_coverage / required_element) checks that every
mandatory fact is rendered by the text of at least one chapter of the version (D11:
presence in the prose, not merely a row). It reads the ``fact_usage`` rows too: a rendered
fact with no row gets its row backfilled (reported), and a row whose chapter no longer
renders the fact (a rewritten chapter) is reported as stale. Evidence lists each missing
fact with the chapter the plan (``ctx.extra["plan"]``) assigned it to, when known.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from app.bible.models import Fact
from app.validators.programmatic.text import (
    as_mapping,
    fact_rendered,
    memory_title,
    normalise,
    words,
)
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

_UNTRACKED_KINDS: Final = frozenset({"trait", "occasion"})
_NAME_KINDS: Final = frozenset({"recipient", "person", "pet"})
_PARTICLES: Final = frozenset({"de", "del", "la", "las", "los", "el", "y"})


def _is_name(fact: Fact) -> bool:
    return fact.key.endswith(".name") or (fact.kind in _NAME_KINDS and len(words(fact.value)) <= 4)


def fact_in_text(fact: Fact, normalised_text: str, brief: Mapping[str, object] | None) -> bool:
    """Whether the (already normalised) chapter text renders `fact`."""
    if _is_name(fact):
        present = set(normalised_text.split())
        tokens = [normalise(t) for t in words(fact.value)]
        return any(t in present for t in tokens if len(t) >= 3 and t not in _PARTICLES)
    value = memory_title(fact.key, fact.value, brief) if fact.kind == "memory" else fact.value
    return fact_rendered(value, "", normalised=normalised_text)


def tracked_facts(ctx: ValidationContext) -> list[Fact]:
    return [
        f
        for f in ctx.repo.list_facts(ctx.novel_id)
        if f.mandatory or f.kind not in _UNTRACKED_KINDS
    ]


def planned_chapter(plan: Mapping[str, object] | None, fact: Fact) -> int | None:
    """The chapter of ``plan["chapters"]`` whose entry mentions the fact's key or value."""
    if plan is None:
        return None
    chapters = plan.get("chapters")
    if not isinstance(chapters, Sequence) or isinstance(chapters, str):
        return None
    needle_value = normalise(fact.value)
    for position, entry in enumerate(chapters, start=1):
        item = as_mapping(entry)
        if item is None:
            continue
        dump = json.dumps(item, ensure_ascii=False, default=str)
        if fact.key in dump or (needle_value and needle_value in normalise(dump)):
            for field in ("number", "chapter", "index"):
                number = item.get(field)
                if isinstance(number, int):
                    return number
            return position
    return None


@dataclass(frozen=True, slots=True)
class FactUsageRecorder:
    name: str = "fact_usage_recorder"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        if ctx.chapter is None:
            return ValidationResult(
                self.name, True, None, [], "Sin número de capítulo: no se registra uso de hechos."
            )
        brief = as_mapping(ctx.extra.get("brief"))
        normalised = normalise(ctx.text)
        found: list[str] = []
        for fact in tracked_facts(ctx):
            if fact_in_text(fact, normalised, brief):
                ctx.repo.record_fact_usage(
                    fact.id, chapter=ctx.chapter, scene=0, version=ctx.version
                )
                found.append(fact.key)
        mandatory = ctx.repo.list_facts(ctx.novel_id, mandatory=True)
        covered = [
            f.key for f in mandatory if ctx.repo.chapters_using_fact(f.id, version=ctx.version)
        ]
        evidence = [f"capítulo {ctx.chapter}: {', '.join(found) or 'ningún hecho'}"]
        evidence.append(f"obligatorios cubiertos hasta ahora: {len(covered)}/{len(mandatory)}")
        return ValidationResult(
            self.name,
            True,
            None,
            evidence,
            f"Registrados {len(found)} hechos usados en el capítulo {ctx.chapter}.",
        )


@dataclass(frozen=True, slots=True)
class BriefCoverage:
    name: str = "brief_coverage"
    point: ValidationPoint = ValidationPoint.PRE_PUBLISH

    def run(self, ctx: ValidationContext) -> ValidationResult:
        mandatory = ctx.repo.list_facts(ctx.novel_id, mandatory=True)
        if not mandatory:
            return ValidationResult(
                self.name, True, 1.0, [], "El brief no tiene hechos obligatorios."
            )
        brief = as_mapping(ctx.extra.get("brief"))
        plan = as_mapping(ctx.extra.get("plan"))
        chapters = {
            c.chapter: normalise(c.text) for c in ctx.repo.list_chapters(ctx.novel_id, ctx.version)
        }
        missing: list[str] = []
        notes: list[str] = []
        for fact in mandatory:
            rendered = [n for n, text in chapters.items() if fact_in_text(fact, text, brief)]
            recorded = set(ctx.repo.chapters_using_fact(fact.id, version=ctx.version))
            for number in rendered:
                if number not in recorded:
                    ctx.repo.record_fact_usage(
                        fact.id, chapter=number, scene=0, version=ctx.version
                    )
                    notes.append(f"uso registrado a posteriori: {fact.key} en cap. {number}")
            stale = sorted(recorded - set(rendered))
            if stale:
                notes.append(
                    f"uso registrado pero no presente en el texto: {fact.key} cap. {stale}"
                )
            if not rendered:
                assigned = planned_chapter(plan, fact)
                where = f" (el plan lo asignaba al capítulo {assigned})" if assigned else ""
                missing.append(f"{fact.key} = «{fact.value}»{where}")
        covered = len(mandatory) - len(missing)
        score = round(covered / len(mandatory), 3)
        if not missing:
            return ValidationResult(
                self.name,
                True,
                score,
                notes,
                f"Los {len(mandatory)} hechos obligatorios del brief aparecen en la novela.",
            )
        return ValidationResult(
            self.name,
            False,
            score,
            [f"falta: {m}" for m in missing] + notes,
            f"Faltan {len(missing)} de {len(mandatory)} elementos obligatorios del brief: "
            + "; ".join(missing)
            + ". Intégralos de forma natural en el capítulo asignado (no como una lista).",
        )


__all__ = ["BriefCoverage", "FactUsageRecorder", "fact_in_text", "planned_chapter", "tracked_facts"]
