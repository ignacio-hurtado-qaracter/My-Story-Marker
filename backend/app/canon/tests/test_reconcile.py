"""AC 14 - `reconcile` returns a superset of hand-labelled dependents for a character, a nested
location and a tagged axiom.

Two kinds of test, because the criterion is a universal claim about any tree and a fixture
can only show instances of it:

* **Golden cases on the fixture novel.** The expected dependents below were derived by hand
  from the files under `tests/fixtures/repo/` - the six `scenes/NNN.yaml` records (their `pov`,
  `participants`, `location`, `pins`, `tags`), the two `canon/locations/*.md` (`pump_vault`'s
  parent is `kestrel_deep`), `canon/axioms/ax_brine_dark.md` (`scope: [vault, perception,
  light, sound]`) and the three `cast/*/knowledge.yaml` - and are restated beside each test
  with the file and value that makes each scene a dependent. They were not read back from the
  implementation.
* **A property over generated scenes** (`hypothesis`), run against `find_dependents`, the pure
  function the route calls. Each generated scene is built from a *plan* of which references it
  should carry, so the label is known by construction and is independent of the code under
  test: every planted scene must come back with exactly the planted reasons, and a scene
  planted with none must not come back at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.canon import service
from app.canon.models import DependencyReason, Dependent, Reconciliation
from app.canon.service import find_dependents
from app.commons.errors import NotFound
from app.commons.schemas import (
    Certainty,
    KnowledgeState,
    Outcome,
    Scene,
    SelectedEntity,
    TurnRecord,
    Via,
)
from app.commons.stores import Store, paths
from app.commons.stores.frontmatter import render_yaml
from app.commons.stores.turns import turns_path

R = DependencyReason


def _codes(dependents: list[Dependent]) -> dict[str, set[DependencyReason]]:
    return {entry.id: {reason.code for reason in entry.reasons} for entry in dependents}


def _assert_superset(result: Reconciliation, labelled: dict[str, set[DependencyReason]]) -> None:
    """AC 14's shape: every hand-labelled scene is present, with at least its labelled reasons."""
    found = _codes(result.scenes)
    missing = sorted(set(labelled) - set(found))
    assert not missing, f"dependents missing from reconcile: {missing}"
    for scene, reasons in labelled.items():
        assert reasons <= found[scene], f"scene {scene}: {found[scene]} lacks {reasons}"


def _write_turn(store: Store, record: TurnRecord) -> None:
    """Plant a turn record where the orchestrator of plan step 18 will write them, inside the
    test's private `.index/` (never the fixture)."""
    directory = turns_path(store.index_dir)
    directory.mkdir(parents=True, exist_ok=True)
    text = render_yaml(record.model_dump(mode="json"))
    (directory / f"{record.id}.yaml").write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------------------
# Golden cases, hand-labelled from the fixture files
# --------------------------------------------------------------------------------------


def test_character_ilan(fixture_store: Store) -> None:
    # spec 001 / AC 14 - a character.
    # scenes/002.yaml pov: ilan; 004.yaml and 006.yaml participants: [ilan].
    # No knowledge row has fact_ref: ilan, and no scene pins him.
    labelled = {"002": {R.POV}, "004": {R.PARTICIPANT}, "006": {R.PARTICIPANT}}
    result = service.reconcile(fixture_store, "ilan")

    _assert_superset(result, labelled)
    assert result.defined_in == [paths.cast_file("ilan", "dossier")]
    assert result.turns == []


def test_nested_location_pump_vault(fixture_store: Store) -> None:
    # spec 001 / AC 14 - a nested location (canon/locations/pump_vault.md parent: kestrel_deep).
    # location: pump_vault in scenes 002, 003, 004, 006.
    # cast/vance/knowledge.yaml: fact_ref pump_vault, acquired_in "003";
    # cast/ilan/knowledge.yaml:  fact_ref pump_vault, acquired_in "002".
    labelled = {
        "002": {R.LOCATION, R.KNOWLEDGE},
        "003": {R.LOCATION, R.KNOWLEDGE},
        "004": {R.LOCATION},
        "006": {R.LOCATION},
    }
    _assert_superset(service.reconcile(fixture_store, "pump_vault"), labelled)


def test_parent_location_reaches_every_scene_set_inside_it(fixture_store: Store) -> None:
    # spec 001 / AC 14 - "location or any ancestor of its location through Location.parent".
    # location: kestrel_deep in 001 and 005; pump_vault (whose parent is kestrel_deep) in
    # 002, 003, 004 and 006. Loading a cabin implies loading its ship: changing the ship
    # reaches every scene in the cabin.
    labelled = {
        "001": {R.LOCATION},
        "005": {R.LOCATION},
        "002": {R.LOCATION_ANCESTOR},
        "003": {R.LOCATION_ANCESTOR},
        "004": {R.LOCATION_ANCESTOR},
        "006": {R.LOCATION_ANCESTOR},
    }
    _assert_superset(service.reconcile(fixture_store, "kestrel_deep"), labelled)


def test_pinned_and_tagged_axiom_ax_brine_dark(fixture_store: Store) -> None:
    # spec 001 / AC 14 - a tagged axiom (scope: [vault, perception, light, sound]).
    # pins include ax_brine_dark in 003 and 006; 006 tags [vault, perception] meet the scope.
    # cast/vance/knowledge.yaml acquired_in "006"; cast/quiej/knowledge.yaml acquired_in "004"
    # (the planted invariant-1 row of the fixture README - still a dependent).
    labelled = {
        "003": {R.PINNED},
        "004": {R.KNOWLEDGE},
        "006": {R.PINNED, R.TAG_SCOPE, R.KNOWLEDGE},
    }
    result = service.reconcile(fixture_store, "ax_brine_dark")

    _assert_superset(result, labelled)
    tag_detail = next(
        reason.detail
        for entry in result.scenes
        if entry.id == "006"
        for reason in entry.reasons
        if reason.code is R.TAG_SCOPE
    )
    assert "perception" in tag_detail
    assert "vault" in tag_detail


def test_hand_labels_are_the_whole_answer_on_the_fixture(fixture_store: Store) -> None:
    # spec 001 / AC 14 - the derivations above are complete for this tree, so the superset is
    # also exact here: nothing is reported that the files do not say
    assert set(_codes(service.reconcile(fixture_store, "ilan").scenes)) == {"002", "004", "006"}
    assert set(_codes(service.reconcile(fixture_store, "ax_brine_dark").scenes)) == {
        "003",
        "004",
        "006",
    }


def test_lexicon_term_pinned_by_id(fixture_store: Store) -> None:
    # spec 001 / AC 14 - scenes pin lexicon terms too: 003 and 004 pin lx_readkey
    result = service.reconcile(fixture_store, "lx_readkey")
    _assert_superset(result, {"003": {R.PINNED}, "004": {R.PINNED}})
    assert result.defined_in == [paths.LEXICON]


def test_turn_records_that_selected_the_entity(fixture_store: Store) -> None:
    # spec 001 / AC 14 - "every turn record whose selected list contains it"
    _write_turn(
        fixture_store,
        TurnRecord(
            id="005-1",
            scene="005",
            selected=[
                SelectedEntity(entity_id="ax_calving_window", kind="axiom", score=1.0, pinned=True),
                SelectedEntity(entity_id="ilan", kind="character", score=0.4),
            ],
        ),
    )
    _write_turn(
        fixture_store,
        TurnRecord(
            id="003-1",
            scene="003",
            selected=[SelectedEntity(entity_id="pump_vault", kind="location", score=0.9)],
        ),
    )

    result = service.reconcile(fixture_store, "ilan")

    assert [turn.id for turn in result.turns] == ["005-1"]
    assert _codes(result.turns) == {"005-1": {R.SELECTED}}
    # The scene that turn wrote saw ilan in its context, so it depends on him too.
    assert R.SELECTED in _codes(result.scenes)["005"]


def test_results_are_sorted_and_deduplicated(fixture_store: Store) -> None:
    # spec 001 / AC 14 - one entry per scene, reasons each once, both in a stable order
    result = service.reconcile(fixture_store, "ax_brine_dark")
    ids = [entry.id for entry in result.scenes]
    assert ids == sorted(set(ids))
    for entry in result.scenes:
        pairs = [(reason.code.value, reason.detail) for reason in entry.reasons]
        assert pairs == sorted(set(pairs))


def test_an_id_that_defines_nothing_is_not_found(fixture_store: Store) -> None:
    # spec 001 / AC 14 - an empty answer for a typo would read as "nothing depends on it"
    with pytest.raises(NotFound):
        service.reconcile(fixture_store, "nowhere_ship")


def test_http_reconcile(fixture_client: TestClient) -> None:
    # spec 001 / AC 14 - IF-05 `POST /canon/reconcile`
    response = fixture_client.post("/canon/reconcile", json={"entity_id": "pump_vault"})
    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == "pump_vault"
    assert [scene["id"] for scene in body["scenes"]] == ["002", "003", "004", "006"]

    assert (
        fixture_client.post("/canon/reconcile", json={"entity_id": "nowhere_ship"}).status_code
        == 404
    )
    assert fixture_client.post("/canon/reconcile", json={"entity_id": "Bad Id"}).status_code == 422
    extra = fixture_client.post("/canon/reconcile", json={"entity_id": "ilan", "depth": 2})
    assert extra.status_code == 422


# --------------------------------------------------------------------------------------
# Property over generated scenes
# --------------------------------------------------------------------------------------

TARGET = "target"
PLANS = ("pov", "participant", "location", "descendant", "pin", "tag")
CODE_OF = {
    "pov": R.POV,
    "participant": R.PARTICIPANT,
    "location": R.LOCATION,
    "descendant": R.LOCATION_ANCESTOR,
    "pin": R.PINNED,
    "tag": R.TAG_SCOPE,
}
PARENTS: dict[str, str | None] = {
    TARGET: None,
    "inner": TARGET,
    "innermost": "inner",
    "elsewhere": None,
    "elsewhere_room": "elsewhere",
}
"""A location tree where `target` is an ancestor of `inner` and `innermost`, and the other
branch never reaches it. Scenes planted with `descendant` are set in the first branch; scenes
with no location plan are set in the second."""
SCOPE = ("Brine", "dark ")
"""The target's scope, as an axiom's. Planted tags vary case and spacing; unplanted ones are
drawn from a vocabulary disjoint from it."""


@dataclass(frozen=True)
class Planted:
    scenes: dict[str, Scene]
    knowledge: list[KnowledgeState]
    turns: list[TurnRecord]
    expected_scenes: dict[str, set[DependencyReason]]
    expected_turns: set[str]


def _scene(identifier: str, plan: frozenset[str], draw: st.DrawFn) -> Scene:
    pov = TARGET if "pov" in plan else draw(st.sampled_from(["c_one", "c_two"]))
    participants = ["c_three"]
    if "participant" in plan:
        participants.insert(draw(st.integers(0, 1)), TARGET)
    if "location" in plan:
        location = TARGET
    elif "descendant" in plan:
        location = draw(st.sampled_from(["inner", "innermost"]))
    else:
        location = draw(st.sampled_from(["elsewhere", "elsewhere_room"]))
    tags = ["ice"]
    if "tag" in plan:
        tags.append(draw(st.sampled_from([" brine", "BRINE", "Dark", "dark"])))
    return Scene(
        id=identifier,
        pov=pov,
        participants=participants,
        story_time=draw(st.integers(-50, 500)),
        discourse_order=int(identifier),
        location=location,
        goal="g",
        conflict="c",
        outcome=Outcome.YES,
        value_change="v: a -> b (+)",
        entry_state="in",
        exit_state="out",
        tags=tags,
        pins=[TARGET, "o_pin"] if "pin" in plan else ["o_pin"],
        budget=100,
    )


@st.composite
def planted(draw: st.DrawFn) -> Planted:
    plans = draw(st.lists(st.frozensets(st.sampled_from(PLANS)), max_size=10))
    scenes: dict[str, Scene] = {}
    expected: dict[str, set[DependencyReason]] = {}
    for position, raw in enumerate(plans, start=1):
        plan = raw
        if "pov" in plan:
            plan = plan - {"participant"}  # the POV is never repeated among participants
        if "location" in plan:
            plan = plan - {"descendant"}  # one location per scene
        identifier = f"{position:03d}"
        scenes[identifier] = _scene(identifier, plan, draw)
        if plan:
            expected[identifier] = {CODE_OF[name] for name in plan}

    scene_ids = [*scenes, "999"]  # a knowledge row may name a scene with no record
    knowledge: list[KnowledgeState] = []
    for acquired_in, about_target in draw(
        st.lists(st.tuples(st.sampled_from(scene_ids), st.booleans()), max_size=6)
    ):
        knowledge.append(
            KnowledgeState(
                character="c_one",
                fact_ref=TARGET if about_target else "other_fact",
                acquired_in=acquired_in,
                via=Via.WITNESSED,
                certainty=Certainty.KNOWS,
                may_tell=[],
            )
        )
        if about_target:
            expected.setdefault(acquired_in, set()).add(R.KNOWLEDGE)

    turns: list[TurnRecord] = []
    expected_turns: set[str] = set()
    for attempt, (scene, selects_target) in enumerate(
        draw(
            st.lists(
                st.tuples(st.sampled_from(scene_ids[:-1] or ["001"]), st.booleans()), max_size=4
            )
        ),
        start=1,
    ):
        selected = [SelectedEntity(entity_id="o_pin", kind="axiom", score=0.1)]
        if selects_target:
            selected.append(SelectedEntity(entity_id=TARGET, kind="axiom", score=0.9))
        turn_id = f"{scene}-{attempt}"
        turns.append(TurnRecord(id=turn_id, scene=scene, selected=selected))
        if selects_target:
            expected_turns.add(turn_id)
            expected.setdefault(scene, set()).add(R.SELECTED)

    return Planted(scenes, knowledge, turns, expected, expected_turns)


@settings(max_examples=300, deadline=None)
@given(planted())
def test_property_every_planted_reference_is_found_and_nothing_else(case: Planted) -> None:
    # spec 001 / AC 14 - property over generated scenes: superset of the planted labels, and
    # (because every unplanted field is drawn from a disjoint vocabulary) exactly them
    scenes, turns = find_dependents(
        TARGET,
        scenes=case.scenes,
        parents=PARENTS,
        scope=SCOPE,
        knowledge=case.knowledge,
        turns=case.turns,
    )

    found = _codes(scenes)
    for scene, reasons in case.expected_scenes.items():
        assert scene in found, f"planted dependent {scene} missing"
        assert reasons <= found[scene]
    assert found == case.expected_scenes
    assert {turn.id for turn in turns} == case.expected_turns
    assert [entry.id for entry in scenes] == sorted(found)
    for entry in scenes:
        pairs = [(reason.code.value, reason.detail) for reason in entry.reasons]
        assert pairs == sorted(set(pairs))


def test_location_cycle_terminates() -> None:
    # spec 001 / AC 14 - a cycle in Location.parent is a canon fault, not a hung request
    cyclic: dict[str, str | None] = {"a": "b", "b": "a"}
    scene = Scene(
        id="001",
        pov="c_one",
        participants=[],
        story_time=0,
        discourse_order=1,
        location="a",
        goal="g",
        conflict="c",
        outcome=Outcome.NO,
        value_change="v: a -> b (-)",
        entry_state="in",
        exit_state="out",
        budget=1,
    )
    scenes, _ = find_dependents("b", scenes={"001": scene}, parents=cyclic)
    assert _codes(scenes) == {"001": {R.LOCATION_ANCESTOR}}
