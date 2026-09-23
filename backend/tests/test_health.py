"""The startup contract and the one route that exists at plan step 2.

These back AC 30 rather than a criterion of their own: the gate is a demonstrated run, and
a gate whose `pytest` stage collects nothing demonstrates nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.commons.config import get_settings
from app.commons.deps import get_embedder
from app.commons.embeddings import EmbeddingModelUnavailableError, FakeEmbedder
from app.main import create_app, verify_store_root


# spec 001 / AC 30 — the gate needs a green pytest stage from step 2 onward.
def test_health_reports_vector_model_and_root(minimal_store: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_embedder] = FakeEmbedder
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["vector"] in {"available", "unavailable"}
    assert body["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert Path(body["store_root"]) == minimal_store


# spec 001 / AC 30 — FR-STORE-01: refuse to start against a directory that is not a story.
def test_startup_refuses_a_root_without_canon_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORY_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match=r"canon/project\.md is missing"):
            verify_store_root(get_settings())
    finally:
        get_settings.cache_clear()


# spec 001 / AC 30 — the refusal must happen on startup, not on first request.
def test_app_does_not_serve_without_a_store_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STORY_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="is not a story tree"), TestClient(create_app()):
            pass  # pragma: no cover - the context manager raises on entry
    finally:
        get_settings.cache_clear()


# spec 001 / AC 9 — FR-EMB-03: offline, a model missing from the cache stops the start and
# names the directory to populate. `minimal_store` sets EMBED_OFFLINE=1 over an empty cache.
def test_offline_startup_refuses_a_missing_model(minimal_store: Path) -> None:
    cache = get_settings().model_cache_dir
    with pytest.raises(EmbeddingModelUnavailableError) as raised, TestClient(create_app()):
        pass  # pragma: no cover - the context manager raises on entry
    assert str(cache) in str(raised.value)
    assert "EMBED_OFFLINE" in str(raised.value)
