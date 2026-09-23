"""FR-OPS-02, `select_entities` -- AC 11 (ids only, pins first, POV absent) and AC 7's
selection half (FTS5-ranked without `sqlite-vec`, fused with it).

Every test runs on a private copy of the fixture novel with `FakeEmbedder` (NFR-09). The fake's
vectors are unrelated to meaning, so nothing here asserts *which* entity is semantically
nearest; what is asserted is structure -- what comes first, what is absent, what is never
returned, and that the same tree gives the same answer. Scene 006 is the fixture's case for
pinning (README "Selection and assembly"): `pins: [ax_brine_dark, lx_vault]` and
`tags: [vault, perception]` against that axiom's scope, so the two mechanisms overlap on
purpose and the axiom must appear once.
"""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.canon.models import Axiom
from app.commons.config import Settings, get_settings
from app.commons.db import IndexHit, IndexReport, rebuild, search_text, status
from app.commons.db.connection import vector_extension_available
from app.commons.embeddings import FakeEmbedder
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Scene, SelectedEntity
from app.commons.stores import Store, paths
from app.scenes import service
from app.scenes.models import Selection
from app.scenes.select import fuse, query_text

SCENES = ("001", "002", "003", "004", "005", "006")
INDEXED_DIGESTS = frozenset({"901", "902"})
UNINDEXED_DIGESTS = frozenset({"002", "003", "990"})
"""README "Digests and the as-of rule": only the two chapter digests are rows. The scene
digests (002, 003) and the arc digest (990) must never come back from a selection."""

TEXT_FIELD_NAMES = frozenset({"text", "body", "content", "prose", "summary"})

requires_sqlite_vec = pytest.mark.skipif(
    not vector_extension_available(),
    reason="sqlite-vec does not load here; the CI `present` cell runs this (AC 7)",
)


class RecordingEmbedder(FakeEmbedder):
    """The fake, recording every batch it is asked to embed."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return super().embed(texts)


@pytest.fixture
def settings(fixture_store: Store) -> Settings:
    """The settings of the fixture copy: `STORY_INDEX` inside the test's temporary directory.

    Settings rather than the index path, because a module under `app/scenes/` may not import
    `pathlib` (NFR-04, the import contract) -- tests included.
    """
    del fixture_store  # requested for its side effect: settings now point at the copy
    return get_settings()


@pytest.fixture
def without_sqlite_vec(monkeypatch: pytest.MonkeyPatch) -> None:
    """`import sqlite_vec` fails, as in the `absent` cell of the CI matrix (AC 7). A `None`
    entry in `sys.modules` raises `ImportError`, as an uninstalled package does."""
    monkeypatch.setitem(sys.modules, "sqlite_vec", None)
    assert not vector_extension_available()


def select(store: Store, settings: Settings, scene: str = "006") -> Selection:
    return service.select_entities(store, FakeEmbedder(), settings, scene)


def keys(selection: Selection) -> list[tuple[str, str, bool]]:
    return [(entry.entity_id, entry.kind, entry.pinned) for entry in selection.entities]


def rewrite_scene(store: Store, identifier: str, **changes: list[str]) -> Scene:
    """Write a variant of a fixture scene into the private copy, as the architect."""
    scene = store.read(paths.scene(identifier), Scene)
    changed = scene.model_copy(update=changes)
    store.write(paths.scene(identifier), changed, role=AgentRole.ARCHITECT, actor=Actor.HUMAN)
    return changed


def field_names(model: type[BaseModel]) -> set[str]:
    """Every field name reachable from `model` through nested models and lists of them."""
    found: set[str] = set()
    for name, info in model.model_fields.items():
        found.add(name)
        annotation = info.annotation
        nested = getattr(annotation, "__args__", (annotation,))
        for candidate in nested:
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                found |= field_names(candidate)
    return found


# --------------------------------------------------------------------------------------
# AC 11 -- identifiers only
# --------------------------------------------------------------------------------------


# spec 001 / AC 11 -- the result types have no text field: the exact field sets, so a text
# field added later fails here rather than reaching the writer's context by the back door.
def test_the_selection_types_carry_no_text() -> None:
    assert set(SelectedEntity.model_fields) == {"entity_id", "kind", "score", "pinned"}
    assert set(Selection.model_fields) == {"scene", "pov", "fused", "entities", "index_update"}
    reachable = field_names(Selection)
    assert {"entity_id", "kind", "score", "pinned", "mode", "rows"} <= reachable
    assert not reachable & TEXT_FIELD_NAMES
    assert not set(IndexReport.model_fields) & TEXT_FIELD_NAMES


# spec 001 / AC 11 -- and on the wire: no string in the answer is a record's text. Every
# entry is exactly an id, a kind, a score and a flag.
def test_the_route_answers_ids_kinds_and_scores(fixture_client: TestClient) -> None:
    response = fixture_client.post("/scenes/006/select")

    assert response.status_code == 200
    body = response.json()
    assert body["scene"] == "006"
    assert body["entities"]
    assert all(set(entry) == {"entity_id", "kind", "score", "pinned"} for entry in body["entities"])
    assert not set(body) & TEXT_FIELD_NAMES


# --------------------------------------------------------------------------------------
# AC 11 -- pins first, then tag-scope axioms
# --------------------------------------------------------------------------------------


# spec 001 / AC 11 -- scene 006: the pinned entities come first, in the record's order, the
# axiom its tags also pin appears once, and everything after them is ranked, not pinned.
def test_scene_006_pins_come_first_in_record_order(
    fixture_store: Store, settings: Settings
) -> None:
    selection = select(fixture_store, settings)

    assert keys(selection)[:2] == [("ax_brine_dark", "axiom", True), ("lx_vault", "term", True)]
    ranked = selection.entities[2:]
    assert ranked
    assert not any(entry.pinned for entry in ranked)
    assert [entry.entity_id for entry in selection.entities].count("ax_brine_dark") == 1


# spec 001 / AC 11 -- the axioms whose scope the tags intersect follow the pins, by id, matched
# trimmed and case-folded as `reconcile` matches them.
def test_tag_scope_axioms_follow_the_pins_by_id(fixture_store: Store, settings: Settings) -> None:
    rewrite_scene(fixture_store, "006", pins=["lx_vault"], tags=[" LAW ", "Surface", "vault"])

    selection = select(fixture_store, settings)

    assert keys(selection)[:4] == [
        ("lx_vault", "term", True),
        ("ax_brine_dark", "axiom", True),
        ("ax_calving_window", "axiom", True),
        ("ax_indemnity_burn", "axiom", True),
    ]
    assert not any(entry.pinned for entry in selection.entities[4:])
    assert "ax_cold_soak" not in [entry.entity_id for entry in selection.entities[:4]]


# spec 001 / AC 11 -- a pinned entity keeps the fused score the ranking gave it; a pinned entity
# the ranking did not reach scores 0. Either way its place is decided by the pin.
def test_a_pinned_entry_carries_its_fused_score(fixture_store: Store, settings: Settings) -> None:
    selection = select(fixture_store, settings)
    brine = selection.entities[0]

    assert brine.entity_id == "ax_brine_dark"
    assert brine.score > 0.0

    unranked = service.select_entities(fixture_store, FakeEmbedder(), settings, "006", limit=0)
    assert keys(unranked) == [("ax_brine_dark", "axiom", True), ("lx_vault", "term", True)]


# spec 001 / AC 11 -- a pin that names no entity is a defect of the scene record: refused with
# the file and the field, never skipped.
def test_a_pin_naming_no_entity_is_refused(fixture_store: Store, settings: Settings) -> None:
    rewrite_scene(fixture_store, "006", pins=["lx_vault", "ax_never_written"])

    with pytest.raises(InvalidRecord) as refused:
        select(fixture_store, settings)

    assert refused.value.context["file"] == "scenes/006.yaml"
    assert refused.value.context["field"] == "pins.1"
    assert "ax_never_written" in str(refused.value)


# spec 001 / AC 11 -- the same refusal on the wire is IF-07's 422, naming file and field.
def test_the_route_refuses_an_unresolvable_pin_with_422(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    rewrite_scene(fixture_store, "006", pins=["ax_never_written"])

    response = fixture_client.post("/scenes/006/select")

    assert response.status_code == 422
    body = response.json()
    assert (body["error"], body["file"], body["field"]) == (
        "invalid_record",
        "scenes/006.yaml",
        "pins.0",
    )


# spec 001 / FR-OPS-02 -- a scene that does not exist is a 404, not an empty selection.
def test_the_route_404s_for_a_missing_scene(fixture_client: TestClient) -> None:
    response = fixture_client.post("/scenes/999/select")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# --------------------------------------------------------------------------------------
# AC 11 -- the POV is absent
# --------------------------------------------------------------------------------------


# spec 001 / AC 11 -- the POV is absent from every scene's selection, although its id is in the
# query text and its dossier therefore ranks: the exclusion is doing the work.
@pytest.mark.parametrize("scene", SCENES)
def test_the_pov_is_absent(fixture_store: Store, settings: Settings, scene: str) -> None:
    record = fixture_store.read(paths.scene(scene), Scene)

    selection = select(fixture_store, settings, scene)

    assert selection.pov == record.pov
    assert (record.pov, "character") not in [(e.entity_id, e.kind) for e in selection.entities]
    ranked_by_text = search_text(settings.index_path, query_text(record), limit=100)
    assert (record.pov, "character") in [(hit.entity_id, hit.kind) for hit in ranked_by_text]


# spec 001 / AC 11 -- pinning the POV does not bring it back: it enters assembly by identifier.
def test_a_pinned_pov_is_dropped(fixture_store: Store, settings: Settings) -> None:
    rewrite_scene(fixture_store, "006", pins=["vance", "lx_vault"])

    selection = select(fixture_store, settings)

    assert keys(selection)[0] == ("lx_vault", "term", True)
    assert "vance" not in [entry.entity_id for entry in selection.entities]


# --------------------------------------------------------------------------------------
# FR-IDX-02 -- scene and arc digests are never selected
# --------------------------------------------------------------------------------------


# spec 001 / AC 11 -- no scene digest and no arc digest (990) in any scene's selection; the
# only digests that can appear are the two chapter digests.
@pytest.mark.parametrize("scene", SCENES)
def test_no_scene_or_arc_digest_is_selected(
    fixture_store: Store, settings: Settings, scene: str
) -> None:
    selection = select(fixture_store, settings, scene)

    digests = {e.entity_id for e in selection.entities if e.kind == "chapter_digest"}
    assert digests <= INDEXED_DIGESTS
    assert not {e.entity_id for e in selection.entities} & UNINDEXED_DIGESTS


# spec 001 / AC 11 -- and a pin cannot smuggle one in: the arc digest is not an entity a pin
# can name.
def test_a_pin_on_the_arc_digest_is_refused(fixture_store: Store, settings: Settings) -> None:
    rewrite_scene(fixture_store, "006", pins=["990"])

    with pytest.raises(InvalidRecord) as refused:
        select(fixture_store, settings)

    assert refused.value.context["field"] == "pins.0"


# --------------------------------------------------------------------------------------
# FR-IDX-08 -- the incremental update runs at the start of every selection
# --------------------------------------------------------------------------------------


# spec 001 / FR-IDX-08 -- an entity written after the last rebuild is selected without an
# explicit rebuild: the update ran first. Its statement shares words with scene 006's record.
def test_an_entity_written_after_the_last_rebuild_is_selected(
    fixture_store: Store, settings: Settings
) -> None:
    before = rebuild(fixture_store, FakeEmbedder(), settings.index_path)
    axiom = Axiom(
        id="ax_seal_ring",
        statement="A seal ring on a core cradle holds only while the throat stays closed.",
        scope=["seal"],
        consequences=["A broken ring is known by touch, never guessed"],
        cost="certainty about the core",
        body="Written after the rebuild, to prove the selection updates the index first.\n",
    )
    fixture_store.write(
        paths.canon_entity("axioms", "ax_seal_ring"),
        axiom,
        role=AgentRole.WORLD_BUILDER,
        actor=Actor.HUMAN,
    )

    selection = select(fixture_store, settings)

    assert ("ax_seal_ring", "axiom", False) in keys(selection)
    assert selection.index_update.mode == "incremental"
    assert selection.index_update.rows == before.rows + 1


# spec 001 / FR-IDX-08 -- on a tree never indexed, the first selection builds the index
# rather than failing or ranking nothing (FR-IDX-07's forced rebuild).
def test_the_first_selection_builds_the_index(fixture_store: Store, settings: Settings) -> None:
    assert status(fixture_store, settings.index_path).rows == 0

    selection = select(fixture_store, settings)

    assert selection.index_update.mode == "rebuild"
    assert selection.index_update.reason == "the index has never been built"
    assert len(selection.entities) > 2


# --------------------------------------------------------------------------------------
# AC 7 -- FTS5-only without sqlite-vec, fused with it
# --------------------------------------------------------------------------------------


# spec 001 / AC 7 -- without sqlite-vec: selection works, is FTS5-ranked in BM25 order, pins
# still come first, and the embedder is never called -- there is nowhere to put a vector.
def test_without_sqlite_vec_selection_is_fts5_ranked(
    without_sqlite_vec: None, fixture_store: Store, settings: Settings
) -> None:
    embedder = RecordingEmbedder()
    record = fixture_store.read(paths.scene("006"), Scene)

    selection = service.select_entities(fixture_store, embedder, settings, "006")

    assert selection.fused is False
    assert selection.index_update.vector == "unavailable"
    assert embedder.calls == []
    assert keys(selection)[:2] == [("ax_brine_dark", "axiom", True), ("lx_vault", "term", True)]
    excluded = {("character", record.pov), ("axiom", "ax_brine_dark"), ("term", "lx_vault")}
    bm25_order = [
        hit.entity_id
        for hit in search_text(settings.index_path, query_text(record), limit=100)
        if (hit.kind, hit.entity_id) not in excluded
    ]
    assert [entry.entity_id for entry in selection.entities[2:]] == bm25_order


# spec 001 / AC 7 -- with sqlite-vec: the ranking is fused, and the query embedded is the
# scene record's query text.
@requires_sqlite_vec
def test_with_sqlite_vec_selection_is_fused(fixture_store: Store, settings: Settings) -> None:
    embedder = RecordingEmbedder()
    record = fixture_store.read(paths.scene("006"), Scene)

    selection = service.select_entities(fixture_store, embedder, settings, "006")

    assert selection.fused is True
    assert selection.index_update.vector == "available"
    assert embedder.calls[-1] == [query_text(record)]
    assert keys(selection)[:2] == [("ax_brine_dark", "axiom", True), ("lx_vault", "term", True)]


# --------------------------------------------------------------------------------------
# The route, determinism, fusion and the query
# --------------------------------------------------------------------------------------


# spec 001 / AC 11 -- the route returns the same selection as the function, entry for entry.
def test_the_route_returns_what_the_function_returns(
    fixture_client: TestClient, fixture_store: Store, settings: Settings
) -> None:
    body = fixture_client.post("/scenes/006/select").json()

    selection = select(fixture_store, settings)

    assert body["entities"] == [entry.model_dump(mode="json") for entry in selection.entities]
    assert (body["pov"], body["fused"]) == (selection.pov, selection.fused)


# spec 001 / AC 11 -- the same tree gives the same selection, order and scores included.
def test_selection_is_deterministic(fixture_store: Store, settings: Settings) -> None:
    first = select(fixture_store, settings)
    second = select(fixture_store, settings)

    assert first.entities == second.entities


# spec 001 / AC 11 -- ties are ordered by kind, then id, whatever order the inputs gave them.
def test_fusion_orders_ties_by_kind_then_id() -> None:
    text = [IndexHit("pump_vault", "location", 9.0), IndexHit("ax_z", "axiom", 8.0)]
    vector = [IndexHit("ax_a", "axiom", 0.9), IndexHit("ilan", "character", 0.8)]
    expected = [
        ("axiom", "ax_a"),
        ("location", "pump_vault"),
        ("axiom", "ax_z"),
        ("character", "ilan"),
    ]

    assert [(hit.kind, hit.entity_id) for hit in fuse(text, vector)] == expected
    assert [(hit.kind, hit.entity_id) for hit in fuse(vector, text)] == expected


# spec 001 / FR-OPS-02 -- reciprocal rank: agreement between the halves beats one half's first
# place, and one list alone keeps its own order.
def test_fusion_rewards_agreement_and_keeps_a_single_list_in_order() -> None:
    text = [IndexHit("a", "axiom", 3.0), IndexHit("b", "axiom", 2.0), IndexHit("c", "axiom", 1.0)]
    vector = [IndexHit("d", "axiom", 0.9), IndexHit("c", "axiom", 0.8)]

    fused = fuse(text, vector)

    assert fused[0].entity_id == "c"
    assert fused[0].score == pytest.approx(1 / 63 + 1 / 62)
    assert [hit.entity_id for hit in fuse(text)] == ["a", "b", "c"]
    assert fuse() == []


# spec 001 / FR-OPS-02 -- the query is the eight dramatic fields, `notes` included; the pinning
# fields are not part of it.
def test_the_query_is_the_scene_records_dramatic_fields(fixture_store: Store) -> None:
    record = fixture_store.read(paths.scene("006"), Scene)

    query = query_text(record)

    assert record.notes is not None
    for value in (
        record.goal,
        record.conflict,
        record.value_change,
        record.pov,
        record.location,
        record.entry_state,
        record.exit_state,
        record.notes,
    ):
        assert value in query
    assert "perception" not in query
    assert "ax_brine_dark" not in query
