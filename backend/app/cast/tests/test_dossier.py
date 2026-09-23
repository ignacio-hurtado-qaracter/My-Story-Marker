"""AC 10 - `dossier(character, at=T)` never includes knowledge or valence dated after `T`.

Two kinds of test, because the criterion is a universal statement and a fixture can only show
instances of it:

* **Fixture cases** pin the answer on the fixture novel, whose analepses make the axes
  disagree on purpose: scene 002 is read second and happened first, 006 is read last and
  happened before 004. Every expected value below is read off the fixture's README tables.
* **Properties** (`hypothesis`) over generated knowledge, valence and arc tables, run against
  `trim_dossier` - the same pure function the route runs, with the disk taken out of the loop
  so thousands of tables cost seconds.

ChangeEvents are covered too, although FR-OPS-01 does not name them: `docs/architecture.md`
("as they were at that instant") and `definitions.md` ChangeEvent ("before it, the old value
holds") do, and the docs outrank the spec. Ilan's left hand is the fixture's case.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.cast import service
from app.cast.models import ArcEntry, Character, TrimmedDossier
from app.cast.service import SceneInstant, trim_dossier
from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Certainty,
    ChangeEvent,
    ChangesFile,
    DatedValence,
    KnowledgeFile,
    KnowledgeState,
    Relationship,
    RelationshipsFile,
    Via,
)
from app.commons.stores import Store, paths

GRAFT = "graft-steel prosthesis, five digits, no sensation below the wrist"
FLESH = "flesh; the hand he splices with"


def _facts(dossier: TrimmedDossier) -> list[tuple[str, str]]:
    return [(row.fact_ref, row.acquired_in) for row in dossier.knowledge]


def _valence(dossier: TrimmedDossier) -> dict[str, tuple[str, int]]:
    return {edge.to: (edge.valence.scene, edge.valence.value) for edge in dossier.relationships}


# --------------------------------------------------------------------------------------
# Fixture cases
# --------------------------------------------------------------------------------------


# spec 001 / AC 10
def test_before_his_first_scene_ilan_has_no_knowledge_valence_or_arc(
    fixture_store: Store,
) -> None:
    """Hour 119 is one hour before scene 002, the earliest scene in story time. Everything
    Ilan has is anchored at or after it, so nothing dated may appear."""
    dossier = service.dossier(fixture_store, "ilan", 119)

    assert dossier.at == 119
    assert dossier.arc is None
    assert dossier.knowledge == []
    assert dossier.relationships == []


# spec 001 / AC 10
def test_ilan_left_hand_is_flesh_before_scene_002_and_graft_from_it(
    fixture_store: Store,
) -> None:
    """The registered ChangeEvent of `cast/ilan/changes.yaml` is at scene 002 (hour 120).
    `immutable_physical.left_hand` on disk still reads the pre-change value; the dossier must
    apply the change from 002's story time onward and not before."""
    before = service.dossier(fixture_store, "ilan", 119)
    at_change = service.dossier(fixture_store, "ilan", 120)
    later = service.dossier(fixture_store, "ilan", 318)

    assert before.immutable_physical["left_hand"] == FLESH
    assert at_change.immutable_physical["left_hand"] == GRAFT
    assert later.immutable_physical["left_hand"] == GRAFT
    # The attribute with no ChangeEvent is untouched at every instant (invariant 3's other
    # half: the lungs are the fixture's unregistered-change trap and must stay as stored).
    assert later.immutable_physical["lungs"] == before.immutable_physical["lungs"]


# spec 001 / AC 10
def test_ilan_at_scene_002_has_its_rows_arc_and_first_readings(fixture_store: Store) -> None:
    dossier = service.dossier(fixture_store, "ilan", 120)

    assert dossier.arc is not None
    assert dossier.arc.scene == "002"
    assert _facts(dossier) == [("pump_vault", "002"), ("ax_indemnity_burn", "002")]
    assert _valence(dossier) == {"quiej": ("002", -1), "vance": ("002", 2)}


# spec 001 / AC 10
def test_ilan_at_hour_318_takes_the_latest_readings_on_the_story_axis(
    fixture_store: Store,
) -> None:
    """004 (hour 318) is later in story than 006 (hour 310), though read earlier."""
    dossier = service.dossier(fixture_store, "ilan", 318)

    assert dossier.arc is not None
    assert dossier.arc.scene == "004"
    assert _valence(dossier) == {"quiej": ("004", -3), "vance": ("004", -1)}


# spec 001 / AC 10
@pytest.mark.parametrize(
    ("at", "brine_dark_known", "ilan_reading"),
    [(309, False, ("003", 1)), (310, True, ("006", 2))],
)
def test_vance_learns_the_brine_dark_exactly_at_scene_006(
    fixture_store: Store,
    at: int,
    brine_dark_known: bool,
    ilan_reading: tuple[str, int],
) -> None:
    """Scene 006 is at hour 310 and is the last scene the reader meets. One hour before it,
    neither the knowledge row nor the valence reading anchored there may appear."""
    dossier = service.dossier(fixture_store, "vance", at)

    assert (("ax_brine_dark", "006") in _facts(dossier)) is brine_dark_known
    assert _valence(dossier)["ilan"] == ilan_reading
    assert dossier.arc is not None
    assert dossier.arc.scene == "003"  # 006 is not an arc anchor; 004 (318) is still ahead


# spec 001 / AC 10
def test_latest_valence_is_story_order_not_discourse_order(fixture_store: Store) -> None:
    """vance -> ilan: +2 at 006 (hour 310, discourse 6) and +3 at 004 (hour 318, discourse 4).
    At 318 the latest on the story axis is 004's +3; a discourse ordering would give +2."""
    dossier = service.dossier(fixture_store, "vance", 318)

    assert _valence(dossier) == {"ilan": ("004", 3), "quiej": ("005", -2)}
    assert dossier.arc is not None
    assert dossier.arc.scene == "004"


# spec 001 / AC 10
def test_knowledge_is_ordered_on_the_story_axis(fixture_store: Store) -> None:
    """quiej's file lists 002 (hour 120), 001 (300), 004 (318). At 302 the 004 row is future;
    the other two come back in story order, which here is also file order."""
    dossier = service.dossier(fixture_store, "quiej", 302)

    assert _facts(dossier) == [("ax_indemnity_burn", "002"), ("ax_calving_window", "001")]


# spec 001 / AC 10
def test_the_undated_markdown_body_never_reaches_the_dossier(fixture_store: Store) -> None:
    """vance's dossier body says "until scene 004, where for the first time she does not" -
    undated prose that names her future. It cannot be shown to hold at hour 300, so it is not
    part of the trimmed record at all."""
    full = service.read_character(fixture_store, "vance")
    dossier = service.dossier(fixture_store, "vance", 300)

    assert "until scene 004" in full.body
    assert "body" not in TrimmedDossier.model_fields
    assert "until scene 004" not in dossier.model_dump_json()


# --------------------------------------------------------------------------------------
# Rows that cannot be placed, forgettings, foreign rows, missing files
# --------------------------------------------------------------------------------------


def _write_knowledge(store: Store, character: str, rows: list[KnowledgeState]) -> None:
    store.write(
        paths.cast_file(character, "knowledge"),
        KnowledgeFile(knowledge=rows),
        role=AgentRole.CANONISER,
    )


def _write_changes(store: Store, character: str, changes: list[ChangeEvent]) -> None:
    store.write(
        paths.cast_file(character, "changes"),
        ChangesFile(changes=changes),
        role=AgentRole.CANONISER,
    )


def _row(character: str, fact_ref: str, scene: str) -> KnowledgeState:
    return KnowledgeState(
        character=character,
        fact_ref=fact_ref,
        acquired_in=scene,
        via=Via.WITNESSED,
        certainty=Certainty.KNOWS,
    )


def _change(attribute: str, before: str, after: str, scene: str) -> ChangeEvent:
    return ChangeEvent(
        character="ilan",
        attribute=attribute,
        from_value=before,
        to_value=after,
        scene=scene,
        cause="a registered cause",
    )


# spec 001 / AC 10
def test_a_row_anchored_to_a_missing_scene_is_never_shown(fixture_store: Store) -> None:
    """`acquired_in: "099"` names no scene, so the row cannot be shown to be at or before any
    instant; it is excluded however late `at` is. FR-AUD-01 is what reports it."""
    existing = service.read_knowledge(fixture_store, "ilan").knowledge
    _write_knowledge(fixture_store, "ilan", [*existing, _row("ilan", "kestrel_deep", "099")])

    dossier = service.dossier(fixture_store, "ilan", 1_000_000)

    assert "kestrel_deep" not in {row.fact_ref for row in dossier.knowledge}
    assert len(dossier.knowledge) == len(existing)


# spec 001 / AC 10
def test_a_registered_forgetting_erases_the_fact_from_its_scene_onward(
    fixture_store: Store,
) -> None:
    """`Knows -> Unaware` registered at 006 (hour 310): the 002 row holds at 309 and is gone
    at 310. Learnt again at 004 (hour 318), the new row survives - the forgetting erased what
    was held when it happened, not the fact for ever."""
    existing = service.read_knowledge(fixture_store, "ilan").knowledge
    _write_knowledge(fixture_store, "ilan", [*existing, _row("ilan", "pump_vault", "004")])
    current = service.read_changes(fixture_store, "ilan").changes
    _write_changes(fixture_store, "ilan", [*current, _change("pump_vault", "knew it", "", "006")])

    assert ("pump_vault", "002") in _facts(service.dossier(fixture_store, "ilan", 309))
    assert "pump_vault" not in {
        row.fact_ref for row in service.dossier(fixture_store, "ilan", 310).knowledge
    }
    relearnt = [
        scene
        for fact, scene in _facts(service.dossier(fixture_store, "ilan", 318))
        if fact == "pump_vault"
    ]
    assert relearnt == ["004"]


# spec 001 / AC 10
def test_a_change_that_cannot_be_placed_withholds_the_attribute(fixture_store: Store) -> None:
    """A second left_hand change anchored to a scene that does not exist: neither value can be
    shown to hold, so the attribute is withheld rather than guessed. Other attributes stay."""
    current = service.read_changes(fixture_store, "ilan").changes
    _write_changes(fixture_store, "ilan", [*current, _change("left_hand", GRAFT, "none", "099")])

    dossier = service.dossier(fixture_store, "ilan", 318)

    assert "left_hand" not in dossier.immutable_physical
    assert "lungs" in dossier.immutable_physical


# spec 001 / AC 10
def test_changes_apply_in_story_order_not_file_order(fixture_store: Store) -> None:
    """Two more left_hand changes, filed 004 (hour 318) before 006 (hour 310). At 318 the body
    is 004's value, the latest on the story axis; applying the file in order would leave 006's
    value in force, a hand the character has already lost again."""
    current = service.read_changes(fixture_store, "ilan").changes
    _write_changes(
        fixture_store,
        "ilan",
        [
            *current,
            _change("left_hand", "second graft", "stump", "004"),
            _change("left_hand", GRAFT, "second graft", "006"),
        ],
    )

    assert service.dossier(fixture_store, "ilan", 309).immutable_physical["left_hand"] == GRAFT
    assert (
        service.dossier(fixture_store, "ilan", 310).immutable_physical["left_hand"]
        == "second graft"
    )
    assert service.dossier(fixture_store, "ilan", 318).immutable_physical["left_hand"] == "stump"


# spec 001 / AC 10
def test_a_change_filed_under_another_character_is_not_applied(fixture_store: Store) -> None:
    """A hand-edited `cast/ilan/changes.yaml` holding quiej's events: neither her body change
    nor her forgetting is ilan's, so his hand and his knowledge are untouched."""
    current = service.read_changes(fixture_store, "ilan").changes
    foreign = [
        ChangeEvent(
            character="quiej",
            attribute=attribute,
            from_value="before",
            to_value=after,
            scene="002",
            cause="a registered cause",
        )
        for attribute, after in [("left_hand", "a claw"), ("pump_vault", "")]
    ]
    _write_changes(fixture_store, "ilan", [*current, *foreign])

    dossier = service.dossier(fixture_store, "ilan", 318)

    assert dossier.immutable_physical["left_hand"] == GRAFT
    assert ("pump_vault", "002") in _facts(dossier)


# spec 001 / AC 10
def test_a_row_filed_under_another_character_is_not_shown(fixture_store: Store) -> None:
    """The write route refuses a foreign row; a hand-edited file can still hold one, and
    quiej's knowledge must never surface in ilan's dossier."""
    existing = service.read_knowledge(fixture_store, "ilan").knowledge
    foreign = _row("quiej", "kestrel_deep", "002")
    _write_knowledge(fixture_store, "ilan", [*existing, foreign])

    dossier = service.dossier(fixture_store, "ilan", 318)

    assert all(row.character == "ilan" for row in dossier.knowledge)


def test_a_missing_changes_file_is_not_found_rather_than_no_changes(
    fixture_store: Store,
) -> None:
    """FR-STORE-06: never repaired. Read as empty, a missing `changes.yaml` would show Ilan's
    flesh hand after 002."""
    paths.resolve(fixture_store.root, paths.cast_file("ilan", "changes")).unlink()

    with pytest.raises(NotFound):
        service.dossier(fixture_store, "ilan", 318)


# --------------------------------------------------------------------------------------
# The route
# --------------------------------------------------------------------------------------


# spec 001 / AC 10
def test_the_route_trims_to_the_instant_in_the_query(fixture_client: TestClient) -> None:
    before = fixture_client.get("/cast/ilan/dossier", params={"at": 119})
    after = fixture_client.get("/cast/ilan/dossier", params={"at": 120})

    assert before.status_code == 200
    assert after.status_code == 200
    assert before.json()["immutable_physical"]["left_hand"] == FLESH
    assert before.json()["knowledge"] == []
    assert after.json()["immutable_physical"]["left_hand"] == GRAFT
    assert after.json()["arc"]["scene"] == "002"
    assert "body" not in after.json()


@pytest.mark.parametrize("query", [{}, {"at": "noon"}, {"at": "1.5"}])
def test_the_route_requires_an_integer_instant(
    fixture_client: TestClient, query: dict[str, str]
) -> None:
    """There is no default instant: a dossier "as of now" has no meaning on the story axis."""
    response = fixture_client.get("/cast/ilan/dossier", params=query)

    assert response.status_code == 422


def test_the_route_is_not_found_for_an_unknown_character(fixture_client: TestClient) -> None:
    response = fixture_client.get("/cast/nobody/dossier", params={"at": 0})

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# --------------------------------------------------------------------------------------
# Properties
# --------------------------------------------------------------------------------------

CHARACTER = "ada"
FACTS = ("f1", "f2", "f3")
OTHERS = ("bo", "cy")


@dataclass(frozen=True)
class Tables:
    """One generated world: a clock over some scenes, and a character's dated tables whose
    anchors may or may not be in the clock."""

    clock: dict[str, SceneInstant]
    record: Character
    knowledge: KnowledgeFile
    changes: ChangesFile
    relationships: RelationshipsFile
    at: int


def _scene_id(number: int) -> str:
    return f"{number:03d}"


# Scene numbers 0-11 exist in the clock with some probability; 12-14 never do, so a share of
# every table is anchored to scenes that cannot be placed. A story-time range of -4..4 over
# up to twelve scenes forces ties, which is where "the latest" is easiest to get wrong.
anchors = st.integers(min_value=0, max_value=14).map(_scene_id)


@st.composite
def tables(draw: st.DrawFn, *, with_changes: bool = False) -> Tables:
    numbers = draw(st.sets(st.integers(min_value=0, max_value=11), max_size=12))
    clock = {
        _scene_id(number): SceneInstant(
            story_time=draw(st.integers(min_value=-4, max_value=4)),
            discourse_order=draw(st.integers(min_value=1, max_value=20)),
            scene=_scene_id(number),
        )
        for number in sorted(numbers)
    }
    arc = [
        ArcEntry(scene=scene, state=f"state {index}")
        for index, scene in enumerate(draw(st.lists(anchors, max_size=6)))
    ]
    rows = [
        KnowledgeState(
            character=CHARACTER,
            fact_ref=draw(st.sampled_from(FACTS)),
            acquired_in=scene,
            via=Via.DEDUCED,
            certainty=draw(st.sampled_from(list(Certainty))),
        )
        for scene in draw(st.lists(anchors, max_size=8))
    ]
    edges = [
        Relationship(
            from_character=source,
            to_character=target,
            valence=[
                DatedValence(scene=scene, value=draw(st.integers(min_value=-3, max_value=3)))
                for scene in draw(st.lists(anchors, max_size=5))
            ],
        )
        for source, target in [(CHARACTER, "bo"), (CHARACTER, "cy"), ("bo", CHARACTER)]
        if draw(st.booleans())
    ]
    changes: list[ChangeEvent] = []
    if with_changes:
        for index in range(draw(st.integers(min_value=0, max_value=6))):
            forgets = draw(st.booleans())
            changes.append(
                ChangeEvent(
                    character=CHARACTER,
                    attribute=draw(st.sampled_from(FACTS if forgets else ("eyes", "hand"))),
                    from_value="before",
                    # Distinct values, so a value in the body can be traced to its event.
                    to_value="" if forgets else f"value {index}",
                    scene=draw(anchors),
                    cause="generated",
                )
            )
    record = Character(
        id=CHARACTER,
        name="Ada",
        immutable_physical={"eyes": "baseline eyes", "hand": "baseline hand"},
        wants="w",
        needs="n",
        lies="l",
        arc=arc,
        competences=["c"],
        body="Undated prose that must never reach the trim.",
    )
    return Tables(
        clock=clock,
        record=record,
        knowledge=KnowledgeFile(knowledge=rows),
        changes=ChangesFile(changes=changes),
        relationships=RelationshipsFile(relationships=edges),
        at=draw(st.integers(min_value=-6, max_value=6)),
    )


def _trim(case: Tables) -> TrimmedDossier:
    return trim_dossier(
        case.record, case.knowledge, case.changes, case.relationships, case.clock, case.at
    )


def _is_placed_by(scene: str, case: Tables) -> bool:
    instant = case.clock.get(scene)
    return instant is not None and instant.story_time <= case.at


# spec 001 / AC 10
@settings(max_examples=400, deadline=None)
@given(tables())
def test_property_no_knowledge_dated_after_at_and_none_missing(case: Tables) -> None:
    """Every row shown has an existing scene at or before `at`, and (with no forgettings in
    play) every such row is shown, in story order."""
    dossier = _trim(case)

    for row in dossier.knowledge:
        assert _is_placed_by(row.acquired_in, case)
    expected = [row for row in case.knowledge.knowledge if _is_placed_by(row.acquired_in, case)]
    assert sorted(dossier.knowledge, key=repr) == sorted(expected, key=repr)
    times = [case.clock[row.acquired_in].story_time for row in dossier.knowledge]
    assert times == sorted(times)


# spec 001 / AC 10
@settings(max_examples=400, deadline=None)
@given(tables())
def test_property_valence_is_the_latest_reading_at_or_before_at(case: Tables) -> None:
    """Every reading shown is at or before `at`, and no reading of that edge at or before `at`
    is later on the story axis. Only this character's outgoing edges appear, and only those
    that have a reading to show."""
    dossier = _trim(case)
    shown = {edge.to: edge.valence for edge in dossier.relationships}

    for edge in case.relationships.relationships:
        if edge.from_character != CHARACTER:
            continue
        placed = [reading for reading in edge.valence if _is_placed_by(reading.scene, case)]
        if not placed:
            assert edge.to_character not in shown
            continue
        reading = shown[edge.to_character]
        assert _is_placed_by(reading.scene, case)
        latest = max(case.clock[candidate.scene] for candidate in placed)
        assert case.clock[reading.scene] == latest
    assert set(shown) <= set(OTHERS)


# spec 001 / AC 10
@settings(max_examples=400, deadline=None)
@given(tables())
def test_property_arc_entry_is_the_latest_anchored_at_or_before_at(case: Tables) -> None:
    dossier = _trim(case)
    placed = [entry for entry in case.record.arc if _is_placed_by(entry.scene, case)]

    if not placed:
        assert dossier.arc is None
        return
    assert dossier.arc is not None
    assert _is_placed_by(dossier.arc.scene, case)
    assert case.clock[dossier.arc.scene] == max(case.clock[entry.scene] for entry in placed)


# spec 001 / AC 10
@settings(max_examples=400, deadline=None)
@given(tables(with_changes=True))
def test_property_changes_after_at_never_show(case: Tables) -> None:
    """With ChangeEvents in play: no knowledge row survives a forgetting that happened at or
    before `at` and not before its acquisition, and every body value is either the stored
    baseline or the `to` of a change placed at or before `at` - never a later one."""
    dossier = _trim(case)

    for row in dossier.knowledge:
        assert _is_placed_by(row.acquired_in, case)
        acquired = case.clock[row.acquired_in]
        for change in case.changes.changes:
            if change.to_value or change.attribute != row.fact_ref:
                continue
            assert change.scene in case.clock  # an unplaceable forgetting withholds the fact
            assert not (_is_placed_by(change.scene, case) and acquired <= case.clock[change.scene])

    for attribute, value in dossier.immutable_physical.items():
        on_attribute = [c for c in case.changes.changes if c.attribute == attribute]
        assert all(change.scene in case.clock for change in on_attribute)
        placed = [c for c in on_attribute if _is_placed_by(c.scene, case)]
        if not placed:
            assert value == case.record.immutable_physical[attribute]
            continue
        latest = max(placed, key=lambda c: case.clock[c.scene])
        latest_time = case.clock[latest.scene]
        assert value in {c.to_value for c in placed if case.clock[c.scene] == latest_time}


# spec 001 / AC 10 -- a dossier.md naming another id is refused, not trimmed to nothing: the
# trim filters by the record's id, and an empty dossier with a 200 would read as a character
# who knows nothing.
def test_a_dossier_whose_record_names_another_id_is_refused(
    fixture_store: Store, fixture_client: TestClient
) -> None:
    relative = paths.cast_file("ilan", "dossier")
    target = fixture_store.root / relative
    text = target.read_text(encoding="utf-8")
    assert "\nid: ilan\n" in text
    target.write_text(text.replace("\nid: ilan\n", "\nid: ilan2\n", 1), encoding="utf-8")

    with pytest.raises(InvalidRecord) as raised:
        service.dossier(fixture_store, "ilan", 400)
    assert raised.value.as_body()["file"] == relative
    response = fixture_client.get("/cast/ilan/dossier", params={"at": 400})
    assert response.status_code == 422
