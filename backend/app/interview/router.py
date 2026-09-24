"""The interview API (spec 006): validate a brief, ingest it, run one interviewer turn.

The brief routes take the brief as a plain JSON object rather than as the `Brief` model, so
an incomplete or contradictory brief is answered with its `BriefReport` instead of a
generic 422 (the interviewer needs the missing field named, definitions Brief § Validation).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, JsonValue

from app.bible import BibleRepository
from app.commons.deps import ModelClientDep
from app.commons.observability import Observer, get_observer
from app.interview.brief import BriefReport, validate_brief
from app.interview.interviewer import OPENING_QUESTION, Interviewer, TurnResult
from app.interview.service import InvalidBriefError, ingest_brief, new_novel_id, open_bible

router = APIRouter(prefix="/interview", tags=["interview"])


def get_bible() -> Iterator[BibleRepository]:
    """One repository per request on `HARNESS_DB`; tests override it with `:memory:`."""
    repo = open_bible()
    try:
        yield repo
    finally:
        repo.close()


BibleDep = Annotated[BibleRepository, Depends(get_bible)]
ObserverDep = Annotated[Observer, Depends(get_observer)]


class IngestRequest(BaseModel):
    brief: dict[str, JsonValue] = Field(description="A brief with the brief.v1.json shape.")
    novel_id: str | None = Field(
        default=None, description="The id minted at the start of the interview, if any."
    )


class IngestResponse(BaseModel):
    novel_id: str


class TurnRequest(BaseModel):
    novel_id: str | None = Field(default=None, description="Omit on the first turn.")
    draft: dict[str, JsonValue] = Field(default_factory=dict)
    answer: str = Field(description="The client's last answer. Untrusted data.")
    last_question: str = Field(default=OPENING_QUESTION)


@router.post("/validate")
def validate(brief: dict[str, JsonValue]) -> BriefReport:
    """Missing fields, contradictions and schema errors of a brief."""
    return validate_brief(brief)


@router.post(
    "/briefs",
    status_code=status.HTTP_201_CREATED,
    responses={422: {"description": "Invalid brief; `detail` is its BriefReport."}},
)
def ingest(
    body: IngestRequest, repo: BibleDep, observer: ObserverDep, client: ModelClientDep
) -> IngestResponse:
    """Validate and ingest a brief into the story bible; returns the novel id."""
    try:
        novel_id = ingest_brief(
            repo, body.brief, novel_id=body.novel_id, observer=observer, client=client
        )
    except InvalidBriefError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.report.model_dump(),
        ) from error
    return IngestResponse(novel_id=novel_id)


@router.post("/turn")
def turn(
    body: TurnRequest, repo: BibleDep, observer: ObserverDep, client: ModelClientDep
) -> TurnResult:
    """One interviewer step: merge the answer into the draft, return the next question."""
    interviewer = Interviewer(client, observer, novel_id=body.novel_id or new_novel_id(), repo=repo)
    interviewer.last_question = body.last_question
    return interviewer.safe_step(body.draft, body.answer)


__all__ = ["get_bible", "router"]
