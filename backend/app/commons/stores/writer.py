"""Writes. Every one names a role, is checked against Figure 3, lands atomically, and is
logged.

Three requirements meet in one function, and the order they run in is the design:

1. **FR-STORE-03** -- the role is checked *before any byte touches disk*. Not after the write
   and rolled back, not while writing: a refused write leaves the tree byte-identical, which
   is what AC 16 measures with a tree hash.
2. **FR-STORE-07** -- temp file, fsync, rename. A process killed mid-write leaves either the
   old file or the new one, never half of either. The store layer never runs git; the tree is
   a working tree and a human commits.
3. **FR-STORE-04** -- provenance is appended by this function, so no write can skip it.

There is no `role=None` path and no internal bypass. The orchestrator itself holds no role and
cannot write to the tree except through a role's tool set (FR-TURN-06); its own records go to
`.index/`, which is not a store and does not come through here.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from app.commons.errors import PermissionDenied
from app.commons.permissions import Actor, AgentRole, may_write
from app.commons.stores import frontmatter as fm
from app.commons.stores import paths, provenance


def _refuse_unless_permitted(role: AgentRole, relative: str) -> None:
    if not may_write(role, relative):
        raise PermissionDenied(
            f"Figure 3 does not allow {role.value} to write {relative}",
            role=role.value,
            path=relative,
        )


def _atomic_write(target: Path, text: str) -> bytes:
    """FR-STORE-07. Returns the bytes written, so the caller hashes exactly what landed."""
    data = text.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed explicitly before the rename
        mode="wb",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        temporary.replace(target)
    except BaseException:
        handle.close()
        temporary.unlink(missing_ok=True)
        raise
    return data


def serialise(relative: str, record: BaseModel) -> str:
    """A record as the text its extension calls for.

    `by_alias=True` because the YAML keys are the contract: `ChangeEvent` and `Relationship`
    carry `from` and `to`, which cannot be Python identifiers, and a file written by field
    name would not be the file `definitions.md` describes.
    """
    payload = record.model_dump(mode="json", by_alias=True)
    return fm.render_markdown(payload) if fm.is_markdown(relative) else fm.render_yaml(payload)


def write_record(
    root: Path,
    index_dir: Path,
    relative: str,
    record: BaseModel,
    *,
    role: AgentRole,
    actor: Actor = Actor.AGENT,
    scene: str | None = None,
    turn: str | None = None,
) -> provenance.ProvenanceRecord:
    """The one way a store file changes. Returns the provenance line that was appended."""
    _refuse_unless_permitted(role, relative)
    target = paths.resolve(root, relative)
    data = _atomic_write(target, serialise(relative, record))
    line = provenance.ProvenanceRecord(
        path=paths.relative_to_root(root, target),
        role=role,
        actor=actor,
        content_hash=provenance.content_hash(data),
        at=provenance.now(),
        scene=scene,
        turn=turn,
    )
    provenance.append(index_dir, line)
    return line


def write_text(
    root: Path,
    index_dir: Path,
    relative: str,
    text: str,
    *,
    role: AgentRole,
    actor: Actor = Actor.AGENT,
    scene: str | None = None,
    turn: str | None = None,
) -> provenance.ProvenanceRecord:
    """The same guarantees for a file whose content is already rendered.

    Used where a record has been serialised elsewhere and re-serialising would change bytes
    for no reason. It is still checked, still atomic and still logged: there is no path into
    the tree that skips any of the three.
    """
    _refuse_unless_permitted(role, relative)
    target = paths.resolve(root, relative)
    data = _atomic_write(target, text)
    line = provenance.ProvenanceRecord(
        path=paths.relative_to_root(root, target),
        role=role,
        actor=actor,
        content_hash=provenance.content_hash(data),
        at=provenance.now(),
        scene=scene,
        turn=turn,
    )
    provenance.append(index_dir, line)
    return line


__all__ = ["serialise", "write_record", "write_text"]
