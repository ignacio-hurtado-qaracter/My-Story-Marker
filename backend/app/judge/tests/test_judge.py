"""Spec 011 — the D11 pass rule, and the human-vs-judge comparison end to end."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.bible import BibleRepository
from app.commons.llm import FakeModelClient, Reply
from app.commons.observability import NoopObserver
from app.judge import JudgeChapter
from app.judge.compare import compare
from app.judge.models import ChapterJudgement, CriterionScore
from app.judge.rubric import evaluate, render_review_template
from app.validators import ValidationContext, ValidationPoint, run_point


# spec 011 / AC 1
def test_pass_rule() -> None:
    good = {"continuidad": 4, "tono": 4, "calidad_narrativa": 3, "personalizacion_natural": 4}
    assert evaluate(good).passed
    # one criterion below 3 fails even with a high mean (D11: quality and personalisation)
    assert not evaluate({**good, "personalizacion_natural": 2, "tono": 5}).passed
    # every criterion >= 3 but the mean below 3.5 fails
    assert not evaluate(dict.fromkeys(good, 3)).passed
    # a blocking defect fails whatever the scores
    assert not evaluate(dict.fromkeys(good, 5), ["final abrupto"]).passed


def _judgement(scores: dict[str, int]) -> ChapterJudgement:
    return ChapterJudgement.model_validate(
        {
            **{k: CriterionScore(score=v, justification=f"cita {k}") for k, v in scores.items()},
            "comentario_general": "Reforzar el diálogo de la escena 2.",
            "blocking_issues": [],
        }
    )


# spec 011 / AC 3
def test_compare_tiny_db(tmp_path: Path) -> None:
    repo = BibleRepository.open(tmp_path / "harness.sqlite")
    novel = repo.create_novel(novel_id="nov-test", title="Prueba", recipient_name="Ana")
    version = repo.create_version(novel.id).version
    repo.save_chapter_version(novel.id, version, 1, text="Ana abrió la puerta.", summary="Inicio")
    llm = {"continuidad": 4, "tono": 4, "calidad_narrativa": 2, "personalizacion_natural": 5}
    observer = NoopObserver()
    ctx = ValidationContext(
        novel_id=novel.id,
        version=version,
        chapter=1,
        scene=None,
        text="Ana abrió la puerta.",
        repo=repo,
        observer=observer,
        extra={"client": FakeModelClient([Reply.of(_judgement(llm))]), "brief": {"tone": "tierno"}},
    )
    [result] = run_point(ValidationPoint.CHAPTER_CLOSE, ctx, validators=[JudgeChapter()])
    assert not result.passed  # calidad_narrativa 2 < 3
    assert "calidad_narrativa" in result.explanation

    review = yaml.safe_load(render_review_template(chapters=1))
    review["novel_id"], review["version"] = novel.id, version
    human = {"continuidad": 5, "tono": 4, "calidad_narrativa": 3, "personalizacion_natural": 3}
    for key, value in human.items():
        review["chapters"][0][key] = {"score": value, "justification": "ok"}
    review_path = tmp_path / "review.yaml"
    review_path.write_text(yaml.safe_dump(review, allow_unicode=True), encoding="utf-8")

    target, text = compare(review_path, repo, out_dir=tmp_path)
    assert target == tmp_path / "comparison-nov-test.md"
    assert "| cap. 1 | continuidad | 5 | 4 | +1 |" in text
    assert "| cap. 1 | personalizacion_natural | 3 | 5 | -2 |" in text
    assert "| **total** | **1.00** | 4 |" in text  # (1 + 0 + 1 + 2) / 4
    assert "| cap. 1 | aprueba | suspende | **no** |" in text
    repo.close()
