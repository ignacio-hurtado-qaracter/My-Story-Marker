"""Programmatic check of a `NovelPlan` (spec 007 AC 5).

Returns a list of problems in plain Spanish-neutral English, fed back verbatim to the
planner for its one replan. An empty list means the plan is usable.
"""

from __future__ import annotations

import itertools
import re
import unicodedata
from collections.abc import Collection, Iterable
from datetime import date

from app.novel.models import NovelPlan

SCENES_PER_CHAPTER = 3
CHAPTER_BUDGET_MIN = 1100
CHAPTER_BUDGET_MAX = 1350
#: Two chapters whose synopses share this share of the smaller one's content words (and at
#: least `OVERLAP_MIN_SHARED` of them) tell the same core: the plan is rejected (tuning 1).
OVERLAP_MAX = 0.6
OVERLAP_MIN_SHARED = 4
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOP = frozenset(
    [
        "ante",
        "antes",
        "aqui",
        "aunque",
        "bajo",
        "cada",
        "casi",
        "como",
        "contra",
        "cual",
        "cuando",
        "desde",
        "donde",
        "ella",
        "ellas",
        "ellos",
        "entonces",
        "entre",
        "esta",
        "este",
        "esto",
        "estos",
        "estas",
        "hace",
        "hacia",
        "hasta",
        "mientras",
        "mismo",
        "mucho",
        "nada",
        "otra",
        "otro",
        "para",
        "pero",
        "poco",
        "porque",
        "sobre",
        "solo",
        "tambien",
        "tanto",
        "todo",
        "todos",
        "toda",
        "todas",
        "tras",
        "luego",
        "despues",
        "ahora",
        "dentro",
        "fuera",
        "tiene",
        "tienen",
        "puede",
        "cosas",
        "veces",
        "tiempo",
        "parte",
    ]
)


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def check_plan(
    plan: NovelPlan,
    *,
    chapters: int,
    mandatory_keys: Collection[str],
    known_keys: Collection[str],
    exact_names: Iterable[str] = (),
    known_places: Iterable[str] = (),
) -> list[str]:
    problems: list[str] = []
    numbers = sorted(c.number for c in plan.chapters)
    if numbers != list(range(1, chapters + 1)):
        problems.append(f"chapters must be numbered 1..{chapters} exactly once; got {numbers}")
    for number in range(1, chapters + 1):
        scenes = plan.scenes_of(number)
        positions = [s.scene for s in scenes]
        if positions != list(range(1, SCENES_PER_CHAPTER + 1)):
            problems.append(
                f"chapter {number} must have scenes 1..{SCENES_PER_CHAPTER}; got {positions}"
            )
        budget = sum(s.word_budget for s in scenes)
        if scenes and not CHAPTER_BUDGET_MIN <= budget <= CHAPTER_BUDGET_MAX:
            problems.append(
                f"chapter {number}: scene word_budget sum is {budget}, must be "
                f"{CHAPTER_BUDGET_MIN}-{CHAPTER_BUDGET_MAX}"
            )
    extra = sorted({s.chapter for s in plan.scenes} - set(range(1, chapters + 1)))
    if extra:
        problems.append(f"scenes reference chapters that do not exist: {extra}")

    used = {key for s in plan.scenes for key in s.facts_used}
    missing = sorted(set(mandatory_keys) - used)
    if missing:
        problems.append(
            "these mandatory facts are not in any scene's facts_used: " + ", ".join(missing)
        )
    unknown = sorted(used - set(known_keys))
    if unknown:
        problems.append("facts_used contains unknown keys: " + ", ".join(unknown))

    for scene in plan.scenes:
        if parse_iso(scene.story_date) is None:
            problems.append(
                f"chapter {scene.chapter} scene {scene.scene}: story_date "
                f"{scene.story_date!r} is not YYYY-MM-DD"
            )
    for event in plan.events:
        if parse_iso(event.story_date) is None:
            problems.append(f"event {event.seq}: story_date {event.story_date!r} is not ISO")
    problems += event_place_problems(plan, known_places)
    covered = {(e.chapter, e.scene) for e in plan.events}
    lacking = [f"{s.chapter}.{s.scene}" for s in plan.scenes if (s.chapter, s.scene) not in covered]
    if lacking:
        problems.append(
            "every scene needs at least one chronology event; missing: " + ", ".join(lacking)
        )
    for character in plan.characters:
        if character.birth_date and parse_iso(character.birth_date) is None:
            problems.append(f"character {character.name}: birth_date is not YYYY-MM-DD")

    problems += timeline_problems(plan)
    problems += overlap_problems(plan, exact_names)

    names = {c.name for c in plan.characters}
    for name in exact_names:
        if name and name not in names:
            problems.append(f"character {name!r} from the brief must appear with that exact name")
    return problems


def place_names(plan: NovelPlan, known_places: Iterable[str] = ()) -> list[str]:
    """Every place an event may name: the plan's own, then the bible's (brief)."""
    return [*(p.name for p in plan.places), *known_places]


def resolve_place(name: str | None, known: Iterable[str]) -> str | None:
    """The known place `name` refers to (exact, then case- and accent-insensitive), or
    None. The Lean export needs a `place_id` for every event (spec 007, plan events must
    have a place)."""
    if not name or not name.strip():
        return None
    candidates = [k for k in known if k]
    if name in candidates:
        return name
    folded = _fold(name.strip())
    return next((k for k in candidates if _fold(k.strip()) == folded), None)


def event_place_problems(plan: NovelPlan, known_places: Iterable[str] = ()) -> list[str]:
    """A chronology event without a resolvable place cannot be exported to Lean, and no
    prose rewrite can fix a plan row: it is a plan problem, sent back to the planner."""
    known = place_names(plan, known_places)
    problems: list[str] = []
    for event in plan.events:
        if resolve_place(event.place, known) is not None:
            continue
        if not event.place or not event.place.strip():
            problems.append(
                f"El evento e{event.seq} del capítulo {event.chapter} no tiene lugar: "
                "cada evento debe nombrar uno de los lugares de `places`"
            )
        else:
            problems.append(
                f"El evento e{event.seq} del capítulo {event.chapter} no tiene lugar "
                f"conocido: «{event.place}» no está en `places`; usa uno de ellos"
            )
    return problems


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _content(text: str, exclude: Collection[str]) -> set[str]:
    return {
        w for w in _WORD.findall(_fold(text)) if len(w) >= 5 and w not in _STOP and w not in exclude
    }


def chapter_anchor(plan: NovelPlan, number: int) -> date | None:
    """The date of a chapter's present action: its latest scene date (an earlier scene
    may be a memory)."""
    dates = [d for s in plan.scenes_of(number) if (d := parse_iso(s.story_date)) is not None]
    return max(dates) if dates else None


def timeline_problems(plan: NovelPlan) -> list[str]:
    """Tuning 1: every chapter has an explicit `time_marker`, and the chapters that are
    not flagged `flashback` move forward (or stay) in story time."""
    problems: list[str] = []
    previous: tuple[int, date] | None = None
    for chapter in sorted(plan.chapters, key=lambda c: c.number):
        if len(chapter.time_marker.strip()) < 3:
            problems.append(
                f"chapter {chapter.number}: time_marker is missing; give the explicit story "
                "time of its present action relative to the previous chapter"
            )
        anchor = chapter_anchor(plan, chapter.number)
        if chapter.flashback or anchor is None:
            continue
        if previous is not None and anchor < previous[1]:
            problems.append(
                f"chapter {chapter.number} ({anchor}) happens before chapter {previous[0]} "
                f"({previous[1]}) but is not flagged flashback: keep chapters in story order "
                "or set flashback=true and say so in its time_marker"
            )
        previous = (chapter.number, anchor)
    return problems


def overlap_problems(plan: NovelPlan, exact_names: Iterable[str] = ()) -> list[str]:
    """Tuning 1: two chapters must not tell the same core (token overlap of synopses,
    names and places left out)."""
    named = [*exact_names, *(c.name for c in plan.characters), *(p.name for p in plan.places)]
    names = {w for n in named for w in _content(n, ())}
    words = {c.number: _content(f"{c.title} {c.synopsis}", names) for c in plan.chapters}
    problems: list[str] = []
    for a, b in itertools.combinations(sorted(words), 2):
        shared = words[a] & words[b]
        smaller = min(len(words[a]), len(words[b]))
        if smaller and len(shared) >= OVERLAP_MIN_SHARED and len(shared) / smaller >= OVERLAP_MAX:
            problems.append(
                f"chapters {a} and {b} tell the same core (shared: {', '.join(sorted(shared))}); "
                "give each chapter its own event and never narrate one scene in two chapters"
            )
    return problems


__all__ = [
    "CHAPTER_BUDGET_MAX",
    "CHAPTER_BUDGET_MIN",
    "OVERLAP_MAX",
    "OVERLAP_MIN_SHARED",
    "SCENES_PER_CHAPTER",
    "chapter_anchor",
    "check_plan",
    "event_place_problems",
    "overlap_problems",
    "parse_iso",
    "place_names",
    "resolve_place",
    "timeline_problems",
]
