"""`calendar_consistency` — weekday names match the real calendar (spec 008 / AC 8; tuning 2).

The writer names weekdays ("el martes 23 de junio") that the calendar contradicts, and the
judge blocks the novel on them (tuning iteration 2). This validator finds the Spanish
patterns

* ``<día de la semana> [,] [el] [día] <n> de <mes> [de <año>]`` (with at most commas and
  a few time words between weekday and date: "Domingo por la mañana, el veintiuno de
  junio", "el lunes siguiente, 29 de junio"), and
* ``[el] <n> de <mes> [de <año>], [que era] <día de la semana>``,

with the day as digits or Spanish words ("veintitrés", "treinta y uno"), and checks the
weekday with ``datetime.date.weekday()``. A date without a year takes it from the plan
(``ctx.extra["plan"]``): the year of a plan date of this chapter with the same day and
month, else the latest year among the chapter's dates, else the latest year of the plan.
Without a plan and without a year the mention is skipped, never guessed.

The helpers (``weekday_es``, ``format_date_es``, ``find_weekday_mentions``,
``fix_weekdays``) are shared with the plan enrichment of the pipeline
(``app.novel.calendar_facts``).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from app.validators.programmatic.text import as_mapping
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

WEEKDAYS: Final[tuple[str, ...]] = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
MONTHS: Final[tuple[str, ...]] = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

_DAY_WORDS: Final[dict[str, int]] = {
    "primero": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciséis": 16,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintiún": 21,
    "veintiun": 21,
    "veintidós": 22,
    "veintidos": 22,
    "veintitrés": 23,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiséis": 26,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
    "treinta y uno": 31,
    "treinta": 30,
}

_WEEKDAY_RE: Final = r"lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo"
_DAY_RE: Final = r"\d{1,2}|" + "|".join(
    sorted((re.escape(w) for w in _DAY_WORDS), key=len, reverse=True)
)
_MONTH_RE: Final = (
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|"
    r"octubre|noviembre|diciembre"
)
_DATE_RE: Final = (
    rf"(?:el\s+)?(?:d[íi]a\s+)?(?P<day>{_DAY_RE})\s+de\s+(?P<month>{_MONTH_RE})"
    r"(?:\s+(?:de|del)\s+(?P<year>\d{4}))?"
)
# weekday first: between weekday and date only commas and a few time words ("por la
# mañana", "siguiente"), so "cada domingo desde el 3 de mayo" is not read as a claim
_GAP_WORDS: Final = (
    r"por\s+la\s+(?:mañana|tarde|noche)|de\s+(?:madrugada|mañana)|siguiente|"
    r"pr[óo]ximo|pasado|anterior|al\s+amanecer|temprano"
)
_WEEKDAY_FIRST: Final = re.compile(
    rf"\b(?P<weekday>{_WEEKDAY_RE})\b[\s,]*(?:(?:{_GAP_WORDS})[\s,]*){{0,2}}{_DATE_RE}\b",
    re.IGNORECASE,
)
# date first: the weekday right after, with only a comma or "que era/fue" between
_DATE_FIRST: Final = re.compile(
    rf"\b{_DATE_RE}\s*,?\s*(?:que\s+(?:era|fue|caía\s+en)\s+|un\s+)?(?P<weekday>{_WEEKDAY_RE})\b",
    re.IGNORECASE,
)


def weekday_es(date: dt.date) -> str:
    """The Spanish weekday name of `date` (lunes…domingo)."""
    return WEEKDAYS[date.weekday()]


def format_date_es(date: dt.date) -> str:
    """'domingo 21 de junio de 2026'."""
    return f"{weekday_es(date)} {date.day} de {MONTHS[date.month - 1]} de {date.year}"


def _plain(word: str) -> str:
    return word.lower().replace("é", "e").replace("á", "a")


def _day(raw: str) -> int | None:
    raw = " ".join(raw.lower().split())
    if raw.isdigit():
        return int(raw)
    return _DAY_WORDS.get(raw)


def _month(raw: str) -> int:
    raw = raw.lower()
    return 9 if raw == "setiembre" else MONTHS.index(raw) + 1


@dataclass(frozen=True, slots=True)
class WeekdayMention:
    """A weekday named next to a date. `said` is the weekday as written; `real` the one the
    calendar gives for `date`; `start`/`end`/`weekday_start`/`weekday_end` are offsets in
    the text."""

    quote: str
    said: str
    date: dt.date
    real: str
    start: int
    end: int
    weekday_start: int
    weekday_end: int

    @property
    def wrong(self) -> bool:
        return _plain(self.said) != _plain(self.real)


YearFor = Mapping[tuple[int, int], int]


def _resolve_year(
    day: int, month: int, explicit: str | None, years: YearFor, default: int | None
) -> int | None:
    if explicit:
        return int(explicit)
    return years.get((month, day), default)


def find_weekday_mentions(
    text: str, *, years: YearFor | None = None, default_year: int | None = None
) -> list[WeekdayMention]:
    """Every weekday+date mention in `text` whose date can be resolved. `years` maps
    (month, day) → year for dates the plan knows; `default_year` covers the others."""
    known = years or {}
    found: list[WeekdayMention] = []
    taken: list[tuple[int, int]] = []
    for pattern in (_WEEKDAY_FIRST, _DATE_FIRST):
        for m in pattern.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            day = _day(m.group("day"))
            if day is None:
                continue
            month = _month(m.group("month"))
            year = _resolve_year(day, month, m.group("year"), known, default_year)
            if year is None:
                continue
            try:
                date = dt.date(year, month, day)
            except ValueError:
                continue
            taken.append((m.start(), m.end()))
            found.append(
                WeekdayMention(
                    quote=m.group(0),
                    said=m.group("weekday"),
                    date=date,
                    real=weekday_es(date),
                    start=m.start(),
                    end=m.end(),
                    weekday_start=m.start("weekday"),
                    weekday_end=m.end("weekday"),
                )
            )
    return sorted(found, key=lambda w: w.start)


def fix_weekdays(
    text: str, *, years: YearFor | None = None, default_year: int | None = None
) -> str:
    """`text` with every wrong weekday replaced by the real one (case kept for the first
    letter). Used on the planner's own text, never on prose (prose goes back to the editor)."""
    out = text
    for mention in reversed(find_weekday_mentions(text, years=years, default_year=default_year)):
        if not mention.wrong:
            continue
        real = mention.real.capitalize() if mention.said[:1].isupper() else mention.real
        out = out[: mention.weekday_start] + real + out[mention.weekday_end :]
    return out


def _iso(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _chapter_dates(chapter: Mapping[str, object]) -> list[dt.date]:
    dates: list[dt.date] = []
    calendar = chapter.get("calendar")
    if isinstance(calendar, Sequence) and not isinstance(calendar, str):
        for entry in calendar:
            item = as_mapping(entry)
            date = _iso(item.get("date")) if item is not None else None
            if date is not None:
                dates.append(date)
    if not dates:
        scenes = chapter.get("scenes")
        if isinstance(scenes, Sequence) and not isinstance(scenes, str):
            for scene in scenes:
                item = as_mapping(scene)
                date = _iso(item.get("story_date")) if item is not None else None
                if date is not None:
                    dates.append(date)
    return dates


def plan_years(plan: object, chapter: int | None) -> tuple[dict[tuple[int, int], int], int | None]:
    """(month, day) → year for the plan dates (this chapter's first), and the default year:
    the latest year among this chapter's dates, else the latest of the plan."""
    plan_map = as_mapping(plan)
    if plan_map is None:
        return {}, None
    chapters_raw = plan_map.get("chapters")
    chapters = (
        [c for c in (as_mapping(x) for x in chapters_raw) if c is not None]
        if isinstance(chapters_raw, Sequence) and not isinstance(chapters_raw, str)
        else []
    )
    own: list[dt.date] = []
    other: list[dt.date] = []
    for chap in chapters:
        dates = _chapter_dates(chap)
        (own if chap.get("number") == chapter else other).extend(dates)
    years: dict[tuple[int, int], int] = {}
    for date in [*other, *own]:  # this chapter's dates win
        years[(date.month, date.day)] = date.year
    if own:
        return years, max(d.year for d in own)
    if other:
        return years, max(d.year for d in other)
    return years, None


@dataclass(frozen=True, slots=True)
class CalendarConsistency:
    name: str = "calendar_consistency"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        years, default = plan_years(ctx.extra.get("plan"), ctx.chapter)
        mentions = find_weekday_mentions(ctx.text, years=years, default_year=default)
        wrong = [m for m in mentions if m.wrong]
        if not wrong:
            return ValidationResult(
                self.name,
                True,
                1.0,
                [f"«{m.quote}» ✓" for m in mentions[:8]],
                f"Días de la semana coherentes con el calendario ({len(mentions)} menciones).",
            )
        evidence = [
            f"El capítulo dice «{m.quote}», pero el {m.date.day} de "
            f"{MONTHS[m.date.month - 1]} de {m.date.year} es {m.real}"
            for m in wrong
        ]
        explanation = (
            "; ".join(evidence)
            + ". Corrige el día de la semana o elimínalo (basta con quitar el nombre del día; "
            "no cambies la fecha del plan)."
        )
        score = round(1.0 - len(wrong) / len(mentions), 3)
        return ValidationResult(self.name, False, score, evidence, explanation)


__all__ = [
    "MONTHS",
    "WEEKDAYS",
    "CalendarConsistency",
    "WeekdayMention",
    "find_weekday_mentions",
    "fix_weekdays",
    "format_date_es",
    "plan_years",
    "weekday_es",
]
