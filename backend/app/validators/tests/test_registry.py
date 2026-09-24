"""Spec 005 — K3 registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.bible import BibleRepository
from app.commons.observability import NoopObserver
from app.validators import (
    ValidationContext,
    ValidationPoint,
    ValidationResult,
    run_point,
)


@dataclass(frozen=True)
class _WordCount:
    name: str = "chapter_length"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        words = len(ctx.text.split())
        return ValidationResult(
            name=self.name,
            passed=words >= 3,
            score=1.0,
            evidence=[f"{words} words"],
            explanation="length in range",
        )


@dataclass(frozen=True)
class _Crashes:
    name: str = "crashes"
    point: ValidationPoint = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        raise RuntimeError("boom")


# spec 005 / AC 4 — V06
def test_run_point_persists_and_scores(tmp_path: Path) -> None:
    repo = BibleRepository.open(tmp_path / "h.sqlite")
    novel = repo.create_novel()
    observer = NoopObserver()
    with observer.trace("generation", session_id=novel.id) as trace:
        ctx = ValidationContext(
            novel_id=novel.id,
            version=1,
            chapter=3,
            scene=None,
            text="uno dos tres cuatro",
            repo=repo,
            observer=observer,
        )
        results = run_point(
            ValidationPoint.CHAPTER_CLOSE, ctx, validators=[_WordCount(), _Crashes()]
        )

    assert [(r.name, r.passed) for r in results] == [("chapter_length", True), ("crashes", False)]
    stored = repo.list_validator_results(novel.id, chapter=3)
    assert [(s.name, s.passed, s.point, s.trace_id) for s in stored] == [
        ("chapter_length", True, "chapter_close", trace.id),
        ("crashes", False, "chapter_close", trace.id),
    ]
    assert stored[0].evidence == ("4 words",)
    assert "RuntimeError: boom" in stored[1].evidence[0]
    assert [(s.name, s.value, s.trace_id) for s in observer.scores] == [
        ("validator:chapter_length", 1.0, trace.id),
        ("validator:crashes", 0.0, trace.id),
    ]
