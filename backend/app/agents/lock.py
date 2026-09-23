"""The turn lock: one turn at a time on a store root (FR-TURN-05).

A lock **file** under `.index/`, because the rule is about the store root and not about a
process: two turns on one tree would interleave their writes to `ledger/proposed.yaml` and
`ledger/violations.yaml`, and each would audit and promote against a tree the other was
halfway through changing. `.index/` is not a store (Decision R2-1), so this module owns the
file directly; it and `agents/records.py` are the two named exceptions to the boundary rules
of AC 3 and to the filesystem contract of NFR-04, and they touch nothing but `.index/`.

**Acquired by exclusive creation** (`open("x")`, O_CREAT | O_EXCL): the file either did not
exist and is now ours, or it existed and the caller gets `TurnLocked`, a 409 (IF-07). The file
holds the id of the turn that took it, so the refusal names who holds the lock. A process-local
set of held locks answers the same question inside this process, where the file alone could not
tell a running turn from a crashed one.

**Released on every exit path** by the caller's `finally` (`app.agents.turn.TurnRun`). A process
that dies outright cannot run a `finally`, and leaves the file behind: the record of the turn it
was running is still `running` (FR-TURN-07 writes it after every step), and resuming *that* turn
takes the lock over (`take_over`) -- the one holder that can be proved not to be running, since
the file names it and this process does not hold it. A lock left by any other turn is released
by resuming that turn, or removed by a person; it is never broken by a new turn, which cannot
know whether the holder is alive (P5: one worker, a synchronous turn).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.commons.errors import TurnLocked

LOCK_FILE: Final[str] = "turn.lock"
"""`.index/turn.lock`, beside the turn records and the provenance log."""

_HELD: set[str] = set()
"""The lock files this process holds, by resolved path. A turn is synchronous and runs on one
worker (P5), so an entry here is a turn running now."""
_GUARD: Final[threading.Lock] = threading.Lock()


@dataclass(frozen=True, slots=True)
class TurnLockHandle:
    """A held lock: the file and the turn it was taken for."""

    path: Path
    turn_id: str


def lock_path(index_dir: Path) -> Path:
    return index_dir / LOCK_FILE


def holder(index_dir: Path) -> str | None:
    """The turn id the lock file names, or None when no turn holds the lock."""
    path = lock_path(index_dir)
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def acquire(index_dir: Path, turn_id: str, *, take_over: bool = False) -> TurnLockHandle:
    """FR-TURN-05. Take the store root's turn lock for `turn_id`, or `TurnLocked`.

    `take_over` is the resume of a crashed turn: a lock file that names this very turn, held
    by no turn of this process, was left by a process that died, and is taken over.
    """
    path = lock_path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    with _GUARD:
        if key in _HELD:
            message = (
                f"turn {holder(index_dir)} is running on this store root; one turn at a time "
                "(FR-TURN-05)"
            )
            raise TurnLocked(message)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(f"{turn_id}\n")
        except FileExistsError:
            current = holder(index_dir)
            if not (take_over and current == turn_id):
                message = (
                    f"turn {current} holds the lock {LOCK_FILE} on this store root; one turn at "
                    f"a time (FR-TURN-05). Resume turn {current} to finish it, or remove "
                    f".index/{LOCK_FILE} if no process is running it"
                )
                raise TurnLocked(message) from None
            path.write_text(f"{turn_id}\n", encoding="utf-8")
        _HELD.add(key)
    return TurnLockHandle(path=path, turn_id=turn_id)


def release(handle: TurnLockHandle) -> None:
    """Give the lock back. Idempotent, and the file is removed only while it still names the
    turn that took it."""
    key = str(handle.path.resolve())
    with _GUARD:
        _HELD.discard(key)
        try:
            current = handle.path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return
        if current == handle.turn_id:
            handle.path.unlink(missing_ok=True)


__all__ = ["LOCK_FILE", "TurnLockHandle", "acquire", "holder", "lock_path", "release"]
