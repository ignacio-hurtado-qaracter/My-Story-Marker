"""Reading the turn records under `.index/turns/`.

`.index/` is not a store, but it is still files, and the boundary rules of AC 3 allow file
primitives only in `commons/stores/` and a few named owners of `.index/`. The provenance log
is read here for the same reason. `agents/records.py` writes turn records (plan step 18);
reading them lives here so that `canon/`'s `reconcile` can see them without importing a
feature that sits above it (NFR-04).
"""

from __future__ import annotations

from pathlib import Path

from app.commons.errors import InvalidRecord
from app.commons.schemas.turn import TurnRecord
from app.commons.stores import frontmatter as fm

TURNS_DIR = "turns"


def turns_path(index_dir: Path) -> Path:
    return index_dir / TURNS_DIR


def read_turn_records(index_dir: Path) -> list[TurnRecord]:
    """Every turn record, sorted by file name so the order never depends on the filesystem.

    A record that does not validate is an error naming the file, as for any store file: a
    turn record `reconcile` silently skipped would hide exactly the scenes it exists to name.
    """
    directory = turns_path(index_dir)
    if not directory.is_dir():
        return []
    records: list[TurnRecord] = []
    for path in sorted(directory.glob("*.yaml")):
        name = f"{TURNS_DIR}/{path.name}"
        try:
            records.append(TurnRecord.model_validate(fm.parse_yaml(path.read_text("utf-8"))))
        except ValueError as error:
            message = f".index/{name} is not a valid turn record: {error}"
            raise InvalidRecord(message, file=name) from error
    return records


__all__ = ["TURNS_DIR", "read_turn_records", "turns_path"]
