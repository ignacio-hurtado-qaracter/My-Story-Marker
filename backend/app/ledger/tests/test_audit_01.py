"""FR-AUD-01 -- invariant 1, knowledge monotonicity, record half. Golden on the fixture
(README planted row 1) and the edges the fixture does not plant."""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Certainty,
    KnowledgeFile,
    KnowledgeState,
    Severity,
    Via,
    Violation,
)
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 1


def findings(store: Store) -> dict[str, list[Violation]]:
    """Invariant-1 findings per scene, scenes with none left out."""
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


# spec 001 / AC 15 -- README row 1: quiej's row anchored at 004, blocking, and nowhere else.
def test_the_planted_knowledge_row_is_found_at_004_only(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert {scene: [v.severity for v in hits] for scene, hits in found.items()} == {
        "004": [Severity.BLOCKING]
    }
    quote = found["004"][0].evidence.quote
    assert quote.startswith(f"{paths.cast_file('quiej', 'knowledge')} (quiej, ax_brine_dark, 004)")
    assert "ax_brine_dark" in quote
    assert "pov vance" in quote


# spec 001 / AC 15 -- every other anchor resolves cleanly (README row 1, second paragraph).
def test_rows_anchored_where_their_holder_is_present_are_clean(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert set(found) == {"004"}
    assert len(found["004"]) == 1


# spec 001 / AC 15 -- "every acquired_in resolves": a dangling anchor is blocking wherever
# its holder is present, because that is where "does he know this yet?" has no answer.
def test_an_unresolvable_anchor_is_reported_where_the_holder_is(fixture_store: Store) -> None:
    relative = paths.cast_file("ilan", "knowledge")
    knowledge = fixture_store.read(relative, KnowledgeFile)
    dangling = KnowledgeState(
        character="ilan",
        fact_ref="te_dive_rig",
        acquired_in="099",
        via=Via.WAS_TOLD,
        certainty=Certainty.BELIEVES,
        may_tell=[],
    )
    extended = KnowledgeFile(knowledge=[*knowledge.knowledge, dangling])
    fixture_store.write(relative, extended, role=AgentRole.CANONISER)

    found = findings(fixture_store)
    dangling_hits = {
        scene: [v for v in hits if "099" in v.evidence.quote] for scene, hits in found.items()
    }
    assert {scene for scene, hits in dangling_hits.items() if hits} == {"002", "004", "006"}
    for hits in dangling_hits.values():
        assert all(v.severity is Severity.BLOCKING for v in hits)


# spec 001 / AC 15 -- the check reads participants, not only the POV (DR-03).
def test_a_participant_anchor_is_accepted(fixture_store: Store) -> None:
    relative = paths.cast_file("ilan", "knowledge")
    knowledge = fixture_store.read(relative, KnowledgeFile)
    at_004 = KnowledgeState(
        character="ilan",
        fact_ref="ax_brine_dark",
        acquired_in="004",
        via=Via.WITNESSED,
        certainty=Certainty.KNOWS,
        may_tell=[],
    )
    fixture_store.write(
        relative,
        KnowledgeFile(knowledge=[*knowledge.knowledge, at_004]),
        role=AgentRole.CANONISER,
    )
    found = findings(fixture_store)
    assert len(found["004"]) == 1
    assert "quiej" in found["004"][0].evidence.quote


# spec 001 / AC 16 -- a finding's identity is its record's key, not the row's position: a row
# inserted ahead of it must not turn a finding a human already resolved into a new one.
def test_a_row_inserted_ahead_does_not_change_the_finding_id(fixture_store: Store) -> None:
    before = [v.id for v in findings(fixture_store)["004"]]
    relative = paths.cast_file("quiej", "knowledge")
    knowledge = fixture_store.read(relative, KnowledgeFile)
    unrelated = KnowledgeState(
        character="quiej",
        fact_ref="te_dive_rig",
        acquired_in="001",
        via=Via.WAS_TOLD,
        certainty=Certainty.BELIEVES,
        may_tell=[],
    )
    fixture_store.write(
        relative,
        KnowledgeFile(knowledge=[unrelated, *knowledge.knowledge]),
        role=AgentRole.CANONISER,
    )
    assert [v.id for v in findings(fixture_store)["004"]] == before
