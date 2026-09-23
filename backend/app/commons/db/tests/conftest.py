"""Fixtures for the index suites: the index path of the fixture copy, and an app client whose
embedder is the deterministic fake (NFR-06, NFR-09 -- no model load, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.commons.config import get_settings
from app.commons.db.connection import vector_extension_available
from app.commons.deps import get_embedder
from app.commons.embeddings import Embedder, FakeEmbedder


@pytest.fixture
def index_path(fixture_root: Path) -> Path:
    """`STORY_INDEX` of the fixture copy: inside the test's temporary directory."""
    del fixture_root  # requested for its side effect: settings now point at the copy
    return get_settings().index_path


def _fake_embedder() -> Embedder:
    return FakeEmbedder()


@pytest.fixture
def index_client(fixture_client: TestClient) -> TestClient:
    """The whole app on the fixture copy, with `FakeEmbedder` in place of `fastembed`.

    Built on the root `fixture_client` rather than by importing `app.main` here: `app.main`
    mounts every feature router, and a module under `app/commons/` may not import a feature,
    not even from a test (NFR-04, the import contract). The override is read per request, so
    setting it after startup is enough.
    """
    app = fixture_client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_embedder] = _fake_embedder
    return fixture_client


@pytest.fixture
def without_sqlite_vec(monkeypatch: pytest.MonkeyPatch) -> None:
    """`import sqlite_vec` fails, as in the `absent` cell of the CI matrix (AC 7).

    A `None` entry in `sys.modules` makes the import raise `ImportError`, which is exactly
    the failure an uninstalled package produces.
    """
    monkeypatch.setitem(sys.modules, "sqlite_vec", None)
    assert not vector_extension_available()
