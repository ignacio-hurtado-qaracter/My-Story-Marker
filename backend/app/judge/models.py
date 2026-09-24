"""Output schemas of the judge role (spec 011). Field names match `rubric.py` keys."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=1, le=5, description="Puntuación 1-5 según las anclas de la rúbrica.")
    justification: str = Field(
        min_length=1,
        description="En español, 1-3 frases, citando o refiriendo el texto evaluado.",
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
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Solo defectos bloqueantes graves de la rúbrica; vacío si no hay.",
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
    contradicciones: list[str] = Field(
        default_factory=list,
        description="Contradicciones entre capítulos, cada una nombrando los capítulos.",
    )
    capitulos_a_reparar: list[int] = Field(
        default_factory=list, description="Números de los capítulos que conviene reescribir."
    )

    def scores(self) -> dict[str, CriterionScore]:
        return {**super().scores(), "final_satisfactorio": self.final_satisfactorio}


__all__ = ["ChapterJudgement", "CriterionScore", "NovelJudgement"]
