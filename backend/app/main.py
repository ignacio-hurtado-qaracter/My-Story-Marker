"""The FastAPI application.

`main.py` composes; it does not implement. It builds the app, mounts each feature's router
and registers the exception handlers, and every other line of behaviour lives in a feature
or in `commons/`.

The feature routers of IF-01 are mounted at the bottom of `create_app` and implemented
nowhere near it. That is the point: a rule written here would be a rule outside the feature
that owns the store family it touches, and outside the store layer that asks Figure 3
whether the write is allowed (FR-PERM-03). `main.py` therefore knows six router objects and
not one store path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.canon.router import router as canon_router
from app.cast.router import router as cast_router
from app.commons.config import Settings, get_settings
from app.commons.db.connection import vector_extension_available
from app.commons.errors import register_exception_handlers
from app.commons.permissions import AgentRole, readable_patterns, writable_patterns
from app.ledger.router import router as ledger_router
from app.manuscript.router import router as manuscript_router
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup checks run once, before the first request is served."""
    del app
    verify_store_root(get_settings())
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

    return app


app = create_app()
