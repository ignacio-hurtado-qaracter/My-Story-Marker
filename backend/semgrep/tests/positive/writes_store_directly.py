"""Planted positives for AC 3. Every call below must be reported.

This file is never imported and never runs. It exists so the rule can be shown to fire, and
so that a rule that was accidentally narrowed to nothing fails loudly rather than passing
silently on a clean tree.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def bypass_the_store_layer(root: Path) -> None:
    (root / "canon" / "axioms" / "fold-drive.md").write_text("statement: anything goes\n")
    (root / "manuscript" / "014.md").read_text()
    with open(root / "ledger" / "violations.yaml", "w") as handle:
        handle.write("violations: []\n")
    os.remove(root / "scenes" / "014.yaml")
    shutil.copy(root / "canon" / "style.md", root / "canon" / "style.bak.md")
    (root / "cast" / "mara" / "knowledge.yaml").unlink()
