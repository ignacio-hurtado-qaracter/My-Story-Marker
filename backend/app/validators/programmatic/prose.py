"""`prose_repetition` — optional prose linter X02 (spec 008 / AC 7).

Three signals over the chapter:

- **word repetition**: a paragraph (blank-line separated) that repeats the same content
  word (≥ 6 letters, not a stopword) four or more times;
- **phrase repetition**: a 4-gram with at least two content words (≥ 4 letters) that
  occurs three or more times across the chapter;
- **AI clichés**: stock Spanish phrases typical of machine prose (``CLICHES``), matched
  after normalisation.

The linter is **soft** to avoid rewrite loops: it passes with a lowered score
(1 - 0.1 per hit) and fails only when the chapter is severe — three or more clichés, or
three or more repetition hits.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Final

from app.validators.programmatic.text import STOPWORDS, normalise, phrase_in
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

CLICHES: Final[tuple[str, ...]] = (
    "un torbellino de emociones",
    "en lo más profundo de su ser",
    "no pudo evitar sonreír",
    "una sensación de calidez",
    "el tiempo pareció detenerse",
    "una mezcla de emociones",
    "su corazón latía con fuerza",
    "un nudo en la garganta",
    "una sonrisa se dibujó en su rostro",
    "como si el mundo entero",
    "sin previo aviso",
    "el peso del mundo",
    "un escalofrío recorrió su espalda",
    "sus ojos brillaban de emoción",
    "una lágrima rodó por su mejilla",
    "respiró hondo",
    "algo había cambiado para siempre",
)
SEVERE: Final = 3
_PARAGRAPH: Final = re.compile(r"\n\s*\n")


def repetition_hits(text: str) -> list[str]:
    """(repetition) Human-readable hits for repeated words and 4-gram phrases."""
    hits: list[str] = []
    for number, paragraph in enumerate(_PARAGRAPH.split(text), start=1):
        counts = Counter(
            w for w in normalise(paragraph).split() if len(w) >= 6 and w not in STOPWORDS
        )
        hits += [
            f"párrafo {number}: «{word}» x{count}" for word, count in counts.items() if count >= 4
        ]
    tokens = normalise(text).split()
    grams = Counter(tuple(tokens[i : i + 4]) for i in range(len(tokens) - 3))
    for gram, count in grams.items():
        content = sum(1 for w in gram if len(w) >= 4 and w not in STOPWORDS)
        if count >= 3 and content >= 2:
            hits.append(f"frase «{' '.join(gram)}» x{count}")
    return hits


def cliches_in(text: str) -> list[str]:
    """(cliche) The clichés of ``CLICHES`` present in `text`."""
    norm = normalise(text)
    return [c for c in CLICHES if phrase_in(c, norm)]


@dataclass(frozen=True, slots=True)
class ProseRepetition:
    name: str = "prose_repetition"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        hits = repetition_hits(ctx.text)
        cliches = cliches_in(ctx.text)
        evidence = hits + [f"cliché: «{c}»" for c in cliches]
        score = round(max(0.0, 1.0 - 0.1 * len(evidence)), 3)
        if not evidence:
            return ValidationResult(self.name, True, 1.0, [], "Sin repeticiones ni clichés.")
        severe = len(cliches) >= SEVERE or len(hits) >= SEVERE
        advice = []
        if hits:
            advice.append(f"varía {len(hits)} repetición(es) de palabras o frases")
        if cliches:
            advice.append("sustituye los clichés (" + "; ".join(cliches) + ") por imágenes propias")
        explanation = "Pule la prosa: " + " y ".join(advice) + "."
        if not severe:
            explanation += " (aviso leve, no bloquea)"
        return ValidationResult(self.name, not severe, score, evidence, explanation)


__all__ = ["CLICHES", "SEVERE", "ProseRepetition", "cliches_in", "repetition_hits"]
