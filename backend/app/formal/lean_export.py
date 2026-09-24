"""Export a story chronology to a Lean 4 file. Spec 012 (B8), AC 1 — L01.

The input is the chronology JSON that the story-bible block produces (``chronology_json``)::

    {"novel_id": "...",
     "characters": [{"id": "c1", "name": "...", "birth_date": "1990-05-12" | null}],
     "places": [{"id": "p1", "name": "..."}],
     "events": [{"id": "e1", "seq": 1, "story_date": "2020-06-01", "place_id": "p1",
                 "participants": ["c1"], "kind": "normal" | "death" | "departure",
                 "declared_ages": {"c1": 30}, "chapter": 1, "description": "..."}]}

The output is the source of ``formal/lean/Chronology/Generated/Story.lean``: a
``def story : Story`` over the model of ``Chronology/Basic.lean`` and one theorem per
invariant, each proved ``by decide``. A false invariant makes ``lake build`` fail on the
theorem that names it.

Nothing from the input is ever spliced into Lean as code. Ids become ``Nat`` indices;
the original ids, names and the novel id appear only as escaped string literals in a
lookup table the checks never read.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from collections.abc import Mapping, Sequence

__all__ = ["INVARIANTS", "ChronologyError", "day_number", "export_lean", "lean_string"]

#: The invariants of ``Basic.lean``, by the name the generated theorem carries
#: (``story_<name>``) and the Bool check it proves.
INVARIANTS: dict[str, str] = {
    "temporalOrder": "temporalOrderB",
    "agesCoherent": "agesCoherentB",
    "noBilocation": "noBilocationB",
    "noAfterExit": "noAfterExitB",
}

_KINDS = {"normal": ".normal", "death": ".death", "departure": ".departure"}
_SIMPLE_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


class ChronologyError(ValueError):
    """The chronology JSON is malformed: a missing field, a bad date, a dangling id."""


def lean_string(value: str) -> str:
    """Return ``value`` as a Lean 4 string literal that cannot end early or inject code."""
    out: list[str] = ['"']
    for ch in value:
        code = ord(ch)
        if ch in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[ch])
        elif 0xD800 <= code <= 0xDFFF:
            out.append("\\uFFFD")  # a lone surrogate is not a Unicode scalar value
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\x{code:02x}")
        elif unicodedata.category(ch) in {"Cc", "Cf", "Co", "Cn", "Zl", "Zp"}:
            out.append(f"\\u{code:04x}" if code <= 0xFFFF else "\\uFFFD")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _str(obj: Mapping[str, object], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise ChronologyError(f"{where}: '{key}' must be a string")
    return value


def _nat(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ChronologyError(f"{what} must be a non-negative integer")
    return value


def _parse_date(value: object, what: str) -> dt.date:
    if not isinstance(value, str):
        raise ChronologyError(f"{what} must be a YYYY-MM-DD string")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ChronologyError(f"{what}: invalid date {value!r}") from exc


def _date(d: dt.date) -> str:
    return f"⟨{d.year}, {d.month}, {d.day}⟩"


def day_number(d: dt.date) -> int:
    """``Date.dayNumber`` of ``Basic.lean``: days since 0000-03-01 (proleptic Gregorian).

    Python's ordinal counts 0001-01-01 as 1, which is day 306 of that epoch. Lean
    re-checks every value (``datesConsistent``), so a mistake here fails the build.
    """
    return d.toordinal() + 305


def _records(chronology: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = chronology.get(key, [])
    if not isinstance(value, list):
        raise ChronologyError(f"'{key}' must be a list")
    records: list[Mapping[str, object]] = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ChronologyError(f"{key}[{i}] must be an object")
        records.append(item)
    return records


def _index(records: Sequence[Mapping[str, object]], kind: str) -> dict[str, int]:
    index: dict[str, int] = {}
    for i, rec in enumerate(records):
        rid = _str(rec, "id", f"{kind}[{i}]")
        if rid in index:
            raise ChronologyError(f"duplicate {kind} id {rid!r}")
        index[rid] = i
    return index


def _lookup(index: Mapping[str, int], rid: object, what: str) -> int:
    if not isinstance(rid, str) or rid not in index:
        raise ChronologyError(f"{what}: unknown id {rid!r}")
    return index[rid]


def _list(items: Sequence[str], indent: str) -> str:
    if not items:
        return "[]"
    sep = f",\n{indent}  "
    return f"[\n{indent}  " + sep.join(items) + f"\n{indent}]"


def export_lean(chronology: Mapping[str, object], novel_id: str) -> str:
    """Return the Lean 4 source of the generated story module for ``chronology``.

    Raises ``ChronologyError`` when the chronology is malformed.
    """
    characters = _records(chronology, "characters")
    places = _records(chronology, "places")
    events = _records(chronology, "events")
    char_ix = _index(characters, "characters")
    place_ix = _index(places, "places")
    _index(events, "events")  # rejects duplicate event ids
    # `temporalOrderB` checks adjacent events, so they are listed in discourse order. `seq`
    # is a position in the telling: two events cannot hold the same one.
    seqs = [_nat(ev.get("seq"), f"events[{i}].seq") for i, ev in enumerate(events)]
    if len(set(seqs)) != len(seqs):
        raise ChronologyError("two events share the same seq")
    events = [events[i] for i in sorted(range(len(events)), key=seqs.__getitem__)]

    char_terms: list[str] = []
    char_names: list[str] = []
    for i, ch in enumerate(characters):
        where = f"characters[{i}]"
        birth = ch.get("birth_date")
        birth_term = (
            "none" if birth is None else f"some {_date(_parse_date(birth, where + '.birth_date'))}"
        )
        char_terms.append(f"{{ id := {i}, birth := {birth_term} }}")
        name = ch.get("name", "")
        char_names.append(
            f"({i}, {lean_string(_str(ch, 'id', where))}, "
            f"{lean_string(name if isinstance(name, str) else '')})"
        )

    place_terms: list[str] = []
    place_names: list[str] = []
    for i, pl in enumerate(places):
        name = pl.get("name", "")
        place_terms.append(f"{{ id := {i} }}")
        place_names.append(
            f"({i}, {lean_string(_str(pl, 'id', f'places[{i}]'))}, "
            f"{lean_string(name if isinstance(name, str) else '')})"
        )

    event_terms: list[str] = []
    event_names: list[str] = []
    for i, ev in enumerate(events):
        where = f"events[{i}]"
        kind = ev.get("kind", "normal")
        if not isinstance(kind, str) or kind not in _KINDS:
            raise ChronologyError(f"{where}.kind must be one of {sorted(_KINDS)}")
        participants_raw = ev.get("participants", [])
        if not isinstance(participants_raw, list):
            raise ChronologyError(f"{where}.participants must be a list")
        participants = [str(_lookup(char_ix, p, f"{where}.participants")) for p in participants_raw]
        ages_raw = ev.get("declared_ages") or {}
        if not isinstance(ages_raw, dict):
            raise ChronologyError(f"{where}.declared_ages must be an object")
        ages = [
            f"({_lookup(char_ix, c, f'{where}.declared_ages')}, "
            f"{_nat(age, f'{where}.declared_ages[{c!r}]')})"
            for c, age in ages_raw.items()
        ]
        date = _parse_date(ev.get("story_date"), where + ".story_date")
        event_terms.append(
            "{ "
            f"id := {i}, seq := {_nat(ev.get('seq'), where + '.seq')}, "
            f"date := {_date(date)}, day := {day_number(date)}, "
            f"place := {_lookup(place_ix, ev.get('place_id'), where + '.place_id')}, "
            f"participants := [{', '.join(participants)}], kind := {_KINDS[kind]}, "
            f"declaredAges := [{', '.join(ages)}]"
            " }"
        )
        event_names.append(f"({i}, {lean_string(_str(ev, 'id', where))})")

    theorems = "\n".join(
        f"theorem story_{name} : {check} story = true := by decide +kernel"
        for name, check in INVARIANTS.items()
    )
    simp_set = ", ".join(f"story_{name}" for name in INVARIANTS)

    return f"""/-
Generated by backend/app/formal/lean_export.py (spec 012). Do not edit: regenerated on
every run. The checks read `story` only; the tables above it are for humans.
-/
import Chronology.Basic

namespace Chronology.Generated
open Chronology

def novelId : String := {lean_string(novel_id)}

/-- `(index, id, name)` of every character. -/
def characterTable : List (Prod Nat (Prod String String)) := {_list(char_names, "")}

/-- `(index, id, name)` of every place. -/
def placeTable : List (Prod Nat (Prod String String)) := {_list(place_names, "")}

/-- `(index, id)` of every event. -/
def eventTable : List (Prod Nat String) := {_list(event_names, "")}

def story : Story where
  characters := {_list(char_terms, "  ")}
  places := {_list(place_terms, "  ")}
  events := {_list(event_terms, "  ")}

-- One theorem per invariant, so a failure names the invariant it breaks. `decide +kernel`
-- evaluates the Bool check in the kernel only: plain `decide` first reduces it in the
-- elaborator, which hits `maxRecDepth` beyond about a hundred events. `native_decide` is
-- not used: it would trust the compiler instead of the kernel. A false check is a build
-- error.
{theorems}

theorem story_ok : validStory story = true := by
  simp [validStory, {simp_set}]

theorem story_valid : ValidStory story := validStory_sound story story_ok

end Chronology.Generated
"""
