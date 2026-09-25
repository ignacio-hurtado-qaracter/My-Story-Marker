"""The plan's chronology, made Lean-valid before any prose is written (spec 007).

The `lean_chronology` pre-publish validator (B4, spec 008) proves four invariants over the
chronology rows the planner produced: events in `seq` order are not dated backwards, nobody
appears before birth or with a wrong declared age, nobody is in two places on one day, and
nobody appears after a death or departure. Rewriting prose cannot repair a chronology row,
so the pipeline checks the plan here: deterministic fixes first (re-sequence by date,
declared ages recomputed from birth dates, a same-day second place moved to the next day),
then B4's own `diagnose` for what is left, which goes back to the planner as feedback.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Mapping
from datetime import date, timedelta

from app.novel.models import NovelPlan, ParticipantAge, PlanEvent
from app.novel.plan_check import parse_iso, place_names, resolve_place

Births = Mapping[str, str | None]
_Diagnose = Callable[[Mapping[str, object]], dict[str, list[str]]]


def _age(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def plan_births(plan: NovelPlan, known: Births) -> dict[str, str | None]:
    """Birth dates by name: the bible's (brief) first, then the planner's."""
    births: dict[str, str | None] = {c.name: c.birth_date for c in plan.characters}
    births.update({k: v for k, v in known.items() if v})
    return births


def as_chronology(plan: NovelPlan, births: Births) -> dict[str, object]:
    """The plan in `BibleRepository.chronology_json` format (names used as ids)."""
    return {
        "characters": [{"id": n, "name": n, "birth_date": b} for n, b in births.items()],
        "places": [{"id": p.name, "name": p.name} for p in plan.places],
        "events": [
            {
                "id": f"e{e.seq}",
                "seq": e.seq,
                "story_date": e.story_date,
                "place_id": e.place,
                "participants": list(e.participants),
                "kind": e.kind,
                "declared_ages": {a.name: a.age for a in e.declared_ages},
                "chapter": e.chapter,
                "description": e.description,
            }
            for e in plan.events
        ],
    }


def normalise_events(
    plan: NovelPlan, births: Births, known_places: Iterable[str] = ()
) -> NovelPlan:
    """Deterministic fixes: every event's place resolved to a known place name (its
    scene's place when its own is missing or unknown), bilocations moved to the next day,
    `seq` re-numbered in date order, declared ages recomputed (dropped when the character
    is not yet born)."""
    events = _separate_bilocations(_inherit_places(plan, known_places))
    events.sort(key=lambda e: (parse_iso(e.story_date) or date.max, e.chapter, e.scene, e.seq))
    fixed: list[PlanEvent] = []
    for seq, event in enumerate(events, start=1):
        on = parse_iso(event.story_date)
        ages: list[ParticipantAge] = []
        for declared in event.declared_ages:
            birth = parse_iso(births.get(declared.name))
            if birth is None or on is None:
                ages.append(declared)
            elif on >= birth:
                ages.append(ParticipantAge(name=declared.name, age=_age(birth, on)))
        fixed.append(event.model_copy(update={"seq": seq, "declared_ages": ages}))
    return plan.model_copy(update={"events": fixed})


def _inherit_places(plan: NovelPlan, known_places: Iterable[str]) -> list[PlanEvent]:
    """Defence in depth for the Lean export (spec 007): an event whose place does not
    resolve takes its scene's place when that one does; otherwise it is left for
    `check_plan` to reject."""
    known = place_names(plan, known_places)
    scene_place = {(s.chapter, s.scene): s.place for s in plan.scenes}
    out: list[PlanEvent] = []
    for event in plan.events:
        place = resolve_place(event.place, known) or resolve_place(
            scene_place.get((event.chapter, event.scene)), known
        )
        out.append(event if place is None else event.model_copy(update={"place": place}))
    return out


def _separate_bilocations(events: list[PlanEvent]) -> list[PlanEvent]:
    """A character in two places on one day: the later event (by chapter, scene) moves to
    the next free day. Bounded: each event moves at most 30 days."""
    ordered = sorted(events, key=lambda e: (e.chapter, e.scene, e.seq))
    where: dict[tuple[str, date], str] = {}
    out: list[PlanEvent] = []
    for event in ordered:
        on = parse_iso(event.story_date)
        if on is None:
            out.append(event)
            continue
        for _ in range(30):
            clash = any(where.get((p, on), event.place) != event.place for p in event.participants)
            if not clash:
                break
            on += timedelta(days=1)
        for person in event.participants:
            where.setdefault((person, on), event.place)
        out.append(event.model_copy(update={"story_date": on.isoformat()}))
    return out


def _diagnose() -> _Diagnose | None:
    try:
        module = importlib.import_module("app.validators.programmatic.chronology")
    except ImportError:
        return None
    found = getattr(module, "diagnose", None)
    return found if callable(found) else None


def chronology_problems(plan: NovelPlan, births: Births) -> list[str]:
    diagnose = _diagnose()
    if diagnose is None:
        return []
    found = diagnose(as_chronology(plan, births))
    return [f"chronology {name}: {s}" for name, sentences in found.items() for s in sentences]


__all__ = ["as_chronology", "chronology_problems", "normalise_events", "plan_births"]
