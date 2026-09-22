"""The SQLite connection: WAL, a busy timeout, retries, and the optional vector extension.

FR-IDX-03 is the requirement that shapes this module, and it is stricter than it looks: **no
code path fails for a missing extension.** The CI matrix runs one cell with `sqlite-vec`
uninstalled, so the import is guarded, the migration that needs it is skipped and recorded as
skipped, and selection falls back to FTS5 alone. The backend starts either way and `/health`
says which.

FR-IDX-06 is the other half. A single writer is the supported deployment (a turn holds a lock
file, FR-TURN-05), but a rebuild and a read can still overlap, and `SQLITE_BUSY` is a normal
outcome rather than an error. It becomes `IndexBusy` -- a 503 -- only after the timeout and
the retries are exhausted, so a caller that sees one knows waiting longer would not have
helped.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Final

from app.commons.errors import IndexBusy

BUSY_TIMEOUT_MS: Final[int] = 5_000
"""How long SQLite itself waits for a lock before returning SQLITE_BUSY."""

RETRY_ATTEMPTS: Final[int] = 3
RETRY_BACKOFF_SECONDS: Final[float] = 0.05


def vector_extension_available() -> bool:
    """True when `sqlite-vec` loads into this interpreter's SQLite.

    Three separate things can go wrong and all of them are ordinary, not exceptional: the
    package may not be installed (the `absent` cell of the CI matrix), the interpreter may
    have been built without `enable_load_extension`, or the load may fail on the platform.
    Each answers the same question with `False`, and selection falls back to FTS5 only.
    """
    connection = sqlite3.connect(":memory:")
    try:
        return load_vector_extension(connection)
    finally:
        connection.close()


def load_vector_extension(connection: sqlite3.Connection) -> bool:
    """Try to load `sqlite-vec` into an open connection. Never raises."""
    try:
        # Guarded: the CI matrix runs a cell with the package uninstalled, and FR-IDX-03
        # says no code path fails for a missing extension.
        import sqlite_vec
    except ImportError:
        return False

    enable = getattr(connection, "enable_load_extension", None)
    if enable is None:
        return False
    try:
        enable(True)
        sqlite_vec.load(connection)
        connection.execute("select vec_version()").fetchone()
    except (AttributeError, OSError, sqlite3.Error):
        return False
    else:
        return True
    finally:
        # Extension loading is left disabled again whatever happened: leaving it on would
        # let any later `load_extension()` on this connection reach arbitrary shared objects.
        with suppress(AttributeError, sqlite3.Error):
            enable(False)


def connect(index_path: Path, *, with_vector: bool = True) -> sqlite3.Connection:
    """Open the index, applying the pragmas FR-IDX-06 asks for.

    WAL because a reader and the rebuild overlap; `foreign_keys` because the schema is small
    enough that there is no excuse for dangling rows; `synchronous = NORMAL` because the index
    is derived and rebuildable, so trading a little durability for speed costs nothing that
    cannot be regenerated from the tree.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(index_path, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma journal_mode = WAL")
    connection.execute("pragma synchronous = NORMAL")
    connection.execute("pragma foreign_keys = ON")
    connection.execute(f"pragma busy_timeout = {BUSY_TIMEOUT_MS}")
    if with_vector:
        load_vector_extension(connection)
    return connection


@contextmanager
def opened(index_path: Path, *, with_vector: bool = True) -> Iterator[sqlite3.Connection]:
    """A connection that is always closed, even when the body raises."""
    connection = connect(index_path, with_vector=with_vector)
    try:
        yield connection
    finally:
        connection.close()


def is_busy(error: sqlite3.Error) -> bool:
    """`SQLITE_BUSY` and `SQLITE_LOCKED`, told apart from every other operational error.

    Matching on the message rather than a code because `sqlite3.OperationalError` does not
    carry one portably. Narrow on purpose: retrying a syntax error would turn a bug into a
    slow bug.
    """
    text = str(error).lower()
    return "locked" in text or "busy" in text


def with_retry[ResultT](operation: Callable[[], ResultT]) -> ResultT:
    """Run `operation`, retrying only on lock contention, then raise `IndexBusy`.

    FR-IDX-06: `IndexBusy` **only after the timeout**. A 503 that appeared before waiting
    would teach callers to retry immediately, which is the one thing that makes contention
    worse.
    """
    last: sqlite3.Error | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return operation()
        except sqlite3.Error as error:
            if not is_busy(error):
                raise
            last = error
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))

    message = (
        f"the index is locked by another writer after {RETRY_ATTEMPTS} attempts and a "
        f"{BUSY_TIMEOUT_MS} ms busy timeout"
    )
    raise IndexBusy(message) from last


__all__ = [
    "BUSY_TIMEOUT_MS",
    "RETRY_ATTEMPTS",
    "connect",
    "is_busy",
    "load_vector_extension",
    "opened",
    "vector_extension_available",
    "with_retry",
]
