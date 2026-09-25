"""Contract K5: the reader's HTTP routes under `/novels` (spec 014).

Every route reads the story bible (K1) through a `BibleRepository` opened per request, so
the threadpool never shares a connection. The only route that leads to a write is
`POST /novels/{id}/changes`, and it writes nothing itself: it starts a background job that
calls `app.novel.pipeline.change_fact`, the operation that owns the new version (K4).

The routes are plain `def`: they block on SQLite, and FastAPI runs them in its threadpool.

Spec 018 (SEC-01): every route sees the story bible through `repo.scoped_to(<caller>)`, and
every `/novels/{novel_id}/...` route resolves the novel through `owned_novel_id` first, so a
novel of another owner answers exactly like a missing one (404).
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.auth import CurrentUserDep
from app.bible import BibleNotFoundError, BibleRepository
from app.commons.config import get_settings
from app.commons.deps import get_model_client
from app.commons.llm import ModelClient
from app.export.pdf import export_pdf, pdf_filename
from app.interview.brief import validate_brief
from app.reader import service
from app.reader.changes import (
    INJECTION_POLICY,
    ChangeJobs,
    change_injection_markers,
    editable_fact,
)
from app.reader.generation import GenerationJobs, TooManyGenerationsError
from app.reader.models import (
    ChangeAccepted,
    ChangeJob,
    ChangeRequest,
    ChapterDetail,
    ChapterIndex,
    GenerateAccepted,
    GenerateRequest,
    GenerationStatus,
    NovelDetail,
    NovelSummary,
    StoryBible,
    VersionInfo,
)


def get_bible_path() -> Path:
    """`HARNESS_DB`. Tests override this dependency with a temporary file."""
    return get_settings().harness_db_path


BiblePathDep = Annotated[Path, Depends(get_bible_path)]


def get_repository(path: BiblePathDep) -> Iterator[BibleRepository]:
    # A sync generator dependency runs in one threadpool thread and the sync endpoint in
    # another, so the connection may not be bound to its opening thread. It is still used
    # by one request at a time and closed when the request ends.
    with BibleRepository.open(path, check_same_thread=False) as repo:
        yield repo


RepoDep = Annotated[BibleRepository, Depends(get_repository)]
"""The unscoped repository: `/auth` uses it to find users; no reader route does."""


def get_owned_repository(repo: RepoDep, user: CurrentUserDep) -> BibleRepository:
    """Spec 018: the repository as the caller sees it -- only the caller's novels."""
    return repo.scoped_to(user.id)


OwnedRepoDep = Annotated[BibleRepository, Depends(get_owned_repository)]


def _client_or_none() -> ModelClient | None:
    try:
        return get_model_client(get_settings())
    except Exception:  # no CLI configured: resolution stays deterministic-only
        return None


_JOBS = ChangeJobs(client_factory=_client_or_none)


def get_change_jobs() -> ChangeJobs:
    return _JOBS


JobsDep = Annotated[ChangeJobs, Depends(get_change_jobs)]

_GENERATIONS = GenerationJobs(client_factory=_client_or_none)


def get_generation_jobs() -> GenerationJobs:
    return _GENERATIONS


GenerationsDep = Annotated[GenerationJobs, Depends(get_generation_jobs)]

router = APIRouter(prefix="/novels", tags=["reader"])

# SQLite integers are 64-bit; a larger number in the URL is a 422, never a 500.
_MAX = 2**31 - 1
Version = Annotated[int, PathParam(ge=1, le=_MAX)]
ChapterNumber = Annotated[int, PathParam(ge=1, le=_MAX)]


def _not_found(error: BibleNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def owned_novel_id(novel_id: str, repo: OwnedRepoDep) -> str:
    """The path's novel id, once the caller is known to own it; 404 otherwise."""
    try:
        repo.get_novel(novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error
    return novel_id


NovelId = Annotated[str, Depends(owned_novel_id)]


@router.get("")
def list_novels(repo: OwnedRepoDep) -> list[NovelSummary]:
    """Every novel, with its current (latest published) version."""
    return service.list_novels(repo)


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"description": "Invalid brief; `detail` is its BriefReport."},
        429: {"description": "Two generations are already running."},
    },
)
def start_generation(
    body: GenerateRequest, path: BiblePathDep, user: CurrentUserDep, jobs: GenerationsDep
) -> GenerateAccepted:
    """Spec 020: validate the brief, then ingest it (owned by the caller) and run `generate`
    in the background. Poll `GET /novels/{id}/generation`."""
    report = validate_brief(body.brief)
    if not report.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=report.model_dump()
        )
    try:
        job = jobs.submit(path, body.brief, owner_id=user.id, chapters=body.chapters)
    except TooManyGenerationsError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)
        ) from error
    return GenerateAccepted(novel_id=job.novel_id, job_id=job.job_id)


@router.get("/{novel_id}/generation")
def generation_status(
    novel_id: str, repo: RepoDep, user: CurrentUserDep, jobs: GenerationsDep
) -> GenerationStatus:
    """Spec 020: phase, chapters done / total, cost so far and the last validator failures.
    404 for a novel of another owner, exactly like a missing one."""
    job = jobs.for_novel(novel_id)
    if job is not None and job.owner_id != user.id:
        job = None
    try:
        if job is None:
            repo.scoped_to(user.id).get_novel(novel_id)
        return jobs.status(repo.scoped_to(user.id), novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}")
def get_novel(novel_id: NovelId, repo: OwnedRepoDep) -> NovelDetail:
    """Title, recipient, personalised dedication (R04) and the versions."""
    try:
        return service.novel_detail(repo, novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions")
def list_versions(novel_id: NovelId, repo: OwnedRepoDep) -> list[VersionInfo]:
    """Every version with its parent and changed chapters; none is ever deleted (R07)."""
    try:
        return service.list_versions(repo, novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions/{version}/chapters")
def chapter_index(novel_id: NovelId, version: Version, repo: OwnedRepoDep) -> ChapterIndex:
    """The navigable index (R01), each chapter marked when changed vs the parent (R06)."""
    try:
        return service.chapter_index(repo, novel_id, version)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions/{version}/chapters/{n}")
def read_chapter(
    novel_id: NovelId, version: Version, n: ChapterNumber, repo: OwnedRepoDep
) -> ChapterDetail:
    """One chapter's text, whether it changed, and the facts it uses."""
    try:
        return service.chapter_detail(repo, novel_id, version, n)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/bible")
def story_bible(
    novel_id: NovelId,
    repo: OwnedRepoDep,
    version: Annotated[
        int | None, Query(ge=1, le=_MAX, description="Default: the current version.")
    ] = None,
) -> StoryBible:
    """Character and place sheets with the chapters where each appears (R03)."""
    try:
        return service.story_bible(repo, novel_id, version)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.post("/{novel_id}/changes", status_code=status.HTTP_202_ACCEPTED)
def request_change(
    novel_id: NovelId, change: ChangeRequest, repo: OwnedRepoDep, path: BiblePathDep, jobs: JobsDep
) -> ChangeAccepted:
    """R05: resolve the fact to change and run `change_fact` in the background."""
    if change.fact_key and editable_fact(repo, novel_id, change.fact_key) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"the novel has no fact {change.fact_key!r}",
        )
    markers = change_injection_markers(change)
    if markers:
        # SEC-05: the new value would become a fact in the writer's prompt. Logged, refused.
        repo.log_policy_decision(
            policy=INJECTION_POLICY,
            decision="reject",
            novel_id=novel_id,
            detail="prescan: " + ", ".join(markers),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="the request looks like an instruction to the system, not a change of fact",
        )
    job = jobs.submit(path, novel_id, change)
    return ChangeAccepted(job_id=job.job_id)


@router.get("/{novel_id}/changes/{job_id}")
def change_status(novel_id: NovelId, job_id: str, jobs: JobsDep) -> ChangeJob:
    """Poll a change: queued → resolving → running → done | failed."""
    job = jobs.get(job_id)
    if job is None or job.novel_id != novel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"no job {job_id!r}")
    return job


@router.get(
    "/{novel_id}/versions/{version}/pdf",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_pdf(novel_id: NovelId, version: Version, repo: OwnedRepoDep) -> FileResponse:
    """The interactive PDF of this version (cover, novedades, index, sheets)."""
    try:
        repo.get_version(novel_id, version)
        directory = Path(tempfile.mkdtemp(prefix="msm-pdf-"))
        name = pdf_filename(novel_id, version)
        written = export_pdf(repo, novel_id, version, directory / name)
    except BibleNotFoundError as error:
        raise _not_found(error) from error

    def cleanup() -> None:
        written.unlink(missing_ok=True)
        directory.rmdir()

    return FileResponse(
        written, media_type="application/pdf", filename=name, background=BackgroundTask(cleanup)
    )


__all__ = [
    "OwnedRepoDep",
    "RepoDep",
    "get_bible_path",
    "get_change_jobs",
    "get_generation_jobs",
    "get_owned_repository",
    "get_repository",
    "router",
]
