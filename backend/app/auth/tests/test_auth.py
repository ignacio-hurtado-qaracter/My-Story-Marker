"""Spec 018 (X03, SEC-01): login, and a user never reaches another user's novels."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastmcp.exceptions import ToolError as McpToolError

from app.auth.router import router as auth_router
from app.bible import LOCAL_OWNER_ID, BibleRepository
from app.commons.db.authoritative import connection as authoritative
from app.commons.observability import NoopObserver
from app.interview.router import get_bible
from app.interview.router import router as interview_router
from app.mcp_server.server import run_tool
from app.reader.dev_seed import NOVEL_ID, seed
from app.reader.router import get_bible_path
from app.reader.router import router as reader_router
from app.tools import DOWNLOAD_NOVEL, LIST_NOVELS, call_tool
from app.tools.models import ListNovelsOutput

SECRET = "test-secret-" + "x" * 40  # dummy, test only
PASSWORD = "correct horse battery"  # dummy, test only


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("AUTH_SECRET", SECRET)
    monkeypatch.delenv("STORY_MAKER_USER", raising=False)
    path = tmp_path / "harness.sqlite"
    with BibleRepository.open(path) as repo:
        seed(repo)
    return path


@pytest.fixture
def client(db: Path) -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(reader_router)
    app.include_router(interview_router)
    app.dependency_overrides[get_bible_path] = lambda: db

    def bible() -> Iterator[BibleRepository]:
        with BibleRepository.open(db, check_same_thread=False) as repo:
            yield repo

    app.dependency_overrides[get_bible] = bible
    return TestClient(app)


def _register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _give_seed_novel_to(db: Path, email: str) -> None:
    with BibleRepository.open(db) as repo:
        user = repo.find_user_by_email(email)
        assert user is not None
        repo.connection.execute("update novel set owner_id = ? where id = ?", (user.id, NOVEL_ID))


def test_register_login_and_hash(client: TestClient, db: Path) -> None:
    # spec 018 / AC 1
    headers = _register(client, "Ana@Example.com")
    assert client.get("/auth/me", headers=headers).json()["email"] == "ana@example.com"
    with BibleRepository.open(db) as repo:
        user = repo.find_user_by_email("ana@example.com")
    assert user is not None
    assert user.password_hash.startswith("$2b$")
    assert PASSWORD not in user.password_hash

    ok = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    wrong = client.post("/auth/login", json={"email": "ana@example.com", "password": "x" * 12})
    assert wrong.status_code == 401
    nobody = client.post("/auth/login", json={"email": "no@example.com", "password": PASSWORD})
    assert nobody.status_code == 401
    local = client.post("/auth/login", json={"email": "local@localhost", "password": PASSWORD})
    assert local.status_code == 401  # the built-in owner has no usable password
    again = client.post("/auth/register", json={"email": "ana@example.com", "password": PASSWORD})
    assert again.status_code == 409


def test_reader_requires_a_token(client: TestClient) -> None:
    # spec 018 / AC 2
    assert client.get("/novels").status_code == 401
    assert client.get(f"/novels/{NOVEL_ID}").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/novels", headers=bad).status_code == 401
    assert client.post("/interview/turn", json={"answer": "hola"}).status_code == 401


def test_user_cannot_reach_another_users_novel(client: TestClient, db: Path) -> None:
    # spec 018 / AC 3
    ana = _register(client, "ana@example.com")
    bea = _register(client, "bea@example.com")
    _give_seed_novel_to(db, "ana@example.com")

    assert [n["id"] for n in client.get("/novels", headers=ana).json()] == [NOVEL_ID]
    assert client.get(f"/novels/{NOVEL_ID}/versions/2/chapters/1", headers=ana).status_code == 200
    assert client.get(f"/novels/{NOVEL_ID}/versions/2/pdf", headers=ana).status_code == 200

    assert client.get("/novels", headers=bea).json() == []
    for path in (
        f"/novels/{NOVEL_ID}",
        f"/novels/{NOVEL_ID}/versions",
        f"/novels/{NOVEL_ID}/versions/2/chapters",
        f"/novels/{NOVEL_ID}/versions/2/chapters/1",
        f"/novels/{NOVEL_ID}/versions/2/pdf",
        f"/novels/{NOVEL_ID}/bible",
        f"/novels/{NOVEL_ID}/changes/some-job",
    ):
        assert client.get(path, headers=bea).status_code == 404, path
    change = client.post(
        f"/novels/{NOVEL_ID}/changes", json={"request": "el perro se llama Luna"}, headers=bea
    )
    assert change.status_code == 404
    # SEC-08: the interview may not write under another owner's novel id either.
    with BibleRepository.open(db) as repo:
        before = repo.list_validator_results(NOVEL_ID)
    brief = client.post("/interview/briefs", json={"brief": {}, "novel_id": NOVEL_ID}, headers=bea)
    assert brief.status_code == 404
    with BibleRepository.open(db) as repo:
        assert repo.list_validator_results(NOVEL_ID) == before
        # The audit log, scoped: Bea sees none of Ana's novel's decisions.
        repo.log_policy_decision(policy="p", decision="allow", novel_id=NOVEL_ID)
        bea_id = repo.find_user_by_email("bea@example.com")
        assert bea_id is not None
        assert repo.scoped_to(bea_id.id).list_policy_decisions() == []
        assert repo.list_policy_decisions(NOVEL_ID) != []


def test_mcp_tools_are_scoped_to_the_env_user(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # spec 018 / AC 4
    with BibleRepository.open(db) as repo:
        ana = repo.create_user(email="ana@example.com", password_hash="!")
        bea = repo.create_user(email="bea@example.com", password_hash="!")
        repo.connection.execute("update novel set owner_id = ? where id = ?", (ana.id, NOVEL_ID))
        listed = call_tool("list_novels", repo.scoped_to(bea.id))
        assert isinstance(listed, ListNovelsOutput)
        assert listed.novels == []

    def listed_ids(email: str | None) -> list[str]:
        out = run_tool(LIST_NOVELS, {}, observer=NoopObserver(), db_path=db, user_email=email)
        assert isinstance(out, ListNovelsOutput)
        return [n.id for n in out.novels]

    assert listed_ids("ana@example.com") == [NOVEL_ID]
    assert listed_ids("bea@example.com") == []
    assert listed_ids(None) == []  # STORY_MAKER_USER unset: the `local` owner
    monkeypatch.setenv("STORY_MAKER_USER", "Ana@example.com")
    assert listed_ids(None) == [NOVEL_ID]
    with pytest.raises(McpToolError, match="no novel"):
        run_tool(
            DOWNLOAD_NOVEL,
            {"novel_id": NOVEL_ID},
            observer=NoopObserver(),
            db_path=db,
            user_email="bea@example.com",
        )
    with pytest.raises(McpToolError, match="no registered user"):
        listed_ids("typo@example.com")


def test_existing_novels_belong_to_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # spec 018 / AC 5: a novel from before migration 1700 and a CLI novel belong to `local`.
    path = tmp_path / "old.sqlite"
    everything = authoritative._available
    monkeypatch.setattr(
        authoritative, "_available", lambda: [m for m in everything() if m[0] != "1700_auth"]
    )
    old = authoritative.open_authoritative(path)
    old.execute(
        "insert into novel (id, session_id, status, created_at, updated_at) "
        "values ('nov-old', 'nov-old', 'draft', 'now', 'now')"
    )
    old.close()
    monkeypatch.setattr(authoritative, "_available", everything)

    with BibleRepository.open(path) as repo:
        assert repo.get_novel("nov-old").owner_id == LOCAL_OWNER_ID
        assert repo.create_novel(novel_id="nov-cli").owner_id == LOCAL_OWNER_ID
        ana = repo.create_user(email="ana@example.com", password_hash="!")
        monkeypatch.setenv("STORY_MAKER_USER", "ana@example.com")
        assert repo.create_novel(novel_id="nov-ana").owner_id == ana.id
        with pytest.raises(sqlite3.IntegrityError):
            repo.create_user(email="ana@example.com", password_hash="!")
