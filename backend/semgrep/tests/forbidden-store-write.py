# mirror-scope: app/canon/service.py
"""Fixture for AC 3, the two rules of `forbidden-store-write.yaml`, read by `semgrep --test`
and by the AST mirror alike (`tests/test_boundaries_mirror.py`).

Every line after a "ruleid" annotation must be reported, and no line after an "ok"
annotation may be (semgrep's test format). The mirror evaluates this file as if it were the
module named on the first line: both rules are scoped to `app/`, with the store layer exempt.

This file is never imported and never runs. It exists so the rules can be shown to fire, and
so that a rule accidentally narrowed to nothing fails loudly instead of passing on a clean
tree; the silent lines matter as much, because a rule that flags the correct way of writing
a store file teaches people to suppress it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def bypass_the_store_layer(root: Path, store, record, role) -> None:
    # ruleid: forbidden-store-write
    (root / "canon" / "axioms" / "fold-drive.md").write_text("statement: anything goes\n")
    # ruleid: forbidden-store-write
    (root / "manuscript" / "014.md").write_bytes(b"")
    # ruleid: forbidden-store-write
    (root / "manuscript" / "014.md").read_text()
    # ruleid: forbidden-store-write
    (root / "manuscript" / "014.md").read_bytes()
    # ruleid: forbidden-store-write
    with open(root / "ledger" / "violations.yaml", "w") as handle:
        handle.flush()
    # ruleid: forbidden-store-write
    with (root / "ledger" / "violations.yaml").open("w") as handle:
        handle.flush()
    # ruleid: forbidden-store-write
    with (root / "ledger" / "violations.yaml").open() as handle:
        handle.flush()
    # ruleid: forbidden-store-write
    (root / "cast" / "mara" / "knowledge.yaml").unlink()
    # ruleid: forbidden-store-write
    (root / "scenes" / "014.yaml").rename(root / "scenes" / "015.yaml")
    # ruleid: forbidden-store-write
    (root / "scenes" / "014.yaml").replace(root / "scenes" / "015.yaml")
    # ruleid: forbidden-store-write
    (root / "canon" / "axioms").mkdir()
    # ruleid: forbidden-store-write
    (root / "canon" / "axioms").rmdir()
    # ruleid: forbidden-store-write
    (root / "canon" / "style.md").touch()
    # ruleid: forbidden-store-write
    os.remove(root / "scenes" / "014.yaml")
    # ruleid: forbidden-store-write
    os.unlink(root / "scenes" / "014.yaml")
    # ruleid: forbidden-store-write
    os.rename(root / "a", root / "b")
    # ruleid: forbidden-store-write
    os.replace(root / "a", root / "b")
    # ruleid: forbidden-store-write
    os.makedirs(root / "canon")
    # ruleid: forbidden-store-write
    os.rmdir(root / "canon")
    # ruleid: forbidden-store-write
    shutil.copy(root / "canon" / "style.md", root / "canon" / "style.bak.md")
    # ruleid: forbidden-store-write
    shutil.copy2(root / "a", root / "b")
    # ruleid: forbidden-store-write
    shutil.copyfile(root / "a", root / "b")
    # ruleid: forbidden-store-write
    shutil.copytree(root / "a", root / "b")
    # ruleid: forbidden-store-write
    shutil.move(root / "a", root / "b")
    # ruleid: forbidden-store-write
    shutil.rmtree(root / "canon")

    # The store layer is the right way, and `str.replace` takes two arguments where
    # `Path.replace` takes one: the arity is what tells them apart.
    # ok: forbidden-store-write
    store.write("manuscript/014.md", record, role=role)
    # ok: forbidden-store-write
    store.read("scenes/014.yaml", object)
    # ok: forbidden-store-write
    "canon\\axioms".replace("\\", "/")


def build_paths_by_hand(character: str, scene: str, kind: str) -> list[str]:
    return [
        # ruleid: store-path-built-by-hand
        f"cast/{character}/voice.md",
        # ruleid: store-path-built-by-hand
        f'manuscript/{scene}.md',
        # ruleid: store-path-built-by-hand
        "scenes/%s.yaml" % scene,
        # ruleid: store-path-built-by-hand
        'canon/%s' % kind,
        # ruleid: store-path-built-by-hand
        "ledger/" + kind,
        # A fixed store path is a constant, not a path built from an identifier.
        # ok: store-path-built-by-hand
        "ledger/violations.yaml",
        # Not a store family.
        # ok: store-path-built-by-hand
        f"notes/{scene}.txt",
    ]
