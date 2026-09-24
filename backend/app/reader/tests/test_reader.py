"""Spec 014: the reader API index, change resolution and the PDF export, on the dev seed."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bible import BibleRepository
from app.export import export_pdf
from app.reader.changes import ChangeJobs, match_fact, resolve_change
from app.reader.dev_seed import NOVEL_ID, seed
from app.reader.models import ChangeRequest
from app.reader.router import get_bible_path, router


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "harness.sqlite"
    with BibleRepository.open(path) as repo:
        seed(repo)
    return path


def test_chapter_index(db: Path) -> None:
    # spec 014 / AC 1
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_bible_path] = lambda: db
    client = TestClient(app)

    novel = client.get(f"/novels/{NOVEL_ID}").json()
    assert novel["current_version"] == 2
    assert novel["dedication"].startswith("Para Lucía")

    index = client.get(f"/novels/{NOVEL_ID}/versions/2/chapters").json()
    assert [c["n"] for c in index["chapters"]] == [1, 2, 3]
    assert [c["changed_vs_parent"] for c in index["chapters"]] == [True, False, True]
    first = client.get(f"/novels/{NOVEL_ID}/versions/1/chapters").json()
    assert not any(c["changed_vs_parent"] for c in first["chapters"])

    bible = client.get(f"/novels/{NOVEL_ID}/bible").json()
    chapters = {c["name"]: c["chapters"] for c in bible["characters"] + bible["places"]}
    assert chapters["Nala"] == [1, 3]  # from fact usage
    assert chapters["El pueblo"] == [2]  # from the name search fallback


def test_change_resolution_is_deterministic(db: Path) -> None:
    # spec 014 / AC 3
    with BibleRepository.open(db) as repo:
        facts = repo.list_facts(NOVEL_ID)
        found = match_fact(
            facts, fragment="Nala trotando a su lado", request="el perro se llama Luna"
        )
        assert found is not None
        assert found.key == "pet.toby.name"
        resolved = resolve_change(
            repo, NOVEL_ID, ChangeRequest(request="el perro se llama Luna"), client=None
        )
    assert (resolved.fact_key, resolved.new_value, resolved.resolved_by) == (
        "pet.toby.name", "Luna", "match"
    )

    # The job hands the resolved fact to K4 `change_fact` (a stand-in for B3's here).
    calls: list[tuple[str, str]] = []

    def fake_change_fact(
        repo: BibleRepository, novel_id: str, fact_key: str, new_value: str
    ) -> object:
        calls.append((fact_key, new_value))
        return SimpleNamespace(new_version=3, changed_chapters=[1, 3], status="published")

    jobs = ChangeJobs(change_fact_loader=lambda: fake_change_fact)
    change = ChangeRequest(request="el perro se llama Luna")
    job = jobs.submit(db, NOVEL_ID, change, background=False)
    done = jobs.get(job.job_id)
    assert calls == [("pet.toby.name", "Luna")]
    assert done is not None
    assert (done.status, done.new_version, done.changed_chapters) == ("done", 3, [1, 3])


def test_pdf_export(db: Path, tmp_path: Path) -> None:
    # spec 014 / AC 2
    with BibleRepository.open(db) as repo:
        out = export_pdf(repo, NOVEL_ID, 2, tmp_path / "demo-v2.pdf")
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    pages = len(re.findall(rb"/Type /Page(?!s)", data))
    # cover, novedades, index, three chapters, characters and places
    assert pages >= 7
    links = len(re.findall(rb"/Subtype /Link", data))
    # novedades 2 + index 3 chapters + sheet link + sheet entries' chapter links + back link
    assert links >= 10
    assert b"/Outlines" in data


def test_concurrent_requests_all_succeed(db: Path) -> None:
    # spec 014 / AC 1 (clarified): the per-request repository is opened in one threadpool
    # thread and used in another, so its connection must not be bound to its opening thread.
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_bible_path] = lambda: db
    # One shared portal (event loop), so concurrent requests spread over its worker threads.
    with TestClient(app, raise_server_exceptions=False) as client:

        def fetch(_: int) -> int:
            return client.get(f"/novels/{NOVEL_ID}").status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            codes = list(pool.map(fetch, range(20)))
    assert codes == [200] * 20
