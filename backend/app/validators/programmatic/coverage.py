"""`fact_usage_recorder` and `brief_coverage` — invariant 13, V03, M01 (spec 008 / AC 3).

**fact_usage_recorder** (``chapter_close``) detects which facts of the bible the chapter
renders and records one ``fact_usage(fact, version, chapter, scene=0)`` row per fact
through the repository (K1). This is what keeps "chapters using each fact" truthful for
the reader and for ``change_fact``. It always passes; its evidence reports the facts found
and the mandatory coverage so far. Matching (``fact_values`` + ``text.fact_rendered``):

- name facts (key ``*.name`` or kind recipient/person/pet) match when any token of the
  name (≥ 3 letters, not a particle) appears as a word — "Lucía" renders "Lucía Pérez";
- memories (tuning iteration 1) match on normalised **content words** — casefolded,
  accents stripped and plurals folded by ``app.policy.normalise`` (``caracoles`` renders
  ``caracol``); content words are ≥ 4 letters, not stopwords, not digits and not a name of
  the brief (recipient, people, pets, places) nor a generic title word ("primera",
  "última"…), so a name alone never proves a memory. A
  memory is rendered when the chapter contains **at least half (and at least one) of the
  title's content words**, *or* **at least 30 % of the description's content words**. The
  title and description come from the brief when available, else from the fact value
  (``"<title>: <description>"``). Before, a title of ≤ 3 words had to appear as an exact
  phrase ("El caracol campeón"), which failed chapters that told the memory in full;
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
from functools import lru_cache
from typing import Final

from app.bible.models import Fact
from app.policy.normalise import normalise as fold
from app.policy.normalise import term_variants
from app.validators.programmatic.text import (
    STOPWORDS,
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


MEMORY_TITLE_SHARE: Final = 0.5
MEMORY_DESCRIPTION_SHARE: Final = 0.3
_MIN_CONTENT_LETTERS: Final = 4
#: Words too common in memory titles to prove anything on their own.
_GENERIC: Final = frozenset(
    [
        "primer",
        "primera",
        "primero",
        "ultima",
        "ultimo",
        "gran",
        "grande",
        "nuevo",
        "nueva",
        "dias",
        "noche",
        "tarde",
        "vez",
    ]
)


@lru_cache(maxsize=64)
def _text_keys(normalised_text: str) -> frozenset[str]:
    """Every singular candidate of every word of the text (policy normaliser)."""
    keys: set[str] = set()
    for token in set(fold(normalised_text).split()):
        keys |= term_variants(token)
    return frozenset(keys)


def _brief_names(brief: Mapping[str, object] | None) -> frozenset[str]:
    """Folded tokens of every name in the brief: never content words of a memory."""
    if brief is None:
        return frozenset()
    names: list[str] = []
    recipient = as_mapping(brief.get("recipient"))
    if recipient is not None and isinstance(recipient.get("name"), str):
        names.append(str(recipient["name"]))
    for field in ("people", "pets", "places"):
        items = brief.get(field)
        if isinstance(items, Sequence) and not isinstance(items, str):
            for item in items:
                entry = as_mapping(item)
                if entry is not None and isinstance(entry.get("name"), str):
                    names.append(str(entry["name"]))
    return frozenset(t for name in names for t in fold(name).split())


def content_words(value: str, exclude: frozenset[str] = frozenset()) -> set[str]:
    """Folded words of ≥ 4 letters that are not stopwords, digits or excluded names."""
    return {
        token
        for token in fold(value).split()
        if len(token) >= _MIN_CONTENT_LETTERS
        and token.isalpha()
        and token not in STOPWORDS
        and token not in _GENERIC
        and token not in exclude
    }


def _present(word: str, keys: frozenset[str]) -> bool:
    return bool(term_variants(word) & keys)


def memory_parts(fact: Fact, brief: Mapping[str, object] | None) -> tuple[str, str]:
    """(title, description) of a memory fact: the brief's when found, else the value's."""
    title = memory_title(fact.key, fact.value, brief)
    memories = brief.get("memories") if brief is not None else None
    if isinstance(memories, Sequence) and not isinstance(memories, str):
        for item in memories:
            entry = as_mapping(item)
            if entry is not None and entry.get("title") == title:
                description = entry.get("description")
                return title, description if isinstance(description, str) else ""
    rest = fact.value[len(title) :] if fact.value.startswith(title) else fact.value
    return title, rest.lstrip(" :—.")


def memory_rendered(
    title: str, description: str, normalised_text: str, names: frozenset[str] = frozenset()
) -> bool:
    """The memory rule of the module docstring (tuning iteration 1)."""
    keys = _text_keys(normalised_text)
    title_words = content_words(title, names)
    if title_words:
        found = sum(_present(w, keys) for w in title_words)
        if found >= 1 and found >= MEMORY_TITLE_SHARE * len(title_words):
            return True
    described = content_words(description, names)
    if described:
        found = sum(_present(w, keys) for w in described)
        if found >= 1 and found >= MEMORY_DESCRIPTION_SHARE * len(described):
            return True
    return False


def _is_name(fact: Fact) -> bool:
    return fact.key.endswith(".name") or (fact.kind in _NAME_KINDS and len(words(fact.value)) <= 4)


def fact_in_text(fact: Fact, normalised_text: str, brief: Mapping[str, object] | None) -> bool:
    """Whether the (already normalised) chapter text renders `fact`."""
    if _is_name(fact):
        present = set(normalised_text.split())
        tokens = [normalise(t) for t in words(fact.value)]
        return any(t in present for t in tokens if len(t) >= 3 and t not in _PARTICLES)
    if fact.kind == "memory":
        title, description = memory_parts(fact, brief)
        return memory_rendered(title, description, normalised_text, _brief_names(brief))
    return fact_rendered(fact.value, "", normalised=normalised_text)


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


__all__ = [
    "MEMORY_DESCRIPTION_SHARE",
    "MEMORY_TITLE_SHARE",
    "BriefCoverage",
    "FactUsageRecorder",
    "content_words",
    "fact_in_text",
    "memory_parts",
    "memory_rendered",
    "planned_chapter",
    "tracked_facts",
]
