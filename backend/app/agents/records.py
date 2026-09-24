"""Turn records under `.index/turns/NNN-<n>.yaml` (FR-TURN-07, plan decision P6).

`.index/` is not a store: Figure 3 does not govern it and no agent reads it, and the
orchestrator writes its own records there directly (Decision R2-1, FR-TURN-06). So this module
writes files itself -- it and `agents/lock.py` are the named exceptions to the boundary rules
of AC 3 -- and touches nothing outside `.index/turns/`. Reading goes through
`Store.turn_records`, the reader `canon`'s `reconcile` already uses, so a record is validated
the same way whoever reads it.

**Rewritten whole after every step** (FR-TURN-07), which is why the shape is YAML and not the
append-only JSON Lines of the provenance log (P6). The rewrite goes to a sibling temporary file
first and is renamed over the record, so a process killed mid-write leaves the previous
complete record rather than half of the next one: the record is what a resume starts from
(FR-TURN-09). The temporary name does not end in `.yaml`, so no reader ever lists it.

`NNN-<n>` numbers the attempts at a scene from 1; the next is one past the highest recorded,
compared as numbers so that attempt 10 follows attempt 9 however the file names sort.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from app.commons.errors import NotFound
from app.commons.schemas import TurnRecord
from app.commons.schemas.turn import TURN_ID_PATTERN
from app.commons.stores import Store, turns
from app.commons.stores.frontmatter import render_yaml

_TURN_ID: Final[re.Pattern[str]] = re.compile(TURN_ID_PATTERN)
TEMPORARY_SUFFIX: Final[str] = ".tmp"


def turn_id(value: str) -> str:
    """A turn id, or `ValueError`: it becomes a file name, so it is held to its grammar."""
    if not _TURN_ID.fullmatch(value):
        message = f"{value!r} is not a turn id: expected {TURN_ID_PATTERN}"
        raise ValueError(message)
    return value


def record_path(index_dir: Path, identifier: str) -> Path:
    return turns.turns_path(index_dir) / f"{turn_id(identifier)}.yaml"


def attempt(identifier: str) -> int:
    """The `<n>` of `NNN-<n>`."""
    return int(turn_id(identifier).partition("-")[2])


def list_all(store: Store) -> list[TurnRecord]:
    """Every turn record, by scene and then attempt."""
    return sorted(store.turn_records(), key=lambda record: (record.scene, attempt(record.id)))


def load(store: Store, identifier: str) -> TurnRecord:
    """One turn record, or `NotFound` (404)."""
    turn_id(identifier)
    for record in store.turn_records():
        if record.id == identifier:
            return record
    message = f"no turn record {identifier} under .index/{turns.TURNS_DIR}/"
    raise NotFound(message, kind="turn", identifier=identifier)


def next_turn_id(store: Store, scene_id: str) -> str:
    """`NNN-<n>` for the next attempt at `scene_id`."""
    attempts = [attempt(record.id) for record in store.turn_records() if record.scene == scene_id]
    return f"{scene_id}-{max(attempts, default=0) + 1}"


def save(store: Store, record: TurnRecord) -> None:
    """Write the record whole, through a sibling temporary file renamed over it."""
    target = record_path(store.index_dir, record.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}{TEMPORARY_SUFFIX}")
    temporary.write_text(render_yaml(record.model_dump(mode="json")), encoding="utf-8")
    temporary.replace(target)


__all__ = [
    "TEMPORARY_SUFFIX",
    "attempt",
    "list_all",
    "load",
    "next_turn_id",
    "record_path",
    "save",
    "turn_id",
]
