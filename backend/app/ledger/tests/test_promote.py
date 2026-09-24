"""AC 13 - `promote` is add-only (FR-OPS-06). It sets an empty field, appends one clause to a
filled text field, one item to a list and one new key to a mapping, and never replaces what a
record holds. What the record already specifies -- a different identifier or name, a key it
already has with another value, a body key a registered change names -- is not applied: the
fact is settled `rejected` with no ruling and only `ledger/proposed.yaml` is written.
`promote` always answers `Promoted`, never escalates, and never sets `conflict` or
`existing_value`. No code path under `ledger/` or `agents/` writes canon except `promote` and
`rule`, and `rule`, the one path that can overwrite, refuses `actor: agent`.

Measured with a hash of every file in the tree before and after each call, because "never
replaces" and "changes nothing" are claims about bytes, and a status code or a returned object
cannot prove them. An append is checked by its exact new value, never by `payload in value`,
which an overwrite would satisfy too.

The fixture values these tests lean on are named in `tests/fixtures/repo/README.md`: the
queued facts `pf_001` (pending, vance's competences) and `pf_002` (already rejected), and the
two invented facts of Draft A - F1, the throat releasing only from the vault side, aimed at
`pump_vault.geometry`, which already holds text and so is extended by it; and F2, the four-hour
indemnity cut, aimed at `ax_cold_soak.exceptions`, an empty list.
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
from app.commons.schemas import ChangeEvent, ChangesFile, FactStatus, ProposedFact, RulingKind
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import service
from app.ledger.models import Promoted
from app.ledger.service import PromotableField, PromotableTarget, ProposedAppend

CANONISER = AgentRole.CANONISER
F1_PAYLOAD = "the throat releases only from the vault side, never from the gallery"
F2_PAYLOAD = "cut to four hours on a co-op indemnity dive; the lung lining goes first"
PUMP_VAULT = paths.canon_entity("locations", "pump_vault")
COLD_SOAK = paths.canon_entity("axioms", "ax_cold_soak")
VANCE = paths.cast_file("vance", "dossier")
ILAN = paths.cast_file("ilan", "dossier")


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


def _promote(store: Store, fact_id: str) -> Promoted:
    return service.promote(store, fact_id, role=CANONISER, actor=Actor.AGENT)


def _written(writes: list[ProvenanceRecord]) -> list[str]:
    return [line.path for line in writes]


def _geometry(store: Store) -> str:
    return canon_service.entity(store, "locations", "pump_vault", Location).geometry


def _set_failure_mode(store: Store, text: str) -> None:
    """Give the hand sonar's `failure_mode` a known text, as the world builder would."""
    sonar = canon_service.entity(store, "technology", "te_hand_sonar", Technology)
    store.write(
        paths.canon_entity("technology", "te_hand_sonar"),
        sonar.model_copy(update={"failure_mode": text}),
        role=AgentRole.WORLD_BUILDER,
    )


def _assert_not_applied(store: Store, result: Promoted, fact_id: str, target: str) -> None:
    """A fact the record already specifies: `Promoted` by type, `rejected` by status, with no
    ruling (a ruling is a human's), no collision recorded, and nothing but the queue written."""
    assert isinstance(result, Promoted)
    assert result.changed is False
    assert result.target_path == target
    assert _written(result.writes) == [paths.PROPOSED]
    recorded = _on_disk(store, fact_id)
    assert recorded.status is FactStatus.REJECTED
    assert recorded.ruling is None
    assert recorded.conflict is False
    assert recorded.existing_value is None
    assert result.fact == recorded


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
# Add-only: a filled field is extended, never replaced; what is already specified is not applied
# --------------------------------------------------------------------------------------


def test_a_filled_scalar_gets_the_payload_appended_as_one_more_clause(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - F1 extends `geometry`: the old text is kept byte for byte and the
    # payload follows it after "; ". No escalation, no collision recorded.
    geometry = _geometry(fixture_store)
    _queue(fixture_store, _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_f1")

    assert isinstance(result, Promoted)
    assert result.changed is True
    assert result.target_path == PUMP_VAULT
    assert _written(result.writes) == [PUMP_VAULT, paths.PROPOSED]
    assert _changed(before, _hashes(fixture_store)) == {PUMP_VAULT, paths.PROPOSED}
    assert _geometry(fixture_store) == f"{geometry.rstrip()}; {F1_PAYLOAD}"
    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.status is FactStatus.PROMOTED
    assert recorded.conflict is False
    assert recorded.existing_value is None
    assert recorded.ruling is None


def test_the_appended_payload_is_stripped_and_the_existing_text_is_never_edited(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - only trailing whitespace of the old text goes (a block scalar ends in a
    # newline); its closing punctuation stays, and the payload's own padding is dropped
    _set_failure_mode(fixture_store, "it lies in a working shelf.\n")
    _queue(fixture_store, _fact("pf_pad", "te_hand_sonar", "failure_mode", "  and in brine  "))

    result = _promote(fixture_store, "pf_pad")

    assert result.changed is True
    sonar = canon_service.entity(fixture_store, "technology", "te_hand_sonar", Technology)
    assert sonar.failure_mode == "it lies in a working shelf.; and in brine"


def test_a_scalar_that_already_says_the_payload_is_settled_with_no_write(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - the payload's words are a run of the text's words, in another case and
    # with other punctuation: canon already says it, so it is promoted and nothing is appended
    _queue(
        fixture_store, _fact("pf_door", "pump_vault", "geometry", "The Throat is the ONLY door.")
    )
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_door")

    assert isinstance(result, Promoted)
    assert result.changed is False
    assert result.fact.status is FactStatus.PROMOTED
    assert _written(result.writes) == [paths.PROPOSED]
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_containment_is_word_bounded(fixture_store: Store) -> None:
    # spec 001 / AC 13 - "red" is not said by "reddish": a substring test would drop the detail
    # and still mark the fact promoted
    _set_failure_mode(fixture_store, "a reddish glow in silty water")
    _queue(fixture_store, _fact("pf_red", "te_hand_sonar", "failure_mode", "red"))

    result = _promote(fixture_store, "pf_red")

    assert result.changed is True
    sonar = canon_service.entity(fixture_store, "technology", "te_hand_sonar", Technology)
    assert sonar.failure_mode == "a reddish glow in silty water; red"


@pytest.mark.parametrize(
    "payload",
    ["lungs: tolerates brine", "LUNGS: tolerates brine", "left-hand: a hook", "Left Hand: a hook"],
    ids=["same-key", "key-case", "key-hyphen", "key-space"],
)
def test_a_mapping_key_the_record_has_is_never_changed(fixture_store: Store, payload: str) -> None:
    # spec 001 / AC 13 - a stored key with a different value is not applied, whatever the case
    # or the separators of the key; the dossier is byte-identical and no one is asked
    dossier = fixture_store.read_raw(ILAN)
    _queue(fixture_store, _fact("pf_body", "ilan", "immutable_physical", payload))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_body")

    _assert_not_applied(fixture_store, result, "pf_body", ILAN)
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}
    assert fixture_store.read_raw(ILAN) == dossier


def test_a_body_key_only_a_registered_change_names_is_not_applied(fixture_store: Store) -> None:
    # spec 001 / AC 13, invariant 3 - a key the stored map lacks but a ChangeEvent names: adding
    # it to the base map would make it hold from the story's start and rewrite the history the
    # change records. The change is dated after the fact's scene, so no as-of body holds it.
    changes = cast_service.read_changes(fixture_store, "ilan")
    scar = ChangeEvent(
        character="ilan",
        attribute="right_eye",
        from_value="clear",
        to_value="clouded by brine",
        scene="006",
        cause="a cracked mask in the vault",
    )
    fixture_store.write(
        paths.cast_file("ilan", "changes"),
        ChangesFile(changes=[*changes.changes, scar]),
        role=CANONISER,
    )
    assert "right_eye" not in cast_service.read_character(fixture_store, "ilan").immutable_physical
    dossier = fixture_store.read_raw(ILAN)
    _queue(fixture_store, _fact("pf_eye", "ilan", "immutable_physical", "Right Eye: clear"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_eye")

    _assert_not_applied(fixture_store, result, "pf_eye", ILAN)
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}
    assert fixture_store.read_raw(ILAN) == dossier


def test_a_name_is_never_appended_to(fixture_store: Store) -> None:
    # spec 001 / AC 13 - a different name is not applied; the same name in another case is
    # already in canon
    name = cast_service.read_character(fixture_store, "ilan").name
    _queue(
        fixture_store,
        _fact("pf_alias", "ilan", "name", "Ilan the splicer"),
        _fact("pf_name", "ilan", "name", name.upper()),
    )
    dossier = fixture_store.read_raw(ILAN)

    alias = _promote(fixture_store, "pf_alias")
    same = _promote(fixture_store, "pf_name")

    _assert_not_applied(fixture_store, alias, "pf_alias", ILAN)
    assert same.changed is False
    assert same.fact.status is FactStatus.PROMOTED
    assert fixture_store.read_raw(ILAN) == dossier


def test_an_identifier_is_set_once_and_never_changed(fixture_store: Store) -> None:
    # spec 001 / AC 13 - `parent` is an EntityId: a different id is not applied, the same id is a
    # no-op, and an empty one is set. Appending would have made an invalid id.
    parent = canon_service.entity(fixture_store, "locations", "pump_vault", Location).parent
    assert parent is not None
    root = canon_service.entity(fixture_store, "locations", "kestrel_deep", Location)
    assert root.parent is None
    _queue(
        fixture_store,
        _fact("pf_moved", "pump_vault", "parent", "the_gallery"),
        _fact("pf_same_parent", "pump_vault", "parent", parent),
        _fact("pf_root_parent", "kestrel_deep", "parent", "the_shelf"),
    )
    vault = fixture_store.read_raw(PUMP_VAULT)

    moved = _promote(fixture_store, "pf_moved")
    same = _promote(fixture_store, "pf_same_parent")
    rooted = _promote(fixture_store, "pf_root_parent")

    _assert_not_applied(fixture_store, moved, "pf_moved", PUMP_VAULT)
    assert fixture_store.read_raw(PUMP_VAULT) == vault
    assert (same.changed, same.fact.status) == (False, FactStatus.PROMOTED)
    assert rooted.changed is True
    kestrel = canon_service.entity(fixture_store, "locations", "kestrel_deep", Location)
    assert kestrel.parent == "the_shelf"


def test_a_promotion_that_died_between_its_two_writes_settles_with_no_second_write(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - canon first, queue second: canon already holds what the fact adds (an
    # appended clause, an added key, a set identifier) while the fact is still pending. The next
    # promote settles it as promoted and writes nothing but the queue.
    geometry = _geometry(fixture_store)
    vault = canon_service.entity(fixture_store, "locations", "pump_vault", Location)
    fixture_store.write(
        PUMP_VAULT,
        vault.model_copy(update={"geometry": f"{geometry.rstrip()}; {F1_PAYLOAD}"}),
        role=CANONISER,
    )
    ilan = cast_service.read_character(fixture_store, "ilan")
    fixture_store.write(
        ILAN,
        ilan.model_copy(update={"immutable_physical": {**ilan.immutable_physical, "eyes": "grey"}}),
        role=CANONISER,
    )
    root = canon_service.entity(fixture_store, "locations", "kestrel_deep", Location)
    fixture_store.write(
        paths.canon_entity("locations", "kestrel_deep"),
        root.model_copy(update={"parent": "the_shelf"}),
        role=CANONISER,
    )
    _queue(
        fixture_store,
        _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD),
        _fact("pf_eyes", "ilan", "immutable_physical", "eyes: grey"),
        _fact("pf_root", "kestrel_deep", "parent", "the_shelf"),
    )

    for fact_id in ("pf_f1", "pf_eyes", "pf_root"):
        before = _hashes(fixture_store)
        result = _promote(fixture_store, fact_id)
        assert isinstance(result, Promoted), fact_id
        assert (result.changed, result.fact.status) == (False, FactStatus.PROMOTED), fact_id
        assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}, fact_id


def test_a_legacy_collided_fact_is_promoted_add_only_and_keeps_its_record(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - a queue entry an earlier, collision-checking promote left pending with
    # `conflict: true`: promoted like any other fact, and `conflict` and `existing_value` are
    # carried over exactly as they were (promote never sets or clears them)
    geometry = _collided(fixture_store)

    result = _promote(fixture_store, "pf_f1")

    assert isinstance(result, Promoted)
    assert result.changed is True
    assert _geometry(fixture_store) == f"{geometry.rstrip()}; {F1_PAYLOAD}"
    recorded = _on_disk(fixture_store, "pf_f1")
    assert recorded.status is FactStatus.PROMOTED
    assert recorded.conflict is True
    assert recorded.existing_value == geometry
    assert recorded.ruling is None


def _read_target(store: Store, target: PromotableTarget) -> BaseModel:
    """The record `target` names, read through its owning service."""
    if target.record_type == Character.__name__:
        return cast_service.read_character(store, target.entity)
    kind = target.path.split("/")[1]
    return canon_service.entity(store, kind, target.entity, canon_service.CANON_MODELS[kind])


def _valid_payload(field: PromotableField) -> str:
    """A payload every promotable field of its shape accepts: an identifier-shaped word fits an
    `EntityId` scalar or list item as well as free text."""
    if field.shape is service.FieldShape.MAPPING:
        return "promoted_key: a promoted value"
    return "promoted_value"


def _fixture_targets(store: Store) -> tuple[PromotableTarget, ...]:
    """Every canon entity and every character of the fixture, as `promote` resolves them."""
    entities = [
        relative.rsplit("/", 1)[1].removesuffix(".md")
        for kind in paths.CANON_KINDS
        for relative in store.list_files(f"{paths.CANON}/{kind}", ".md")
    ]
    entities.extend(store.list_subdirectories(paths.CAST))
    return service.promotable_targets(store, entities)


def test_no_promotion_of_any_field_of_any_fixture_record_overwrites_anything(
    fixture_store: Store,
) -> None:
    # spec 001 / AC 13 - the property: over every promotable field of every fixture record, with
    # a payload the field accepts, promote answers `Promoted`, writes nothing but the target and
    # the queue, and what the field held survives as a prefix (text, list) or a sub-map with
    # equal values. Any overwrite or escalation fails it.
    targets = _fixture_targets(fixture_store)
    assert {target.record_type for target in targets} == {
        "Axiom",
        "Technology",
        "Location",
        "Faction",
        "HistoricalEvent",
        "Character",
    }
    number = 0
    for target in targets:
        for field in target.fields:
            number += 1
            fact_id = f"pf_prop_{number}"
            _queue(fixture_store, _fact(fact_id, target.entity, field.name, _valid_payload(field)))
            old = getattr(_read_target(fixture_store, target), field.attribute)
            before = _hashes(fixture_store)

            result = _promote(fixture_store, fact_id)

            where = f"{target.entity}.{field.name}"
            new = getattr(_read_target(fixture_store, target), field.attribute)
            changed = _changed(before, _hashes(fixture_store))
            assert isinstance(result, Promoted), where
            assert changed <= {target.path, paths.PROPOSED}, where
            assert result.fact.status in {FactStatus.PROMOTED, FactStatus.REJECTED}, where
            assert (result.fact.conflict, result.fact.existing_value) == (False, None), where
            if result.fact.status is FactStatus.REJECTED:
                assert changed == {paths.PROPOSED}, where
            if isinstance(old, list):
                assert new[: len(old)] == old, where
            elif isinstance(old, dict):
                assert all(new.get(key) == value for key, value in old.items()), where
            else:
                assert str(new).startswith((old or "").rstrip()), where


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
        (_fact("pf_x", "pump_vault", "geometry", "-- ... --"), "payload"),
        (_fact("pf_x", "ilan", "immutable_physical", "eyes: ..."), "payload"),
    ],
    ids=[
        "entity-missing",
        "field-missing",
        "integer-field",
        "list-of-records",
        "identifier",
        "payload-fails-field",
        "mapping-without-key",
        "payload-asserts-nothing",
        "mapping-value-asserts-nothing",
    ],
)
def test_unpromotable_fact_is_refused_and_nothing_is_written(
    fixture_store: Store, fact: ProposedFact, field: str
) -> None:
    # spec 001 / AC 13 - a target that does not exist is not promoted, and not settled as "not
    # applied"; a payload with no word would be "contained" in any text, so it is refused too
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
# rule: a human's manual decision, and the one path that can overwrite canon
# --------------------------------------------------------------------------------------


def _collided(store: Store) -> str:
    """Queue F1 as an earlier, collision-checking `promote` left it -- pending, `conflict: true`,
    the geometry it collided with recorded -- built directly, since no promotion records a
    collision now. Returns the original geometry."""
    geometry = _geometry(store)
    legacy = _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD).model_copy(
        update={"conflict": True, "existing_value": geometry}
    )
    _queue(store, legacy)
    return geometry


def test_accept_promotes_despite_the_collision(fixture_store: Store) -> None:
    # spec 001 / AC 13 - `rule` with actor human is the one path that overwrites a value
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
    _queue(fixture_store, _fact("pf_wants", "ilan", "wants", "the way back up"))
    monkeypatch.setattr(Store, "write", recording_write)

    _promote(fixture_store, "pf_001")
    _promote(fixture_store, "pf_f2")
    _promote(fixture_store, "pf_f1")
    service.rule(
        fixture_store, "pf_wants", RulingKind.ACCEPT, "decided", role=CANONISER, actor=Actor.HUMAN
    )

    assert callers == [
        ("promote", VANCE),
        ("promote", COLD_SOAK),
        ("promote", PUMP_VAULT),
        ("rule", ILAN),
    ]


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


def test_http_promote_extends_a_filled_field_and_reports_a_fact_not_applied(
    fixture_client: TestClient,
) -> None:
    # spec 001 / AC 13 - both answers are `Promoted`: a client reads `fact.status`, promoted for
    # the appended clause, rejected with no ruling for the key the record already has
    facts = [
        _fact("pf_f1", "pump_vault", "geometry", F1_PAYLOAD).model_dump(mode="json"),
        _fact("pf_lungs", "ilan", "immutable_physical", "lungs: tolerates brine").model_dump(
            mode="json"
        ),
    ]
    queued = fixture_client.post("/ledger/proposed", json={"facts": facts}, headers=CANONISER_AGENT)
    assert queued.status_code == 200

    appended = fixture_client.post("/ledger/proposed/pf_f1/promote", headers=CANONISER_AGENT)
    assert appended.status_code == 200
    assert appended.json()["outcome"] == "promoted"
    assert appended.json()["changed"] is True
    assert appended.json()["fact"]["status"] == "promoted"
    assert appended.json()["fact"]["conflict"] is False

    specified = fixture_client.post("/ledger/proposed/pf_lungs/promote", headers=CANONISER_AGENT)
    assert specified.status_code == 200
    assert specified.json()["outcome"] == "promoted"
    assert specified.json()["changed"] is False
    assert specified.json()["fact"]["status"] == "rejected"
    assert specified.json()["fact"]["ruling"] is None
    assert specified.json()["fact"]["conflict"] is False


def test_http_a_human_rules_on_a_legacy_collision(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    # spec 001 / AC 13 - the rule route stays a human's tool: the agent is refused, the human
    # settles the collision an earlier promote recorded
    _collided(fixture_store)
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
# A character's body: the stored map is what promotion adds to, never the as-of body
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


def test_a_body_fact_restating_a_registered_change_is_not_applied(fixture_store: Store) -> None:
    # spec 001 / AC 13 - `left_hand` is a key the stored map already has, so the registered
    # change's new value is not added over it: the change stays in `changes.yaml`, the stored
    # map is never rewritten, and nobody is asked
    changed = _registered(fixture_store, "ilan", "left_hand")
    _queue(fixture_store, _body_fact("pf_hand_now", f"left_hand: {changed}", "006"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_hand_now")

    _assert_not_applied(fixture_store, result, "pf_hand_now", ILAN)
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}


def test_a_body_fact_restating_the_stored_value_is_already_in_canon(fixture_store: Store) -> None:
    # spec 001 / AC 13 - the value the stored map holds, even though a registered change later
    # replaces it: canon already says it, so the fact is promoted and nothing is written but the
    # queue. No as-of comparison, and no collision with the changed value.
    base = cast_service.read_character(fixture_store, "ilan").immutable_physical["left_hand"]
    assert base != _registered(fixture_store, "ilan", "left_hand")
    _queue(fixture_store, _body_fact("pf_hand_old", f"left_hand: {base}", "006"))
    before = _hashes(fixture_store)

    result = _promote(fixture_store, "pf_hand_old")

    assert isinstance(result, Promoted)
    assert (result.changed, result.fact.status) == (False, FactStatus.PROMOTED)
    assert _changed(before, _hashes(fixture_store)) == {paths.PROPOSED}
    stored = cast_service.read_character(fixture_store, "ilan").immutable_physical
    assert stored["left_hand"] == base, "the stored map is never rewritten by a promotion"
