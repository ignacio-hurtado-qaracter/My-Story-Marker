"""The store layer: the only path to `canon/`, `cast/`, `structure/`, `scenes/`,
`manuscript/` and `ledger/`.

FR-STORE-02 is a rule about the whole codebase, not about this package: *only modules under
`app/commons/stores/` open, read, write, rename or delete files under the store root.* A
feature's `repository.py` calls `Store`; nothing anywhere else builds a path or opens a file.
The `semgrep` rule of AC 3 and its AST mirror are what prove it, because an import contract
can see that a module imported `pathlib` but not what path it then used.

`Store` is the surface. It is a value, not a service: it holds the two directories and no
state, because FR-STORE-08 forbids an in-process record cache across requests -- the tree is a
git working tree that people edit, and a read has to see that.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.commons.permissions import Actor, AgentRole
from app.commons.stores import paths, provenance, reader, writer


@dataclass(frozen=True, slots=True)
class Store:
    """A bound store root and the `.index/` beside it.

    `index_dir` is here rather than somewhere else because provenance is appended by the same
    call that writes (FR-STORE-04); a `Store` that could write without knowing where to log
    would be a `Store` that can skip the log.
    """

    root: Path
    index_dir: Path

    def exists(self, relative: str) -> bool:
        return reader.exists(self.root, relative)

    def read[RecordT: BaseModel](self, relative: str, model: type[RecordT]) -> RecordT:
        """FR-STORE-06. Validated, or `InvalidRecord` naming file and field."""
        return reader.read_record(self.root, relative, model)

    def read_raw(self, relative: str) -> str:
        return reader.read_raw(self.root, relative)

    def list_files(self, directory: str, suffix: str) -> list[str]:
        return reader.list_records(self.root, directory, suffix)

    def list_subdirectories(self, directory: str) -> list[str]:
        return reader.list_subdirectories(self.root, directory)

    def write(
        self,
        relative: str,
        record: BaseModel,
        *,
        role: AgentRole,
        actor: Actor = Actor.AGENT,
        scene: str | None = None,
        turn: str | None = None,
    ) -> provenance.ProvenanceRecord:
        """FR-STORE-03, -04, -07. Checked, atomic, logged, in that order."""
        return writer.write_record(
            self.root,
            self.index_dir,
            relative,
            record,
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )

    def write_text(
        self,
        relative: str,
        text: str,
        *,
        role: AgentRole,
        actor: Actor = Actor.AGENT,
        scene: str | None = None,
        turn: str | None = None,
    ) -> provenance.ProvenanceRecord:
        return writer.write_text(
            self.root,
            self.index_dir,
            relative,
            text,
            role=role,
            actor=actor,
            scene=scene,
            turn=turn,
        )

    def provenance(
        self, *, path: str | None = None, since: str | None = None
    ) -> list[provenance.ProvenanceRecord]:
        """IF-03. Read-only; the log is append-only and nothing here can rewrite it."""
        return provenance.read(self.index_dir, path=path, since=since)


__all__ = ["Store", "paths", "provenance", "reader", "writer"]
