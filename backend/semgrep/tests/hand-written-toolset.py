# mirror-scope: app/agents/roles.py
"""Fixture for AC 17, `hand-written-toolset`, read by `semgrep --test` and by the AST mirror
alike (`tests/test_boundaries_mirror.py`).

Every line after a "ruleid" annotation must be reported, and no line after an "ok"
annotation may be (semgrep's test format). The mirror evaluates this file as if it were the
module named on the first line, because the rule is scoped to `app/agents/`.

FR-PERM-06 derives each role's tools from the write table by code precisely so a list like
the ones below cannot drift away from Figure 3. This file is never imported and never runs.
"""

from __future__ import annotations

# ruleid: hand-written-toolset
WRITER_TOOLS = [
    "manuscript/014.md",
    "manuscript/digests/014.md",
    "ledger/proposed.yaml",
    "canon/axioms/fold-drive.md",
]

# ruleid: hand-written-toolset
AUDITOR_TOOLS = ("ledger/violations.yaml", "ledger/proposed.yaml")

# ruleid: hand-written-toolset
CANONISER_TOOLS = {"canon/axioms/fold-drive.md", "cast/mara/knowledge.yaml"}

# One path is a path, not a tool set.
# ok: hand-written-toolset
ONE_PATH = ["ledger/violations.yaml"]

# Words that are not store paths.
# ok: hand-written-toolset
ROLES = ["writer", "auditor"]
