"""AC 8, FR-IDX-06: concurrent writers do not corrupt the index, and SQLITE_BUSY becomes a
503 only after the timeout.

The two-writer test uses real processes, not threads: the claim is about two processes
holding the same file, and threads in one interpreter share a GIL and a `sqlite3` module
state that would make contention gentler than it is. On Windows `multiprocessing` spawns,
so the writer below is a module-level function the child can import.
"""

from __future__ import annotations

import multiprocessing
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.commons.db import connection as db_connection
from app.commons.db import rebuild, search_text, status
from app.commons.db.connection import RETRY_ATTEMPTS, with_retry
from app.commons.db.index import IndexKind, IndexRow, apply_changes, opened_index, text_hash
from app.commons.embeddings import FakeEmbedder
from app.commons.errors import IndexBusy
from app.commons.stores import Store

WRITES_PER_PROCESS = 200


def _writer(index_path: str, worker: int, count: int) -> None:
    """One process's share: `count` separate write transactions, each one row.

    Separate transactions on purpose -- one big transaction would take the lock once and
    prove nothing about contention. Every write goes through `apply_changes`, the same path
    the incremental update uses, so the busy handling under test is the production one.
    """
    embedder = FakeEmbedder()
    with opened_index(Path(index_path)) as index:
        for number in range(count):
            text = f"worker {worker} row {number}"
            row = IndexRow(
                entity_id=f"w{worker}-{number:04d}",
                kind=IndexKind.AXIOM,
                path=f"worker-{worker}.md",
                text=text,
                content_hash=text_hash(text),
                updated_at=None,
            )
            [vector] = embedder.embed([text])
            apply_changes(
                index,
                upserts=[(row, vector if index.vector else None)],
                deletes=[],
                metadata={"writer": str(worker)},
            )


# spec 001 / AC 8 -- two processes x 200 writes: exact counts, and integrity_check is ok.
def test_two_processes_writing_concurrently_complete_without_corruption(tmp_path: Path) -> None:
    index_path = tmp_path / "index.sqlite"
    with opened_index(index_path) as index:
        vector = index.vector

    context = multiprocessing.get_context("spawn")
    workers = [
        context.Process(target=_writer, args=(str(index_path), worker, WRITES_PER_PROCESS))
        for worker in (1, 2)
    ]
    for process in workers:
        process.start()
    for process in workers:
        process.join(timeout=180)
    assert [process.exitcode for process in workers] == [0, 0]

    with opened_index(index_path) as index:
        connection = index.connection
        entity = connection.execute("select count(*) from entity").fetchone()[0]
        fts = connection.execute("select count(*) from entity_fts").fetchone()[0]
        per_worker = dict(
            connection.execute(
                "select path, count(*) from entity group by path order by path"
            ).fetchall()
        )
        vectors = (
            connection.execute("select count(*) from entity_vec").fetchone()[0] if vector else 0
        )
        integrity = connection.execute("pragma integrity_check").fetchone()[0]

    assert entity == fts == 2 * WRITES_PER_PROCESS
    assert per_worker == {"worker-1.md": WRITES_PER_PROCESS, "worker-2.md": WRITES_PER_PROCESS}
    assert vectors == (2 * WRITES_PER_PROCESS if vector else 0)
    assert integrity == "ok"


@pytest.fixture
def short_timeout(monkeypatch: pytest.MonkeyPatch) -> int:
    """The busy timeout shortened for the test. Production waits 5 s per attempt."""
    timeout_ms = 200
    monkeypatch.setattr(db_connection, "BUSY_TIMEOUT_MS", timeout_ms)
    monkeypatch.setattr(db_connection, "RETRY_BACKOFF_SECONDS", 0.01)
    return timeout_ms


def _hold_write_lock(index_path: Path) -> sqlite3.Connection:
    """Another writer holding the index: `BEGIN IMMEDIATE` and not committing."""
    blocker = sqlite3.connect(
        index_path, isolation_level=None, timeout=0, check_same_thread=False
    )
    blocker.execute("begin immediate")
    blocker.execute(
        "insert into index_metadata (key, value) values ('blocker', 'holding') "
        "on conflict (key) do update set value = excluded.value"
    )
    return blocker


# spec 001 / AC 8 -- forced busy: IndexBusy -> 503, and only after the busy timeout.
def test_a_held_write_lock_becomes_503_only_after_the_timeout(
    fixture_store: Store, index_path: Path, index_client: TestClient, short_timeout: int
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    blocker = _hold_write_lock(index_path)
    try:
        started = time.monotonic()
        response = index_client.post("/index/rebuild")
        elapsed = time.monotonic() - started
    finally:
        blocker.execute("rollback")
        blocker.close()

    assert response.status_code == 503
    assert response.json()["error"] == "index_busy"
    assert elapsed >= short_timeout / 1000
    # Once the other writer lets go, the same request succeeds: busy was a state, not a fault.
    assert index_client.post("/index/rebuild").status_code == 200


# spec 001 / AC 8 -- a writer that lets go within the timeout is waited for, not refused.
def test_a_lock_released_within_the_timeout_is_waited_for(
    fixture_store: Store, index_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_connection, "BUSY_TIMEOUT_MS", 3_000)
    rebuild(fixture_store, FakeEmbedder(), index_path)
    blocker = _hold_write_lock(index_path)

    def release() -> None:
        time.sleep(0.3)
        blocker.execute("rollback")

    releaser = threading.Thread(target=release)
    releaser.start()
    try:
        report = rebuild(fixture_store, FakeEmbedder(), index_path)
    finally:
        releaser.join()
        blocker.close()
    assert report.rows == 21


# spec 001 / AC 8 -- WAL: a reader is not blocked by a writer holding the lock. With the
# shortened timeout a blocked read would end in IndexBusy, so answering at all is the proof;
# no wall-clock bound is asserted, because one would only measure the CI machine.
def test_readers_are_not_blocked_by_a_writer(
    fixture_store: Store, index_path: Path, short_timeout: int
) -> None:
    del short_timeout  # requested for its side effect
    rebuild(fixture_store, FakeEmbedder(), index_path)
    blocker = _hold_write_lock(index_path)
    try:
        report = status(fixture_store, index_path)
        hits = search_text(index_path, "brine lamp light")
    finally:
        blocker.execute("rollback")
        blocker.close()

    assert report.rows == 21
    assert hits


# spec 001 / AC 8 -- the retry loop: busy is retried RETRY_ATTEMPTS times, then IndexBusy.
def test_busy_is_retried_then_raised_as_index_busy(short_timeout: int) -> None:
    calls: list[int] = []

    def always_busy() -> None:
        calls.append(1)
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(IndexBusy, match="locked by another writer"):
        with_retry(always_busy)
    # FR-IDX-06 asks for a retry; a single attempt would satisfy `== RETRY_ATTEMPTS` too.
    assert RETRY_ATTEMPTS > 1
    assert len(calls) == RETRY_ATTEMPTS


# spec 001 / AC 8 -- a lock that clears between attempts is retried into success, not a 503.
def test_busy_that_clears_on_the_next_attempt_succeeds(short_timeout: int) -> None:
    del short_timeout  # requested for its side effect: a fast backoff
    calls: list[int] = []

    def busy_once() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.OperationalError("database is locked")
        return "done"

    assert with_retry(busy_once) == "done"
    assert len(calls) == 2


# spec 001 / AC 8 -- FR-IDX-06 names WAL: it is what lets a reader and a writer overlap. The
# reader test above would pass under a rollback journal too, so the mode is asserted directly.
def test_an_opened_index_is_in_wal_mode(tmp_path: Path) -> None:
    with opened_index(tmp_path / "index.sqlite") as index:
        mode = index.connection.execute("pragma journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"


# spec 001 / AC 8 -- and nothing else is retried: retrying a bug turns it into a slow bug.
def test_an_error_that_is_not_busy_is_raised_at_once() -> None:
    calls: list[int] = []

    def broken() -> None:
        calls.append(1)
        raise sqlite3.OperationalError("no such table: nowhere")

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        with_retry(broken)
    assert len(calls) == 1
