"""Planted positive for AC 13: a canon write under `ledger/` outside promote/rule.

Resolving a collision here rather than escalating it is the failure mode `ProposedFact`
names: canon fills with improvised noise and stops being worth consulting.
"""

from __future__ import annotations

from typing import Protocol


class StoreLike(Protocol):
    def write(self, path: str, record: object, *, role: object) -> None: ...


def resolve_collision_quietly(store: StoreLike, record: object, role: object) -> None:
    store.write("canon/axioms/fold-drive.md", record, role=role)
