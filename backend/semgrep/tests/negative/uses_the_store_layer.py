"""Planted negatives. None of this may be reported.

A rule that fires here is a rule that would make the correct way of doing things fail the
gate, which is worse than one that misses: it teaches people to suppress it.
"""

from __future__ import annotations

from typing import Protocol


class StoreLike(Protocol):
    def write(self, path: str, record: object, *, role: object) -> None: ...
    def read(self, path: str, model: type) -> object: ...


def write_the_proper_way(store: StoreLike, record: object, role: object) -> None:
    store.write("manuscript/014.md", record, role=role)


def read_the_proper_way(store: StoreLike, model: type) -> object:
    return store.read("scenes/014.yaml", model)


def one_path_is_not_a_toolset() -> list[str]:
    return ["ledger/violations.yaml"]
