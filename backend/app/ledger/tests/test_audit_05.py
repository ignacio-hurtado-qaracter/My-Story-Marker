"""FR-AUD-04 -- invariant 5, possible transits. Golden on the fixture (README planted rows 4
and 5, "The complete transit walk, per character") and the edges: a missing matrix entry is a
note, staying put needs no entry, and no matrix at all skips the check."""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import Severity, TemporalSystem, Violation
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 5


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


def with_matrix(store: Store, matrix: dict[str, dict[str, int]]) -> None:
    time = store.read(paths.TIME, TemporalSystem)
    updated = TemporalSystem.model_validate({**time.model_dump(), "transit_matrix": matrix})
    store.write(paths.TIME, updated, role=AgentRole.WORLD_BUILDER)


# spec 001 / AC 15 -- README rows 4 and 5: exactly two pairs, {001, 003} and {004, 005},
# blocking, each reported against both of its scenes.
def test_the_two_planted_pairs_are_blocking_on_all_four_scenes(fixture_store: Store) -> None:
    assert severities(fixture_store) == {
        "001": [Severity.BLOCKING],
        "003": [Severity.BLOCKING],
        "004": [Severity.BLOCKING],
        "005": [Severity.BLOCKING],
    }


# spec 001 / AC 15 -- "Total FR-AUD-04 findings in the whole fixture: exactly two" pairs.
def test_the_findings_are_exactly_two_distinct_pairs(fixture_store: Store) -> None:
    found = findings(fixture_store)
    quotes = {v.evidence.quote for hits in found.values() for v in hits}
    assert len(quotes) == 2
    assert found["001"][0].evidence.quote == found["003"][0].evidence.quote
    assert found["004"][0].evidence.quote == found["005"][0].evidence.quote
    first = found["001"][0].evidence.quote
    assert first.startswith(f"{paths.scene('001')} (hour 300, kestrel_deep) -> ")
    assert "vance crosses in 2 hours against" in first
    assert first.endswith(f"{paths.TIME} transit_matrix[kestrel_deep][pump_vault] = 6")
    assert "vance crosses in 0 hours against" in found["004"][0].evidence.quote


# spec 001 / AC 15 -- a missing entry between two places is a note: undecidable, not a pass.
def test_a_missing_matrix_entry_is_a_note(fixture_store: Store) -> None:
    with_matrix(
        fixture_store,
        {"kestrel_deep": {"kestrel_deep": 0, "pump_vault": 6}, "pump_vault": {"pump_vault": 0}},
    )
    assert severities(fixture_store) == {
        "001": [Severity.BLOCKING, Severity.NOTE],
        "002": [Severity.NOTE],
        "003": [Severity.BLOCKING],
        "004": [Severity.NOTE],
        "005": [Severity.NOTE],
    }
    assert "is missing" in findings(fixture_store)["002"][0].evidence.quote


# spec 001 / AC 15 -- staying in one place is not a movement and needs no diagonal entry.
def test_staying_put_needs_no_matrix_entry(fixture_store: Store) -> None:
    with_matrix(
        fixture_store, {"kestrel_deep": {"pump_vault": 6}, "pump_vault": {"kestrel_deep": 6}}
    )
    assert severities(fixture_store) == {
        "001": [Severity.BLOCKING],
        "003": [Severity.BLOCKING],
        "004": [Severity.BLOCKING],
        "005": [Severity.BLOCKING],
    }


# spec 001 / AC 15 -- FR-AUD-04 is `>=`: a crossing that takes exactly the matrix's hours is
# possible. Pricing the gallery-to-vault leg at 2 makes 001 -> 003 (delta 2) legal, and only
# the {004, 005} pair (delta 0 the other way, still priced at 6) remains.
def test_a_crossing_exactly_as_long_as_the_matrix_is_possible(fixture_store: Store) -> None:
    with_matrix(
        fixture_store,
        {
            "kestrel_deep": {"kestrel_deep": 0, "pump_vault": 2},
            "pump_vault": {"pump_vault": 0, "kestrel_deep": 6},
        },
    )
    assert severities(fixture_store) == {
        "004": [Severity.BLOCKING],
        "005": [Severity.BLOCKING],
    }


# spec 001 / AC 15 -- no time system at all: the check is skipped and says so.
def test_an_absent_time_system_skips_the_check(fixture_store: Store) -> None:
    (fixture_store.root / paths.TIME).unlink()
    report = audit_scene(fixture_store, "003", semantic=False)
    assert [entry.check for entry in report.skipped] == ["FR-AUD-04"]
    assert paths.TIME in report.skipped[0].reason
    assert all(finding.invariant != INVARIANT for finding in report.violations)
