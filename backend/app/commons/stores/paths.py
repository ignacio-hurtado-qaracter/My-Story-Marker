"""Identifiers to paths, and nothing else builds a store path.

FR-STORE-05: **paths derive from identifiers inside the store layer, never from the client.**
A route takes an id, hands it to one of the functions below, and receives a store-relative
POSIX path. No caller anywhere concatenates a path itself, which is what makes "an identifier
that would escape the root is rejected" a property of the system rather than a habit.

Two grammars, both from FR-STORE-05: entity ids match `^[a-z0-9][a-z0-9_-]*$`, scene ids
match `^\\d{3}$`. `definitions.md` adds the reason they are strict: identifiers are stable
forever, because renaming an entity breaks every edge that points at it. The backend never
renames (DR-08).
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Final

from app.commons.permissions import normalise
from app.commons.schemas.common import ENTITY_ID_PATTERN, SCENE_ID_PATTERN

_ENTITY_ID = re.compile(ENTITY_ID_PATTERN)
_SCENE_ID = re.compile(SCENE_ID_PATTERN)

CANON_KINDS: Final[tuple[str, ...]] = (
    "axioms",
    "technology",
    "locations",
    "factions",
    "history",
)
"""The directories under `canon/` that hold one file per entity, per the storage layout.
`project.md`, `style.md`, `lexicon.yaml` and `time.yaml` are single files and have their own
functions; a kind not listed here has no path."""

LEDGER_FILES: Final[tuple[str, ...]] = (
    "setups",
    "threads",
    "timeline",
    "proposed",
    "violations",
)
"""The five ledger files, per the storage layout."""

CAST_FILES: Final[dict[str, str]] = {
    "dossier": "dossier.md",
    "voice": "voice.md",
    "knowledge": "knowledge.yaml",
    "changes": "changes.yaml",
}
"""The four per-character files. `changes.yaml` is here because Decision R2-5 put
ChangeEvents at `cast/{id}/changes.yaml`, written by the canoniser and read by the auditor."""


def entity_id(value: str) -> str:
    """FR-STORE-05. Returns the id, or raises `ValueError` naming what is wrong with it."""
    if not _ENTITY_ID.fullmatch(value):
        message = (
            f"{value!r} is not a valid entity id: expected {ENTITY_ID_PATTERN} "
            "(lower case, starting with a letter or digit)"
        )
        raise ValueError(message)
    return value


def scene_id(value: str) -> str:
    """FR-STORE-05. `NNN`, three digits, stable forever."""
    if not _SCENE_ID.fullmatch(value):
        message = f"{value!r} is not a valid scene id: expected {SCENE_ID_PATTERN}"
        raise ValueError(message)
    return value


def canon_kind(value: str) -> str:
    if value not in CANON_KINDS:
        message = f"{value!r} is not a canon kind; expected one of {', '.join(CANON_KINDS)}"
        raise ValueError(message)
    return value


# --- canon/ ---------------------------------------------------------------------------

CANON = "canon"
PROJECT = "canon/project.md"
STYLE = "canon/style.md"
LEXICON = "canon/lexicon.yaml"
TIME = "canon/time.yaml"


def canon_entity(kind: str, identifier: str) -> str:
    """`canon/<kind>/<id>.md`."""
    return f"canon/{canon_kind(kind)}/{entity_id(identifier)}.md"


def canon_dir(kind: str) -> str:
    """`canon/<kind>`, for listing one kind's records."""
    return f"canon/{canon_kind(kind)}"


# --- cast/ ----------------------------------------------------------------------------

CAST = "cast"
RELATIONSHIPS = "cast/relationships.yaml"


def cast_file(character: str, which: str) -> str:
    """`cast/<id>/<file>` for one of the four per-character files."""
    if which not in CAST_FILES:
        message = f"{which!r} is not a cast file; expected one of {', '.join(CAST_FILES)}"
        raise ValueError(message)
    return f"cast/{entity_id(character)}/{CAST_FILES[which]}"


def cast_dir(character: str) -> str:
    """`cast/<id>`, one directory per character."""
    return f"cast/{entity_id(character)}"


# --- structure/ and scenes/ -----------------------------------------------------------

ARCS = "structure/arcs.yaml"
SCENES = "scenes"
CHAPTERS = "structure/chapters.yaml"


def scene(identifier: str) -> str:
    """`scenes/NNN.yaml`."""
    return f"scenes/{scene_id(identifier)}.yaml"


# --- manuscript/ ----------------------------------------------------------------------

MANUSCRIPT = "manuscript"
DIGESTS = "manuscript/digests"


def draft(identifier: str) -> str:
    """`manuscript/NNN.md`. Never enters a context except as the previous scene's tail."""
    return f"manuscript/{scene_id(identifier)}.md"


def digest(identifier: str) -> str:
    """`manuscript/digests/NNN.md`. At chapter and arc level the id is still the file name;
    the range it covers lives in the record's `scene_ref` (DR-11)."""
    return f"manuscript/digests/{scene_id(identifier)}.md"


# --- ledger/ --------------------------------------------------------------------------


def ledger(name: str) -> str:
    """`ledger/<name>.yaml`."""
    if name not in LEDGER_FILES:
        message = f"{name!r} is not a ledger file; expected one of {', '.join(LEDGER_FILES)}"
        raise ValueError(message)
    return f"ledger/{name}.yaml"


SETUPS = "ledger/setups.yaml"
THREADS = "ledger/threads.yaml"
TIMELINE = "ledger/timeline.yaml"
PROPOSED = "ledger/proposed.yaml"
VIOLATIONS = "ledger/violations.yaml"


# --- resolution -----------------------------------------------------------------------


def resolve(root: Path, relative: str) -> Path:
    """Store-relative path to an absolute one, refusing anything that leaves the root.

    The containment check is belt and braces over `normalise`: `normalise` rejects `..` and
    absolute paths textually, and this re-checks after resolution, which also catches a
    symlink pointing out of the tree. Two cheap checks are worth it here -- this is the only
    function in the process that turns a string into a file the backend will open.
    """
    safe = normalise(relative)
    root_resolved = root.resolve()
    target = (root_resolved / PurePosixPath(safe)).resolve()
    if target != root_resolved and root_resolved not in target.parents:
        message = f"{relative!r} resolves outside the store root"
        raise ValueError(message)
    return target


def relative_to_root(root: Path, target: Path) -> str:
    """The inverse, as the POSIX string the permission table and provenance log speak."""
    return target.resolve().relative_to(root.resolve()).as_posix()


__all__ = [
    "ARCS",
    "CANON",
    "CANON_KINDS",
    "CAST",
    "CAST_FILES",
    "CHAPTERS",
    "DIGESTS",
    "LEDGER_FILES",
    "LEXICON",
    "MANUSCRIPT",
    "PROJECT",
    "PROPOSED",
    "RELATIONSHIPS",
    "SCENES",
    "SETUPS",
    "STYLE",
    "THREADS",
    "TIME",
    "TIMELINE",
    "VIOLATIONS",
    "canon_dir",
    "canon_entity",
    "canon_kind",
    "cast_dir",
    "cast_file",
    "digest",
    "draft",
    "entity_id",
    "ledger",
    "relative_to_root",
    "resolve",
    "scene",
    "scene_id",
]
