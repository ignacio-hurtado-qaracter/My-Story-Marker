"""Export a versioned JSON Schema per store document type (DR-01, DR-10).

    uv run python scripts/export_schemas.py            # write backend/schemas/*.v1.json
    uv run python scripts/export_schemas.py --check    # exit 1 if any file is stale

The registry below is the **only** place that names every store document type at once. It
has to live outside `app/`: it knows both the shared records in `commons/schemas/` and the
feature-owned ones in `app/canon/`, `app/cast/` and `app/scenes/`, and a `commons/` module
that imported a feature would break NFR-04.

Exported files are committed. A drift between a model and its schema is a contract change
that nobody reviewed, which is why `--check` is a gate stage rather than a convenience.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from app.canon.models import (
    Axiom,
    Faction,
    HistoricalEvent,
    Location,
    Project,
    StyleBible,
    Technology,
)
from app.cast.models import Character, VoiceProfile
from app.commons.schemas.change_event import ChangesFile
from app.commons.schemas.digest import SceneDigest
from app.commons.schemas.draft import Draft
from app.commons.schemas.knowledge import KnowledgeFile
from app.commons.schemas.lexicon import LexiconFile
from app.commons.schemas.proposed import ProposedFile
from app.commons.schemas.relationship import RelationshipsFile
from app.commons.schemas.scene import Scene
from app.commons.schemas.setup import SetupsFile
from app.commons.schemas.thread import ThreadsFile
from app.commons.schemas.time import TemporalSystem
from app.commons.schemas.violation import ViolationsFile
from app.scenes.models import ArcsFile, ChaptersFile

SCHEMA_VERSION_SUFFIX = "v1"

DOCUMENT_MODELS: dict[str, type[BaseModel]] = {
    # canon/
    "project": Project,
    "style_bible": StyleBible,
    "axiom": Axiom,
    "technology": Technology,
    "faction": Faction,
    "location": Location,
    "historical_event": HistoricalEvent,
    "lexicon": LexiconFile,
    "temporal_system": TemporalSystem,
    # cast/
    "character": Character,
    "voice_profile": VoiceProfile,
    "knowledge": KnowledgeFile,
    "changes": ChangesFile,
    "relationships": RelationshipsFile,
    # structure/
    "arcs": ArcsFile,
    "chapters": ChaptersFile,
    # scenes/
    "scene": Scene,
    # manuscript/
    "draft": Draft,
    "scene_digest": SceneDigest,
    # ledger/
    "setups": SetupsFile,
    "threads": ThreadsFile,
    "proposed": ProposedFile,
    "violations": ViolationsFile,
}
"""Every file type under the stores, per the storage layout. A type missing here has no
exported schema, which DR-01 forbids; the test in `tests/test_schema_export.py` is what
makes the omission visible."""


def schemas_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"


def render(model: type[BaseModel]) -> str:
    """One canonical rendering, so `--check` compares content and not formatting."""
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def target_path(name: str) -> Path:
    return schemas_dir() / f"{name}.{SCHEMA_VERSION_SUFFIX}.json"


def write_all() -> list[Path]:
    directory = schemas_dir()
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in DOCUMENT_MODELS.items():
        path = target_path(name)
        path.write_text(render(model), encoding="utf-8")
        written.append(path)
    return written


def stale() -> list[str]:
    """Names whose committed schema is missing or no longer matches the model."""
    drifted: list[str] = []
    for name, model in DOCUMENT_MODELS.items():
        path = target_path(name)
        if not path.is_file() or path.read_text(encoding="utf-8") != render(model):
            drifted.append(name)
    return drifted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any committed schema is stale",
    )
    args = parser.parse_args(argv)

    if args.check:
        drifted = stale()
        if drifted:
            print("stale JSON Schemas (run without --check to regenerate):")
            for name in drifted:
                print(f"  - {target_path(name).name}")
            return 1
        print(f"{len(DOCUMENT_MODELS)} JSON Schemas up to date")
        return 0

    written = write_all()
    print(f"wrote {len(written)} JSON Schemas to {schemas_dir()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
