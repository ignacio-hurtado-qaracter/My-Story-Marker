"""FR-AUD-02 -- invariant 2, closed debts. Golden on the fixture (README planted row 2) and
the edges: escalation at the last scene, an unplaceable deadline, a deliberate abandonment,
and an absent setups file.

`ledger/setups.yaml` has no writer in Figure 3, so the edges that change it write the private
copy of the fixture directly, as a human editing the tree would.
"""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import Scene, SetupResolution, SetupsFile, Severity, Violation
from app.commons.stores import Store, paths
from app.commons.stores.writer import serialise
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 2


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


def overwrite_setups(store: Store, record: SetupsFile) -> None:
    """Hand-edit the private copy: no role may write this file (Figure 3)."""
    (store.root / paths.SETUPS).write_text(serialise(paths.SETUPS, record), encoding="utf-8")
    assert store.read(paths.SETUPS, SetupsFile) == record


# spec 001 / AC 15 -- README row 2: su_readkey at 004 and 005, reviewable, nowhere else.
def test_the_open_overdue_setup_is_reviewable_at_004_and_005(fixture_store: Store) -> None:
    assert severities(fixture_store) == {"004": [Severity.REVIEWABLE], "005": [Severity.REVIEWABLE]}
    for hits in findings(fixture_store).values():
        assert "su_readkey" in hits[0].evidence.quote


# spec 001 / AC 15 -- the paid setup is never reported ("closed items leave the working tier").
def test_the_paid_setup_is_never_reported(fixture_store: Store) -> None:
    for hits in findings(fixture_store).values():
        assert all("su_graft" not in v.evidence.quote for v in hits)


# spec 001 / AC 15 -- blocking at the last scene by discourse order (the branch the fixture
# deliberately leaves unexercised; here 005 is moved to the end of the reading order).
def test_the_debt_is_blocking_at_the_last_scene(fixture_store: Store) -> None:
    relative = paths.scene("005")
    moved = fixture_store.read(relative, Scene).model_copy(update={"discourse_order": 7})
    fixture_store.write(relative, moved, role=AgentRole.ARCHITECT)
    assert severities(fixture_store) == {"004": [Severity.REVIEWABLE], "005": [Severity.BLOCKING]}


# spec 001 / AC 15 -- a deliberate abandonment is a decision, not a loose end (DR-05).
def test_a_deliberately_abandoned_setup_is_not_reported(fixture_store: Store) -> None:
    setups = fixture_store.read(paths.SETUPS, SetupsFile)
    readkey = setups.setups[0].model_copy(
        update={"resolution": SetupResolution.DELIBERATELY_ABANDONED}
    )
    overwrite_setups(fixture_store, SetupsFile(setups=[readkey, *setups.setups[1:]]))
    assert severities(fixture_store) == {}


# spec 001 / AC 15 -- a deadline naming no scene cannot be placed: a note, never silence.
def test_an_unplaceable_deadline_is_a_note(fixture_store: Store) -> None:
    setups = fixture_store.read(paths.SETUPS, SetupsFile)
    readkey = setups.setups[0].model_copy(update={"due_by": "099"})
    overwrite_setups(fixture_store, SetupsFile(setups=[readkey, *setups.setups[1:]]))
    assert severities(fixture_store) == {scene: [Severity.NOTE] for scene in SCENES}
    assert "099" in findings(fixture_store)["001"][0].evidence.quote


# spec 001 / AC 15 -- no setups file: the check is skipped and says so, it does not pass.
def test_an_absent_setups_file_skips_the_check(fixture_store: Store) -> None:
    (fixture_store.root / paths.SETUPS).unlink()
    report = audit_scene(fixture_store, "004", semantic=False)
    skipped = {entry.check: entry.reason for entry in report.skipped}
    assert set(skipped) == {"FR-AUD-02", "FR-AUD-05", "FR-AUD-07"}  # 004 has no draft either
    assert paths.SETUPS in skipped["FR-AUD-02"]
    assert "FR-AUD-02" not in [ref.check for ref in report.checked]
    assert all(finding.invariant != INVARIANT for finding in report.violations)


# spec 001 / AC 16 -- a finding's identity is the setup's id, not its position in the file.
def test_a_setup_inserted_ahead_does_not_change_the_finding_ids(fixture_store: Store) -> None:
    before = {scene: [v.id for v in hits] for scene, hits in findings(fixture_store).items()}
    setups = fixture_store.read(paths.SETUPS, SetupsFile)
    paid = next(setup for setup in setups.setups if setup.paid_in is not None)
    extra = paid.model_copy(update={"id": "su_extra_paid"})
    overwrite_setups(fixture_store, SetupsFile(setups=[extra, *setups.setups]))
    after = {scene: [v.id for v in hits] for scene, hits in findings(fixture_store).items()}
    assert after == before
