"""The Brief: the commission for one gift novel, and its validation (spec 006).

`Brief` is the contract shape of `specs/004-exam-refactor-programme/004-contracts.md`; its
JSON Schema is exported to `backend/schemas/brief.v1.json` by `scripts/export_schemas.py`.
`validate_brief` applies the rules of `docs/definitions.md#brief`: required fields,
contradictions (age vs genre/tone, birth date vs age, memory dates, vetoed topics) and schema
errors. A brief is valid only when all three lists are empty.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections.abc import Mapping
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_VERSION: Final[str] = "1"

Gender = Literal["femenino", "masculino", "no_binario"]
Occasion = Literal[
    "cumpleaños", "boda", "aniversario", "jubilación", "nacimiento", "graduación", "otro"
]
Genre = Literal[
    "aventura",
    "fantasía",
    "comedia",
    "romance",
    "misterio",
    "ciencia_ficción",
    "realista",
    "fábula",
]
Tone = Literal["tierno", "divertido", "emotivo", "épico", "nostálgico", "oscuro"]

CHILD_AGE: Final[int] = 12
"""Under this age: no `tone: oscuro`, no `genre: romance` (definitions, Brief rule 2)."""
TEEN_AGE: Final[int] = 16
"""Under this age: no romance with a dark tone (rule 2, "explicit content")."""
AGE_TOLERANCE_YEARS: Final[int] = 1
"""`age` is the age at the time of the gift, which may be just before a birthday."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Recipient(_Strict):
    """The real person the novel is written for (definitions, Recipient)."""

    name: str = Field(min_length=1, description="Canonical name, checked exactly in prose.")
    age: int = Field(ge=0, le=120, description="Age at the time of the gift.")
    gender: Gender | None = None
    birth_date: dt.date | None = None
    relation_to_buyer: str = ""
    traits: list[str] = Field(min_length=1)
    hobbies: list[str] = Field(default_factory=list)
    profession: str | None = None


class Person(_Strict):
    name: str = Field(min_length=1)
    relation: str = ""
    traits: list[str] = Field(default_factory=list)
    birth_date: dt.date | None = None


class Pet(_Strict):
    name: str = Field(min_length=1)
    species: str = ""
    description: str = ""


class BriefPlace(_Strict):
    name: str = Field(min_length=1)
    description: str = ""


class Memory(_Strict):
    title: str = Field(min_length=1)
    description: str = ""
    date: dt.date | None = None
    place: str | None = None
    people: list[str] = Field(default_factory=list)


class Length(_Strict):
    chapters: int = Field(default=10, ge=1, le=30)
    words_min: int = Field(default=1000, ge=100)
    words_max: int = Field(default=1500, ge=100)


class Brief(_Strict):
    """Contract shape (004-contracts, Brief). Enum values are Spanish (spec 004 D9)."""

    recipient: Recipient
    occasion: Occasion = "otro"
    buyer_name: str = ""
    dedication: str = Field(min_length=1)
    people: list[Person] = Field(default_factory=list)
    pets: list[Pet] = Field(default_factory=list)
    places: list[BriefPlace] = Field(default_factory=list)
    memories: list[Memory] = Field(min_length=1)
    genre: Genre
    tone: Tone
    length: Length = Field(default_factory=Length)
    language: Literal["es"] = "es"
    forbidden_terms: list[str] = Field(
        default_factory=list, description="Words or topics the client does NOT want."
    )
    mandatory_elements: list[str] = Field(default_factory=list)
    free_text: str | None = Field(
        default=None, description="Untrusted pasted text; only extracted facts are used."
    )


class BriefReport(BaseModel):
    """What `validate_brief` answers. `valid` iff all three lists are empty."""

    valid: bool
    missing: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


REQUIRED_PATHS: Final[tuple[str, ...]] = (
    "recipient.name",
    "recipient.age",
    "recipient.traits",
    "memories",
    "genre",
    "tone",
    "length",
    "dedication",
)
"""Definitions, Brief rule 1. `length` has a default of 10 chapters, but the interviewer
must still ask for it; a brief that never stated it is reported missing."""


def _lookup(data: Mapping[str, object], path: str) -> object:
    current: object = data
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def missing_fields(data: Mapping[str, object]) -> list[str]:
    """Rule 1: required paths that are absent, null, empty strings or empty lists."""
    return [path for path in REQUIRED_PATHS if _is_empty(_lookup(data, path))]


def normalise(text: str) -> str:
    """Lowercase, accents stripped: the comparison form for vetoed terms."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def slug(text: str) -> str:
    """Stable ASCII slug for fact keys: `Abuela Carmen` -> `abuela-carmen`."""
    return re.sub(r"[^a-z0-9]+", "-", normalise(text)).strip("-") or "x"


def _years_between(born: dt.date, on: dt.date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def contradictions(brief: Brief, *, today: dt.date | None = None) -> list[str]:
    """Rules 2 and 3 plus the date checks. Each message names both fields involved."""
    found: list[str] = []
    reference = today or dt.date.today()
    recipient = brief.recipient
    age = recipient.age
    if age < CHILD_AGE and brief.tone == "oscuro":
        found.append(
            f"recipient.age={age} vs tone=oscuro: un tono oscuro no es apto para menos de "
            f"{CHILD_AGE} años"
        )
    if age < CHILD_AGE and brief.genre == "romance":
        found.append(
            f"recipient.age={age} vs genre=romance: el romance no es apto para menos de "
            f"{CHILD_AGE} años"
        )
    elif age < TEEN_AGE and brief.genre == "romance" and brief.tone == "oscuro":
        found.append(
            f"recipient.age={age} vs genre=romance/tone=oscuro: no apto para menos de "
            f"{TEEN_AGE} años"
        )
    if recipient.birth_date is not None:
        computed = _years_between(recipient.birth_date, reference)
        if abs(computed - age) > AGE_TOLERANCE_YEARS:
            found.append(
                f"recipient.birth_date={recipient.birth_date.isoformat()} vs recipient.age={age}: "
                f"la fecha de nacimiento da {computed} años"
            )
        for index, memory in enumerate(brief.memories):
            if memory.date is not None and memory.date < recipient.birth_date:
                found.append(
                    f"memories[{index}].date={memory.date.isoformat()} vs recipient.birth_date="
                    f"{recipient.birth_date.isoformat()}: el recuerdo es anterior al nacimiento"
                )
    for index, memory in enumerate(brief.memories):
        if memory.date is not None and memory.date > reference:
            found.append(
                f"memories[{index}].date={memory.date.isoformat()}: el recuerdo está en el futuro"
            )
    if brief.length.words_min > brief.length.words_max:
        found.append(
            f"length.words_min={brief.length.words_min} vs length.words_max="
            f"{brief.length.words_max}: el mínimo supera al máximo"
        )
    vetoed = [(term, normalise(term)) for term in brief.forbidden_terms if term.strip()]
    mandatory_texts = [
        (f"mandatory_elements[{i}]", text) for i, text in enumerate(brief.mandatory_elements)
    ] + [(f"memories[{i}]", f"{m.title} {m.description}") for i, m in enumerate(brief.memories)]
    for where, text in mandatory_texts:
        folded = normalise(text)
        for term, folded_term in vetoed:
            if folded_term in folded:
                found.append(f"{where} vs forbidden_terms: menciona el tema vetado {term!r}")
    return found


def _error_path(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc)


def validate_brief(data: Mapping[str, object], *, today: dt.date | None = None) -> BriefReport:
    """Validate a raw brief (e.g. parsed JSON). Never raises on bad input."""
    missing = missing_fields(data)
    try:
        brief = Brief.model_validate(dict(data))
    except ValidationError as error:
        errors = [
            f"{_error_path(item['loc'])}: {item['msg']}"
            for item in error.errors()
            if _error_path(item["loc"]) not in missing
        ]
        return BriefReport(valid=False, missing=missing, errors=errors)
    found = contradictions(brief, today=today)
    return BriefReport(valid=not missing and not found, missing=missing, contradictions=found)


def brief_json_schema() -> dict[str, object]:
    """The JSON Schema exported to `backend/schemas/brief.v1.json`."""
    return Brief.model_json_schema()


__all__ = [
    "REQUIRED_PATHS",
    "SCHEMA_VERSION",
    "Brief",
    "BriefPlace",
    "BriefReport",
    "Gender",
    "Genre",
    "Length",
    "Memory",
    "Occasion",
    "Person",
    "Pet",
    "Recipient",
    "Tone",
    "brief_json_schema",
    "contradictions",
    "missing_fields",
    "normalise",
    "slug",
    "validate_brief",
]
