"""Spec 020: a new novel from the web -- ingest a brief and run `generate` in the background.

`GenerationJobs` follows the change-job pattern of `app.reader.changes`: an in-memory job
table, one daemon thread per job, its own repository connection, and every failure reported
in the job rather than raised into the thread. The route writes nothing itself:
`app.interview.service.ingest_brief` creates the novel (owned by the caller, spec 018) and
`app.novel.pipeline.generate` (K4) owns everything after it.

A job's status is the job merged with the story bible, so a novel whose job this process
does not know (a restart, a CLI run) is still answered from its checkpoints and versions.

Lean: every novel has its own Lake copy (`app.novel.setup.register_lean_for`). Inside one
process the validator registry holds one `LeanChronology` at a time, but each `lake build`
writes its own novel's chronology first and runs under `lean_runner._BUILD_LOCK`, so two
concurrent runs never check each other's story.
"""

from __future__ import annotations

import datetime as dt
import importlib
import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Protocol, cast

from pydantic import JsonValue

from app.bible import BibleNotFoundError, BibleRepository
from app.commons.llm import ModelClient
from app.commons.observability import get_observer
from app.interview.service import ingest_brief, new_novel_id
from app.novel._bible_ext import load_plan
from app.reader.models import GenerationIssue, GenerationState, GenerationStatus

PIPELINE_MODULE: Final[str] = "app.novel.pipeline"
MAX_RUNNING: Final[int] = 2
"""At most this many generations per process (spec 020): each one is a long chain of
model calls, and a third would only queue behind the same CLI login."""
MAX_ISSUES: Final[int] = 5
_ACTIVE: Final[frozenset[str]] = frozenset({"queued", "running"})


class TooManyGenerationsError(RuntimeError):
    """`MAX_RUNNING` generations are already running in this process."""


class _Generate(Protocol):
    def __call__(
        self,
        repo: BibleRepository,
        novel_id: str,
        *,
        chapters: int | None = ...,
        progress: Callable[[str], None] | None = ...,
    ) -> object: ...


def load_generate() -> _Generate:
    """K4 `generate`, looked up per job so a test's monkeypatch of the module applies."""
    module = importlib.import_module(PIPELINE_MODULE)
    return cast("_Generate", module.generate)


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class GenerationJob:
    job_id: str
    novel_id: str
    owner_id: str
    status: GenerationState
    phase: str
    chapters: int
    started_at: str
    updated_at: str
    detail: str = ""


def phase_of(line: str, current: str) -> str:
    """The pipeline's progress line → a phase code the page translates."""
    text = line.strip()
    if text.startswith("pre_publish failed"):
        return "repairing"
    if text.startswith("version") and text.endswith("published"):
        return "published"
    if text.startswith("STOPPED"):
        return "stopped"
    if text.startswith("chapter"):
        return "writing"
    return current


def with_chapters(brief: Mapping[str, JsonValue], chapters: int | None) -> dict[str, JsonValue]:
    """The brief with `length.chapters` replaced when the request names a number."""
    data = dict(brief)
    if chapters is not None:
        length = data.get("length")
        base: dict[str, JsonValue] = dict(length) if isinstance(length, dict) else {}
        data["length"] = {**base, "chapters": chapters}
    return data


def _brief_chapters(brief: Mapping[str, JsonValue]) -> int:
    length = brief.get("length")
    if isinstance(length, dict):
        value = length.get("chapters")
        if isinstance(value, int) and value > 0:
            return value
    return 10


class GenerationJobs:
    """In-memory job table. A restart forgets the jobs; the novels stay in the database."""

    def __init__(
        self,
        *,
        max_running: int = MAX_RUNNING,
        client_factory: Callable[[], ModelClient | None] = lambda: None,
        generate_loader: Callable[[], _Generate] = load_generate,
    ) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = threading.Lock()
        self._max = max_running
        self._client_factory = client_factory
        self._loader = generate_loader

    def for_novel(self, novel_id: str) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(novel_id)

    def running(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status in _ACTIVE)

    def _set(self, novel_id: str, **changes: object) -> GenerationJob:
        with self._lock:
            job = replace(self._jobs[novel_id], updated_at=_now(), **changes)  # type: ignore[arg-type]  # keyword fields of the dataclass; spec 020
            self._jobs[novel_id] = job
            return job

    def submit(
        self,
        db_path: Path | str,
        brief: Mapping[str, JsonValue],
        *,
        owner_id: str,
        chapters: int | None = None,
        background: bool = True,
    ) -> GenerationJob:
        """Raises `TooManyGenerationsError` at the cap. The brief is validated by the caller."""
        data = with_chapters(brief, chapters)
        now = _now()
        job = GenerationJob(
            job_id=uuid.uuid4().hex[:12],
            novel_id=new_novel_id(),
            owner_id=owner_id,
            status="queued",
            phase="ingesting",
            chapters=_brief_chapters(data),
            started_at=now,
            updated_at=now,
        )
        with self._lock:
            if sum(1 for j in self._jobs.values() if j.status in _ACTIVE) >= self._max:
                message = f"{self._max} generations are already running"
                raise TooManyGenerationsError(message)
            self._jobs[job.novel_id] = job
        if background:
            thread = threading.Thread(
                target=self._run,
                args=(job.novel_id, db_path, data),
                name=f"generate-{job.job_id}",
                daemon=True,
            )
            thread.start()
        else:
            self._run(job.novel_id, db_path, data)
        return job

    def _run(self, novel_id: str, db_path: Path | str, brief: dict[str, JsonValue]) -> None:
        job = self._set(novel_id)
        try:
            with BibleRepository.open(db_path) as repo:
                ingest_brief(
                    repo,
                    brief,
                    novel_id=novel_id,
                    observer=get_observer(),
                    client=self._client_factory(),
                    owner_id=job.owner_id,
                )
                self._set(novel_id, status="running", phase="planning")

                def progress(line: str) -> None:
                    current = self.for_novel(novel_id)
                    phase = phase_of(line, current.phase if current else "planning")
                    self._set(novel_id, phase=phase, detail=line.strip()[:300])

                result = self._loader()(
                    repo, novel_id, chapters=job.chapters, progress=progress
                )
                status = str(getattr(result, "status", "stopped_error"))
                final: GenerationState = (
                    cast("GenerationState", status)
                    if status in ("published", "blocked", "stopped_error")
                    else "stopped_error"
                )
                self._set(
                    novel_id,
                    status=final,
                    phase="published" if final == "published" else "stopped",
                    detail=str(getattr(result, "detail", ""))[:500],
                )
        except Exception as error:  # a failed job is reported, never raised into a thread
            self._set(
                novel_id,
                status="stopped_error",
                phase="stopped",
                detail=f"{type(error).__name__}: {error}"[:500],
            )

    def status(self, repo: BibleRepository, novel_id: str) -> GenerationStatus:
        """The job (when this process runs it) merged with the story bible."""
        job = self.for_novel(novel_id)
        try:
            novel = repo.get_novel(novel_id)
        except BibleNotFoundError:
            if job is None:
                raise
            novel = None
        total = job.chapters if job else 0
        done = 0
        version_no: int | None = None
        version_status = ""
        issues: list[GenerationIssue] = []
        cost_usd, calls = 0.0, 0
        if novel is not None:
            plan = load_plan(repo, novel_id)
            if plan is not None:
                total = len(plan.chapters)
            if not total:
                brief = repo.get_brief(novel_id)
                total = _brief_chapters(brief.data) if brief else 10
            latest = repo.latest_version(novel_id)
            if latest is not None:
                version_no, version_status = latest.version, latest.status
                done = sum(
                    1
                    for cp in repo.list_checkpoints(novel_id, latest.version)
                    if cp.status == "complete"
                )
                failed = [
                    r
                    for r in repo.list_validator_results(novel_id, version=latest.version)
                    if not r.passed
                ]
                issues = [
                    GenerationIssue(
                        name=r.name, point=r.point, chapter=r.chapter,
                        explanation=r.explanation[:300],
                    )
                    for r in reversed(failed[-MAX_ISSUES:])
                ]
            cost = repo.cost_summary(novel_id)
            cost_usd, calls = cost.cost_usd, cost.calls
        state: GenerationState
        if job is not None:
            state = job.status
        elif version_status in ("published", "blocked"):
            state = cast("GenerationState", version_status)
        elif novel is not None and novel.status == "stopped_error":
            state = "stopped_error"
        else:
            state = "running"
        phase = job.phase if job else ("published" if state == "published" else "")
        if state == "running" and total and done >= total and phase == "writing":
            phase = "pre_publish"
        return GenerationStatus(
            novel_id=novel_id,
            job_id=job.job_id if job else None,
            status=state,
            phase=phase,
            chapters_done=min(done, total) if total else done,
            chapters_total=total,
            version=version_no,
            cost_usd=round(cost_usd, 4),
            calls=calls,
            issues=issues,
            detail=job.detail if job else "",
            started_at=job.started_at if job else (novel.created_at if novel else None),
            updated_at=job.updated_at if job else (novel.updated_at if novel else None),
        )


__all__ = [
    "MAX_RUNNING",
    "GenerationJob",
    "GenerationJobs",
    "TooManyGenerationsError",
    "load_generate",
    "phase_of",
    "with_chapters",
]
