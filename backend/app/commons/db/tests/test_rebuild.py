"""AC 6 (rebuild half), FR-IDX-02, -04, -07, -08, and the index half of AC 9.

The claim under test is that the index is **derived, never a source**: it is a function of
the tree, so rebuilding it twice -- or deleting it and rebuilding -- gives the same rows and
the same embeddings, no row outlives its file, and an incremental update ends exactly where
a rebuild would. Expected values come from the fixture's README ("Digests and the as-of
rule"): twelve canon entity files, four lexicon terms, three characters, and two chapter
digests (`901`, `902`) -- the scene digests and the arc digest `990` are never rows.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.commons.db import (
    CANON_KIND_BY_DIRECTORY,
    EmbeddingModelMismatchError,
    IndexHit,
    IndexKind,
    ensure_current,
    rebuild,
    search_text,
    search_vector,
    status,
    update,
)
from app.commons.db.connection import vector_extension_available
from app.commons.db.index import META_EMBEDDING_DIM, META_EMBEDDING_MODEL, fts_query
from app.commons.db.tests.support import (
    CountingEmbedder,
    OtherModelEmbedder,
    delete_index,
    embeddings_of,
    fts_of,
    metadata_of,
    raw,
    requires_sqlite_vec,
    rows_by_key,
    rows_of,
)
from app.commons.embeddings import FakeEmbedder
from app.commons.errors import InvalidRecord
from app.commons.permissions import AgentRole
from app.commons.stores import Store, paths

EXPECTED_KINDS = {
    "axiom": 4,
    "technology": 2,
    "location": 2,
    "faction": 2,
    "historical_event": 2,
    "term": 4,
    "character": 3,
    "chapter_digest": 2,
}
EXPECTED_ROWS = sum(EXPECTED_KINDS.values())

AXIOM = paths.canon_entity("axioms", "ax_brine_dark")


def _edit(store: Store, relative: str, old: str, new: str, role: AgentRole) -> None:
    """Change one store file through the store layer, so provenance records the write."""
    text = store.read_raw(relative)
    assert old in text
    store.write_text(relative, text.replace(old, new, 1), role=role)


# spec 001 / AC 6 -- two rebuilds of the same tree: identical rows and identical embeddings.
def test_two_rebuilds_yield_identical_rows_and_embeddings(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    first_rows, first_vectors = rows_of(index_path), embeddings_of(index_path)

    rebuild(fixture_store, FakeEmbedder(), index_path)

    assert len(first_rows) == EXPECTED_ROWS
    assert rows_of(index_path) == first_rows
    assert embeddings_of(index_path) == first_vectors
    if vector_extension_available():
        assert len(first_vectors) == EXPECTED_ROWS


# spec 001 / AC 6 -- delete the index outright and rebuild: the same rows, the same vectors.
def test_delete_and_rebuild_reproduces_rows_and_embeddings(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    before_rows, before_vectors = rows_of(index_path), embeddings_of(index_path)

    delete_index(index_path)
    assert not index_path.exists()
    rebuild(fixture_store, FakeEmbedder(), index_path)

    assert rows_of(index_path) == before_rows
    assert embeddings_of(index_path) == before_vectors


# spec 001 / AC 6 -- orphans are zero after a rebuild (FR-IDX-07).
def test_orphans_are_zero_after_a_rebuild(fixture_store: Store, index_path: Path) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    report = status(fixture_store, index_path)

    assert report.orphans == 0
    assert report.rows == EXPECTED_ROWS


# spec 001 / AC 6 -- and the orphan count is real: a row whose file is gone is counted, and a
# rebuild removes it. "An index entry with no backing record in the stores is a bug."
def test_a_row_whose_file_is_gone_is_an_orphan_until_rebuilt(
    fixture_root: Path, fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    (fixture_root / "canon" / "technology" / "te_hand_sonar.md").unlink()

    assert status(fixture_store, index_path).orphans == 1

    rebuild(fixture_store, FakeEmbedder(), index_path)
    after = status(fixture_store, index_path)
    assert after.orphans == 0
    assert after.rows == EXPECTED_ROWS - 1


# spec 001 / AC 6 -- FR-IDX-02 and plan step 9: exactly the rows the tree implies.
def test_rows_are_one_per_entity_term_character_and_chapter_digest(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    keyed = rows_by_key(index_path)

    assert status(fixture_store, index_path).kinds == dict(sorted(EXPECTED_KINDS.items()))
    terms = {entity_id for kind, entity_id in keyed if kind == "term"}
    assert terms == {"lx_soak", "lx_calving", "lx_readkey", "lx_vault"}
    assert {keyed[("term", term)][0] for term in terms} == {paths.LEXICON}
    assert {entity_id for kind, entity_id in keyed if kind == "character"} == {
        "vance",
        "ilan",
        "quiej",
    }
    assert keyed[("character", "vance")][0] == paths.cast_file("vance", "dossier")
    indexed_paths = {path for path, _, _, _ in keyed.values()}
    # The fixed block and the calendar are loaded by identity, never ranked.
    assert not indexed_paths & {paths.PROJECT, paths.STYLE, paths.TIME}


# spec 001 / AC 6 -- plan step 9: a scene digest and an arc digest never become rows.
def test_scene_and_arc_digests_never_become_rows(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    digest_rows = {
        entity_id: path
        for (kind, entity_id), (path, _, _, _) in rows_by_key(index_path).items()
        if path.startswith(paths.DIGESTS)
    }

    assert digest_rows == {"901": paths.digest("901"), "902": paths.digest("902")}
    # Words only the arc digest 990 uses: a ranking must not be able to reach it.
    hits = search_text(index_path, "arc of the descent paying for it with her brother")
    assert all(hit.entity_id not in {"002", "003", "990"} for hit in hits)


# spec 001 / AC 6 -- nor does a scene digest written later, through an incremental update.
def test_a_scene_digest_written_later_never_becomes_a_row(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    digest_text = (
        "---\nschema_version: 1\nscene_ref: '004'\nlevel: scene\npovs:\n- vance\n"
        "delta: Vance asked the graft hand for the seating sequence and it answered.\n"
        "words: 11\n---\n\n"
    )
    fixture_store.write_text(paths.digest("004"), digest_text, role=AgentRole.WRITER)

    report = update(fixture_store, FakeEmbedder(), index_path)

    assert report.embedded == 0
    assert ("chapter_digest", "004") not in rows_by_key(index_path)
    assert status(fixture_store, index_path).rows == EXPECTED_ROWS


# spec 001 / AC 6 -- `updated_at` is the last recorded write, never the rebuild's clock, so
# two rebuilds stay identical even for a file written through the backend.
def test_updated_at_is_the_last_provenance_write_and_rebuilds_stay_identical(
    fixture_store: Store, index_path: Path
) -> None:
    _edit(fixture_store, AXIOM, "Four metres", "Four metres flat", AgentRole.WORLD_BUILDER)
    [written] = fixture_store.provenance(path=AXIOM)

    rebuild(fixture_store, FakeEmbedder(), index_path)
    first = rows_of(index_path)
    rebuild(fixture_store, FakeEmbedder(), index_path)

    assert rows_of(index_path) == first
    keyed = rows_by_key(index_path)
    assert keyed[("axiom", "ax_brine_dark")][3] == written.at
    assert keyed[("axiom", "ax_cold_soak")][3] is None


# spec 001 / AC 6 -- FR-IDX-08: an update re-embeds only the rows whose hash changed, and
# ends with exactly the rows and vectors a fresh rebuild of the same tree would have.
def test_an_update_reembeds_only_changed_rows_and_matches_a_rebuild(
    fixture_store: Store, index_path: Path, tmp_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    _edit(fixture_store, AXIOM, "Four metres", "Four metres flat", AgentRole.WORLD_BUILDER)
    # One term of four in the shared lexicon file: one row, not four.
    _edit(fixture_store, paths.LEXICON, "KOHLD sohk", "KOHLD SOHK", AgentRole.WORLD_BUILDER)
    (fixture_store.root / "canon" / "factions" / "divers_register.md").unlink()

    counting = CountingEmbedder()
    report = update(fixture_store, counting, index_path)

    assert report.mode == "incremental"
    assert report.removed == 1
    assert report.rows == EXPECTED_ROWS - 1
    if vector_extension_available():
        assert report.embedded == 2
        assert len(counting.texts) == 2
        assert any("KOHLD SOHK" in text for text in counting.texts)
        assert any("Four metres flat" in text for text in counting.texts)
    else:
        assert counting.texts == []

    fresh = tmp_path / "fresh" / "index.sqlite"
    rebuild(fixture_store, FakeEmbedder(), fresh)
    assert rows_by_key(index_path) == rows_by_key(fresh)
    assert embeddings_of(index_path) == embeddings_of(fresh)
    # The FTS copy too: a deleted entity must not stay searchable, nor an edited one keep
    # its old text (FR-IDX-02 -- an entry with no backing record is a bug).
    assert fts_of(index_path) == fts_of(fresh)
    assert all(attached for _, _, _, attached in fts_of(index_path))
    assert status(fixture_store, index_path).orphans == 0


# spec 001 / AC 6 -- FR-IDX-08: nothing changed, nothing embedded.
def test_an_update_of_an_unchanged_tree_embeds_nothing(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    before = rows_of(index_path)
    counting = CountingEmbedder()

    report = update(fixture_store, counting, index_path)

    assert (report.mode, report.embedded, report.removed) == ("incremental", 0, 0)
    assert counting.calls == []
    assert rows_of(index_path) == before


# spec 001 / AC 9 -- a different embedding model forces a rebuild (FR-IDX-07): vectors from
# two models must never sit in one table.
def test_a_different_embedder_model_forces_a_rebuild(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    other = OtherModelEmbedder()

    report = update(fixture_store, other, index_path)

    assert report.mode == "rebuild"
    assert report.reason is not None
    assert "fake-sha256-384" in report.reason
    assert other.model_name in report.reason
    assert metadata_of(index_path)[META_EMBEDDING_MODEL] == other.model_name
    if vector_extension_available():
        assert report.embedded == EXPECTED_ROWS
        fresh_other = {
            key: vector
            for key, vector in embeddings_of(index_path).items()
            if key == ("axiom", "ax_brine_dark")
        }
        rebuild(fixture_store, FakeEmbedder(), index_path)
        assert embeddings_of(index_path)[("axiom", "ax_brine_dark")] != fresh_other[
            ("axiom", "ax_brine_dark")
        ]


# spec 001 / AC 9 -- the recorded metadata is what decides: edit it, and the next update
# rebuilds even though the embedder did not change.
def test_changed_embedding_model_metadata_forces_a_rebuild(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    connection, _ = raw(index_path)
    try:
        connection.execute(
            "update index_metadata set value = 'sentence-transformers/all-MiniLM-L6-v2' "
            "where key = ?",
            (META_EMBEDDING_MODEL,),
        )
    finally:
        connection.close()

    report = update(fixture_store, FakeEmbedder(), index_path)

    assert report.mode == "rebuild"
    assert report.reason is not None
    assert "all-MiniLM-L6-v2" in report.reason
    assert metadata_of(index_path)[META_EMBEDDING_MODEL] == "fake-sha256-384"


# spec 001 / AC 9 -- FR-IDX-07 names `embedding_dim` beside the model: a recorded dimension
# that differs from the embedder's forces a rebuild on its own.
def test_changed_embedding_dim_metadata_forces_a_rebuild(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    connection, _ = raw(index_path)
    try:
        connection.execute(
            "update index_metadata set value = '768' where key = ?", (META_EMBEDDING_DIM,)
        )
    finally:
        connection.close()

    report = update(fixture_store, FakeEmbedder(), index_path)

    assert report.mode == "rebuild"
    assert report.reason is not None
    assert "768" in report.reason
    assert metadata_of(index_path)[META_EMBEDDING_DIM] == "384"


# spec 001 / AC 9 -- a query embedded by another model is refused rather than fused, and
# `ensure_current` is what makes the refusal unreachable for a caller that uses it.
@requires_sqlite_vec
def test_a_vector_query_from_another_model_is_refused_until_ensure_current(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    other = OtherModelEmbedder()
    [query] = other.embed(["brine and light"])

    with pytest.raises(EmbeddingModelMismatchError, match="fake-sha256-384"):
        search_vector(index_path, query, embedding_model=other.model_name)

    forced = ensure_current(fixture_store, other, index_path)
    assert forced is not None
    assert forced.mode == "rebuild"
    assert search_vector(index_path, query, embedding_model=other.model_name)
    assert ensure_current(fixture_store, other, index_path) is None


# spec 001 / AC 6 -- a file that does not parse is refused naming it, and the index built
# before it is left exactly as it was: nothing is half rebuilt.
def test_an_unparseable_file_is_refused_and_leaves_the_index_untouched(
    fixture_root: Path, fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    before = rows_of(index_path)
    broken = fixture_root / "canon" / "locations" / "pump_vault.md"
    broken.write_text("---\nschema_version: 1\nid: pump_vault\n", encoding="utf-8")

    with pytest.raises(InvalidRecord) as refused:
        rebuild(fixture_store, FakeEmbedder(), index_path)

    assert refused.value.context["file"] == paths.canon_entity("locations", "pump_vault")
    assert rows_of(index_path) == before


# spec 001 / AC 6 -- a canon file whose declared id disagrees with its name is refused, as
# the canon write route refuses it.
def test_a_canon_file_whose_id_disagrees_with_its_name_is_refused(
    fixture_root: Path, fixture_store: Store, index_path: Path
) -> None:
    target = fixture_root / "canon" / "axioms" / "ax_cold_soak.md"
    target.write_text(
        target.read_text(encoding="utf-8").replace("id: ax_cold_soak", "id: ax_other", 1),
        encoding="utf-8",
    )

    with pytest.raises(InvalidRecord) as refused:
        rebuild(fixture_store, FakeEmbedder(), index_path)

    assert refused.value.context == {
        "file": paths.canon_entity("axioms", "ax_cold_soak"),
        "field": "id",
    }


# spec 001 / AC 6 -- every canon directory has a row kind, so none is silently unindexed.
def test_every_canon_directory_has_a_row_kind() -> None:
    assert set(CANON_KIND_BY_DIRECTORY) == set(paths.CANON_KINDS)
    assert set(CANON_KIND_BY_DIRECTORY.values()) <= set(IndexKind)


# spec 001 / AC 7 -- FR-OPS-02: hits carry identifiers, kinds and scores and nothing else.
def test_search_hits_carry_no_text(fixture_store: Store, index_path: Path) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    hits = search_text(index_path, "brine lamp light four metres sound")

    assert hits
    assert set(IndexHit.__dataclass_fields__) == {"entity_id", "kind", "score"}
    assert hits[0].entity_id == "ax_brine_dark"
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


# spec 001 / AC 7 -- a scene record is free text, not FTS5 syntax: punctuation that FTS5
# reads as operators must not break the search.
@pytest.mark.parametrize(
    "query",
    ['NEAR("brine" lamp)', "cold-soak: 6 hours * AND OR NOT", '"', "", "   ", "-- ;"],
)
def test_free_text_with_fts_syntax_does_not_break_the_search(
    fixture_store: Store, index_path: Path, query: str
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    hits = search_text(index_path, query)
    assert isinstance(hits, list)
    if fts_query(query) is None:
        assert hits == []


# spec 001 / AC 6 -- IF-05: the two routes, on the fixture, with the fake embedder.
def test_the_rebuild_and_status_routes(index_client: TestClient) -> None:
    rebuilt = index_client.post("/index/rebuild")
    assert rebuilt.status_code == 200
    body = rebuilt.json()
    assert (body["mode"], body["reason"], body["rows"]) == ("rebuild", "requested", EXPECTED_ROWS)
    assert body["embedding_model"] == "fake-sha256-384"

    reported = index_client.get("/index/status")
    assert reported.status_code == 200
    state = reported.json()
    assert (state["rows"], state["orphans"]) == (EXPECTED_ROWS, 0)
    assert state["embedding_dim"] == 384
    assert state["rebuild_required"] is None
    assert state["migrations"]["0001_init"] == "applied"


# spec 001 / AC 6 -- the route reports an unparseable file as IF-07's 422, naming it.
def test_the_rebuild_route_reports_an_unparseable_file_as_422(
    fixture_root: Path, index_client: TestClient
) -> None:
    (fixture_root / "cast" / "ilan" / "dossier.md").write_text(
        "---\nid: ilan\n", encoding="utf-8"
    )

    response = index_client.post("/index/rebuild")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_record"
    assert response.json()["file"] == paths.cast_file("ilan", "dossier")


# spec 001 / AC 6 -- the index file is SQLite's to integrity-check, not ours to trust.
def test_a_rebuilt_index_passes_integrity_check(fixture_store: Store, index_path: Path) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    connection = sqlite3.connect(index_path)
    try:
        assert connection.execute("pragma integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()
