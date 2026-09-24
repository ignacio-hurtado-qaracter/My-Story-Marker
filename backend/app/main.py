"""The FastAPI application.

`main.py` composes; it does not implement. It builds the app, mounts each feature's router
and registers the exception handlers, and every other line of behaviour lives in a feature
or in `commons/`.

The feature routers of IF-01 are mounted at the bottom of `create_app` and implemented
nowhere near it. That is the point: a rule written here would be a rule outside the feature
that owns the store family it touches, and outside the store layer that asks Figure 3
whether the write is allowed (FR-PERM-03). `main.py` therefore knows the feature routers and
not one store path.

It also makes the one wiring no feature can make for itself: the audit route (`scenes`) is
handed the model-backed auditor (`agents`) through `commons.deps.get_semantic_auditor`,
because NFR-04's layers put `agents` above `scenes` and the route may not import it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, Field

from app.agents import service as agents_service
from app.agents.router import router as agents_router
from app.canon.router import router as canon_router
from app.cast.router import router as cast_router
from app.commons.config import Settings, get_settings
from app.commons.db import IndexReport, IndexStatus, rebuild, status
from app.commons.db.connection import vector_extension_available
from app.commons.deps import (
    EmbedderDep,
    SettingsDep,
    StoreDep,
    get_embedder,
    get_semantic_auditor,
)
from app.commons.errors import register_exception_handlers
from app.commons.permissions import AgentRole, readable_patterns, writable_patterns
from app.interview.router import router as interview_router
from app.ledger.router import router as ledger_router
from app.manuscript.router import router as manuscript_router
from app.reader.router import router as reader_router
from app.scenes.router import router as scenes_router
from app.scenes.router import structure_router

STORE_ROOT_MARKER = Path("canon") / "project.md"
"""FR-STORE-01. The file whose absence means this directory is not a story."""


class HealthResponse(BaseModel):
    """What `/health` answers. `vector` is the FR-IDX-03 signal a client needs to know
    whether selection is fused or FTS5-only."""

    status: str = Field(description="`ok` when the app is serving.")
    vector: str = Field(description="`available` or `unavailable`, per FR-IDX-03.")
    embedding_model: str = Field(description="The configured 384-d model name, FR-EMB-02.")
    store_root: str = Field(description="The store root this process is bound to.")


class RolePermissions(BaseModel):
    """One row of Figure 3, as the API reports it."""

    role: AgentRole
    writes: list[str] = Field(description="FR-PERM-02. Store globs this role may write.")
    inputs: list[str] = Field(
        description=(
            "FR-AGENT-09, Figure 3's `In` column. Stricter than `writes`: anything not "
            "listed here is not available to the role, whatever it may read in principle."
        )
    )


class PermissionsResponse(BaseModel):
    """FR-PERM-04. The table, exported so a reviewer can read what the process enforces
    rather than what a document says it should."""

    roles: list[RolePermissions]


def verify_store_root(settings: Settings) -> None:
    """FR-STORE-01: refuse to start without `canon/project.md`.

    Starting against an empty or wrong directory is worse than not starting: the first write
    would create a plausible-looking tree somewhere nobody meant, and the provenance log
    would faithfully record it.
    """
    marker = settings.story_root / STORE_ROOT_MARKER
    if not marker.is_file():
        message = (
            f"STORY_ROOT {settings.story_root!s} is not a story tree: "
            f"{STORE_ROOT_MARKER.as_posix()} is missing"
        )
        raise RuntimeError(message)


def verify_embedding_model(app: FastAPI, settings: Settings) -> None:
    """FR-EMB-03: with `EMBED_OFFLINE=1`, a missing model is a startup error naming the path to
    populate, not a 500 on the first rebuild hours later.

    Offline, loading the model is the only honest check -- the files are either in the cache
    or they are not, and nothing will fetch them -- and it costs one load that the first
    rebuild would pay anyway, since the loaded embedder is cached. Online, a missing model is
    downloaded on first use, which FR-EMB-02 allows during a rebuild, so nothing is loaded
    here. An app whose embedder dependency is overridden (every offline test, NFR-09) has no
    model to load.
    """
    if not settings.embed_offline or get_embedder in app.dependency_overrides:
        return
    get_embedder(settings)


def index_router() -> APIRouter:
    """IF-05, `POST /index/rebuild` and `GET /index/status` (FR-IDX-04, FR-IDX-07).

    The index is not a store: it is not governed by Figure 3 and no agent reads it, so
    neither route takes an `X-Agent-Role`. Both are plain `def` because they block on SQLite
    and, for the rebuild, on the embedder (FR-EMB-04); FastAPI runs them in its threadpool
    rather than on the event loop. `IndexBusy` from either becomes a 503 through the shared
    handler, only after the busy timeout (FR-IDX-06).
    """
    router = APIRouter(prefix="/index", tags=["index"])

    @router.post("/rebuild")
    def rebuild_index(
        store: StoreDep, embedder: EmbedderDep, settings: SettingsDep
    ) -> IndexReport:
        """Empty the derived tables and repopulate them from the tree."""
        return rebuild(store, embedder, settings.index_path)

    @router.get("/status")
    def index_status(store: StoreDep, settings: SettingsDep) -> IndexStatus:
        """Row and orphan counts, the recorded model, and vector availability."""
        return status(store, settings.index_path)

    return router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup checks run once, before the first request is served."""
    settings = get_settings()
    verify_store_root(settings)
    verify_embedding_model(app, settings)
    yield


def create_app() -> FastAPI:
    """App factory. Tests build their own instance against a temporary store root rather
    than importing a module-level app bound to whatever the environment happened to say."""
    app = FastAPI(
        title="My Story Marker — backend",
        version="0.1.0",
        summary="The only process that reads and writes the harness stores.",
        lifespan=lifespan,
    )
    register_exception_handlers(app)

    @app.get("/health", tags=["meta"])
    def health() -> HealthResponse:
        settings = get_settings()
        return HealthResponse(
            status="ok",
            vector="available" if vector_extension_available() else "unavailable",
            embedding_model=settings.embed_model,
            store_root=str(settings.story_root),
        )

    @app.get("/permissions", tags=["meta"])
    def permissions() -> PermissionsResponse:
        return PermissionsResponse(
            roles=[
                RolePermissions(
                    role=role,
                    writes=list(writable_patterns(role)),
                    inputs=list(readable_patterns(role)),
                )
                for role in AgentRole
            ]
        )

    # IF-01. The six store families, each mounted from the feature that owns it. Prefixes
    # and tags are declared on the routers themselves, so this list stays a list of owners
    # rather than a second, drifting copy of the route table.
    #
    # `scenes` exports two routers because it owns two store families: `scenes/` holds the
    # per-scene records and `structure/` the arcs and chapters they hang from, and Figure 3
    # gives both to the architect. Splitting the feature to match the URL prefixes would put
    # one role's two outputs in two places for no reason a reader could name.
    app.include_router(canon_router)
    app.include_router(cast_router)
    app.include_router(structure_router)
    app.include_router(scenes_router)
    app.include_router(manuscript_router)
    app.include_router(ledger_router)
    app.include_router(agents_router)
    app.include_router(index_router())
    # Spec 006 (B2): the interview and brief routes, backed by the story bible (K1).
    app.include_router(interview_router)
    # Spec 014 (K5): the gift-novel reader over the story bible, under `/novels`.
    app.include_router(reader_router)

    # FR-AGENT-07, IF-05: `POST /scenes/{id}/audit` runs the auditor role for its semantic
    # half. `scenes` cannot import `agents` (NFR-04), so the route asks `commons.deps` for a
    # `SemanticAuditor` and the provider is substituted here. Its own dependencies -- the model
    # client, the embedder, the settings -- are resolved per request, so a test's overrides of
    # those reach it too.
    app.dependency_overrides[get_semantic_auditor] = agents_service.semantic_auditor

    return app


app = create_app()
