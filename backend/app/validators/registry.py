"""Contract K3: the validator registry and `run_point` (spec 005).

`register` adds a validator to its point (a second one with the same name at the same point
replaces the first, so re-importing a module is harmless). `run_point` runs every validator
of a point in registration order and, for each result:

1. persists it as a `validator_result` row through the repository (K1);
2. sends it as a Langfuse score named `validator:<name>` on the current trace (K2).

A validator that raises becomes a **failed** result carrying the exception type as its
evidence: a crashing check never counts as a pass, and never stops the others.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from app.validators.protocol import (
    ValidationContext,
    ValidationPoint,
    ValidationResult,
    Validator,
)

SCORE_PREFIX: Final[str] = "validator:"
_COMMENT_LIMIT: Final[int] = 1000

_REGISTRY: dict[ValidationPoint, list[Validator]] = {point: [] for point in ValidationPoint}


def register[V: Validator](validator: V) -> V:
    """Add `validator` to its point; returns it so it can be used as a decorator result."""
    bucket = _REGISTRY[validator.point]
    bucket[:] = [v for v in bucket if v.name != validator.name]
    bucket.append(validator)
    return validator


def unregister(name: str, point: ValidationPoint | None = None) -> None:
    for key in [point] if point is not None else list(ValidationPoint):
        _REGISTRY[key][:] = [v for v in _REGISTRY[key] if v.name != name]


def clear_registry() -> None:
    """For tests."""
    for bucket in _REGISTRY.values():
        bucket.clear()


def validators_for(point: ValidationPoint) -> list[Validator]:
    return list(_REGISTRY[point])


def _run_one(validator: Validator, ctx: ValidationContext) -> ValidationResult:
    with ctx.observer.span(
        f"{SCORE_PREFIX}{validator.name}",
        metadata={"point": validator.point.value, "chapter": ctx.chapter, "scene": ctx.scene},
    ) as span:
        try:
            result = validator.run(ctx)
        except Exception as error:  # a crashing check is a failed check, never a pass
            result = ValidationResult(
                name=validator.name,
                passed=False,
                score=0.0,
                evidence=[f"{type(error).__name__}: {error}"[:500]],
                explanation="validator raised an exception",
            )
        span.update(output={"passed": result.passed, "score": result.score})
    return result


def run_point(
    point: ValidationPoint,
    ctx: ValidationContext,
    *,
    validators: Sequence[Validator] | None = None,
) -> list[ValidationResult]:
    """Run every validator registered for `point` (or the given ones), persist and score
    each result, and return them in order."""
    chosen = list(validators) if validators is not None else validators_for(point)
    results: list[ValidationResult] = []
    for validator in chosen:
        result = _run_one(validator, ctx)
        trace_id = ctx.trace_id or ctx.observer.current_trace_id()
        ctx.repo.save_validator_result(
            novel_id=ctx.novel_id,
            name=validator.name,
            point=point.value,
            passed=result.passed,
            score=result.score,
            evidence=result.evidence,
            explanation=result.explanation,
            version=ctx.version,
            chapter=ctx.chapter,
            scene=ctx.scene,
            trace_id=trace_id,
        )
        value = result.score if result.score is not None else (1.0 if result.passed else 0.0)
        verdict = "pass" if result.passed else "fail"
        ctx.observer.score(
            f"{SCORE_PREFIX}{validator.name}",
            value,
            comment=f"{verdict}: {result.explanation}"[:_COMMENT_LIMIT],
            trace_id=trace_id,
        )
        results.append(result)
    return results


def all_passed(results: Sequence[ValidationResult]) -> bool:
    return all(result.passed for result in results)


__all__ = [
    "SCORE_PREFIX",
    "all_passed",
    "clear_registry",
    "register",
    "run_point",
    "unregister",
    "validators_for",
]
