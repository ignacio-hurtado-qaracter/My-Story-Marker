"""The tree-wide round trip: every file in the fixture novel read through the real store.

`tests/test_schema_export.py` proves each model has a schema and each schema is fresh. It
cannot prove that anything anyone actually wrote matches one. This does: it walks
`tests/fixtures/repo/` file by file, decides which document type each path is, and reads it
through `Store.read` -- the same parse-then-validate path the backend uses at runtime, not
`model_validate` on a dict a test built. That distinction is the one the digest defect fell
through, where every file on disk was unreadable while the object-level round trip was green.

Two failures are reported and neither is tolerated:

* a file that does not validate, named with its path and the offending field;
* a file that maps to **no** document type at all, which means either the fixture grew a
  path the storage layout does not have, or the layout grew one the registry forgot.

Cross-feature by necessity (correction C7): it needs the feature-owned models in
`app/canon/`, `app/cast/`, `app/scenes/` and `app/ledger/` as well as the shared ones, and a
module under `app/commons/` may not import a feature (NFR-04).

The tree is read where it lies rather than copied: every call here is a read, and NFR-09's
"never write to a real tree" is satisfied by not writing at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.commons.stores import Store
from scripts.export_schemas import DOCUMENT_FORMATS, DOCUMENT_MODELS

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "repo"

NOT_STORE_FILES = frozenset({"README.md", "CLAUDE.md"})
"""The two files at the store root that are documentation, not records. `CLAUDE.md` is
listed at the store root by the storage layout and `README.md` is the answer key AC 28 is
reviewed against; neither is a typed document and neither is read by the store layer."""


_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"canon/project\.md", "project"),
    (r"canon/style\.md", "style_bible"),
    (r"canon/lexicon\.yaml", "lexicon"),
    (r"canon/time\.yaml", "temporal_system"),
    (r"canon/axioms/[^/]+\.md", "axiom"),
    (r"canon/technology/[^/]+\.md", "technology"),
    (r"canon/factions/[^/]+\.md", "faction"),
    (r"canon/history/[^/]+\.md", "historical_event"),
    (r"canon/locations/[^/]+\.md", "location"),
    (r"cast/relationships\.yaml", "relationships"),
    (r"cast/[^/]+/dossier\.md", "character"),
    (r"cast/[^/]+/voice\.md", "voice_profile"),
    (r"cast/[^/]+/knowledge\.yaml", "knowledge"),
    (r"cast/[^/]+/changes\.yaml", "changes"),
    (r"structure/arcs\.yaml", "arcs"),
    (r"structure/chapters\.yaml", "chapters"),
    (r"scenes/\d{3}\.yaml", "scene"),
    (r"manuscript/digests/\d{3}\.md", "scene_digest"),
    (r"manuscript/\d{3}\.md", "draft"),
    (r"ledger/setups\.yaml", "setups"),
    (r"ledger/threads\.yaml", "threads"),
    (r"ledger/timeline\.yaml", "timeline"),
    (r"ledger/proposed\.yaml", "proposed"),
    (r"ledger/violations\.yaml", "violations"),
)
"""Path grammar to document type, in the order the storage layout lists them.

`manuscript/digests/NNN.md` is matched before `manuscript/NNN.md` because a draft path and a
digest path differ only by the directory, and the looser pattern would swallow both."""


def _document_type(relative: str) -> str | None:
    for pattern, name in _PATTERNS:
        if re.fullmatch(pattern, relative):
            return name
    return None


def _store_files() -> list[str]:
    return sorted(
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file() and path.name not in NOT_STORE_FILES
    )


@pytest.fixture(scope="module")
def store() -> Store:
    return Store(root=FIXTURE_ROOT, index_dir=FIXTURE_ROOT.parent / ".index-never-written")


# spec 001 / AC 4 — the fixture exists at all, so a rename cannot make this suite vacuous.
def test_the_fixture_tree_is_present() -> None:
    assert FIXTURE_ROOT.is_dir(), f"no fixture repository at {FIXTURE_ROOT}"
    assert _store_files(), "the fixture repository holds no store files"


# spec 001 / AC 4 — DR-01: a file that matches no document type has no schema, which DR-01
# forbids. Reported as its own failure rather than as an unreadable file, because the two
# have different causes and different fixes.
@pytest.mark.parametrize("relative", _store_files(), ids=str)
def test_every_file_has_a_document_type(relative: str) -> None:
    name = _document_type(relative)
    assert name is not None, (
        f"{relative} matches no path in the storage layout; either the fixture invented a "
        "path or the layout gained one that scripts/export_schemas.py does not register"
    )
    assert name in DOCUMENT_MODELS, f"{relative} maps to {name!r}, which has no model"
    assert relative.endswith(DOCUMENT_FORMATS[name]), (
        f"{relative} is stored as {Path(relative).suffix}, but {name!r} is a "
        f"{DOCUMENT_FORMATS[name]} document"
    )


# spec 001 / AC 4 — FR-STORE-06: every record validates through the real read path, or names
# the file and the field that is wrong.
@pytest.mark.parametrize("relative", _store_files(), ids=str)
def test_every_file_validates(store: Store, relative: str) -> None:
    name = _document_type(relative)
    if name is None:
        pytest.skip("covered by test_every_file_has_a_document_type")
    model: type[BaseModel] = DOCUMENT_MODELS[name]
    store.read(relative, model)


# spec 001 / AC 4 — every registered type is actually exercised by the fixture. A type with
# no example is a type whose file format nothing has ever read.
def test_the_fixture_exercises_every_document_type() -> None:
    present = {_document_type(relative) for relative in _store_files()}
    missing = set(DOCUMENT_MODELS) - present
    assert not missing, f"no fixture file for document types: {sorted(missing)}"
