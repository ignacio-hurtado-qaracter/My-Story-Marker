"""`chapter_length` — invariant 11, V01 (spec 008 / AC 1).

Words of the chapter (``BibleRepository.word_count``: whitespace-separated tokens) within
``[words_min, words_max]`` of the brief's ``length`` (``ctx.extra["brief"]``), default
1000-1500. Score 1.0 inside; outside it falls linearly with the relative distance to the
nearest bound and reaches 0 at a distance equal to the bound itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.bible.repository import word_count
from app.validators.programmatic.text import as_mapping
from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

DEFAULT_MIN: Final = 1000
DEFAULT_MAX: Final = 1500


def length_limits(brief: object) -> tuple[int, int]:
    """(chapter_word_range) min and max words from the brief's `length`, or the defaults."""
    brief_map = as_mapping(brief)
    length = as_mapping(brief_map.get("length")) if brief_map is not None else None
    min_words, max_words = DEFAULT_MIN, DEFAULT_MAX
    if length is not None:
        low, high = length.get("words_min"), length.get("words_max")
        if isinstance(low, int) and low > 0:
            min_words = low
        if isinstance(high, int) and high >= min_words:
            max_words = high
    return min_words, max(min_words, max_words)


@dataclass(frozen=True, slots=True)
class ChapterLength:
    name: str = "chapter_length"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        min_words, max_words = length_limits(ctx.extra.get("brief"))
        words = word_count(ctx.text)
        evidence = [f"{words} palabras; rango {min_words}-{max_words}"]
        if min_words <= words <= max_words:
            return ValidationResult(
                self.name,
                True,
                1.0,
                evidence,
                f"Longitud correcta: {words} palabras (rango {min_words}-{max_words}).",
            )
        if words < min_words:
            gap, bound = min_words - words, min_words
            advice = (
                f"El capítulo es corto: tiene {words} palabras y necesita al menos "
                f"{min_words}. Añade unas {gap} palabras desarrollando escenas existentes "
                "(no con relleno)."
            )
        else:
            gap, bound = words - max_words, max_words
            advice = (
                f"El capítulo es largo: tiene {words} palabras y el máximo es {max_words}. "
                f"Recorta unas {gap} palabras sin perder los hechos del brief."
            )
        score = max(0.0, 1.0 - gap / bound)
        return ValidationResult(self.name, False, round(score, 3), evidence, advice)


__all__ = ["DEFAULT_MAX", "DEFAULT_MIN", "ChapterLength", "length_limits"]
