"""Spec 020: `POST /novels/generate` and `GET /novels/{id}/generation`, no model calls."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.novel.pipeline as pipeline
from app.auth import CurrentUser, get_current_user
from app.bible import BibleRepository
from app.reader.generation import GenerationJobs
from app.reader.router import get_bible_path, get_generation_jobs, router

EXAMPLE = Path(__file__).resolve().parents[4] / "evals" / "briefs" / "ejemplo.json"


@pytest.fixture
def client(tmp_path: Path) -> tuple[TestClient, Path, FastAPI]:
    db = tmp_path / "harness.sqlite"
    with BibleRepository.open(db):
        pass
    app = FastAPI()
    app.include_router(router)
    jobs = GenerationJobs()
    app.dependency_overrides[get_bible_path] = lambda: db
    app.dependency_overrides[get_generation_jobs] = lambda: jobs
    return TestClient(app), db, app


def test_invalid_brief_is_422(client: tuple[TestClient, Path, FastAPI]) -> None:
    # spec 020 / AC 1
    http, db, _ = client
    brief = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    brief["recipient"]["age"] = 6
    brief["recipient"].pop("birth_date")
    brief["genre"] = "romance"
    del brief["dedication"]
    response = http.post("/novels/generate", json={"brief": brief})
    assert response.status_code == 422
    report = response.json()["detail"]
    assert report["valid"] is False
    assert "dedication" in report["missing"]
    brief["dedication"] = "Para ti"
    report = http.post("/novels/generate", json={"brief": brief}).json()["detail"]
    assert any("romance" in c for c in report["contradictions"])
    with BibleRepository.open(db) as repo:
        assert repo.list_novels() == []


def test_valid_brief_starts_generate(
    client: tuple[TestClient, Path, FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    # spec 020 / AC 2
    http, _db, app = client
    calls: list[tuple[str, int | None]] = []

    def fake_generate(
        repo: BibleRepository,
        novel_id: str,
        *,
        chapters: int | None = None,
        progress: object = None,
    ) -> object:
        calls.append((repo.get_novel(novel_id).owner_id or "", chapters))
        return SimpleNamespace(status="published", detail="ok")

    monkeypatch.setattr(pipeline, "generate", fake_generate)
    brief = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    response = http.post("/novels/generate", json={"brief": brief, "chapters": 3})
    assert response.status_code == 202
    novel_id = response.json()["novel_id"]
    for _ in range(100):
        state = http.get(f"/novels/{novel_id}/generation").json()
        if state["status"] != "queued" and state["status"] != "running":
            break
        time.sleep(0.05)
    assert state["status"] == "published"
    assert state["chapters_total"] == 3
    assert calls == [("local", 3)]

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="other", email="o@x")
    assert http.get(f"/novels/{novel_id}/generation").status_code == 404
