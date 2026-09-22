"""The append-only provenance log: who wrote what, under which role, and whether a human
was behind it.

FR-STORE-04. One line per store write, appended by the store layer itself so that **no write
can skip it** -- that is the entire design. A provenance log a caller has to remember to
append to records the writes of careful callers and nothing about the interesting ones.

It lives at `.index/provenance.jsonl`, outside the store tree. Nothing under `.index/` is a
store: it is not governed by Figure 3, no agent reads it, and it is written by the store layer
and the orchestrator directly (Decision R2-1). The cost is registered as an accepted risk
(AC 31): the index can be rebuilt from the tree, this log cannot. Losing it loses the history
of how the tree came to be, though not the tree.

JSON Lines rather than YAML because the shape is append-only (plan decision P6). A writer that
has to parse the file before adding to it is a writer that can corrupt it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.commons.permissions import Actor, AgentRole

PROVENANCE_FILE = "provenance.jsonl"


class ProvenanceRecord(BaseModel):
    """One store write. Every field answers a question someone asks after the fact."""

    path: str = Field(description="Store-relative POSIX path that was written.")
    role: AgentRole = Field(description="The Figure 3 role the write was performed under.")
    actor: Actor = Field(
        description=(
            "`agent` or `human` (Decision R2-7). A human acts under a role rather than "
            "beside it, which is why there is no `human` row in Figure 3."
        )
    )
    content_hash: str = Field(description="SHA-256 of the bytes written, hex.")
    at: str = Field(description="ISO-8601 UTC timestamp.")
    scene: str | None = Field(default=None, description="Scene id, when the write is in a turn.")
    turn: str | None = Field(default=None, description="Turn id, when the write is in a turn.")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


def log_path(index_dir: Path) -> Path:
    return index_dir / PROVENANCE_FILE


def append(index_dir: Path, record: ProvenanceRecord) -> None:
    """Append one line. Opened per write, in append mode, and closed immediately.

    Holding the file open across writes would be faster and would also mean a crash loses the
    tail of the log, which is exactly the part that explains what the process was doing when
    it crashed.
    """
    index_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    with log_path(index_dir).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read(index_dir: Path, *, path: str | None = None, since: str | None = None) -> list[
    ProvenanceRecord
]:
    """IF-03, `GET /agents/provenance?path=&since=`. Filters, never aggregates."""
    return [
        record
        for record in _iter_records(index_dir)
        if (path is None or record.path == path) and (since is None or record.at >= since)
    ]


def _iter_records(index_dir: Path) -> Iterator[ProvenanceRecord]:
    target = log_path(index_dir)
    if not target.is_file():
        return
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield ProvenanceRecord.model_validate_json(stripped)


__all__ = [
    "PROVENANCE_FILE",
    "ProvenanceRecord",
    "append",
    "content_hash",
    "log_path",
    "now",
    "read",
]
