"""The authoritative database (spec 005, spec 004 decision D1).

Distinct from the derived index under `.index/`: this file is a *source*, holding the
novel, its versions, the brief and its facts, chronology, forbidden-word lists, the policy
log, validator results and model-call costs. Only `app.bible.BibleRepository` uses it.
"""

from __future__ import annotations

from app.commons.db.authoritative.connection import (
    AUTHORITATIVE_MIGRATIONS_TABLE,
    applied_migrations,
    open_authoritative,
)

__all__ = ["AUTHORITATIVE_MIGRATIONS_TABLE", "applied_migrations", "open_authoritative"]
