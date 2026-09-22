"""The FastAPI application.

`main.py` composes; it does not implement. It builds the app, mounts each feature's router
and registers the exception handlers, and every other line of behaviour lives in a feature
or in `commons/`. Feature routers arrive at plan step 7; until then the app serves
`/health` alone, which is enough to prove the startup contract of FR-STORE-01.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.commons.config import Settings, get_settings
from app.commons.db.connection import vector_extension_available
from app.commons.errors import register_exception_handlers

STORE_ROOT_MARKER = Path("canon") / "project.md"
"""FR-STORE-01. The file whose absence means this directory is not a story."""


class HealthResponse(BaseModel):
    """What `/health` answers. `vector` is the FR-IDX-03 signal a client needs to know
    whether selection is fused or FTS5-only."""

    status: str = Field(description="`ok` when the app is serving.")
    vector: str = Field(description="`available` or `unavailable`, per FR-IDX-03.")
    embedding_model: str = Field(description="The configured 384-d model name, FR-EMB-02.")
    store_root: str = Field(description="The store root this process is bound to.")


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

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        settings = get_settings()
        return HealthResponse(
            status="ok",
            vector="available" if vector_extension_available() else "unavailable",
            embedding_model=settings.embed_model,
            store_root=str(settings.story_root),
        )

    return app


app = create_app()
