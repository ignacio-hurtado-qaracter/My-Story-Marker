"""The HTTP contract of plan step 7: IF-01's mount list, IF-03/IF-04's routes, IF-02's role
header, IF-07's error body and IF-08's committed OpenAPI document.

Cross-feature by necessity, like `test_schema_export.py`: it has to see all six feature
routers at once, and a module inside `app/commons/` that imported a feature would break the
NFR-04 import contract. `tests/` is where `architecture.md` puts a test that spans features.

What it protects, in one sentence per group:

* **The route tables below are copied from the spec, not read back from the app.** A test
  that derived the expected routes from `app.routes` would pass for any set of routes,
  including the wrong one. So IF-03 and IF-04 are transcribed here and compared in both
  directions - every named route is served, and every served route is named - which makes a
  route added, renamed or quietly dropped a failing test rather than a surprise in the
  generated client.
* **`openapi.json` is what the frontend client is generated from.** A model or a route
  changed without exporting it is a contract change nobody reviewed (AC 29, IF-08).
* **A refused write must leave the tree byte-identical.** A 403 is worth nothing unless
  nothing landed, so the test hashes every file before and after rather than trusting the
  status code to mean what it says.

The tables are deliberately brittle across plan steps: the routes each later step adds are
listed in `DEFERRED_ROUTES` with the step that brings them, and moving one into the live
table is the reviewed act of publishing it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

from app.commons.config import get_settings
from app.commons.deps import get_embedder
from app.commons.embeddings import FakeEmbedder
from app.commons.stores import paths
from app.main import create_app
from scripts.export_openapi import openapi_path, render

FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "repo"

DOC_ROUTES = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})
"""FastAPI's own documentation routes. Not part of IF-01 and not the contract; excluded so
the reverse-direction check compares store routes with store routes."""

META_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/permissions"),
    }
)
"""IF-01's two meta routes. `/index` is IF-01's third, and is listed with the operations of
IF-05 that serve it."""

IF_03_READS = frozenset(
    {
        # canon/ - the fixed block, the two single-file records, and the five kinds
        ("GET", "/canon/project"),
        ("GET", "/canon/style"),
        ("GET", "/canon/lexicon"),
        ("GET", "/canon/time"),
        *[("GET", f"/canon/{kind}") for kind in paths.CANON_KINDS],
        *[("GET", f"/canon/{kind}/{{}}") for kind in paths.CANON_KINDS],
        # cast/
        ("GET", "/cast"),
        ("GET", "/cast/relationships"),
        ("GET", "/cast/{}"),
        ("GET", "/cast/{}/voice"),
        ("GET", "/cast/{}/knowledge"),
        ("GET", "/cast/{}/changes"),
        # structure/
        ("GET", "/structure/arcs"),
        ("GET", "/structure/chapters"),
        # scenes/
        ("GET", "/scenes"),
        ("GET", "/scenes/{}"),
        # manuscript/
        ("GET", "/manuscript/{}"),
        ("GET", "/manuscript/digests/{}"),
        # ledger/
        *[("GET", f"/ledger/{name}") for name in paths.LEDGER_FILES],
    }
)
"""IF-03's read routes, expanded over the kinds and ledger files the storage layout names.

Expanded from `paths.CANON_KINDS` and `paths.LEDGER_FILES` rather than spelled out, because
those tuples are the storage layout: a kind added there and given no route is exactly the
drift this asserts against.
"""

IF_04_WRITES = frozenset(
    {
        # canon/ - world_builder and canoniser
        ("PUT", "/canon/lexicon"),
        ("PUT", "/canon/time"),
        *[("PUT", f"/canon/{kind}/{{}}") for kind in paths.CANON_KINDS],
        # cast/ - canoniser
        ("PUT", "/cast/relationships"),
        ("PUT", "/cast/{}/dossier"),
        ("PUT", "/cast/{}/voice"),
        ("PUT", "/cast/{}/knowledge"),
        ("PUT", "/cast/{}/changes"),
        # structure/ and scenes/ - architect
        ("PUT", "/structure/arcs"),
        ("PUT", "/structure/chapters"),
        ("PUT", "/scenes/{}"),
        # manuscript/ - writer and style_editor
        ("PUT", "/manuscript/{}"),
        ("PUT", "/manuscript/digests/{}"),
        # ledger/ - the writer proposes, the auditor reports
        ("POST", "/ledger/proposed"),
        ("PUT", "/ledger/violations"),
    }
)
"""IF-04's write routes. Every one of them takes `X-Agent-Role`; which role Figure 3 then
allows is the store layer's decision and is tested in `app/commons/permissions/tests/`."""

IF_05_OPERATIONS = frozenset(
    {
        ("GET", "/cast/{}/dossier"),  # FR-OPS-01, plan step 10
        ("GET", "/index/status"),  # FR-IDX-07, plan step 9
        ("POST", "/index/rebuild"),  # FR-IDX-04, plan step 9
    }
)
"""IF-03's as-of read and IF-05's operations, as each step publishes them."""

DEFERRED_ROUTES = {
    ("POST", "/canon/reconcile"): "plan step 13, FR-OPS-08",
    ("POST", "/ledger/proposed/{}/promote"): "plan step 13, FR-OPS-06",
    ("POST", "/ledger/proposed/{}/rule"): "plan step 13, FR-OPS-07",
    ("POST", "/scenes/{}/audit"): "plan step 14, FR-AUD",
    ("POST", "/scenes/{}/select"): "plan step 11, FR-OPS-02",
    ("POST", "/scenes/{}/assemble"): "plan step 12, FR-OPS-03",
    ("GET", "/agents/turns"): "the orchestrator",
    ("POST", "/agents/turns"): "the orchestrator",
    ("GET", "/agents/provenance"): "the orchestrator",
}
"""IF-01, IF-03 and IF-05 routes this step does not serve, each with what it is waiting for.

Recorded rather than omitted. A route missing from a table is indistinguishable from a route
forgotten, and this list is what lets the reverse-direction check below tell "not written
yet" apart from "written and never mounted".
"""

EXPECTED_ROUTES = META_ROUTES | IF_03_READS | IF_04_WRITES | IF_05_OPERATIONS


def normalise_template(path: str) -> str:
    """Replace every path parameter with `{}`.

    The spec writes `/scenes/{id}` and `/cast/{id}`; the routers call the parameters `scene`
    and `character`. The name is a detail of a handler's signature, the shape is the
    contract, and comparing shapes keeps this test about IF-03 rather than about somebody's
    choice of variable name.
    """
    out: list[str] = []
    depth = 0
    for char in path:
        if char == "{":
            depth += 1
            if depth == 1:
                out.append("{}")
        elif char == "}":
            depth -= 1
        elif depth == 0:
            out.append(char)
    return "".join(out)


def served_routes(routes: Sequence[BaseRoute]) -> set[tuple[str, str]]:
    """Every `(method, normalised path)` the app answers, minus FastAPI's own doc routes.

    Walked with `iter_route_contexts` rather than by reading `app.routes` directly, because
    `include_router` no longer flattens: an included router is kept as one lazy node, so a
    loop over `app.routes` sees six wrappers and none of the routes inside them. A test that
    read the list naively would have found nothing to check and passed.

    `HEAD` and `OPTIONS` are dropped: Starlette adds them, the spec does not name them, and a
    contract test that reported them would be reporting the framework.
    """
    served: set[tuple[str, str]] = set()
    for context in iter_route_contexts(routes):
        path = context.path
        if path is None or path in DOC_ROUTES:
            continue
        if not isinstance(context.original_route, APIRoute):
            continue
        for method in context.methods or ():
            if method in {"HEAD", "OPTIONS"}:
                continue
            served.add((method, normalise_template(path)))
    return served


def tree_digest(root: Path) -> dict[str, str]:
    """Path to content hash for every file under `root`.

    A dictionary rather than one hash of the whole tree, so a failure names the file that
    changed instead of only reporting that something did.
    """
    digest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digest


@pytest.fixture
def story_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A throwaway copy of the fixture repository (NFR-09).

    A copy rather than the fixture itself because these tests attempt writes: a refused write
    has to be shown to have changed nothing, and a test that proved it against the committed
    fixture would be one bug away from editing the fixture instead. `.index/` is pointed
    outside the copy too, since AC 31 records that provenance is not rebuildable from a tree.
    """
    root = tmp_path / "story"
    shutil.copytree(FIXTURE_REPO, root)

    monkeypatch.setenv("STORY_ROOT", str(root))
    monkeypatch.setenv("STORY_INDEX", str(tmp_path / "index" / "index.sqlite"))
    monkeypatch.setenv("EMBED_CACHE_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("EMBED_OFFLINE", "1")
    get_settings.cache_clear()
    try:
        yield root
    finally:
        get_settings.cache_clear()


@pytest.fixture
def app(story_repo: Path) -> FastAPI:
    """The app bound to the throwaway copy. `story_repo` is requested for the environment it
    sets, not for its value, so the app factory reads the temporary root from settings.

    Built here rather than reached through `TestClient.app`, which is typed as a bare ASGI
    callable and would make every walk of `app.routes` a cast.
    """
    del story_repo
    served = create_app()
    served.dependency_overrides[get_embedder] = FakeEmbedder  # NFR-09: no real model
    return served


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """The same app, served. Requesting both fixtures in one test yields one instance."""
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------------------
# IF-01, IF-03, IF-04 - the route table
# --------------------------------------------------------------------------------------


# spec 001 / AC 29 - IF-01: the six store families and the two meta routes are mounted.
def test_every_if01_family_is_mounted(app: FastAPI) -> None:
    served = served_routes(app.routes)
    families = {path.split("/")[1] for _, path in served}

    assert {"canon", "cast", "structure", "scenes", "manuscript", "ledger"} <= families
    assert served >= META_ROUTES


# spec 001 / AC 29 - IF-03 and IF-04: every route the spec names is served.
@pytest.mark.parametrize(("method", "path"), sorted(EXPECTED_ROUTES))
def test_spec_route_is_served(app: FastAPI, method: str, path: str) -> None:
    assert (method, path) in served_routes(app.routes)


# spec 001 / AC 29 - the other direction: the app serves nothing IF-01/IF-03/IF-04 omits.
def test_app_serves_no_route_the_spec_does_not_name(app: FastAPI) -> None:
    unexpected = served_routes(app.routes) - EXPECTED_ROUTES

    landed = {route: why for route, why in DEFERRED_ROUTES.items() if route in unexpected}
    assert not landed, f"deferred routes are mounted; move them into the tables: {landed}"
    assert not unexpected, f"served but not named by the spec: {sorted(unexpected)}"


# --------------------------------------------------------------------------------------
# IF-08 - the committed OpenAPI document
# --------------------------------------------------------------------------------------


# spec 001 / AC 29 - IF-08: the committed document is what the app actually serves.
def test_committed_openapi_matches_the_app(minimal_store: Path) -> None:
    del minimal_store
    committed = openapi_path()

    assert committed.is_file(), f"{committed} is missing; run scripts/export_openapi.py"
    assert committed.read_text(encoding="utf-8") == render(), (
        f"{committed.name} is stale; run `uv run python scripts/export_openapi.py`"
    )


# spec 001 / AC 29 - and the document describes every route of the tables above.
def test_committed_openapi_describes_the_spec_routes() -> None:
    document = json.loads(openapi_path().read_text(encoding="utf-8"))
    described = {
        (method.upper(), normalise_template(path))
        for path, operations in document["paths"].items()
        for method in operations
    }

    assert described >= EXPECTED_ROUTES


# --------------------------------------------------------------------------------------
# IF-02 - the role header
# --------------------------------------------------------------------------------------


# spec 001 / AC 2 - IF-02: a missing `X-Agent-Role` is a 400, not a 403 and not a default.
def test_write_without_a_role_header_is_400(client: TestClient) -> None:
    arcs = client.get("/structure/arcs").json()

    response = client.put("/structure/arcs", json=arcs)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_role"


# spec 001 / AC 2 - IF-02: a role Figure 3 has never heard of is a 400; the caller is
# malformed, which is a different fact from a caller that was refused.
def test_write_with_an_unknown_role_is_400(client: TestClient) -> None:
    arcs = client.get("/structure/arcs").json()

    response = client.put(
        "/structure/arcs", json=arcs, headers={"X-Agent-Role": "editor_in_chief"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_role"
    assert body["supplied"] == "editor_in_chief"


# spec 001 / AC 2 - IF-02, FR-PERM-03: Figure 3 refuses with a 403 and no byte is written.
def test_forbidden_role_is_403_and_changes_no_byte(
    client: TestClient, story_repo: Path
) -> None:
    arcs = client.get("/structure/arcs").json()
    before = tree_digest(story_repo)

    response = client.put("/structure/arcs", json=arcs, headers={"X-Agent-Role": "writer"})

    assert response.status_code == 403
    assert tree_digest(story_repo) == before


# spec 001 / AC 2 - the role Figure 3 does allow gets through, so the refusal above is a
# statement about the table rather than about the route being broken. The assertion is
# "only that file changed", not "these exact bytes": the store writes canonical YAML and the
# fixture is hand-written, so an identical record legitimately lands with different bytes.
# What must not happen is a second file moving, or anything appearing beside the tree.
def test_the_allowed_role_may_write(client: TestClient, story_repo: Path) -> None:
    arcs = client.get("/structure/arcs").json()
    before = tree_digest(story_repo)

    response = client.put("/structure/arcs", json=arcs, headers={"X-Agent-Role": "architect"})

    assert response.status_code == 200
    after = tree_digest(story_repo)
    assert {path for path in after if after[path] != before.get(path)} == {
        "structure/arcs.yaml"
    }
    assert client.get("/structure/arcs").json() == arcs


# --------------------------------------------------------------------------------------
# IF-07 - one error body shape
# --------------------------------------------------------------------------------------


# spec 001 / AC 29 - IF-07: `error` and `detail` on every error body, whatever the status.
@pytest.mark.parametrize(
    ("method", "path", "headers", "status"),
    [
        ("GET", "/scenes/999", {}, 404),
        ("PUT", "/structure/arcs", {}, 400),
        ("PUT", "/structure/arcs", {"X-Agent-Role": "writer"}, 403),
    ],
)
def test_error_bodies_share_one_shape(
    client: TestClient, method: str, path: str, headers: dict[str, str], status: int
) -> None:
    body = client.get("/structure/arcs").json() if method == "PUT" else None

    response = client.request(method, path, json=body, headers=headers)

    assert response.status_code == status
    reported = response.json()
    assert isinstance(reported["error"], str)
    assert isinstance(reported["detail"], str)


# spec 001 / AC 2 - IF-07: a 403 names both halves of the decision, the role and the path.
def test_permission_denied_body_names_role_and_path(client: TestClient) -> None:
    arcs = client.get("/structure/arcs").json()

    body = client.put("/structure/arcs", json=arcs, headers={"X-Agent-Role": "writer"}).json()

    assert body["error"] == "permission_denied"
    assert body["role"] == "writer"
    assert body["path"] == "structure/arcs.yaml"


# spec 001 / AC 29 - IF-07: a record that is not there is a 404.
def test_reading_a_missing_record_is_404(client: TestClient) -> None:
    response = client.get("/canon/axioms/ax_not_written_yet")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# spec 001 / AC 29 - IF-07, FR-STORE-06: a record that does not match its model is a 422 and
# names the file. Never repaired on the way out: a record the system silently fixed is a
# record nobody can trust.
def test_reading_an_invalid_record_is_422(client: TestClient, story_repo: Path) -> None:
    (story_repo / "structure" / "arcs.yaml").write_text(
        "schema_version: 1\narcs: not-a-list\n", encoding="utf-8"
    )

    response = client.get("/structure/arcs")

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_record"
    assert body["file"] == "structure/arcs.yaml"
