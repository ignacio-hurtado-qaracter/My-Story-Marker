"""AC 2 — six roles against every store family, and exactly Figure 3's outcomes.

The expected grid below is written out by hand from the table in
`docs/architecture.md#figure-3--agents-and-write-permissions`. That is the point: deriving it
from `WRITE_TABLE` would make the test agree with the implementation rather than with the
document, and the whole value of this test is that it disagrees when someone edits the table.

Read the `False` cells, not the `True` ones. `canon/` having exactly two inbound write edges,
the writer having none, and the auditor reaching nothing but `ledger/violations.yaml` are the
properties that stop prose from rewriting the world to justify itself.
"""

from __future__ import annotations

import pytest

from app.commons.permissions.roles import GIFT_NOVEL_ROLES, AgentRole
from app.commons.permissions.table import WRITE_TABLE, may_write, normalise

# One representative path per store family, plus the two paths inside `manuscript/` and
# `ledger/` that Figure 3 treats differently from their family.
PATHS = {
    "canon": "canon/axioms/fold-drive.md",
    "canon_lexicon": "canon/lexicon.yaml",
    "cast": "cast/mara/knowledge.yaml",
    "structure": "structure/chapters.yaml",
    "scenes": "scenes/014.yaml",
    "manuscript_draft": "manuscript/014.md",
    "manuscript_digest": "manuscript/digests/014.md",
    "ledger_proposed": "ledger/proposed.yaml",
    "ledger_violations": "ledger/violations.yaml",
    "ledger_setups": "ledger/setups.yaml",
}

# Figure 3, transcribed. Rows are roles, columns are the keys of PATHS.
EXPECTED: dict[AgentRole, dict[str, bool]] = {
    AgentRole.ARCHITECT: {
        "canon": False,
        "canon_lexicon": False,
        "cast": False,
        "structure": True,
        "scenes": True,
        "manuscript_draft": False,
        "manuscript_digest": False,
        "ledger_proposed": False,
        "ledger_violations": False,
        "ledger_setups": False,
    },
    AgentRole.WORLD_BUILDER: {
        "canon": True,
        "canon_lexicon": True,
        "cast": False,
        "structure": False,
        "scenes": False,
        "manuscript_draft": False,
        "manuscript_digest": False,
        "ledger_proposed": False,
        "ledger_violations": False,
        "ledger_setups": False,
    },
    AgentRole.WRITER: {
        "canon": False,
        "canon_lexicon": False,
        "cast": False,
        "structure": False,
        "scenes": False,
        "manuscript_draft": True,
        "manuscript_digest": True,
        "ledger_proposed": True,
        "ledger_violations": False,
        "ledger_setups": False,
    },
    AgentRole.STYLE_EDITOR: {
        "canon": False,
        "canon_lexicon": False,
        "cast": False,
        "structure": False,
        "scenes": False,
        "manuscript_draft": True,
        "manuscript_digest": False,
        "ledger_proposed": False,
        "ledger_violations": False,
        "ledger_setups": False,
    },
    AgentRole.AUDITOR: {
        "canon": False,
        "canon_lexicon": False,
        "cast": False,
        "structure": False,
        "scenes": False,
        "manuscript_draft": False,
        "manuscript_digest": False,
        "ledger_proposed": False,
        "ledger_violations": True,
        "ledger_setups": False,
    },
    AgentRole.CANONISER: {
        "canon": True,
        "canon_lexicon": True,
        "cast": True,
        "structure": False,
        "scenes": False,
        "manuscript_draft": False,
        "manuscript_digest": False,
        "ledger_proposed": True,
        "ledger_violations": False,
        "ledger_setups": False,
    },
}

GRID = [(role, key, allowed) for role, row in EXPECTED.items() for key, allowed in row.items()]


# spec 001 / AC 2
@pytest.mark.parametrize(
    ("role", "key", "allowed"), GRID, ids=[f"{r.value}-{k}" for r, k, _ in GRID]
)
def test_write_table_matches_figure_3(role: AgentRole, key: str, allowed: bool) -> None:
    assert may_write(role, PATHS[key]) is allowed


# spec 001 / AC 2 — the two properties the document calls the anti-drift mechanism.
def test_canon_has_exactly_two_inbound_write_edges() -> None:
    writers = {role for role in AgentRole if may_write(role, "canon/axioms/fold-drive.md")}
    assert writers == {AgentRole.WORLD_BUILDER, AgentRole.CANONISER}


# spec 001 / AC 2
def test_the_writer_cannot_write_canon_by_any_path() -> None:
    for path in (
        "canon/project.md",
        "canon/style.md",
        "canon/lexicon.yaml",
        "canon/time.yaml",
        "canon/axioms/fold-drive.md",
        "canon/locations/hab-ring.md",
        "cast/mara/dossier.md",
    ):
        assert may_write(AgentRole.WRITER, path) is False


# spec 001 / AC 2
def test_the_auditor_reports_and_does_not_repair() -> None:
    allowed = {
        path
        for path in [*PATHS.values(), "canon/project.md", "cast/mara/dossier.md"]
        if may_write(AgentRole.AUDITOR, path)
    }
    assert allowed == {"ledger/violations.yaml"}


# spec 001 / AC 2 — FR-PERM-05: no configuration widens the table.
def test_every_role_has_a_row_and_no_role_has_an_empty_one() -> None:
    assert set(WRITE_TABLE) == set(AgentRole)
    # spec 005: the gift-novel roles write the authoritative database only, never a file.
    assert all(
        bool(patterns) is (role not in GIFT_NOVEL_ROLES) for role, patterns in WRITE_TABLE.items()
    )


# spec 001 / AC 2 — FR-STORE-05: a path that could leave the root is refused before matching.
@pytest.mark.parametrize(
    "escape",
    [
        "../secrets.yaml",
        "canon/../../etc/passwd",
        "/etc/passwd",
        "C:/Windows/system32",
        "",
        "   ",
        "canon/./../../x",
    ],
    ids=repr,
)
def test_paths_that_escape_the_root_are_refused_for_every_role(escape: str) -> None:
    for role in AgentRole:
        assert may_write(role, escape) is False


# spec 001 / AC 2 — `.index/` is not a store and does not become one by being asked about.
@pytest.mark.parametrize(
    "path", [".index/index.sqlite", ".index/turns/014-1.yaml", ".index/provenance.jsonl"]
)
def test_the_index_is_not_writable_by_any_role(path: str) -> None:
    for role in AgentRole:
        assert may_write(role, path) is False


# spec 001 / AC 2 — Windows separators normalise; the table is written in POSIX.
def test_windows_separators_are_normalised() -> None:
    assert normalise("manuscript\\digests\\014.md") == "manuscript/digests/014.md"
    assert may_write(AgentRole.WRITER, "manuscript\\digests\\014.md") is True


# spec 001 / AC 2 — `NNN` means three digits, not any name.
@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("manuscript/014.md", True),
        ("manuscript/14.md", False),
        ("manuscript/0014.md", False),
        ("manuscript/notes.md", False),
        ("manuscript/014.txt", False),
    ],
)
def test_scene_file_names_are_three_digits(path: str, allowed: bool) -> None:
    assert may_write(AgentRole.WRITER, path) is allowed
