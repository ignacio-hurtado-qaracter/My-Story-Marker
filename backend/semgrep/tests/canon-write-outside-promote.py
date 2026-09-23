# mirror-scope: app/ledger/service.py
"""Fixture for AC 13, `canon-write-outside-promote`, read by `semgrep --test` and by the AST
mirror alike (`tests/test_boundaries_mirror.py`).

Every line after a "ruleid" annotation must be reported, and no line after an "ok" annotation
may be (semgrep's test format). The mirror evaluates this file as if it were the module named on the first line,
because the rule is scoped to `app/ledger/` and `app/agents/`.

This file is never imported and never runs.
"""

from __future__ import annotations

from app.canon import service as canon_service
from app.cast import service as cast_service
from app.cast.service import save_knowledge
from app.commons.stores import paths

PROPOSED_PATH = paths.PROPOSED


def resolve_collision_quietly(store, record, role, target):
    # A literal canon path: the spelling the hand-built-path rule already forbids.
    # ruleid: canon-write-outside-promote
    store.write("canon/axioms/fold-drive.md", record, role=role)
    # The spelling the code rules require -- the one the old rule never saw.
    # ruleid: canon-write-outside-promote
    store.write(paths.canon_entity("axioms", "fold_drive"), record, role=role)
    # ruleid: canon-write-outside-promote
    store.write(paths.cast_file("mara", "knowledge"), record, role=role)
    # ruleid: canon-write-outside-promote
    store.write(paths.LEXICON, record, role=role)
    # ruleid: canon-write-outside-promote
    store.write_text(paths.RELATIONSHIPS, "relationships: []\n", role=role)
    # A path held in a variable cannot be shown not to be canon, so it is refused outside
    # promote() and rule(): this is how promote itself writes, and nowhere else may.
    # ruleid: canon-write-outside-promote
    store.write(target.path, record, role=role)
    # ruleid: canon-write-outside-promote
    store.write(path=target, record=record, role=role)


def settle_through_the_services(store, record, role, actor):
    # ruleid: canon-write-outside-promote
    canon_service.replace_entity(store, "axioms", "fold_drive", record, role=role, actor=actor)
    # ruleid: canon-write-outside-promote
    cast_service.save_dossier(store, "mara", record, role=role, actor=actor)
    # ruleid: canon-write-outside-promote
    save_knowledge(store, "mara", record, role=role, actor=actor)
    # Reading canon is not writing it.
    # ok: canon-write-outside-promote
    canon_service.entity(store, "axioms", "fold_drive", object)


def write_what_the_ledger_owns(store, record, role, scene):
    # ok: canon-write-outside-promote
    store.write(paths.PROPOSED, record, role=role)
    # ok: canon-write-outside-promote
    store.write(PROPOSED_PATH, record, role=role)
    # ok: canon-write-outside-promote
    store.write(paths.draft(scene), record, role=role)
    # ok: canon-write-outside-promote
    store.write("ledger/violations.yaml", record, role=role)


def promote(store, record, role, target):
    # The canoniser's return edge (FR-OPS-06): the one place a canon write belongs.
    # ok: canon-write-outside-promote
    store.write(target.path, record, role=role)
    # ok: canon-write-outside-promote
    canon_service.replace_entity(store, "axioms", "fold_drive", record, role=role, actor=role)


def rule(store, record, role, target):
    # The human gate (FR-OPS-07).
    # ok: canon-write-outside-promote
    store.write(paths.canon_entity("axioms", "fold_drive"), record, role=role)
