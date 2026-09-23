"""AC 7, FR-IDX-03: the vector half is optional, and nothing fails without it.

"No code path fails for a missing extension." With `sqlite_vec` made unimportable -- which
is what the `absent` cell of the CI matrix does for real by uninstalling it -- the backend
starts, `/health` says `vector: unavailable`, a rebuild writes rows and FTS5 alone, and
selection is FTS5-ranked. With it, the vector table is `float[384]` and answers KNN.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.commons.db import rebuild, search_text, search_vector, status, update
from app.commons.db.tests.support import (
    embeddings_of,
    raw,
    requires_sqlite_vec,
    rows_of,
)
from app.commons.embeddings import FakeEmbedder
from app.commons.stores import Store

EXPECTED_ROWS = 21
QUERY = "brine lamp light four metres sound ping"


# spec 001 / AC 7 -- without sqlite-vec: startup is fine and /health says unavailable.
def test_without_sqlite_vec_the_backend_starts_and_health_says_unavailable(
    without_sqlite_vec: None, index_client: TestClient
) -> None:
    response = index_client.get("/health")

    assert response.status_code == 200
    assert response.json()["vector"] == "unavailable"


# spec 001 / AC 7 -- the rebuild and status routes work without it, writing no vectors.
def test_without_sqlite_vec_rebuild_and_status_work(
    without_sqlite_vec: None, index_client: TestClient
) -> None:
    rebuilt = index_client.post("/index/rebuild")
    assert rebuilt.status_code == 200
    assert rebuilt.json()["vector"] == "unavailable"
    assert rebuilt.json()["embedded"] == 0
    assert rebuilt.json()["rows"] == EXPECTED_ROWS

    state = index_client.get("/index/status").json()
    assert state["vector"] == "unavailable"
    assert state["vector_rows"] == 0
    assert state["orphans"] == 0
    assert state["migrations"]["0003_vec"] == "skipped"
    assert state["rebuild_required"] is None


# spec 001 / AC 7 -- selection is FTS5-ranked: ranked hits from the text half, none from the
# vector half, and no error from either.
def test_without_sqlite_vec_selection_is_fts5_ranked(
    without_sqlite_vec: None, fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    [query_vector] = FakeEmbedder().embed([QUERY])

    text_hits = search_text(index_path, QUERY)
    vector_hits = search_vector(
        index_path, query_vector, embedding_model=FakeEmbedder().model_name
    )

    assert text_hits[0].entity_id == "ax_brine_dark"
    assert [hit.score for hit in text_hits] == sorted(
        (hit.score for hit in text_hits), reverse=True
    )
    assert vector_hits == []


# spec 001 / AC 7 -- an incremental update without it embeds nothing and still works.
def test_without_sqlite_vec_update_embeds_nothing(
    without_sqlite_vec: None, fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    report = update(fixture_store, FakeEmbedder(), index_path)

    assert (report.mode, report.embedded, report.vector) == ("incremental", 0, "unavailable")


# spec 001 / AC 7 -- with sqlite-vec: /health says available.
@requires_sqlite_vec
def test_with_sqlite_vec_health_says_available(index_client: TestClient) -> None:
    assert index_client.get("/health").json()["vector"] == "available"


# spec 001 / AC 7 -- with sqlite-vec: the vec0 table is float[384], every stored vector is
# 384-d, and a vector of any other width is refused by the table itself.
@requires_sqlite_vec
def test_with_sqlite_vec_the_vector_table_is_384_dimensional(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    connection, loaded = raw(index_path)
    try:
        assert loaded
        declared = connection.execute(
            "select sql from sqlite_master where name = 'entity_vec'"
        ).fetchone()
        assert "float[384]" in str(declared[0])
        assert "distance_metric=cosine" in str(declared[0])
        widths = {
            int(row[0])
            for row in connection.execute(
                "select vec_length(embedding) from entity_vec"
            ).fetchall()
        }
        assert widths == {384}
        with pytest.raises(sqlite3.Error):
            connection.execute(
                "insert into entity_vec (entity_rowid, embedding) values (?, ?)",
                (9999, bytes(4 * 383)),
            )
    finally:
        connection.close()
    assert len(embeddings_of(index_path)) == EXPECTED_ROWS


# spec 001 / AC 7 -- with sqlite-vec: KNN answers, nearest first, and a row's own vector finds
# that row first with cosine similarity 1.
@requires_sqlite_vec
def test_with_sqlite_vec_knn_finds_the_nearest_row_first(
    fixture_store: Store, index_path: Path
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)
    [own_text] = [text for _, entity_id, _, _, text, _, _ in rows_of(index_path)
                  if entity_id == "pump_vault"]
    [own_vector] = FakeEmbedder().embed([own_text])

    hits = search_vector(
        index_path, own_vector, embedding_model=FakeEmbedder().model_name, limit=5
    )

    assert hits[0].entity_id == "pump_vault"
    assert hits[0].kind == "location"
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)
    assert len(hits) == 5


# spec 001 / AC 7 -- an index built with sqlite-vec and then opened without it keeps working
# FTS5-only, and says so; when the extension returns, the vectors are known to be stale and
# the next update rebuilds rather than fusing half an index.
@requires_sqlite_vec
def test_an_index_built_with_sqlite_vec_survives_losing_it_and_recovers(
    fixture_store: Store, index_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rebuild(fixture_store, FakeEmbedder(), index_path)

    with monkeypatch.context() as patched:
        patched.setitem(sys.modules, "sqlite_vec", None)
        report = rebuild(fixture_store, FakeEmbedder(), index_path)
        state = status(fixture_store, index_path)
        assert (report.vector, report.embedded) == ("unavailable", 0)
        assert (state.vector, state.vector_rows, state.rows) == ("unavailable", 0, EXPECTED_ROWS)
        assert search_text(index_path, QUERY)[0].entity_id == "ax_brine_dark"

    recovered = status(fixture_store, index_path)
    assert recovered.vector == "available"
    assert recovered.rebuild_required is not None
    assert "sqlite-vec" in recovered.rebuild_required

    healed = update(fixture_store, FakeEmbedder(), index_path)
    assert healed.mode == "rebuild"
    assert healed.embedded == EXPECTED_ROWS
    assert status(fixture_store, index_path).rebuild_required is None
