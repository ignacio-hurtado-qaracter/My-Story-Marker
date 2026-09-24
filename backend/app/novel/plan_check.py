"""Programmatic check of a `NovelPlan` (spec 007 AC 5).

Returns a list of problems in plain Spanish-neutral English, fed back verbatim to the
planner for its one replan. An empty list means the plan is usable.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from datetime import date

from app.novel.models import NovelPlan

SCENES_PER_CHAPTER = 3
CHAPTER_BUDGET_MIN = 1100
CHAPTER_BUDGET_MAX = 1350


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
    covered = {(e.chapter, e.scene) for e in plan.events}
    lacking = [f"{s.chapter}.{s.scene}" for s in plan.scenes if (s.chapter, s.scene) not in covered]
    if lacking:
        problems.append(
            "every scene needs at least one chronology event; missing: " + ", ".join(lacking)
        )
    for character in plan.characters:
        if character.birth_date and parse_iso(character.birth_date) is None:
            problems.append(f"character {character.name}: birth_date is not YYYY-MM-DD")

    names = {c.name for c in plan.characters}
    for name in exact_names:
        if name and name not in names:
            problems.append(f"character {name!r} from the brief must appear with that exact name")
    return problems


__all__ = [
    "CHAPTER_BUDGET_MAX",
    "CHAPTER_BUDGET_MIN",
    "SCENES_PER_CHAPTER",
    "check_plan",
    "parse_iso",
]
