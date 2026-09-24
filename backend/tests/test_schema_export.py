"""DR-01 and DR-10 across the whole storage layout, and AC 29's schema half.

This test is cross-feature by necessity, which is why it lives here rather than beside the
models: it has to see the shared records in `commons/schemas/` **and** the feature-owned ones
in `app/canon/`, `app/cast/` and `app/scenes/` at the same time, and a module inside
`app/commons/` that imported a feature would break the NFR-04 import contract.

What it protects: the committed `backend/schemas/*.v1.json` are a contract other things read.
A model edited without regenerating them is a contract change nobody reviewed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from app.commons.schemas.common import StoreDocument
from scripts.export_schemas import (
    DOCUMENT_FORMATS,
    DOCUMENT_MODELS,
    exported_models,
    render,
    schemas_dir,
    stale,
    target_path,
)

STORAGE_LAYOUT_TYPES = {
    # canon/
    "project",
    "style_bible",
    "axiom",
    "technology",
    "location",
    "faction",
    "historical_event",
    "lexicon",
    "temporal_system",
    # cast/
    "character",
    "voice_profile",
    "knowledge",
    "changes",
    "relationships",
    # structure/
    "arcs",
    "chapters",
    # scenes/
    "scene",
    # manuscript/
    "draft",
    "scene_digest",
    # ledger/
    "setups",
    "threads",
    "timeline",
    "proposed",
    "violations",
}
"""Every path in architecture.md's storage layout, by the name its schema file carries.
Hand-written on purpose: deriving it from the registry would make the test agree with itself
rather than with the document."""


# spec 001 / AC 4 — DR-01: every file type under the stores has a model and a schema.
def test_every_storage_layout_type_has_a_model() -> None:
    missing = STORAGE_LAYOUT_TYPES - set(DOCUMENT_MODELS)
    assert not missing, f"storage layout types with no model: {sorted(missing)}"


# spec 001 / AC 4
def test_the_registry_invents_nothing() -> None:
    extra = set(DOCUMENT_MODELS) - STORAGE_LAYOUT_TYPES
    assert not extra, f"models with no path in the storage layout: {sorted(extra)}"


# spec 001 / AC 4 — DR-10: the version is in the filename.
@pytest.mark.parametrize("name", sorted(DOCUMENT_MODELS), ids=str)
def test_schema_filename_carries_its_version(name: str) -> None:
    assert target_path(name).name == f"{name}.v1.json"


# spec 001 / AC 4 — DR-10: the version travels in the record too.
@pytest.mark.parametrize("name", sorted(DOCUMENT_MODELS), ids=str)
def test_every_document_model_is_versioned(name: str) -> None:
    model = DOCUMENT_MODELS[name]
    assert issubclass(model, StoreDocument), f"{model.__name__} is not a StoreDocument"
    assert "schema_version" in model.model_fields


# spec 001 / AC 4 — a document that accepted unknown fields would read a divergent record
# as if it agreed.
@pytest.mark.parametrize("name", sorted(DOCUMENT_MODELS), ids=str)
def test_every_document_forbids_unknown_fields(name: str) -> None:
    model: type[BaseModel] = DOCUMENT_MODELS[name]
    assert model.model_config.get("extra") == "forbid"


# spec 001 / AC 29 — the committed schemas are the exported ones.
def test_committed_schemas_are_not_stale() -> None:
    drifted = stale()
    assert not drifted, (
        "stale JSON Schemas: run `uv run python scripts/export_schemas.py` and commit the "
        f"result. Drifted: {sorted(drifted)}"
    )


# spec 001 / AC 29 — and nothing else is lying around in schemas/.
def test_no_orphan_schema_files() -> None:
    expected = {target_path(name).name for name in exported_models()}
    present = {path.name for path in schemas_dir().glob("*.json")}
    assert present == expected, f"unexpected: {sorted(present - expected)}"


# spec 001 / AC 29 — the rendering is canonical, so `--check` compares content.
def test_rendering_is_stable(tmp_path: Path) -> None:
    del tmp_path
    for model in DOCUMENT_MODELS.values():
        assert render(model) == render(model)


# spec 001 / AC 4 — the tree-wide round trip through the real file format lives in
# `tests/test_fixture_validates.py`, against the fixture repository. Generating instances from
# each schema was tried here first and was the wrong tool: it cost minutes of gate time to
# synthesise records that the fixture already provides as real files, and hypothesis spends
# that time on shapes nobody will ever write. The two concrete regressions -- a digest with no
# `body`, a draft with one -- are pinned in
# `app/commons/stores/tests/test_validate_on_read.py`, where they are fast and exact.


# spec 001 / AC 4 — and every type says which shape it is stored in.
def test_every_document_has_a_declared_format() -> None:
    assert set(DOCUMENT_FORMATS) == set(DOCUMENT_MODELS)
    assert set(DOCUMENT_FORMATS.values()) == {".md", ".yaml"}
