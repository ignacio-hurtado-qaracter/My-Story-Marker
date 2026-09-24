"""Role outputs of the gift-novel pipeline (spec 007) and its run results.

The role outputs are the structured-output formats handed to `claude -p`. They follow the
rule of `app.commons.schemas.role_outputs`: no unions and no model nested more than one
level deep, so the plan's scenes and events are flat lists keyed by chapter number rather
than lists inside lists. Constraints that the model could get "almost right" (ten chapters,
three scenes, every fact used) are *not* in the schema: they are checked by
`plan_check.check_plan`, whose error list feeds the one replan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["published", "blocked", "stopped_error"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanCharacter(_Out):
    name: str = Field(description="Exactly as in the brief for real people; invented otherwise")
    role: str = Field(description="protagonista, familiar, amigo, mascota, secundario...")
    birth_date: str | None = Field(default=None, description="YYYY-MM-DD when known/derivable")
    description: str = ""
    invented: bool = Field(default=False, description="True for characters not in the brief")


class PlanPlace(_Out):
    name: str
    description: str = ""


class PlanChapter(_Out):
    number: int
    title: str
    synopsis: str
    arc_role: str = Field(description="setup, rising, midpoint, climax, resolution...")
    time_marker: str = Field(
        default="",
        description=(
            "Explicit story-time marker of the chapter's present action, relative to the "
            "previous chapter (e.g. 'viernes 26 de junio de 2026, dos días después')"
        ),
    )
    flashback: bool = Field(
        default=False,
        description="True only if the whole chapter happens before the previous chapter",
    )


class PlanScene(_Out):
    chapter: int
    scene: int = Field(description="1-based position in the chapter")
    summary: str
    place: str = Field(description="A place name from `places`")
    characters: list[str] = Field(description="Character names from `characters`")
    story_date: str = Field(description="ISO date YYYY-MM-DD when the scene happens")
    facts_used: list[str] = Field(description="Fact keys from the FACTS document")
    word_budget: int


class ParticipantAge(_Out):
    name: str
    age: int


class PlanEvent(_Out):
    seq: int = Field(description="Chronological order, 1-based")
    chapter: int
    scene: int
    story_date: str = Field(description="ISO date YYYY-MM-DD")
    place: str
    description: str
    participants: list[str] = Field(description="Character names")
    declared_ages: list[ParticipantAge] = Field(
        default_factory=list, description="Only ages the story states explicitly"
    )
    kind: Literal["normal", "death", "departure"] = "normal"


class NovelPlan(_Out):
    """PLANNER output."""

    title: str
    synopsis: str = Field(description="The whole story in 150-250 words")
    characters: list[PlanCharacter]
    places: list[PlanPlace]
    chapters: list[PlanChapter]
    scenes: list[PlanScene]
    events: list[PlanEvent]
    ending_note: str = ""

    def scenes_of(self, chapter: int) -> list[PlanScene]:
        return sorted((s for s in self.scenes if s.chapter == chapter), key=lambda s: s.scene)

    def chapter(self, number: int) -> PlanChapter:
        return next(c for c in self.chapters if c.number == number)


class SceneDraft(_Out):
    """WRITER output: the scene prose, nothing else."""

    text: str = Field(description="The scene in Spanish, no headings, no comments")


class ChapterEdit(_Out):
    """EDITOR output."""

    title: str
    text: str = Field(description="The whole chapter in Spanish, no headings")
    summary: str = Field(description="About 120 words, for the next chapters' context")
    issues: list[str] = Field(default_factory=list, description="Critic self-check findings")


@dataclass(frozen=True, slots=True)
class RunResult:
    novel_id: str
    version: int
    status: RunStatus
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ChangeResult:
    new_version: int
    changed_chapters: list[int] = field(default_factory=list)
    status: RunStatus = "published"
    detail: str = ""


__all__ = [
    "ChangeResult",
    "ChapterEdit",
    "NovelPlan",
    "ParticipantAge",
    "PlanChapter",
    "PlanCharacter",
    "PlanEvent",
    "PlanPlace",
    "PlanScene",
    "RunResult",
    "RunStatus",
    "SceneDraft",
]
