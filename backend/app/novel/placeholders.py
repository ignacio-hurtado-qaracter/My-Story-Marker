"""`no_placeholders` — the pipeline's own guard against anonymised prose (spec 007).

The model may replace personal names with bracketed placeholders ("[NOMBRE_ANONIMIZADO]")
under a privacy policy it applies to the session. In a commissioned gift novel every name
is a character that must appear verbatim, so a scene or chapter carrying a placeholder is
rejected with feedback asking for the real names. Registered at `scene_accept` and
`chapter_close` by `app.novel.setup.register_all`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.validators import ValidationContext, ValidationPoint, ValidationResult

PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\[[A-ZÁÉÍÓÚÑÜ_ ]{4,}\]")


@dataclass(frozen=True, slots=True)
class NoPlaceholders:
    point: ValidationPoint
    name: str = "no_placeholders"

    def run(self, ctx: ValidationContext) -> ValidationResult:
        found = sorted(set(PLACEHOLDER.findall(ctx.text)))
        if not found:
            return ValidationResult(self.name, True, 1.0, [], "Sin marcadores anonimizados.")
        return ValidationResult(
            self.name,
            False,
            0.0,
            [f"marcador: {m}" for m in found[:10]],
            "El texto contiene marcadores anonimizados en lugar de nombres. Son personajes "
            "de una novela encargada: escribe los nombres reales exactamente como en "
            "bible/exact-names.txt, nunca entre corchetes.",
        )


def register_validators() -> None:
    from app.validators import register

    register(NoPlaceholders(ValidationPoint.SCENE_ACCEPT))
    register(NoPlaceholders(ValidationPoint.CHAPTER_CLOSE))


__all__ = ["PLACEHOLDER", "NoPlaceholders", "register_validators"]
