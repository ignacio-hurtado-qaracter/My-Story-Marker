"""The judge rubric (spec 011): one definition for the LLM judge and the human reviewer.

Four criteria scored 1-5 with anchors, in Spanish because the novel and the human review
are in Spanish. The novel judge adds `final_satisfactorio`. The pass rule is decision D11
of spec 004: personalisation and narrative quality weigh the same, so every criterion must
reach `MIN_SCORE` **and** the mean must reach `MIN_MEAN` **and** no blocking defect (the
ones `docs/verification.md` names) may be present.

`render_markdown()` produces `evals/human-review/rubrica.md` and is appended to the judge
prompts; `render_review_template()` produces `evals/human-review/review-template.yaml`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

MIN_SCORE: Final[int] = 3
MIN_MEAN: Final[float] = 3.5
SCALE: Final[tuple[int, int]] = (1, 5)


@dataclass(frozen=True, slots=True)
class Criterion:
    key: str
    title: str
    question: str
    anchors: Mapping[int, str]


CONTINUIDAD: Final = Criterion(
    key="continuidad",
    title="Continuidad",
    question=(
        "¿Es coherente con los capítulos anteriores y sus resúmenes? ¿Los personajes "
        "mantienen nombre, carácter y relaciones? ¿Hay contradicciones o saltos temporales "
        "sin sentido?"
    ),
    anchors={
        1: "Contradice hechos anteriores o cambia a un personaje sin explicación.",
        2: "Varios descuidos de continuidad o un salto temporal que desorienta.",
        3: "Coherente en lo esencial; algún detalle menor dudoso.",
        4: "Coherente; los personajes actúan como se espera de ellos.",
        5: "Continuidad impecable; retoma y hace avanzar lo anterior con naturalidad.",
    },
)
TONO: Final = Criterion(
    key="tono",
    title="Tono",
    question=(
        "¿Mantiene el tono y el género que pidió el brief y es adecuado a la edad del destinatario?"
    ),
    anchors={
        1: "Tono o género opuestos a lo pedido, o inadecuado para la edad.",
        2: "El tono pedido aparece a ratos; cambios de registro chocantes.",
        3: "Tono correcto en general, con altibajos.",
        4: "Tono y género sostenidos y adecuados a la edad.",
        5: "El tono está logrado y da carácter propio al capítulo.",
    },
)
CALIDAD_NARRATIVA: Final = Criterion(
    key="calidad_narrativa",
    title="Calidad narrativa",
    question=(
        "¿Hay arco (algo cambia), buen ritmo respecto a los otros capítulos, prosa no "
        "mecánica ni repetitiva, diálogos creíbles y un cierre que no sea abrupto?"
    ),
    anchors={
        1: "Prosa mecánica o repetitiva, sin arco, o final abrupto.",
        2: "Se lee con esfuerzo: ritmo irregular, repeticiones, diálogos rígidos.",
        3: "Correcta y legible, aunque plana en algunos tramos.",
        4: "Agradable de leer; arco claro, ritmo y diálogos bien llevados.",
        5: "Se lee de un tirón; escenas vivas y cierre que invita a seguir.",
    },
)
PERSONALIZACION_NATURAL: Final = Criterion(
    key="personalizacion_natural",
    title="Personalización natural",
    question=(
        "¿Los datos del brief (nombres, aficiones, recuerdos, mascotas, lugares) están "
        "integrados en la historia y no enumerados o forzados? ¿Se reconocería el "
        "destinatario?"
    ),
    anchors={
        1: "Los datos se enumeran o se meten a calzador; o faltan por completo.",
        2: "Datos presentes pero forzados, sin peso en la trama.",
        3: "Integración aceptable; algún dato se nota añadido.",
        4: "Los datos forman parte natural de las escenas.",
        5: "La historia gira en torno a ellos; el destinatario se reconocería al instante.",
    },
)
FINAL_SATISFACTORIO: Final = Criterion(
    key="final_satisfactorio",
    title="Final satisfactorio",
    question="¿El final cierra el arco de la novela sin ser abrupto ni dejar hilos sueltos?",
    anchors={
        1: "Final abrupto o ausente.",
        2: "Cierra, pero precipitado o con hilos principales sueltos.",
        3: "Final correcto aunque previsible.",
        4: "Cierre satisfactorio del arco principal.",
        5: "Final redondo y emotivo que resignifica la historia.",
    },
)

CHAPTER_CRITERIA: Final[tuple[Criterion, ...]] = (
    CONTINUIDAD,
    TONO,
    CALIDAD_NARRATIVA,
    PERSONALIZACION_NATURAL,
)
NOVEL_CRITERIA: Final[tuple[Criterion, ...]] = (*CHAPTER_CRITERIA, FINAL_SATISFACTORIO)

BLOCKING_DEFECTS: Final[tuple[str, ...]] = (
    "personajes inconsistentes",
    "saltos temporales sin sentido",
    "capítulos que se contradicen",
    "prosa mecánica o repetitiva",
    "final abrupto",
    "personalización forzada",
)
"""`docs/verification.md`: these fail a chapter whatever its score."""


@dataclass(frozen=True, slots=True)
class Verdict:
    passed: bool
    mean: float
    failing: tuple[str, ...]
    reasons: tuple[str, ...]


def evaluate(scores: Mapping[str, int], blocking: Sequence[str] = ()) -> Verdict:
    """The D11 pass rule over `scores` (criterion key -> 1..5)."""
    if not scores:
        return Verdict(passed=False, mean=0.0, failing=(), reasons=("sin puntuaciones",))
    mean = sum(scores.values()) / len(scores)
    failing = tuple(key for key, value in scores.items() if value < MIN_SCORE)
    reasons: list[str] = [f"{key} < {MIN_SCORE}" for key in failing]
    if mean < MIN_MEAN:
        reasons.append(f"media {mean:.2f} < {MIN_MEAN}")
    reasons.extend(f"bloqueante: {issue}" for issue in blocking if issue.strip())
    return Verdict(passed=not reasons, mean=mean, failing=failing, reasons=tuple(reasons))


def render_markdown(*, novel: bool = True) -> str:
    """The rubric as Spanish Markdown (for the human and for the judge prompt)."""
    criteria = NOVEL_CRITERIA if novel else CHAPTER_CRITERIA
    lines = [
        "# Rúbrica de evaluación",
        "",
        (
            f"Escala {SCALE[0]}-{SCALE[1]} por criterio, con una justificación de 1 a 3 "
            "frases que cite el texto."
        ),
        "",
    ]
    for criterion in criteria:
        lines += [f"## {criterion.title} (`{criterion.key}`)", "", criterion.question, ""]
        lines += [f"- **{score}** — {text}" for score, text in sorted(criterion.anchors.items())]
        lines.append("")
    lines += [
        "## Regla de aprobado",
        "",
        (
            f"Aprueba si **todos** los criterios tienen al menos {MIN_SCORE}, la **media** es "
            f"al menos {MIN_MEAN} y no hay ningún defecto bloqueante. Personalización y "
            "calidad narrativa pesan lo mismo: un capítulo que incluye los datos del brief "
            "pero se lee mal no aprueba, y al revés tampoco."
        ),
        "",
        "Defectos bloqueantes (suspenden sea cual sea la nota):",
        "",
    ]
    lines += [f"- {defect}" for defect in BLOCKING_DEFECTS]
    lines.append("")
    return "\n".join(lines)


def _blank_scores(criteria: Sequence[Criterion], indent: str) -> list[str]:
    lines: list[str] = []
    for criterion in criteria:
        lines += [
            f"{indent}{criterion.key}:",
            f"{indent}  score:          # 1-5",
            f'{indent}  justification: ""',
        ]
    return lines


def render_review_template(chapters: int = 10) -> str:
    """A blank human-review YAML for a novel of `chapters` chapters."""
    lines = [
        "# Revisión humana (spec 011). Rúbrica: evals/human-review/rubrica.md",
        "# Rellena score (1-5) y justification (1-3 frases citando el texto) de cada criterio.",
        'novel_id: ""',
        "version: 1",
        'reviewer: ""',
        'date: ""          # AAAA-MM-DD',
        "chapters:",
    ]
    for number in range(1, chapters + 1):
        lines.append(f"  - chapter: {number}")
        lines += _blank_scores(CHAPTER_CRITERIA, "    ")
        lines.append("    blocking_issues: []")
    lines.append("novel:")
    lines += _blank_scores(NOVEL_CRITERIA, "  ")
    lines += ["  contradicciones: []", '  comment: ""', ""]
    return "\n".join(lines)


__all__ = [
    "BLOCKING_DEFECTS",
    "CALIDAD_NARRATIVA",
    "CHAPTER_CRITERIA",
    "CONTINUIDAD",
    "FINAL_SATISFACTORIO",
    "MIN_MEAN",
    "MIN_SCORE",
    "NOVEL_CRITERIA",
    "PERSONALIZACION_NATURAL",
    "TONO",
    "Criterion",
    "Verdict",
    "evaluate",
    "render_markdown",
    "render_review_template",
]
