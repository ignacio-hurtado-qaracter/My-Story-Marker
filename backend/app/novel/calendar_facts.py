"""Calendar facts of the plan (spec 007 / AC 8; tuning iteration 2).

The writer named weekdays that the calendar contradicts ("el martes 24 de junio"), and
counted years that the brief's dates contradict ("treinta años" of a career that started in
1992 and ends in 2026); the judge blocked the novel on both, and repair rewrites did not
converge. Everything here is computed in Python, never asked of a model:

* ``enrich_plan_calendar`` — after the plan passes its check, every weekday the planner
  wrote next to a date is corrected to the real one, and each chapter's ``time_marker``
  ends with ``[fechas: domingo 21 de junio de 2026]`` (the real weekday of its scene dates).
* ``chapter_calendar`` — ``(date, weekday)`` of a chapter's scene dates, for
  ``ctx.extra["plan"]`` (read by the ``calendar_consistency`` validator).
* ``calendar_document`` — ``plan/calendar.txt`` for writer and editor: one line per scene
  date ("Fecha: domingo 21 de junio de 2026 (usa exactamente este día de la semana si lo
  nombras)") and a block of **cifras canónicas**: the story's present, ages and the years
  elapsed since each dated memory, only where both ends are known (brief birth and memory
  dates; the present is the latest scene date of the plan).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from typing import Final

from pydantic import JsonValue

from app.commons.llm import Document
from app.novel.models import NovelPlan
from app.novel.plan_check import parse_iso
from app.validators.programmatic.calendar import MONTHS, fix_weekdays, format_date_es, weekday_es

CALENDAR_PATH: Final[str] = "plan/calendar.txt"
_FECHAS: Final = re.compile(r"\s*\[fechas:[^\]]*\]\s*$")


def _scene_dates(plan: NovelPlan, chapter: int) -> list[dt.date]:
    dates = [parse_iso(s.story_date) for s in plan.scenes_of(chapter)]
    return sorted({d for d in dates if d is not None})


def chapter_calendar(plan: NovelPlan, chapter: int) -> list[dict[str, str]]:
    """The chapter's distinct scene dates with their real weekday."""
    return [
        {"date": d.isoformat(), "weekday": weekday_es(d), "label": format_date_es(d)}
        for d in _scene_dates(plan, chapter)
    ]


def story_present(plan: NovelPlan) -> dt.date | None:
    """The latest scene date of the plan: the story's present."""
    dates = [d for d in (parse_iso(s.story_date) for s in plan.scenes) if d is not None]
    return max(dates) if dates else None


def _years_map(
    plan: NovelPlan, chapter: int | None
) -> tuple[dict[tuple[int, int], int], int | None]:
    years: dict[tuple[int, int], int] = {}
    others = [d for s in plan.scenes if (d := parse_iso(s.story_date)) is not None]
    own = _scene_dates(plan, chapter) if chapter is not None else []
    for d in [*others, *own]:
        years[(d.month, d.day)] = d.year
    default = max(d.year for d in own) if own else (max(d.year for d in others) if others else None)
    return years, default


def enrich_plan_calendar(plan: NovelPlan) -> NovelPlan:
    """Correct the weekdays in the planner's text and stamp each chapter's real dates on
    its `time_marker`. Idempotent."""
    chapters = []
    for chap in plan.chapters:
        years, default = _years_map(plan, chap.number)
        marker = _FECHAS.sub("", fix_weekdays(chap.time_marker, years=years, default_year=default))
        labels = [format_date_es(d) for d in _scene_dates(plan, chap.number)]
        if labels:
            marker = f"{marker} [fechas: {'; '.join(labels)}]".strip()
        chapters.append(
            chap.model_copy(
                update={
                    "time_marker": marker,
                    "synopsis": fix_weekdays(chap.synopsis, years=years, default_year=default),
                }
            )
        )
    scenes = []
    for scene in plan.scenes:
        years, default = _years_map(plan, scene.chapter)
        scenes.append(
            scene.model_copy(
                update={"summary": fix_weekdays(scene.summary, years=years, default_year=default)}
            )
        )
    events = []
    for event in plan.events:
        years, default = _years_map(plan, event.chapter)
        events.append(
            event.model_copy(
                update={
                    "description": fix_weekdays(
                        event.description, years=years, default_year=default
                    )
                }
            )
        )
    years, default = _years_map(plan, None)
    return plan.model_copy(
        update={
            "chapters": chapters,
            "scenes": scenes,
            "events": events,
            "synopsis": fix_weekdays(plan.synopsis, years=years, default_year=default),
        }
    )


def _age(birth: dt.date, on: dt.date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def _long(date: dt.date) -> str:
    return f"{date.day} de {MONTHS[date.month - 1]} de {date.year}"


def _births(brief: Mapping[str, JsonValue]) -> list[tuple[str, dt.date]]:
    out: list[tuple[str, dt.date]] = []
    recipient = brief.get("recipient")
    groups: list[JsonValue] = [recipient] if isinstance(recipient, Mapping) else []
    for key in ("people", "pets"):
        items = brief.get(key)
        if isinstance(items, list):
            groups.extend(items)
    for item in groups:
        if not isinstance(item, Mapping):
            continue
        name, raw = item.get("name"), item.get("birth_date")
        birth = parse_iso(raw) if isinstance(raw, str) else None
        if isinstance(name, str) and name and birth is not None:
            out.append((name, birth))
    return out


def canonical_figures(brief: Mapping[str, JsonValue], present: dt.date | None) -> list[str]:
    """Durations computed from brief dates only, where both ends are known."""
    if present is None:
        return []
    lines = [f"Presente de la historia: {format_date_es(present)} (año {present.year})."]
    births = _births(brief)
    for name, birth in births:
        if birth <= present:
            lines.append(
                f"Edad de {name} en el presente: {_age(birth, present)} años "
                f"(nacimiento: {_long(birth)})."
            )
    memories = brief.get("memories")
    for memory in memories if isinstance(memories, list) else []:
        if not isinstance(memory, Mapping):
            continue
        title, raw = memory.get("title"), memory.get("date")
        when = parse_iso(raw) if isinstance(raw, str) else None
        if not isinstance(title, str) or when is None or when > present:
            continue
        ages = [f"{n} tenía {_age(b, when)}" for n, b in births if b <= when]
        lines.append(
            f"«{title}» ({_long(when)}): hace {_age(when, present)} años cumplidos "
            f"respecto al presente ({when.year}-{present.year})"
            + (f"; {', '.join(ages)} años." if ages else ".")
        )
    return lines


def calendar_document(plan: NovelPlan, chapter: int, brief: Mapping[str, JsonValue]) -> Document:
    """`plan/calendar.txt`: the chapter's real dates and the canonical figures."""
    lines = [
        f"Fechas del capítulo {chapter} (calendario real, calculado; no las cambies):",
    ]
    for scene in plan.scenes_of(chapter):
        date = parse_iso(scene.story_date)
        if date is None:
            continue
        lines.append(
            f"- Escena {scene.scene}: Fecha: {format_date_es(date)} "
            "(usa exactamente este día de la semana si lo nombras)"
        )
    lines += [
        "Si nombras otra fecha, no le pongas día de la semana.",
        "",
        (
            "Cifras canónicas (calculadas de las fechas del brief). Si dices una edad o cuántos "
            "años han pasado, usa exactamente estas cifras; si una descripción del brief da una "
            "cifra redonda distinta, usa la calculada o una expresión compatible con ella (por "
            "ejemplo «más de treinta años»):"
        ),
    ]
    figures = canonical_figures(brief, story_present(plan))
    lines += [f"- {f}" for f in figures] or ["- (sin fechas suficientes en el brief)"]
    return Document(path=CALENDAR_PATH, text="\n".join(lines))


__all__ = [
    "CALENDAR_PATH",
    "calendar_document",
    "canonical_figures",
    "chapter_calendar",
    "enrich_plan_calendar",
    "story_present",
]
