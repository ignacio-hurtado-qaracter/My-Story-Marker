"""Plan step 18 -- AC 20: promotion inside a turn is add-only, so a turn whose facts touch what
canon already holds still ends `merged`; FR-TURN-08's rulings route stays, for older records.

`scripts/collision_002.yaml` has the canoniser extract an assertion about ilan's `wants`, a
field canon already fills. `promote` appends it as one more clause (FR-OPS-06), and the turn
ends `merged` with the fact promoted and reconciled. A fact aimed at a key ilan's body already
has is not applied: the turn records it `rejected`, with a fixed reason code and no collision,
reconciles nothing for it, and still ends `merged`. A pending fact of the scene that carries
`conflict: true` from before promotion was add-only no longer refuses a new turn, and a resumed
record that holds one ends `merged`. The one 409 left before a turn is the lock's (FR-TURN-05,
`test_turn_escalation.py`).

`POST /agents/turns/{id}/rulings` (FR-TURN-08, FR-OPS-07) is kept in the contract. No v1 turn
ends `awaiting_ruling`, so its tests run on a record built by hand as a turn left it before:
the fact queued with `conflict: true`, the record `awaiting_ruling`. `accept` writes the payload
over the value -- the one path that can overwrite canon -- and reconciles, `reject` marks the
fact rejected, and either way the turn moves to `merged` once no collision is left.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents import records, turn
from app.agents.models import RulingRequest
from app.agents.tests.test_turn_happy import (
    TurnEnv,
    load_script,
    make_turn_env,
    scripted,
    sse_events,
    use,
)
from app.cast.models import Character
from app.commons.errors import InvalidRecord, NotFound, PermissionDenied, TurnLocked
from app.commons.llm import FakeModelClient, Reply
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import (
    ExtractOutput,
    FactRecord,
    FactStatus,
    ProposedFact,
    ProposedFactDraft,
    ProposedFile,
    RulingKind,
    TurnOutcome,
    TurnRecord,
    TurnStep,
)
from app.commons.stores import Store, paths
from app.ledger import service as ledger_service

HUMAN_CANONISER = {"X-Agent-Role": "canoniser", "X-Actor": "human"}
CANON_WANTS = "to be left alone with the certification he still has"
PROPOSED_WANTS = "nothing from the co-op but the way back up"
PROPOSED_NEEDS = "the way back up"
ILAN = paths.cast_file("ilan", "dossier")
WANTS_ID = "pf-002-legacywants"
NEEDS_ID = "pf-002-legacyneeds"


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def ilan(store: Store) -> Character:
    return store.read(ILAN, Character)


def queued(store: Store, fact_id: str) -> ProposedFact:
    queue = store.read(paths.PROPOSED, ProposedFile).proposed
    [entry] = [entry for entry in queue if entry.id == fact_id]
    return entry


def rulings(fact_id: str, ruling: RulingKind) -> list[dict[str, str]]:
    return [{"fact_id": fact_id, "ruling": ruling.value, "reason": "The ruling of the editor."}]


def extraction(*facts: tuple[str, str, str]) -> FakeModelClient:
    """`collision_002` with the canoniser's answer replaced by `(entity, field, payload)` facts."""
    script = load_script("collision_002")
    script[AgentRole.CANONISER] = [
        Reply.of(
            ExtractOutput(
                facts=[
                    ProposedFactDraft(
                        target_entity=entity,
                        target_field=field,
                        payload=payload,
                        evidence="wanted nothing from her but the way back up",
                    )
                    for entity, field, payload in facts
                ]
            )
        )
    ]
    return FakeModelClient(script)


# --- AC 20: add-only promotion inside a turn -----------------------------------------------------


# spec 001 / AC 20 -- a filled field gets the detail appended, and the turn is merged.
def test_a_turn_appends_to_a_filled_field_and_ends_merged(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    use(fixture_client, scripted("collision_002"))
    events = sse_events(fixture_client.post("/agents/turns", json={"scene_id": "002"}).text)
    assert events[-1][1]["outcome"] == "merged"
    record = TurnRecord.model_validate(fixture_client.get("/agents/turns/002-1").json())

    assert record.outcome is TurnOutcome.MERGED
    [fact] = record.facts
    assert (fact.target_entity, fact.target_field) == ("ilan", "wants")
    assert fact.status is FactStatus.PROMOTED
    assert fact.changed is True
    assert (fact.conflict, fact.refused, fact.ruling) == (False, None, None)
    assert "002" in fact.reconciled_scenes, "reconciled after the promotion (FR-TURN-04)"
    assert ilan(fixture_store).wants == f"{CANON_WANTS}; {PROPOSED_WANTS}"
    entry = queued(fixture_store, fact.fact_id)
    assert entry.status is FactStatus.PROMOTED
    assert (entry.conflict, entry.existing_value, entry.ruling) == (False, None, None)
    lines = fixture_store.provenance(path=ILAN)
    assert [(line.role, line.actor, line.turn) for line in lines] == [
        (AgentRole.CANONISER, Actor.AGENT, "002-1")
    ]


# spec 001 / AC 20 -- a fact aimed at a key the record already has is recorded as not applied,
# with a fixed reason and nothing reconciled, and the turn is merged all the same.
def test_a_fact_the_record_already_specifies_is_not_applied_and_the_turn_merges(
    turn_env: TurnEnv,
) -> None:
    lungs = ilan(turn_env.store).immutable_physical["lungs"]
    record = turn_env.run(
        extraction(
            ("ilan", "wants", PROPOSED_WANTS),
            ("ilan", "immutable_physical", "lungs: tolerates brine"),
        )
    )

    assert record.outcome is TurnOutcome.MERGED
    wants, body = record.facts
    assert wants.status is FactStatus.PROMOTED
    assert body.status is FactStatus.REJECTED
    assert body.refused == "already_specified field=immutable_physical"
    assert "brine" not in body.refused, "never the payload (NFR-10)"
    assert (body.conflict, body.changed, body.ruling) == (False, False, None)
    assert body.reconciled_scenes == [], "nothing entered canon, so nothing is reconciled"
    entry = queued(turn_env.store, body.fact_id)
    assert entry.status is FactStatus.REJECTED
    assert (entry.conflict, entry.existing_value, entry.ruling) == (False, None, None)
    assert ilan(turn_env.store).immutable_physical["lungs"] == lungs
    assert ilan(turn_env.store).wants == f"{CANON_WANTS}; {PROPOSED_WANTS}"


def queue_legacy(store: Store, *facts: tuple[str, str, str]) -> None:
    """Queue `(id, field, payload)` facts about ilan as a collision-checking `promote` left them:
    pending, `conflict: true`, the value they collided with recorded."""
    held = ilan(store)
    ledger_service.append_proposed(
        store,
        ledger_service.ProposedAppend(
            facts=[
                ProposedFact(
                    id=identifier,
                    extracted_from=paths.draft("002"),
                    target_entity="ilan",
                    target_field=field,
                    payload=payload,
                    source_scene="002",
                    conflict=True,
                    existing_value=str(getattr(held, field)),
                )
                for identifier, field, payload in facts
            ]
        ),
        role=AgentRole.CANONISER,
        actor=Actor.AGENT,
    )


def legacy_record(
    store: Store, *identifiers: tuple[str, str], outcome: TurnOutcome, next_step: TurnStep
) -> TurnRecord:
    """A turn record of scene 002 whose facts `(id, field)` are collisions left pending."""
    record = TurnRecord(
        id="002-1",
        scene="002",
        outcome=outcome,
        started_at="2026-09-01T10:00:00+00:00",
        ended_at="2026-09-01T10:05:00+00:00" if outcome is not TurnOutcome.RUNNING else None,
        next_step=next_step,
        facts=[
            FactRecord(
                fact_id=identifier,
                target_entity="ilan",
                target_field=field,
                proposed_by=["canoniser"],
                conflict=True,
            )
            for identifier, field in identifiers
        ],
    )
    records.save(store, record)
    return record


# spec 001 / AC 20 -- a pending collision of the scene no longer refuses a turn on it (the old
# FR-TURN-05 refusal is gone; the lock's 409 stays).
def test_a_legacy_collision_pending_on_the_scene_does_not_refuse_a_turn(turn_env: TurnEnv) -> None:
    queue_legacy(turn_env.store, (WANTS_ID, "wants", PROPOSED_WANTS))

    record = turn_env.run(scripted("happy_002"))

    assert record.outcome is TurnOutcome.MERGED
    assert queued(turn_env.store, WANTS_ID).status is FactStatus.PENDING, "not this turn's fact"


# spec 001 / AC 20 -- `conflict` does not settle a fact: the promotion step still has work to do.
def test_a_pending_fact_with_a_recorded_collision_is_not_settled() -> None:
    fact = FactRecord(fact_id="pf-002-x", target_entity="ilan", target_field="wants", conflict=True)
    assert fact.settled is False
    assert fact.model_copy(update={"refused": "invalid_record"}).settled is True
    assert fact.model_copy(update={"status": FactStatus.REJECTED}).settled is True


# spec 001 / AC 20 -- a record that crashed before its promotion and holds a collided fact is
# resumed add-only: the fact is promoted, its `conflict` kept, and the turn ends merged.
def test_a_resumed_legacy_record_promotes_its_collided_fact_and_ends_merged(
    turn_env: TurnEnv,
) -> None:
    queue_legacy(turn_env.store, (WANTS_ID, "wants", PROPOSED_WANTS))
    legacy_record(
        turn_env.store,
        (WANTS_ID, "wants"),
        outcome=TurnOutcome.RUNNING,
        next_step=TurnStep.PROMOTE,
    )

    record = turn_env.resume(FakeModelClient(), "002-1")

    assert record.outcome is TurnOutcome.MERGED
    [fact] = record.facts
    assert fact.status is FactStatus.PROMOTED
    assert fact.changed is True
    assert ilan(turn_env.store).wants == f"{CANON_WANTS}; {PROPOSED_WANTS}"
    entry = queued(turn_env.store, WANTS_ID)
    assert entry.status is FactStatus.PROMOTED
    assert (entry.conflict, entry.existing_value) == (True, CANON_WANTS), "carried over as it was"


# --- FR-TURN-08: a human's rulings on a record written before promotion was add-only ------------


def awaiting(store: Store, *facts: tuple[str, str, str]) -> TurnRecord:
    queue_legacy(store, *facts)
    return legacy_record(
        store,
        *((identifier, field) for identifier, field, _ in facts),
        outcome=TurnOutcome.AWAITING_RULING,
        next_step=TurnStep.DONE,
    )


def one_collision(store: Store) -> TurnRecord:
    return awaiting(store, (WANTS_ID, "wants", PROPOSED_WANTS))


def two_collisions(store: Store) -> TurnRecord:
    """A record with two collisions of ilan's dossier left pending: `wants` and `needs`."""
    return awaiting(
        store, (WANTS_ID, "wants", PROPOSED_WANTS), (NEEDS_ID, "needs", PROPOSED_NEEDS)
    )


# spec 001 / FR-TURN-08, FR-OPS-07 -- accept writes the payload over the value, reconciles, and
# the turn is merged.
def test_accepting_a_legacy_collision_promotes_it_and_merges_the_turn(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    use(fixture_client, FakeModelClient())
    one_collision(fixture_store)

    response = fixture_client.post(
        "/agents/turns/002-1/rulings",
        json=rulings(WANTS_ID, RulingKind.ACCEPT),
        headers=HUMAN_CANONISER,
    )

    assert response.status_code == 200
    ruled = TurnRecord.model_validate(response.json())
    assert ruled.outcome is TurnOutcome.MERGED
    [settled] = ruled.facts
    assert settled.status is FactStatus.PROMOTED
    assert settled.ruling is RulingKind.ACCEPT
    assert settled.changed is True
    assert "002" in settled.reconciled_scenes, "reconciled on accept (FR-TURN-04)"
    assert ilan(fixture_store).wants == PROPOSED_WANTS
    entry = queued(fixture_store, WANTS_ID)
    assert entry.status is FactStatus.PROMOTED
    assert entry.ruling is not None
    assert entry.ruling.by == "human"
    lines = fixture_store.provenance(path=ILAN)
    assert [(line.role, line.actor, line.turn) for line in lines] == [
        (AgentRole.CANONISER, Actor.HUMAN, "002-1")
    ]


# spec 001 / FR-TURN-08 -- reject marks the fact rejected, leaves canon as it was, and merges.
def test_rejecting_a_legacy_collision_marks_it_and_merges_the_turn(turn_env: TurnEnv) -> None:
    record = one_collision(turn_env.store)

    ruled = turn.apply_rulings(
        turn_env.store,
        record.id,
        [RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.REJECT, reason="Not canon.")],
        role=AgentRole.CANONISER,
        actor=Actor.HUMAN,
    )

    assert ruled.outcome is TurnOutcome.MERGED
    [settled] = ruled.facts
    assert settled.status is FactStatus.REJECTED
    assert settled.ruling is RulingKind.REJECT
    assert settled.reconciled_scenes == []
    assert ilan(turn_env.store).wants == CANON_WANTS


# spec 001 / AC 13, FR-TURN-08, FR-OPS-07 -- only a human under the canoniser rules, and nothing
# lands otherwise.
@pytest.mark.parametrize(
    "headers",
    [{"X-Agent-Role": "canoniser"}, {"X-Agent-Role": "writer", "X-Actor": "human"}],
    ids=["agent-actor", "writer-role"],
)
def test_a_ruling_needs_the_canoniser_and_a_human(
    fixture_client: TestClient, fixture_store: Store, headers: dict[str, str]
) -> None:
    use(fixture_client, FakeModelClient())
    one_collision(fixture_store)
    before = fixture_store.read_raw(paths.PROPOSED)

    response = fixture_client.post(
        "/agents/turns/002-1/rulings",
        json=rulings(WANTS_ID, RulingKind.ACCEPT),
        headers=headers,
    )

    assert response.status_code == 403
    assert fixture_store.read_raw(paths.PROPOSED) == before
    assert fixture_store.turn_records()[0].outcome is TurnOutcome.AWAITING_RULING
    assert not (fixture_store.index_dir / "turn.lock").exists()


# spec 001 / AC 13, FR-TURN-08 -- a fact that is not one of the turn's collisions is a 404, an
# agent is refused, and a turn that is not awaiting a ruling a 409; none applies anything.
def test_rulings_are_checked_before_any_lands(turn_env: TurnEnv) -> None:
    record = one_collision(turn_env.store)
    store = turn_env.store
    before = store.read_raw(paths.PROPOSED)

    with pytest.raises(NotFound):
        turn.apply_rulings(
            store,
            record.id,
            [
                RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.ACCEPT, reason="Yes."),
                RulingRequest(fact_id="pf_001", ruling=RulingKind.ACCEPT, reason="Yes."),
            ],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )
    assert store.read_raw(paths.PROPOSED) == before
    with pytest.raises(PermissionDenied):
        turn.apply_rulings(
            store,
            record.id,
            [RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.ACCEPT, reason="Yes.")],
            role=AgentRole.CANONISER,
            actor=Actor.AGENT,
        )
    assert store.read_raw(paths.PROPOSED) == before

    merged = turn_env.run(scripted("happy_002"), "006")
    with pytest.raises(TurnLocked):
        turn.apply_rulings(
            store,
            merged.id,
            [RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.ACCEPT, reason="Yes.")],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )


# spec 001 / FR-TURN-08 -- rulings on a turn that does not exist are a 404 over HTTP.
def test_rulings_on_a_missing_turn_are_404(fixture_client: TestClient) -> None:
    use(fixture_client, FakeModelClient())
    response = fixture_client.post(
        "/agents/turns/002-9/rulings",
        json=rulings("pf-002-x", RulingKind.ACCEPT),
        headers=HUMAN_CANONISER,
    )
    assert response.status_code == 404


# spec 001 / FR-TURN-08 -- the turn moves to merged only when no collision remains: a ruling on
# one of two leaves it awaiting the other.
def test_the_turn_stays_awaiting_until_every_collision_is_ruled(turn_env: TurnEnv) -> None:
    record = two_collisions(turn_env.store)
    wants, needs = record.facts
    assert wants.conflict and needs.conflict

    def rule(fact_id: str) -> TurnRecord:
        return turn.apply_rulings(
            turn_env.store,
            record.id,
            [RulingRequest(fact_id=fact_id, ruling=RulingKind.REJECT, reason="Not canon.")],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )

    first = rule(wants.fact_id)
    assert first.outcome is TurnOutcome.AWAITING_RULING
    assert first.ended_at == record.ended_at, "not merged, so not re-ended"
    assert records.load(turn_env.store, record.id).outcome is TurnOutcome.AWAITING_RULING
    assert rule(needs.fact_id).outcome is TurnOutcome.MERGED


# spec 001 / FR-OPS-07 -- a batch with an empty reason is refused before any of its rulings
# lands: the reason is the record of why, and a batch is applied whole or not at all.
def test_a_batch_with_a_blank_reason_applies_nothing(turn_env: TurnEnv) -> None:
    record = two_collisions(turn_env.store)
    before = turn_env.store.read_raw(paths.PROPOSED)

    with pytest.raises(InvalidRecord, match="reason"):
        turn.apply_rulings(
            turn_env.store,
            record.id,
            [
                RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.ACCEPT, reason="Yes."),
                RulingRequest(fact_id=NEEDS_ID, ruling=RulingKind.REJECT, reason="   "),
            ],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )

    assert turn_env.store.read_raw(paths.PROPOSED) == before
    assert ilan(turn_env.store).wants == CANON_WANTS
    assert records.load(turn_env.store, record.id).outcome is TurnOutcome.AWAITING_RULING


# spec 001 / FR-TURN-08 -- a collided fact a later add-only promotion settled is caught before
# the first ruling lands, so the batch is still applied whole or not at all.
def test_a_batch_naming_a_fact_settled_meanwhile_applies_nothing(turn_env: TurnEnv) -> None:
    record = two_collisions(turn_env.store)
    promoted = ledger_service.promote(
        turn_env.store, NEEDS_ID, role=AgentRole.CANONISER, actor=Actor.AGENT
    )
    assert promoted.fact.status is FactStatus.PROMOTED
    before = turn_env.store.read_raw(paths.PROPOSED)
    dossier = turn_env.store.read_raw(ILAN)

    with pytest.raises(InvalidRecord, match="no longer pending"):
        turn.apply_rulings(
            turn_env.store,
            record.id,
            [
                RulingRequest(fact_id=WANTS_ID, ruling=RulingKind.ACCEPT, reason="Yes."),
                RulingRequest(fact_id=NEEDS_ID, ruling=RulingKind.REJECT, reason="No."),
            ],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )

    assert turn_env.store.read_raw(paths.PROPOSED) == before
    assert turn_env.store.read_raw(ILAN) == dossier
    assert records.load(turn_env.store, record.id).outcome is TurnOutcome.AWAITING_RULING
