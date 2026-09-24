"""`lean_chronology` — invariants 14-16 (and 4), L03 (spec 008 / AC 4; spec 012).

``repo.chronology_json(novel_id)`` → ``app.formal.verify_chronology`` (``lake build`` over
the generated Lean file). Score 1 when every invariant is proved, 0 otherwise. A missing
Lean toolchain is a **failure** with an explanation, never a silent pass: this is a
publication gate.

``LeanResult`` names the failed invariants but not the events. To give the editor
actionable feedback, ``diagnose`` re-checks the same four invariants in Python over the
chronology JSON and phrases each offending event pair with its chapter ("El evento e7 del
capítulo 4 sitúa a X en dos lugares el mismo día…"). The diagnosis is evidence only; the
verdict is Lean's.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.formal import verify_chronology
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult


def _date(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _age(birth: dt.date, on: dt.date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def _items(value: object) -> list[Mapping[str, object]]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [v for v in value if isinstance(v, Mapping)]
    return []


def _seq(event: Mapping[str, object]) -> int:
    seq = event.get("seq")
    return seq if isinstance(seq, int) else 0


def _where(event: Mapping[str, object]) -> str:
    chapter = event.get("chapter")
    suffix = f" del capítulo {chapter}" if chapter is not None else ""
    return f"El evento {event.get('id')}{suffix}"


def diagnose(chronology: Mapping[str, object]) -> dict[str, list[str]]:
    """Per invariant, Spanish sentences naming the events that break it."""
    names = {str(c.get("id")): str(c.get("name")) for c in _items(chronology.get("characters"))}
    births = {
        str(c.get("id")): _date(c.get("birth_date")) for c in _items(chronology.get("characters"))
    }
    places = {str(p.get("id")): str(p.get("name")) for p in _items(chronology.get("places"))}
    events = sorted(_items(chronology.get("events")), key=_seq)
    found: dict[str, list[str]] = defaultdict(list)

    def participants(event: Mapping[str, object]) -> list[str]:
        raw = event.get("participants")
        return [str(p) for p in raw] if isinstance(raw, list) else []

    previous: Mapping[str, object] | None = None
    for event in events:
        date = _date(event.get("story_date"))
        if previous is not None:
            before = _date(previous.get("story_date"))
            if date and before and date < before:
                found["temporalOrder"].append(
                    f"{_where(event)} ocurre después de {previous.get('id')} en la historia "
                    f"pero está fechado antes ({date} < {before})."
                )
        if date is not None:
            previous = event
        declared = event.get("declared_ages")
        for cid in participants(event):
            birth = births.get(cid)
            if birth is None or date is None:
                continue
            if date < birth:
                found["agesCoherent"].append(
                    f"{_where(event)} incluye a {names.get(cid, cid)} antes de nacer ({birth})."
                )
            elif isinstance(declared, Mapping) and isinstance(declared.get(cid), int):
                real = _age(birth, date)
                if declared[cid] != real:
                    found["agesCoherent"].append(
                        f"{_where(event)} da a {names.get(cid, cid)} {declared[cid]} años, pero "
                        f"por su nacimiento ({birth}) tendría {real}."
                    )

    seen: dict[tuple[str, dt.date], Mapping[str, object]] = {}
    for event in events:
        date = _date(event.get("story_date"))
        place = event.get("place_id")
        if date is None or place is None:
            continue
        for cid in participants(event):
            other = seen.setdefault((cid, date), event)
            if other is not event and other.get("place_id") != place:
                found["noBilocation"].append(
                    f"{_where(event)} sitúa a {names.get(cid, cid)} en "
                    f"«{places.get(str(place), place)}» el {date}, pero {other.get('id')} "
                    f"(capítulo {other.get('chapter')}) la/lo sitúa el mismo día en "
                    f"«{places.get(str(other.get('place_id')), other.get('place_id'))}»."
                )

    exits: dict[str, Mapping[str, object]] = {}
    for event in events:
        for cid in participants(event):
            if cid in exits:
                exit_event = exits[cid]
                found["noAfterExit"].append(
                    f"{_where(event)} hace aparecer a {names.get(cid, cid)}, que ya había "
                    f"salido de la historia ({exit_event.get('kind')}) en "
                    f"{exit_event.get('id')} (capítulo {exit_event.get('chapter')})."
                )
        if event.get("kind") in {"death", "departure"}:
            for cid in participants(event):
                exits.setdefault(cid, event)
    return dict(found)


@dataclass(frozen=True, slots=True)
class LeanChronology:
    name: str = "lean_chronology"
    point: ValidationPoint = ValidationPoint.PRE_PUBLISH
    lean_dir: Path | None = None

    def run(self, ctx: ValidationContext) -> ValidationResult:
        chronology = ctx.repo.chronology_json(ctx.novel_id)
        result = verify_chronology(chronology, ctx.novel_id, lean_dir=self.lean_dir)
        if result.passed:
            return ValidationResult(
                self.name,
                True,
                1.0,
                [result.lean_file] if result.lean_file else [],
                "Lean 4 ha demostrado los invariantes de la cronología.",
            )
        details = diagnose(chronology)
        failed = result.failed_invariants or list(details)
        evidence = [f"invariante fallido: {name}" for name in result.failed_invariants]
        sentences = [s for name in failed for s in details.get(name, [])]
        evidence += sentences
        if not result.failed_invariants:
            evidence.append(result.output[:500])
            explanation = f"No se pudo verificar la cronología con Lean 4: {result.output[:300]}"
            if sentences:
                explanation += " Además: " + " ".join(sentences[:5])
        else:
            explanation = (
                "La cronología de la historia es incoherente ("
                + ", ".join(result.failed_invariants)
                + "). "
                + (" ".join(sentences[:5]) or "Revisa fechas, lugares y edades de los eventos.")
                + " Corrige el capítulo afectado para que fechas, lugares y edades concuerden."
            )
        return ValidationResult(self.name, False, 0.0, evidence, explanation)


__all__ = ["LeanChronology", "diagnose"]
