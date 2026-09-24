"""Output schemas of the judge role (spec 011). Field names match `rubric.py` keys."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["alta", "media", "baja"]


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5, description="Puntuación 1-5 según las anclas de la rúbrica.")
    justification: str = Field(
        min_length=1,
        description="En español, 1-3 frases, citando o refiriendo el texto evaluado.",
    )


class Issue(BaseModel):
    """One defect the judge found (tuning 1). Only a concrete `alta` issue that names its
    chapters blocks; the rest is feedback (`rubric.blocking_issues`)."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(
        min_length=1, description="En español: qué falla, citando el pasaje o el dato concreto."
    )
    capitulos: list[int] = Field(
        default_factory=list, description="Números de los capítulos implicados."
    )
    severidad: Severity = Field(
        description=(
            "alta: un lector lo notaría y rompe la historia (contradicción comprobada, salto "
            "imposible); media: descuido visible; baja: detalle o sospecha."
        )
    )


class ChapterJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continuidad: CriterionScore
    tono: CriterionScore
    calidad_narrativa: CriterionScore
    personalizacion_natural: CriterionScore
    comentario_general: str = Field(
        description="Feedback accionable para el editor: qué cambiar y dónde, en español."
    )
    blocking_issues: list[Issue] = Field(
        default_factory=list,
        description="Defectos de la lista de la rúbrica, cada uno con capítulos y severidad.",
    )

    def scores(self) -> dict[str, CriterionScore]:
        return {
            "continuidad": self.continuidad,
            "tono": self.tono,
            "calidad_narrativa": self.calidad_narrativa,
            "personalizacion_natural": self.personalizacion_natural,
        }


class NovelJudgement(ChapterJudgement):
    final_satisfactorio: CriterionScore
    contradicciones: list[Issue] = Field(
        default_factory=list,
        description="Contradicciones comprobadas entre capítulos, con capítulos y severidad.",
    )
    capitulos_a_reparar: list[int] = Field(
        default_factory=list, description="Números de los capítulos que conviene reescribir."
    )

    def scores(self) -> dict[str, CriterionScore]:
        return {**super().scores(), "final_satisfactorio": self.final_satisfactorio}


__all__ = ["ChapterJudgement", "CriterionScore", "Issue", "NovelJudgement", "Severity"]
