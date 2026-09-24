"""`exact_names` — invariant 12, V02 (spec 008 / AC 2).

The recipient and every character (people and pets) must be written exactly as stored in
the story bible. Canonical names come from the bible's characters, ``novel.recipient_name``,
``*.name`` facts and, when given, the brief in ``ctx.extra["brief"]``; each name is split
into tokens ("Lucía Pérez" → "Lucía", "Pérez"; particles such as "de" are ignored).

Only **capitalised** tokens of the chapter are compared, so common lowercase words never
match. A capitalised token that is not itself canonical is a near-miss variant of a
canonical token when either

- it is equal to it after casefolding and stripping accents ("Lucia" / "Lucía"), or
- both have at least four letters and are one edit apart ("Tobby" / "Toby").

Never variants: tokens in the stoplist (common Spanish words that start sentences, e.g.
"Nada" against "Nala"), tokens whose lowercase form also appears in the chapter (so the
word is ordinary prose), and ALL-CAPS renderings of a canonical token.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from app.bible import BibleError
from app.validators.programmatic.text import (
    STOPWORDS,
    as_mapping,
    edit_distance,
    normalise,
    words,
)
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

_PARTICLES: Final = frozenset({"de", "del", "la", "las", "los", "el", "y", "van", "von", "da"})

#: Capitalised common words that are one edit from frequent pet or person names.
_NAME_STOP_TEXT: Final = """
    nada cada casa cara para pero toda todo mama papa hola vale mira vamos dijo creo pues
    sola solo ella ello esto esta este eres sera seria dios gracias bueno buena claro vaya
    vino vida hora dias noche tarde manana luego cuando donde como mucho poco nunca quizas
    alli aqui ahora antes hasta desde entre sobre tras bajo tanto tambien porque aunque
    """
NAME_STOPLIST: Final[frozenset[str]] = frozenset(_NAME_STOP_TEXT.split())


def _brief_names(brief: Mapping[str, object] | None) -> list[str]:
    if brief is None:
        return []
    names: list[str] = []
    recipient = as_mapping(brief.get("recipient"))
    if recipient is not None and isinstance(recipient.get("name"), str):
        names.append(str(recipient["name"]))
    for group in ("people", "pets"):
        entries = brief.get(group)
        if isinstance(entries, Sequence) and not isinstance(entries, str):
            for entry in entries:
                item = as_mapping(entry)
                if item is not None and isinstance(item.get("name"), str):
                    names.append(str(item["name"]))
    return names


def canonical_names(ctx: ValidationContext) -> list[str]:
    """(exact_name) Every canonical full name the chapter must respect, de-duplicated."""
    names: list[str] = [c.name for c in ctx.repo.list_characters(ctx.novel_id)]
    try:
        recipient = ctx.repo.get_novel(ctx.novel_id).recipient_name
    except BibleError:
        recipient = None
    if recipient:
        names.append(recipient)
    names += [f.value for f in ctx.repo.list_facts(ctx.novel_id) if f.key.endswith(".name")]
    names += _brief_names(as_mapping(ctx.extra.get("brief")))
    seen: dict[str, None] = {}
    for name in names:
        if name.strip():
            seen.setdefault(name.strip(), None)
    return list(seen)


def _name_tokens(names: Iterable[str]) -> dict[str, str]:
    """Canonical token → the full name it belongs to."""
    tokens: dict[str, str] = {}
    for name in names:
        for token in words(name):
            if normalise(token) not in _PARTICLES and len(token) >= 2:
                tokens.setdefault(token, name)
    return tokens


def find_variants(text: str, names: Iterable[str]) -> Counter[tuple[str, str]]:
    """(name_spelling) Counter of ``(variant as written, canonical token)`` in `text`."""
    canon = _name_tokens(names)
    canon_norm = {token: normalise(token) for token in canon}
    tokens = words(text)
    lowercase = {normalise(t) for t in tokens if t[:1].islower()}
    found: Counter[tuple[str, str]] = Counter()
    for token in tokens:
        if not token[:1].isupper() or token in canon:
            continue
        norm = normalise(token)
        if norm in STOPWORDS or norm in NAME_STOPLIST or norm in lowercase:
            continue
        for canonical, canonical_norm in canon_norm.items():
            if token.isupper() and len(token) > 1 and token == canonical.upper():
                break
            same = norm == canonical_norm
            near = (
                len(norm) >= 4
                and len(canonical_norm) >= 4
                and edit_distance(norm, canonical_norm) == 1
            )
            if same or near:
                found[(token, canonical)] += 1
                break
    return found


@dataclass(frozen=True, slots=True)
class ExactNames:
    name: str = "exact_names"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        names = canonical_names(ctx)
        if not names:
            return ValidationResult(
                self.name,
                True,
                1.0,
                [],
                "No hay nombres canónicos en la biblia; nada que comprobar.",
            )
        variants = find_variants(ctx.text, names)
        if not variants:
            return ValidationResult(
                self.name,
                True,
                1.0,
                [f"canónicos: {', '.join(names)}"],
                "Todos los nombres aparecen exactamente como en la biblia.",
            )
        evidence = [
            f"'{variant}' → '{canonical}' (x{count})"
            for (variant, canonical), count in variants.most_common()
        ]
        fixes = "; ".join(
            f"escribe «{canonical}» en lugar de «{variant}»" for variant, canonical in variants
        )
        total = sum(variants.values())
        return ValidationResult(
            self.name,
            False,
            round(max(0.0, 1.0 - 0.25 * total), 3),
            evidence,
            f"Hay {total} nombre(s) mal escritos respecto a la biblia: {fixes}. Los nombres "
            "del destinatario y de los personajes deben coincidir letra a letra, tildes incluidas.",
        )


__all__ = ["NAME_STOPLIST", "ExactNames", "canonical_names", "find_variants"]
