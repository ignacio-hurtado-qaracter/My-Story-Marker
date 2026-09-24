"""AC 13 - `promote` updates the record on a non-conflicting fact; on a collision it returns an
`Escalation`, changes nothing in canon or cast, and sets `conflict`. No code path under
`ledger/` or `agents/` resolves a collision without a `rule` call carrying `actor: human`.

Measured with a hash of every file in the tree before and after each call, because "changes
nothing" is a claim about bytes, and a status code or a returned object cannot prove it.

The fixture values these tests lean on are named in `tests/fixtures/repo/README.md`: the
queued facts `pf_001` (pending, vance's competences) and `pf_002` (already rejected), and the
two invented facts of Draft A - F1, the throat releasing only from the vault side, aimed at
`pump_vault.geometry`, which is already non-empty and so must collide; and F2, the four-hour
indemnity cut, aimed at `ax_cold_soak.exceptions`, which is an empty list and so must not.
"""

from __future__ import annotations

import hashlib
import inspect

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.canon import service as canon_service
from app.canon.models import Axiom, Location, Technology
from app.cast import service as cast_service
from app.cast.models import Character
from app.commons.errors import InvalidRecord, NotFound, PermissionDenied
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import FactStatus, ProposedFact, RulingKind
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import service
from app.ledger.models import Escalation, Promoted
from app.ledger.service import ProposedAppend

CANONISER = AgentRole.CANONISER
F1_PAYLOAD = "the throat releases only from the vault side, never from the gallery"
F2_PAYLOAD = "cut to four hours on a co-op indemnity dive; the lung lining goes first"
PUMP_VAULT = paths.canon_entity("locations", "pump_vault")
COLD_SOAK = paths.canon_entity("axioms", "ax_cold_soak")
VANCE = paths.cast_file("vance", "dossier")


def _hashes(store: Store) -> dict[str, str]:
    """Every file under the store root, by relative path, to its SHA-256 - bytes, not text, so
    a change a text read would normalise away still counts."""
    root = store.root
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}


def _fact(identifier: str, entity: str, field: str, payload: str) -> ProposedFact:
    return ProposedFact(
        id=identifier,
        extracted_from="manuscript/002.md",
        target_entity=entity,
        target_field=field,
        payload=payload,
        source_scene="002",
    )


def _queue(store: Store, *facts: ProposedFact) -> None:
    """Add facts the way a turn does: appended by the canoniser through the IF-04 route's
    service, never by editing the file."""
    service.append_proposed(
        store, ProposedAppend(facts=list(facts)), role=CANONISER, actor=Actor.AGENT
    )


def _on_disk(store: Store, fact_id: str) -> ProposedFact:
    return next(fact for fact in service.proposed(store).proposed if fact.id == fact_id)


def _promote(store: Store, fact_id: str) -> Promoted | Escalation:
    return service.promote(store, fact_id, role=CANONISER, actor=Actor.AGENT)


def _written(writes: list[ProvenanceRecord]) -> list[str]:
    return [line.path for line in writes]


# --------------------------------------------------------------------------------------
# Non-conflicting facts: the record changes, the fact is promoted
# --------------------------------------------------------------------------------------


def test_list_field_grows_by_the_payload(fixture_store: Store) -> None:
    # spec 001 / AC 13 - non-conflict: record changed, status promoted
    before = _hashes(fixture_store)
    result = _promote(fixture_store, "pf_001")

    assert isinstance(result, Promoted)
    assert result.changed is True
    assert result.fact.status is FactStatus.PROMOTED
    assert result.fact.conflict is False
    assert result.target_path == VANCE
    assert _written(result.writes) == [VANCE, paths.PROPOSED]
    assert {line.role for line in result.writes} == {CANONISER}

    competences = cast_service.read_character(fixture_store, "vance").competences
    assert competences[-1] == "certified for unaccompanied vault work since the shaft collapse"
    assert len(competences) == 4
    assert _on_disk(fixture_store, "pf_001").status is FactStatus.PROMOTED
    assert _changed(before, _hashes(fixture_store)) == {VANCE, paths.PROPOSED}


def test_invented_fact_f2_fills_an_empty_list(fixture_store: Store) -> None:
    # spec 001 / AC 13 - F2 of the fixture README: `exceptions: []` has nothing to collide with
    _queue(fixture_store, _fact("pf_f2", "ax_cold_soak", "exceptions", F2_PAYLOAD))
    result = _promote(fixture_store, "pf_f2")

    assert isinstance(result, Promoted)
    assert result.changed is True
    axiom = canon_service.entity(fixture_store, "axioms", "ax_cold_soak", Axiom)
    assert axiom.exceptions == [F2_PAYLOAD]


def test_list_payload_already_present_settles_without_touching_canon(fixture_store: Store) -> None:
    # spec 001 / AC 13 - canon grows additively; a present item is a no-op, not a collision
    held = cast_service.read_character(fixture_store, "ilan").competences[0]
    _queue(fixture_store, _fact("pf_dup", "ilan", "competences", held))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_dup")

    assert isinstance(result, Promoted)
    assert result.changed is False
    assert result.fact.status is FactStatus.PROMOTED
    assert _written(result.writes) == [paths.PROPOSED]
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_empty_scalar_is_set(fixture_store: Store) -> None:
    # spec 001 / AC 13 - an empty scalar field takes the payload
    sonar = canon_service.entity(fixture_store, "technology", "te_hand_sonar", Technology)
    fixture_store.write(
        paths.canon_entity("technology", "te_hand_sonar"),
        sonar.model_copy(update={"failure_mode": ""}),
        role=AgentRole.WORLD_BUILDER,
    )
    _queue(
        fixture_store,
        _fact("pf_sonar", "te_hand_sonar", "failure_mode", "it lies in a working shelf"),
    )

    result = _promote(fixture_store, "pf_sonar")

    assert isinstance(result, Promoted)
    assert result.changed is True
    reread = canon_service.entity(fixture_store, "technology", "te_hand_sonar", Technology)
    assert reread.failure_mode == "it lies in a working shelf"


def test_equal_scalar_is_promoted_with_no_change(fixture_store: Store) -> None:
    # spec 001 / AC 13 - the target already says exactly this
    geometry = canon_service.entity(fixture_store, "locations", "pump_vault", Location).geometry
    _queue(fixture_store, _fact("pf_same", "pump_vault", "geometry", geometry))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_same")

    assert isinstance(result, Promoted)
    assert result.changed is False
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_mapping_key_absent_is_added_and_same_value_is_a_no_op(fixture_store: Store) -> None:
    # spec 001 / AC 13 - a mapping grows by key; the same value is not a collision
    lungs = cast_service.read_character(fixture_store, "ilan").immutable_physical["lungs"]
    _queue(
        fixture_store,
        _fact("pf_eyes", "ilan", "immutable_physical", "eyes: grey, brine-scarred at the rims"),
        _fact("pf_lungs_same", "ilan", "immutable_physical", f"lungs: {lungs}"),
    )

    added = _promote(fixture_store, "pf_eyes")
    same = _promote(fixture_store, "pf_lungs_same")

    assert isinstance(added, Promoted)
    assert added.changed is True
    assert isinstance(same, Promoted)
    assert same.changed is False
    body = cast_service.read_character(fixture_store, "ilan").immutable_physical
    assert body["eyes"] == "grey, brine-scarred at the rims"
    assert body["lungs"] == lungs


# --------------------------------------------------------------------------------------
# Collisions: escalated, canon and cast byte-identical, conflict recorded
# --------------------------------------------------------------------------------------


def test_scalar_collision_escalates_and_leaves_canon_and_cast_byte_identical(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - conflict -> Escalation, tree byte-identical, conflict=True
    geometry = canon_service.entity(fixture_store, "locations", "pump_vault", Location).geometry
    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_f1")

    assert isinstance(result, Escalation)
    assert result.existing_value == geometry
    assert result.payload == F1_PAYLOAD
    assert result.target_path == PUMP_VAULT
    assert _written(result.writes) == [paths.PROPOSED]
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}

    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.conflict is True
    assert recorded.existing_value == geometry
    assert recorded.status is FactStatus.PENDING
    assert recorded.ruling is None


def test_mapping_collision_records_the_existing_key_and_value(fixture_store: Store) -> None:
    # spec 001 / AC 13 - a different value under an existing key collides
    lungs = cast_service.read_character(fixture_store, "ilan").immutable_physical["lungs"]
    _queue(fixture_store, _fact("pf_lungs", "ilan", "immutable_physical", "lungs: tolerates brine"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_lungs")

    assert isinstance(result, Escalation)
    assert result.existing_value == f"lungs: {lungs}"
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_promote_cannot_resolve_a_recorded_collision(fixture_store: Store) -> None:
    # spec 001 / AC 13 - no code path resolves a collision without a human `rule`
    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    _promote(fixture_store, "pf_f1")
    before = _hashes(fixture_store)

    again = _promote(fixture_store, "pf_f1")

    assert isinstance(again, Escalation)
    assert again.writes == []
    assert _hashes(fixture_store) == before


def test_a_collision_stands_even_if_canon_later_agrees(fixture_store: Store) -> None:
    # spec 001 / AC 13 - `conflict` is never cleared by code, only by a ruling
    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    _promote(fixture_store, "pf_f1")
    vault = canon_service.entity(fixture_store, "locations", "pump_vault", Location)
    fixture_store.write(
        PUMP_VAULT, vault.model_copy(update={"geometry": ""}), role=AgentRole.WORLD_BUILDER
    )

    result = _promote(fixture_store, "pf_f1")

    assert isinstance(result, Escalation)
    assert _on_disk(fixture_store, "pf_f1").status is FactStatus.PENDING


# --------------------------------------------------------------------------------------
# Refusals: nothing promotable, nothing written
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fact", "field"),
    [
        (_fact("pf_x", "nowhere_ship", "geometry", "a hull"), "target_entity"),
        (_fact("pf_x", "pump_vault", "colour", "black"), "target_field"),
        (_fact("pf_x", "hi_exchanger_fire", "date", "-400"), "target_field"),
        (_fact("pf_x", "ilan", "arc", "broken"), "target_field"),
        (_fact("pf_x", "pump_vault", "id", "vault"), "target_field"),
        (_fact("pf_x", "pump_vault", "parent", "Not An Id"), "payload"),
        (_fact("pf_x", "ilan", "immutable_physical", "no colon here"), "payload"),
    ],
    ids=[
        "entity-missing",
        "field-missing",
        "integer-field",
        "list-of-records",
        "identifier",
        "payload-fails-field",
        "mapping-without-key",
    ],
)
def test_unpromotable_fact_is_refused_and_nothing_is_written(
    fixture_store: Store, fact: ProposedFact, field: str
) -> None:
    # spec 001 / AC 13 - a target that does not exist is not promoted, and not escalated
    _queue(fixture_store, fact)
    index = len(service.proposed(fixture_store).proposed) - 1
    before = _hashes(fixture_store)

    with pytest.raises(InvalidRecord) as refused:
        _promote(fixture_store, "pf_x")

    assert refused.value.context["file"] == paths.PROPOSED
    assert refused.value.context["field"] == f"proposed.{index}.{field}"
    assert _hashes(fixture_store) == before


def test_settled_fact_is_refused(fixture_store: Store) -> None:
    # spec 001 / AC 13 - pf_002 is already rejected (fixture README); a ruling is not undone
    before = _hashes(fixture_store)
    with pytest.raises(InvalidRecord) as refused:
        _promote(fixture_store, "pf_002")
    assert refused.value.context["field"] == "proposed.1.status"
    assert _hashes(fixture_store) == before


def test_unknown_fact_is_not_found(fixture_store: Store) -> None:
    # spec 001 / AC 13
    with pytest.raises(NotFound):
        _promote(fixture_store, "pf_999")


@pytest.mark.parametrize("role", [role for role in AgentRole if role is not CANONISER])
def test_promote_runs_under_the_canoniser_only(fixture_store: Store, role: AgentRole) -> None:
    # spec 001 / AC 13 - FR-OPS-06 "under the canoniser role"; refused before any byte moves
    before = _hashes(fixture_store)
    with pytest.raises(PermissionDenied):
        service.promote(fixture_store, "pf_001", role=role, actor=Actor.AGENT)
    assert _hashes(fixture_store) == before


# --------------------------------------------------------------------------------------
# rule: the human gate
# --------------------------------------------------------------------------------------


def _collided(store: Store) -> str:
    """Queue F1 and let `promote` record its collision; returns the original geometry."""
    geometry = canon_service.entity(store, "locations", "pump_vault", Location).geometry
    _queue(store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    assert isinstance(_promote(store, "pf_f1"), Escalation)
    return geometry


def test_accept_promotes_despite_the_collision(fixture_store: Store) -> None:
    # spec 001 / AC 13 - `rule` with actor human is the one path that resolves a collision
    geometry = _collided(fixture_store)
    before = _hashes(fixture_store)

    applied = service.rule(
        fixture_store,
        "pf_f1",
        RulingKind.ACCEPT,
        "the draft is right",
        role=CANONISER,
        actor=Actor.HUMAN,
    )

    assert applied.changed is True
    assert applied.target_path == PUMP_VAULT
    assert _written(applied.writes) == [PUMP_VAULT, paths.PROPOSED]
    assert {line.actor for line in applied.writes} == {Actor.HUMAN}
    assert _changed(before, _hashes(fixture_store)) == {PUMP_VAULT, paths.PROPOSED}
    assert (
        canon_service.entity(fixture_store, "locations", "pump_vault", Location).geometry
        == F1_PAYLOAD
    )

    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.status is FactStatus.PROMOTED
    assert recorded.conflict is True
    assert recorded.existing_value == geometry
    assert recorded.ruling is not None
    assert recorded.ruling.ruling is RulingKind.ACCEPT
    assert recorded.ruling.by == "human"
    assert recorded.ruling.reason == "the draft is right"


def test_reject_marks_the_fact_rejected_and_leaves_canon(fixture_store: Store) -> None:
    # spec 001 / AC 13 - FR-OPS-07 reject; canon and cast untouched
    _collided(fixture_store)
    before = _hashes(fixture_store)

    applied = service.rule(
        fixture_store, "pf_f1", RulingKind.REJECT, "canon stands", role=CANONISER, actor=Actor.HUMAN
    )

    assert applied.target_path is None
    assert applied.changed is False
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}
    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.status is FactStatus.REJECTED
    assert recorded.ruling is not None
    assert recorded.ruling.ruling is RulingKind.REJECT
    assert recorded.ruling.reason == "canon stands"


def test_reject_does_not_need_the_target_to_exist(fixture_store: Store) -> None:
    # spec 001 / AC 13 - a fact about an entity nobody created can still be turned down
    _queue(fixture_store, _fact("pf_ghost", "nowhere_ship", "geometry", "a hull"))
    applied = service.rule(
        fixture_store,
        "pf_ghost",
        RulingKind.REJECT,
        "no such ship",
        role=CANONISER,
        actor=Actor.HUMAN,
    )
    assert applied.fact.status is FactStatus.REJECTED


def test_accept_of_a_fact_promote_never_saw_records_what_it_overwrote(fixture_store: Store) -> None:
    # spec 001 / AC 13 - the overwritten value stays readable on the fact
    geometry = canon_service.entity(fixture_store, "locations", "pump_vault", Location).geometry
    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))

    service.rule(
        fixture_store, "pf_f1", RulingKind.ACCEPT, "decided", role=CANONISER, actor=Actor.HUMAN
    )

    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.conflict is True
    assert recorded.existing_value == geometry


@pytest.mark.parametrize("ruling", list(RulingKind))
def test_an_agent_may_not_rule(fixture_store: Store, ruling: RulingKind) -> None:
    # spec 001 / AC 13 - refused for actor agent, and nothing moves, ledger included
    _collided(fixture_store)
    before = _hashes(fixture_store)

    with pytest.raises(PermissionDenied):
        service.rule(fixture_store, "pf_f1", ruling, "I decided", role=CANONISER, actor=Actor.AGENT)

    assert _hashes(fixture_store) == before
    assert _on_disk(fixture_store, "pf_f1").status is FactStatus.PENDING


def test_a_human_under_another_role_may_not_rule(fixture_store: Store) -> None:
    # spec 001 / AC 13 - FR-OPS-07 "under the canoniser role with actor: human"
    _collided(fixture_store)
    before = _hashes(fixture_store)
    with pytest.raises(PermissionDenied):
        service.rule(
            fixture_store, "pf_f1", RulingKind.ACCEPT, "x", role=AgentRole.WRITER, actor=Actor.HUMAN
        )
    assert _hashes(fixture_store) == before


def test_a_settled_fact_cannot_be_ruled_on_again(fixture_store: Store) -> None:
    # spec 001 / AC 13
    with pytest.raises(InvalidRecord):
        service.rule(
            fixture_store, "pf_002", RulingKind.ACCEPT, "x", role=CANONISER, actor=Actor.HUMAN
        )


# --------------------------------------------------------------------------------------
# Canon is written only from inside `promote` and `rule`
# --------------------------------------------------------------------------------------


def test_every_canon_or_cast_write_comes_from_promote_or_rule(
    fixture_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    # spec 001 / AC 13 - the runtime half of the static rule: it follows variables, which the
    # semgrep pattern and its AST mirror (literal paths only) cannot
    callers: list[tuple[str, str]] = []
    real_write = Store.write

    def recording_write(
        self: Store,
        relative: str,
        record: BaseModel,
        *,
        role: AgentRole,
        actor: Actor = Actor.AGENT,
        scene: str | None = None,
        turn: str | None = None,
    ) -> ProvenanceRecord:
        frame = inspect.currentframe()
        caller = frame.f_back.f_code.co_name if frame and frame.f_back else "?"
        if relative.startswith((paths.CANON + "/", paths.CAST + "/")):
            callers.append((caller, relative))
        return real_write(self, relative, record, role=role, actor=actor, scene=scene, turn=turn)

    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    _queue(fixture_store, _fact("pf_f2", "ax_cold_soak", "exceptions", F2_PAYLOAD))
    monkeypatch.setattr(Store, "write", recording_write)

    _promote(fixture_store, "pf_001")
    _promote(fixture_store, "pf_f2")
    _promote(fixture_store, "pf_f1")
    service.rule(
        fixture_store, "pf_f1", RulingKind.ACCEPT, "decided", role=CANONISER, actor=Actor.HUMAN
    )

    assert callers == [("promote", VANCE), ("promote", COLD_SOAK), ("rule", PUMP_VAULT)]


# --------------------------------------------------------------------------------------
# Over HTTP (IF-05)
# --------------------------------------------------------------------------------------

CANONISER_AGENT = {"X-Agent-Role": "canoniser"}
CANONISER_HUMAN = {"X-Agent-Role": "canoniser", "X-Actor": "human"}


def test_http_promote_answers_promoted(fixture_client: TestClient) -> None:
    # spec 001 / AC 13
    response = fixture_client.post("/ledger/proposed/pf_001/promote", headers=CANONISER_AGENT)
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "promoted"
    assert body["changed"] is True
    assert body["fact"]["status"] == "promoted"


def test_http_collision_escalates_then_a_human_rules(fixture_client: TestClient) -> None:
    # spec 001 / AC 13 - escalation is a 200; the agent is refused; the human settles it
    fact = _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD).model_dump(mode="json")
    queued = fixture_client.post(
        "/ledger/proposed", json={"facts": [fact]}, headers=CANONISER_AGENT
    )
    assert queued.status_code == 200

    escalated = fixture_client.post("/ledger/proposed/pf_f1/promote", headers=CANONISER_AGENT)
    assert escalated.status_code == 200
    assert escalated.json()["outcome"] == "escalation"
    assert escalated.json()["fact"]["conflict"] is True

    ruling = {"ruling": "accept", "reason": "the draft is right"}
    refused = fixture_client.post(
        "/ledger/proposed/pf_f1/rule", json=ruling, headers=CANONISER_AGENT
    )
    assert refused.status_code == 403
    assert refused.json()["error"] == "permission_denied"

    accepted = fixture_client.post(
        "/ledger/proposed/pf_f1/rule", json=ruling, headers=CANONISER_HUMAN
    )
    assert accepted.status_code == 200
    assert accepted.json()["fact"]["status"] == "promoted"
    assert accepted.json()["fact"]["ruling"]["by"] == "human"


def test_http_refusals(fixture_client: TestClient) -> None:
    # spec 001 / AC 13 - IF-02 and IF-07 on the new routes
    assert fixture_client.post("/ledger/proposed/pf_001/promote").status_code == 400
    writer = fixture_client.post(
        "/ledger/proposed/pf_001/promote", headers={"X-Agent-Role": "writer"}
    )
    assert writer.status_code == 403
    assert (
        fixture_client.post("/ledger/proposed/PF-1/promote", headers=CANONISER_AGENT).status_code
        == 422
    )
    assert (
        fixture_client.post("/ledger/proposed/pf_999/promote", headers=CANONISER_AGENT).status_code
        == 404
    )
    settled = fixture_client.post("/ledger/proposed/pf_002/promote", headers=CANONISER_AGENT)
    assert settled.status_code == 422
    assert settled.json()["field"] == "proposed.1.status"
    empty_reason = fixture_client.post(
        "/ledger/proposed/pf_001/rule",
        json={"ruling": "reject", "reason": ""},
        headers=CANONISER_HUMAN,
    )
    assert empty_reason.status_code == 422


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"], ids=["empty", "spaces", "whitespace"])
def test_a_blank_reason_is_refused_and_nothing_is_written(
    fixture_store: Store, reason: str
) -> None:
    # spec 001 / AC 13 - a ruling without a reason is unreviewable; a direct caller (the turn's
    # rulings route, FR-TURN-08) gets the same refusal as the HTTP body, not a 500
    _collided(fixture_store)
    before = _hashes(fixture_store)
    for kind in RulingKind:
        with pytest.raises(InvalidRecord):
            service.rule(
                fixture_store, "pf_f1", kind, reason, role=CANONISER, actor=Actor.HUMAN
            )
    assert _hashes(fixture_store) == before


def test_a_blank_reason_over_http_is_a_422(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    # spec 001 / AC 13 - the request body refuses a reason made only of whitespace
    _collided(fixture_store)
    before = _hashes(fixture_store)
    response = fixture_client.post(
        "/ledger/proposed/pf_f1/rule",
        json={"ruling": "reject", "reason": "   "},
        headers={"X-Agent-Role": "canoniser", "X-Actor": "human"},
    )
    assert response.status_code == 422
    assert _hashes(fixture_store) == before


# --------------------------------------------------------------------------------------
# What a fact may target: one computation for promote and for extraction (FR-AGENT-05)
# --------------------------------------------------------------------------------------

TARGET_OF_EACH_KIND: dict[str, str] = {
    "axioms": "ax_cold_soak",
    "technology": "te_hand_sonar",
    "locations": "pump_vault",
    "factions": "kestrel_coop",
    "history": "hi_exchanger_fire",
    "cast": "vance",
}
"""One existing record per kind `promote` can write, from the fixture tree."""


def _model_of(kind: str) -> type[BaseModel]:
    return Character if kind == "cast" else canon_service.CANON_MODELS[kind]


@pytest.mark.parametrize("kind", sorted(TARGET_OF_EACH_KIND))
def test_promotable_fields_are_exactly_the_fields_promote_does_not_refuse(
    fixture_store: Store, kind: str
) -> None:
    # spec 001 / AC 27, FR-OPS-06 - every field of the record's model is tried through promote:
    # the address is refused for exactly the fields `promotable_fields` leaves out, so what the
    # canoniser is told it may target and what promote can write are the same set
    entity = TARGET_OF_EACH_KIND[kind]
    model = _model_of(kind)
    [target] = service.promotable_targets(fixture_store, [entity])
    listed = {field.attribute for field in target.fields}
    assert target.record_type == model.__name__
    assert listed, "every record kind has fields a fact can fill"

    refused_address: set[str] = set()
    for number, (attribute, info) in enumerate(model.model_fields.items()):
        name = info.alias or attribute
        shape = next((field.shape for field in target.fields if field.attribute == attribute), None)
        payload = "key: value" if shape is service.FieldShape.MAPPING else "a promoted value"
        fact_id = f"pf_shape_{number}"
        _queue(fixture_store, _fact(fact_id, entity, name, payload))
        try:
            _promote(fixture_store, fact_id)
        except InvalidRecord as refusal:
            if str(refusal.context.get("field", "")).endswith(".target_field"):
                refused_address.add(attribute)
    assert refused_address == set(model.model_fields) - listed
    assert {"id", "schema_version"} <= refused_address


def test_promotable_targets_resolve_identifiers_as_promote_does(fixture_store: Store) -> None:
    # spec 001 / AC 27, FR-OPS-06 - the order given, each once; a lexicon term (no record of its
    # own) and an unknown id are left out, because promote refuses a fact addressed to either
    targets = service.promotable_targets(
        fixture_store, ["pump_vault", "lx_soak", "vance", "no_such_entity", "pump_vault"]
    )
    assert [(target.entity, target.path, target.record_type) for target in targets] == [
        ("pump_vault", PUMP_VAULT, "Location"),
        ("vance", VANCE, "Character"),
    ]
    [location, _] = targets
    geometry = location.field("geometry")
    assert geometry is not None
    assert geometry.shape is service.FieldShape.SCALAR
    described = Location.model_fields["geometry"].description or ""
    assert geometry.meaning == " ".join(described.split())
    assert location.field("id") is None
    assert location.field("access") is None, "a list of records is not a string list"


def test_an_identifier_two_kinds_hold_is_neither_listed_nor_promoted(fixture_store: Store) -> None:
    # spec 001 / AC 27, FR-OPS-06 - an id that two record kinds both hold is ambiguous: promote
    # refuses a fact addressed to it, so the list of what a fact may target leaves it out too
    twin = fixture_store.root / paths.canon_entity("technology", "pump_vault")
    twin.write_bytes((fixture_store.root / PUMP_VAULT).read_bytes())
    listed = service.promotable_targets(fixture_store, ["pump_vault", "vance"])
    assert [target.entity for target in listed] == ["vance"]
    _queue(fixture_store, _fact("pf_twin", "pump_vault", "geometry", "a second exit"))
    with pytest.raises(InvalidRecord) as refusal:
        _promote(fixture_store, "pf_twin")
    assert str(refusal.value.context.get("field", "")).endswith(".target_entity")


def test_a_field_the_catalogue_lists_is_one_promote_writes(fixture_store: Store) -> None:
    # spec 001 / AC 27 - a listed field is promoted, not refused: the fixture's F2 address
    [axiom] = service.promotable_targets(fixture_store, ["ax_cold_soak"])
    exceptions = axiom.field("exceptions")
    assert exceptions is not None
    assert exceptions.shape is service.FieldShape.LIST
    _queue(fixture_store, _fact("pf_listed", "ax_cold_soak", exceptions.name, F2_PAYLOAD))
    assert isinstance(_promote(fixture_store, "pf_listed"), Promoted)


@pytest.mark.parametrize(
    ("payload", "split"),
    [("eyes: grey", ("eyes", "grey")), ("eyes grey", None), (": grey", None), ("eyes:", None)],
)
def test_the_mapping_payload_test_is_shared(payload: str, split: tuple[str, str] | None) -> None:
    # spec 001 / AC 27 - the canoniser checks a mapping payload with the split promote uses
    assert service.split_mapping_payload(payload) == split


# --------------------------------------------------------------------------------------
# A character's body is compared as of the fact's scene, with registered changes applied
# --------------------------------------------------------------------------------------


def _registered(store: Store, character: str, attribute: str) -> str:
    """The value the character's change register gives `attribute`, read from the fixture copy
    rather than spelt here, so the test holds for whatever the register says."""
    changes = cast_service.read_changes(store, character).changes
    return next(change.to_value for change in changes if change.attribute == attribute)


def _body_fact(identifier: str, payload: str, scene: str) -> ProposedFact:
    return _fact(identifier, "ilan", "immutable_physical", payload).model_copy(
        update={"source_scene": scene}
    )


def test_a_body_fact_equal_to_a_registered_change_is_settled_with_no_write(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13, AC 26 - the first live turn ended awaiting_ruling on a false conflict:
    # a fact restating the registered left-hand change collided with the stored base value.
    # After the change's scene the record holds the new value, so the fact agrees with it.
    changed = _registered(fixture_store, "ilan", "left_hand")
    _queue(fixture_store, _body_fact("pf_hand_now", f"left_hand: {changed}", "006"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_hand_now")

    assert isinstance(result, Promoted)
    assert result.changed is False
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_a_body_fact_restating_the_value_a_change_replaced_collides_with_the_new_one(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - the stored base value no longer holds after a registered change: a
    # fact asserting it is a collision, and the value it collides with is the as-of one, so
    # the person ruling compares the fact with what the character's body actually is.
    base = cast_service.read_character(fixture_store, "ilan").immutable_physical["left_hand"]
    changed = _registered(fixture_store, "ilan", "left_hand")
    assert base != changed
    _queue(fixture_store, _body_fact("pf_hand_old", f"left_hand: {base}", "006"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_hand_old")

    assert isinstance(result, Escalation)
    assert result.existing_value == f"left_hand: {changed}"
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}
    stored = cast_service.read_character(fixture_store, "ilan").immutable_physical
    assert stored["left_hand"] == base, "the stored map is never rewritten by a comparison"
