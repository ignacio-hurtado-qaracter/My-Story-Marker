"""The derived entity index: one SQLite file outside the tree (FR-IDX-01).

`commons/db/` is the only module that speaks SQLite (NFR-04, the import contract) and the
only owner of `index.sqlite`. What callers outside it get is deliberately narrow: rebuild
and update the index, ask for its status, and search it. **Searches answer identifiers,
kinds and scores, never text** (FR-OPS-02) -- the row text never leaves this package.
"""

from __future__ import annotations

from app.commons.db.index import (
    CANON_DIRECTORY_BY_KIND,
    CANON_KIND_BY_DIRECTORY,
    EmbeddingModelMismatchError,
    IndexHit,
    IndexKind,
    IndexStatus,
    search_text,
    search_vector,
    status,
)
from app.commons.db.rebuild import IndexReport, ensure_current, rebuild, update

__all__ = [
    "CANON_DIRECTORY_BY_KIND",
    "CANON_KIND_BY_DIRECTORY",
    "EmbeddingModelMismatchError",
    "IndexHit",
    "IndexKind",
    "IndexReport",
    "IndexStatus",
    "ensure_current",
    "rebuild",
    "search_text",
    "search_vector",
    "status",
    "update",
]
