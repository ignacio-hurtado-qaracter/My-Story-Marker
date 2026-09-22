"""SQLite connection concerns. At plan step 2 this module carries only the probe that
`/health` reports; step 9 adds the connection factory, WAL and busy-timeout handling.

FR-IDX-03 is the requirement that shapes it: the backend tries to load `sqlite-vec` and
works either way. "No code path fails for a missing extension" means the import itself has
to be guarded, because the CI matrix runs one cell with the package uninstalled.
"""

from __future__ import annotations

import sqlite3


def vector_extension_available() -> bool:
    """True when `sqlite-vec` loads into this interpreter's SQLite.

    Three separate things can go wrong and all of them are ordinary, not exceptional: the
    package may not be installed (the `absent` cell of the CI matrix), the interpreter may
    have been built without `enable_load_extension`, or the load may fail on the platform.
    Each answers the same question with `False`, and selection falls back to FTS5 only.
    """
    try:
        import sqlite_vec  # local import: guarded on purpose, see the docstring
    except ImportError:
        return False

    connection = sqlite3.connect(":memory:")
    try:
        enable_load_extension = getattr(connection, "enable_load_extension", None)
        if enable_load_extension is None:
            return False
        enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.execute("select vec_version()").fetchone()
    except (AttributeError, OSError, sqlite3.Error):
        return False
    else:
        return True
    finally:
        connection.close()
