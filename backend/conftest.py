"""Shared test fixtures for the whole backend suite.

This is the **root** conftest, and it has to be: pytest loads conftests from the rootdir
down to each test file, so a fixture defined in `tests/conftest.py` never reaches the
feature suites under `app/*/tests/`. The plan listed the path as `backend/tests/conftest.py`;
that location cannot serve the feature suites and the file lives here instead.

Two rules from the spec shape this file:

* **NFR-09** — tests run on a temporary copy of the fixture, never on a real tree, and
  live-model tests are excluded unless `--live` is passed.
* **NFR-06** — the offline suite runs with network disabled. Blocking it here rather than
  trusting every test to avoid it is what makes "no network" checkable instead of hoped for.

`fixture_root` / `fixture_store` / `fixture_client` give each test its own copy of the
fixture novel under `tests/fixtures/repo/` (plan step 4), with `.index/` pointed inside the
test's temporary directory. `minimal_store` remains for tests that need only a valid root.
"""

from __future__ import annotations

import shutil
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from app.commons.config import get_settings
from app.commons.stores import Store

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item


def pytest_addoption(parser: Parser) -> None:
    """NFR-09. `--live` is opt-in: it spends the user's Claude Code usage."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="run tests marked `live` against a real model through `claude -p`",
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """Skip `live` tests unless `--live` was passed."""
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="needs --live and a logged-in Claude Code CLI (NFR-09)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0.0.0.0"})
"""Loopback stays open. Blocking it would not prove anything about NFR-06 and would break
the ASGI test client, whose blocking portal opens a self-pipe on Windows."""

SocketAddress = tuple[str, int] | tuple[str, int, int, int] | str | bytes
"""The address forms `socket.connect` accepts, spelled out rather than borrowed from
`socket`'s private alias, which is `Any`-typed and would breach NFR-02."""


def _is_loopback(address: SocketAddress) -> bool:
    """True for an address on this machine, and for anything that is not an IP address at
    all (AF_UNIX paths and raw sockaddr buffers, which cannot leave the host)."""
    if not isinstance(address, tuple) or not address:
        return True
    return address[0] in LOOPBACK_HOSTS


def _refuse_unless_loopback(address: SocketAddress) -> None:
    if _is_loopback(address):
        return
    message = f"network access is disabled in the offline test suite (NFR-06): {address!r}"
    raise RuntimeError(message)


@pytest.fixture(autouse=True)
def _network_disabled(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-06. Outbound sockets raise in the offline suite.

    `live` tests talk to the model API and `model` tests may download weights, so both are
    exempt. Everything else that reaches off this machine is a bug, and this makes it loud
    at the point of the call rather than as a timeout somewhere downstream.
    """
    if request.node.get_closest_marker("live") or request.node.get_closest_marker("model"):
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(sock: socket.socket, address: SocketAddress) -> None:
        _refuse_unless_loopback(address)
        real_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: SocketAddress) -> int:
        _refuse_unless_loopback(address)
        return real_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture
def minimal_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The smallest tree the backend agrees to start against (FR-STORE-01).

    `.index/` is pointed inside `tmp_path` too: AC 31 records that turn and provenance
    records are not rebuildable, so a test must never be able to write into a real one.
    """
    root = tmp_path / "story"
    (root / "canon").mkdir(parents=True)
    (root / "canon" / "project.md").write_text(
        "# Project\n\nA minimal store root, enough to start.\n", encoding="utf-8"
    )

    monkeypatch.setenv("STORY_ROOT", str(root))
    monkeypatch.setenv("STORY_INDEX", str(tmp_path / "index" / "index.sqlite"))
    monkeypatch.setenv("EMBED_CACHE_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("EMBED_OFFLINE", "1")
    get_settings.cache_clear()
    try:
        yield root
    finally:
        get_settings.cache_clear()


FIXTURE_REPO = Path(__file__).resolve().parent / "tests" / "fixtures" / "repo"
"""The fixture novel (plan step 4). Never written to: every test gets its own copy."""


def _point_settings_at(root: Path, index_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORY_ROOT", str(root))
    monkeypatch.setenv("STORY_INDEX", str(index_dir / "index.sqlite"))
    monkeypatch.setenv("EMBED_CACHE_DIR", str(index_dir / "models"))
    monkeypatch.setenv("EMBED_OFFLINE", "1")
    get_settings.cache_clear()


@pytest.fixture
def fixture_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A private copy of the fixture novel, with settings bound to it (NFR-09).

    A copy per test because half the suite writes: a test that promoted a fact into the shared
    fixture would make every later test depend on the order the suite ran in.
    """
    root = tmp_path / "story"
    shutil.copytree(FIXTURE_REPO, root)
    _point_settings_at(root, tmp_path / ".index", monkeypatch)
    try:
        yield root
    finally:
        get_settings.cache_clear()


@pytest.fixture
def fixture_store(fixture_root: Path) -> Store:
    """The `Store` over that copy, with `.index/` beside it inside the test's temp dir."""
    return Store(root=fixture_root, index_dir=fixture_root.parent / ".index")


@pytest.fixture
def fixture_client(fixture_root: Path) -> Iterator[TestClient]:
    """The whole app, started against the copy. Imported lazily so collecting a test that
    does not need the app does not build it."""
    from app.main import create_app

    del fixture_root  # requested for its side effect: settings now point at the copy
    with TestClient(create_app()) as client:
        yield client
