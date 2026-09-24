"""Contract K5: the reader's HTTP routes under `/novels` (spec 014).

Every route reads the story bible (K1) through a `BibleRepository` opened per request, so
the threadpool never shares a connection. The only route that leads to a write is
`POST /novels/{id}/changes`, and it writes nothing itself: it starts a background job that
calls `app.novel.pipeline.change_fact`, the operation that owns the new version (K4).

The routes are plain `def`: they block on SQLite, and FastAPI runs them in its threadpool.
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

from app.bible import BibleNotFoundError, BibleRepository
from app.commons.config import get_settings
from app.commons.deps import get_model_client
from app.commons.llm import ModelClient
from app.export.pdf import export_pdf, pdf_filename
from app.reader import service
from app.reader.changes import ChangeJobs
from app.reader.models import (
    ChangeAccepted,
    ChangeJob,
    ChangeRequest,
    ChapterDetail,
    ChapterIndex,
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
    with BibleRepository.open(path) as repo:
        yield repo


RepoDep = Annotated[BibleRepository, Depends(get_repository)]


def _client_or_none() -> ModelClient | None:
    try:
        return get_model_client(get_settings())
    except Exception:  # no CLI configured: resolution stays deterministic-only
        return None


_JOBS = ChangeJobs(client_factory=_client_or_none)


def get_change_jobs() -> ChangeJobs:
    return _JOBS


JobsDep = Annotated[ChangeJobs, Depends(get_change_jobs)]

router = APIRouter(prefix="/novels", tags=["reader"])

# SQLite integers are 64-bit; a larger number in the URL is a 422, never a 500.
_MAX = 2**31 - 1
Version = Annotated[int, PathParam(ge=1, le=_MAX)]
ChapterNumber = Annotated[int, PathParam(ge=1, le=_MAX)]


def _not_found(error: BibleNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("")
def list_novels(repo: RepoDep) -> list[NovelSummary]:
    """Every novel, with its current (latest published) version."""
    return service.list_novels(repo)


@router.get("/{novel_id}")
def get_novel(novel_id: str, repo: RepoDep) -> NovelDetail:
    """Title, recipient, personalised dedication (R04) and the versions."""
    try:
        return service.novel_detail(repo, novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions")
def list_versions(novel_id: str, repo: RepoDep) -> list[VersionInfo]:
    """Every version with its parent and changed chapters; none is ever deleted (R07)."""
    try:
        return service.list_versions(repo, novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions/{version}/chapters")
def chapter_index(novel_id: str, version: Version, repo: RepoDep) -> ChapterIndex:
    """The navigable index (R01), each chapter marked when changed vs the parent (R06)."""
    try:
        return service.chapter_index(repo, novel_id, version)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/versions/{version}/chapters/{n}")
def read_chapter(novel_id: str, version: Version, n: ChapterNumber, repo: RepoDep) -> ChapterDetail:
    """One chapter's text, whether it changed, and the facts it uses."""
    try:
        return service.chapter_detail(repo, novel_id, version, n)
    except BibleNotFoundError as error:
        raise _not_found(error) from error


@router.get("/{novel_id}/bible")
def story_bible(
    novel_id: str,
    repo: RepoDep,
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
    novel_id: str, change: ChangeRequest, repo: RepoDep, path: BiblePathDep, jobs: JobsDep
) -> ChangeAccepted:
    """R05: resolve the fact to change and run `change_fact` in the background."""
    try:
        repo.get_novel(novel_id)
    except BibleNotFoundError as error:
        raise _not_found(error) from error
    if change.fact_key and repo.find_fact(novel_id, change.fact_key) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"the novel has no fact {change.fact_key!r}",
        )
    job = jobs.submit(path, novel_id, change)
    return ChangeAccepted(job_id=job.job_id)


@router.get("/{novel_id}/changes/{job_id}")
def change_status(novel_id: str, job_id: str, jobs: JobsDep) -> ChangeJob:
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
def download_pdf(novel_id: str, version: Version, repo: RepoDep) -> FileResponse:
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


__all__ = ["get_bible_path", "get_change_jobs", "get_repository", "router"]
