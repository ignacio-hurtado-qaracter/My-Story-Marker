"""Plan step 18 -- AC 20: a collision ends the turn `awaiting_ruling`; a human's ruling ends it.

`scripts/collision_002.yaml` has the canoniser extract an assertion about ilan's `wants`, which
canon already holds with a different value. `promote` escalates rather than overwrite (FR-OPS-06),
so the turn ends `awaiting_ruling` with the collision on the record and canon untouched. Then
`POST /agents/turns/{id}/rulings`, under the canoniser with `X-Actor: human` (FR-TURN-08):
`accept` promotes despite the collision and reconciles the target, `reject` marks the fact
rejected, and either way the turn moves to `merged`. While the ruling is pending, a second turn
on the scene is refused with a 409 (FR-TURN-05).
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
    FactStatus,
    ProposedFactDraft,
    ProposedFile,
    RulingKind,
    TurnOutcome,
    TurnRecord,
)
from app.commons.stores import Store, paths

HUMAN_CANONISER = {"X-Agent-Role": "canoniser", "X-Actor": "human"}
CANON_WANTS = "to be left alone with the certification he still has"
PROPOSED_WANTS = "nothing from the co-op but the way back up"


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def ilan_wants(store: Store) -> str:
    return store.read(paths.cast_file("ilan", "dossier"), Character).wants


def collided(turn_env: TurnEnv) -> TurnRecord:
    record = turn_env.run(scripted("collision_002"))
    assert record.outcome is TurnOutcome.AWAITING_RULING
    return record


def rulings(fact_id: str, ruling: RulingKind) -> list[dict[str, str]]:
    return [{"fact_id": fact_id, "ruling": ruling.value, "reason": "The ruling of the editor."}]


# spec 001 / AC 20 -- a colliding extraction ends the turn awaiting a ruling; canon is untouched.
def test_a_colliding_extraction_ends_the_turn_awaiting_a_ruling(turn_env: TurnEnv) -> None:
    record = collided(turn_env)

    [fact] = record.facts
    assert (fact.target_entity, fact.target_field) == ("ilan", "wants")
    assert fact.conflict is True
    assert fact.status is FactStatus.PENDING
    assert fact.proposed_by == ["canoniser"]
    assert ilan_wants(turn_env.store) == CANON_WANTS
    [queued] = [
        entry
        for entry in turn_env.store.read(paths.PROPOSED, ProposedFile).proposed
        if entry.id == fact.fact_id
    ]
    assert queued.conflict is True
    assert queued.existing_value == CANON_WANTS
    assert queued.status is FactStatus.PENDING


# spec 001 / AC 20, FR-TURN-08 -- accept promotes despite the collision and the turn is merged.
def test_accepting_the_collision_promotes_it_and_merges_the_turn(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    use(fixture_client, scripted("collision_002"))
    events = sse_events(fixture_client.post("/agents/turns", json={"scene_id": "002"}).text)
    assert events[-1][1]["outcome"] == "awaiting_ruling"
    record = TurnRecord.model_validate(fixture_client.get("/agents/turns/002-1").json())
    [fact] = record.facts

    response = fixture_client.post(
        "/agents/turns/002-1/rulings",
        json=rulings(fact.fact_id, RulingKind.ACCEPT),
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
    assert ilan_wants(fixture_store) == PROPOSED_WANTS
    [queued] = [
        entry
        for entry in fixture_store.read(paths.PROPOSED, ProposedFile).proposed
        if entry.id == fact.fact_id
    ]
    assert queued.status is FactStatus.PROMOTED
    assert queued.ruling is not None
    assert queued.ruling.by == "human"
    lines = fixture_store.provenance(path=paths.cast_file("ilan", "dossier"))
    assert [(line.role, line.actor, line.turn) for line in lines] == [
        (AgentRole.CANONISER, Actor.HUMAN, "002-1")
    ]


# spec 001 / AC 20 -- reject marks the fact rejected, leaves canon as it was, and merges the turn.
def test_rejecting_the_collision_marks_it_and_merges_the_turn(turn_env: TurnEnv) -> None:
    record = collided(turn_env)
    [fact] = record.facts

    ruled = turn.apply_rulings(
        turn_env.store,
        record.id,
        [RulingRequest(fact_id=fact.fact_id, ruling=RulingKind.REJECT, reason="Not canon.")],
        role=AgentRole.CANONISER,
        actor=Actor.HUMAN,
    )

    assert ruled.outcome is TurnOutcome.MERGED
    [settled] = ruled.facts
    assert settled.status is FactStatus.REJECTED
    assert settled.ruling is RulingKind.REJECT
    assert settled.reconciled_scenes == []
    assert ilan_wants(turn_env.store) == CANON_WANTS


# spec 001 / AC 20, FR-TURN-05 -- a second turn on the scene is refused while the ruling is
# pending, and allowed once it is given.
def test_a_second_turn_on_the_scene_is_409_while_a_ruling_is_pending(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    use(fixture_client, scripted("collision_002"))
    fixture_client.post("/agents/turns", json={"scene_id": "002"})
    [record] = fixture_store.turn_records()
    [fact] = record.facts

    use(fixture_client, scripted("happy_002"))
    refused = fixture_client.post("/agents/turns", json={"scene_id": "002"})
    assert refused.status_code == 409
    assert refused.json()["error"] == "turn_locked"
    assert fact.fact_id in refused.json()["detail"]
    assert [entry.id for entry in fixture_store.turn_records()] == ["002-1"]

    other_scene = fixture_client.post("/agents/turns", json={"scene_id": "006"})
    assert other_scene.status_code == 200, "the pending ruling holds its own scene only"

    fixture_client.post(
        "/agents/turns/002-1/rulings",
        json=rulings(fact.fact_id, RulingKind.REJECT),
        headers=HUMAN_CANONISER,
    )
    use(fixture_client, scripted("happy_002"))
    again = fixture_client.post("/agents/turns", json={"scene_id": "002"})
    assert again.status_code == 200
    assert sse_events(again.text)[-1][1]["turn_id"] == "002-2"


# spec 001 / FR-TURN-08, FR-OPS-07 -- only a human under the canoniser rules, and nothing lands
# otherwise.
@pytest.mark.parametrize(
    "headers",
    [{"X-Agent-Role": "canoniser"}, {"X-Agent-Role": "writer", "X-Actor": "human"}],
    ids=["agent-actor", "writer-role"],
)
def test_a_ruling_needs_the_canoniser_and_a_human(
    fixture_client: TestClient, fixture_store: Store, headers: dict[str, str]
) -> None:
    use(fixture_client, scripted("collision_002"))
    fixture_client.post("/agents/turns", json={"scene_id": "002"})
    [record] = fixture_store.turn_records()
    [fact] = record.facts
    before = fixture_store.read_raw(paths.PROPOSED)

    response = fixture_client.post(
        "/agents/turns/002-1/rulings",
        json=rulings(fact.fact_id, RulingKind.ACCEPT),
        headers=headers,
    )

    assert response.status_code == 403
    assert fixture_store.read_raw(paths.PROPOSED) == before
    assert fixture_store.turn_records()[0].outcome is TurnOutcome.AWAITING_RULING
    assert not (fixture_store.index_dir / "turn.lock").exists()


# spec 001 / FR-TURN-08 -- a fact that is not one of the turn's collisions is a 404, and a turn
# that is not awaiting a ruling a 409; neither applies anything.
def test_rulings_are_checked_before_any_lands(turn_env: TurnEnv) -> None:
    record = collided(turn_env)
    [fact] = record.facts
    store = turn_env.store
    before = store.read_raw(paths.PROPOSED)

    with pytest.raises(NotFound):
        turn.apply_rulings(
            store,
            record.id,
            [
                RulingRequest(fact_id=fact.fact_id, ruling=RulingKind.ACCEPT, reason="Yes."),
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
            [RulingRequest(fact_id=fact.fact_id, ruling=RulingKind.ACCEPT, reason="Yes.")],
            role=AgentRole.CANONISER,
            actor=Actor.AGENT,
        )
    assert store.read_raw(paths.PROPOSED) == before

    merged = turn_env.run(scripted("happy_002"), "006")
    with pytest.raises(TurnLocked):
        turn.apply_rulings(
            store,
            merged.id,
            [RulingRequest(fact_id=fact.fact_id, ruling=RulingKind.ACCEPT, reason="Yes.")],
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


def two_collisions(turn_env: TurnEnv) -> TurnRecord:
    """A turn whose extraction collides twice with ilan's dossier: `wants` and `needs`."""
    script = load_script("collision_002")
    script[AgentRole.CANONISER] = [
        Reply.of(
            ExtractOutput(
                facts=[
                    ProposedFactDraft(
                        target_entity="ilan",
                        target_field="wants",
                        payload=PROPOSED_WANTS,
                        evidence="wanted nothing from her but the way back up",
                    ),
                    ProposedFactDraft(
                        target_entity="ilan",
                        target_field="needs",
                        payload="the way back up",
                        evidence="the way back up",
                    ),
                ]
            )
        )
    ]
    record = turn_env.run(FakeModelClient(script))
    assert record.outcome is TurnOutcome.AWAITING_RULING
    return record


# spec 001 / AC 20, FR-TURN-08 -- the turn moves to merged only when no collision remains: a
# ruling on one of two leaves it awaiting the other.
def test_the_turn_stays_awaiting_until_every_collision_is_ruled(turn_env: TurnEnv) -> None:
    record = two_collisions(turn_env)
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
    script = load_script("collision_002")
    script[AgentRole.CANONISER] = [
        Reply.of(
            ExtractOutput(
                facts=[
                    ProposedFactDraft(
                        target_entity="ilan",
                        target_field="wants",
                        payload=PROPOSED_WANTS,
                        evidence="wanted nothing from her but the way back up",
                    ),
                    ProposedFactDraft(
                        target_entity="ilan",
                        target_field="needs",
                        payload="the way back up",
                        evidence="the way back up",
                    ),
                ]
            )
        )
    ]
    record = turn_env.run(FakeModelClient(script))
    assert record.outcome is TurnOutcome.AWAITING_RULING
    wants, needs = record.facts
    before = turn_env.store.read_raw(paths.PROPOSED)

    with pytest.raises(InvalidRecord, match="reason"):
        turn.apply_rulings(
            turn_env.store,
            record.id,
            [
                RulingRequest(fact_id=wants.fact_id, ruling=RulingKind.ACCEPT, reason="Yes."),
                RulingRequest(fact_id=needs.fact_id, ruling=RulingKind.REJECT, reason="   "),
            ],
            role=AgentRole.CANONISER,
            actor=Actor.HUMAN,
        )

    assert turn_env.store.read_raw(paths.PROPOSED) == before
    assert ilan_wants(turn_env.store) == CANON_WANTS
    assert records.load(turn_env.store, record.id).outcome is TurnOutcome.AWAITING_RULING
