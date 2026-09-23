"""FR-AUD-08 -- invariant 10, thread latency. Golden on the fixture (README planted row 9) and
the edges: a thread that has not begun, the inactive states, an unplaceable scene, and an
absent threads file.

`ledger/threads.yaml` has no writer in Figure 3, so the edges that change it write the private
copy of the fixture directly, as a human editing the tree would.
"""

from __future__ import annotations

import pytest

from app.commons.schemas import PlotThread, Severity, ThreadsFile, ThreadState, Violation
from app.commons.stores import Store, paths
from app.commons.stores.writer import serialise
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 10


def findings(store: Store) -> dict[str, list[Violation]]:
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


def severities(store: Store) -> dict[str, list[Severity]]:
    return {scene: [v.severity for v in hits] for scene, hits in findings(store).items()}


def overwrite_threads(store: Store, *threads: PlotThread) -> None:
    """Hand-edit the private copy: no role may write this file (Figure 3)."""
    record = ThreadsFile(threads=list(threads))
    (store.root / paths.THREADS).write_text(serialise(paths.THREADS, record), encoding="utf-8")
    assert store.read(paths.THREADS, ThreadsFile) == record


def surface_debt(store: Store) -> PlotThread:
    return store.read(paths.THREADS, ThreadsFile).threads[0]


# spec 001 / AC 15 -- README row 9: th_surface_debt late at 004 (gap 3) and 005 (gap 4).
def test_the_late_thread_is_reviewable_at_004_and_005(fixture_store: Store) -> None:
    assert severities(fixture_store) == {"004": [Severity.REVIEWABLE], "005": [Severity.REVIEWABLE]}
    found = findings(fixture_store)
    assert "a gap of 3 against max_latency 2" in found["004"][0].evidence.quote
    assert "a gap of 4 against max_latency 2" in found["005"][0].evidence.quote


# spec 001 / AC 15 -- the boundary is inclusive: 003, gap 2 against 2, is clean.
def test_a_gap_equal_to_the_latency_is_clean(fixture_store: Store) -> None:
    assert "003" not in findings(fixture_store)


# spec 001 / AC 15 -- a thread is not late before it has first appeared.
def test_a_thread_is_not_late_before_it_begins(fixture_store: Store) -> None:
    late_start = surface_debt(fixture_store).model_copy(
        update={"state": ThreadState.PLANTED, "scenes": ["005"], "max_latency": 1}
    )
    overwrite_threads(fixture_store, late_start)
    assert severities(fixture_store) == {}


# spec 001 / AC 15 -- only planted and developing threads can be late.
@pytest.mark.parametrize(
    "state", [ThreadState.DORMANT, ThreadState.RESOLVED, ThreadState.ABANDONED]
)
def test_inactive_threads_are_never_late(fixture_store: Store, state: ThreadState) -> None:
    resting = surface_debt(fixture_store).model_copy(update={"state": state})
    overwrite_threads(fixture_store, resting)
    assert severities(fixture_store) == {}


# spec 001 / AC 15 -- a listed scene with no record is a note, never silently dropped.
def test_an_unplaceable_scene_is_a_note(fixture_store: Store) -> None:
    dangling = surface_debt(fixture_store).model_copy(update={"scenes": ["001", "006", "099"]})
    overwrite_threads(fixture_store, dangling)
    found = severities(fixture_store)
    assert found["001"] == [Severity.NOTE]
    assert found["004"] == [Severity.NOTE, Severity.REVIEWABLE]


# spec 001 / AC 15 -- no threads file: the check is skipped and says so.
def test_an_absent_threads_file_skips_the_check(fixture_store: Store) -> None:
    (fixture_store.root / paths.THREADS).unlink()
    report = audit_scene(fixture_store, "004", semantic=False)
    skipped = {entry.check: entry.reason for entry in report.skipped}
    assert set(skipped) == {"FR-AUD-05", "FR-AUD-07", "FR-AUD-08"}  # 004 has no draft either
    assert paths.THREADS in skipped["FR-AUD-08"]
    assert all(finding.invariant != INVARIANT for finding in report.violations)


# spec 001 / AC 16 -- a finding's identity is the thread's id, not its position in the file.
def test_a_thread_inserted_ahead_does_not_change_the_finding_ids(fixture_store: Store) -> None:
    before = {scene: [v.id for v in hits] for scene, hits in findings(fixture_store).items()}
    threads = fixture_store.read(paths.THREADS, ThreadsFile).threads
    extra = threads[0].model_copy(update={"id": "th_extra_closed", "state": ThreadState.RESOLVED})
    overwrite_threads(fixture_store, extra, *threads)
    after = {scene: [v.id for v in hits] for scene, hits in findings(fixture_store).items()}
    assert after == before
