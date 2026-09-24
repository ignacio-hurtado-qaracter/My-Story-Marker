"""Contract K3: the validator protocol (spec 005 provides it; spec 008, B4, owns it after).

A validator has a `name`, an execution `point` and a `run(ctx)` that returns one
`ValidationResult`. It never persists or scores anything itself: `registry.run_point` does
both (through K1 and K2), so every validator result reaches the database and Langfuse the
same way (spec 004 § 1.5, V06).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from app.bible import BibleRepository
from app.commons.observability import Observer


class ValidationPoint(StrEnum):
    """Where a validator runs (spec 004 decision D4)."""

    SCENE_ACCEPT = "scene_accept"
    CHAPTER_CLOSE = "chapter_close"
    PRE_PUBLISH = "pre_publish"
    HOOK = "hook"


@dataclass(slots=True)
class ValidationContext:
    """What a validator may look at. `text` is the scene, chapter or novel under test;
    `chapter`/`scene` are None when the point is wider than them. `extra` carries
    point-specific inputs (e.g. the scene plan, the expected names) by agreed keys."""

    novel_id: str
    version: int
    chapter: int | None
    scene: int | None
    text: str
    repo: BibleRepository
    observer: Observer
    extra: dict[str, object] = field(default_factory=dict)
    trace_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """One validator's verdict. `score` in [0, 1] when the validator grades; None when it
    only passes or fails (the Langfuse score is then 1.0 or 0.0)."""

    name: str
    passed: bool
    score: float | None = None
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""


class Validator(Protocol):
    """K3. Implement as a class or a frozen dataclass with these three members."""

    @property
    def name(self) -> str: ...

    @property
    def point(self) -> ValidationPoint: ...

    def run(self, ctx: ValidationContext) -> ValidationResult: ...


__all__ = ["ValidationContext", "ValidationPoint", "ValidationResult", "Validator"]
