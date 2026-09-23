"""AC 17 -- every role's tool set, enumerated, against Figure 3 and against the write table.

Two kinds of expectation, kept apart on purpose. The three properties AC 17 names -- the writer
holds nothing that reaches `canon/`, the auditor holds `ledger/violations.yaml` and nothing
else, the canoniser holds nothing under `manuscript/` -- and the writer's row as FR-PERM-06
spells it are written out by hand from the spec, so the test disagrees with the code when
someone edits the table. The derivation itself is then checked against `WRITE_TABLE` in both
directions and against `may_write` over a spread of paths, because the point of deriving the
tool sets (FR-PERM-06) is that the two cannot diverge, and "cannot" has to be shown.
"""

from __future__ import annotations

import pytest

from app.commons.errors import PermissionDenied
from app.commons.permissions import (
    WRITE_TABLE,
    AgentRole,
    Tool,
    ToolOperation,
    may_write,
    toolset_for,
)

CANON_PROBES = (
    "canon/project.md",
    "canon/style.md",
    "canon/lexicon.yaml",
    "canon/time.yaml",
    "canon/axioms/ax_brine_dark.md",
    "canon/locations/kestrel_deep.md",
)
MANUSCRIPT_PROBES = (
    "manuscript/002.md",
    "manuscript/digests/002.md",
    "manuscript/digests/901.md",
)
PROBES = (
    *CANON_PROBES,
    *MANUSCRIPT_PROBES,
    "cast/ilan/dossier.md",
    "cast/ilan/knowledge.yaml",
    "cast/relationships.yaml",
    "structure/arcs.yaml",
    "structure/chapters.yaml",
    "scenes/004.yaml",
    "ledger/proposed.yaml",
    "ledger/violations.yaml",
    "ledger/setups.yaml",
    "ledger/threads.yaml",
    "ledger/timeline.yaml",
    # Shapes that must reach nothing, whatever the role.
    "manuscript/2.md",
    "manuscript/digests/sub/002.md",
    "canon/../manuscript/002.md",
    "../canon/project.md",
    "/canon/project.md",
    "C:/story/canon/project.md",
    ".index/turns/004-1.yaml",
    "CLAUDE.md",
)


def _tools(role: AgentRole) -> tuple[Tool, ...]:
    return toolset_for(role).tools


# spec 001 / AC 17
def test_the_writer_holds_no_tool_that_reaches_canon() -> None:
    tools = _tools(AgentRole.WRITER)
    assert tools, "the writer must hold its manuscript and proposal tools"
    for tool in tools:
        assert tool.target.split("/")[0] != "canon", tool
        assert not any(tool.matches(path) for path in CANON_PROBES), tool


# spec 001 / AC 17
def test_the_auditor_holds_only_the_violation_report() -> None:
    assert toolset_for(AgentRole.AUDITOR).targets == ("ledger/violations.yaml",)
    reachable = [path for path in PROBES if toolset_for(AgentRole.AUDITOR).covers(path)]
    assert reachable == ["ledger/violations.yaml"]


# spec 001 / AC 17
def test_the_canoniser_holds_nothing_under_manuscript() -> None:
    tools = _tools(AgentRole.CANONISER)
    assert tools
    for tool in tools:
        assert tool.target.split("/")[0] != "manuscript", tool
        assert not any(tool.matches(path) for path in MANUSCRIPT_PROBES), tool


# spec 001 / AC 17 (FR-PERM-06, transcribed from the spec rather than derived)
def test_the_writer_row_is_the_one_fr_perm_06_describes() -> None:
    described = {
        ("manuscript/[0-9][0-9][0-9].md", ToolOperation.WRITE),
        ("manuscript/digests/[0-9][0-9][0-9].md", ToolOperation.WRITE),
        ("ledger/proposed.yaml", ToolOperation.APPEND),
    }
    assert {(tool.target, tool.operation) for tool in _tools(AgentRole.WRITER)} == described


# spec 001 / AC 17
def test_every_tool_is_exactly_a_write_table_entry_and_every_entry_a_tool() -> None:
    derived = [(role, tool.target) for role in AgentRole for tool in _tools(role)]
    table = [(role, pattern) for role in AgentRole for pattern in WRITE_TABLE[role]]
    assert derived == table
    assert all(tool.role is role for role in AgentRole for tool in _tools(role))


# spec 001 / AC 17
@pytest.mark.parametrize("role", list(AgentRole), ids=[role.value for role in AgentRole])
def test_a_tool_set_reaches_exactly_what_may_write_allows(role: AgentRole) -> None:
    toolset = toolset_for(role)
    disagreements = [path for path in PROBES if toolset.covers(path) != may_write(role, path)]
    assert disagreements == []


# spec 001 / AC 17
def test_only_the_canonisation_queue_is_append_only() -> None:
    appended = {
        (role, tool.target)
        for role in AgentRole
        for tool in _tools(role)
        if tool.operation is ToolOperation.APPEND
    }
    assert appended == {
        (AgentRole.WRITER, "ledger/proposed.yaml"),
        (AgentRole.CANONISER, "ledger/proposed.yaml"),
    }
    assert toolset_for(AgentRole.CANONISER).tool_for("ledger/proposed.yaml") == Tool(
        role=AgentRole.CANONISER, target="ledger/proposed.yaml", operation=ToolOperation.APPEND
    )


REFUSED = [
    (AgentRole.WRITER, "canon/axioms/ax_brine_dark.md"),
    (AgentRole.WRITER, "cast/ilan/knowledge.yaml"),
    (AgentRole.WRITER, "ledger/violations.yaml"),
    (AgentRole.STYLE_EDITOR, "manuscript/digests/002.md"),
    (AgentRole.STYLE_EDITOR, "ledger/proposed.yaml"),
    (AgentRole.AUDITOR, "manuscript/002.md"),
    (AgentRole.AUDITOR, "ledger/setups.yaml"),
    (AgentRole.CANONISER, "manuscript/002.md"),
    (AgentRole.CANONISER, "manuscript/digests/002.md"),
    (AgentRole.ARCHITECT, "canon/project.md"),
    (AgentRole.WORLD_BUILDER, "cast/ilan/dossier.md"),
    (AgentRole.WRITER, "../canon/project.md"),
    (AgentRole.CANONISER, ".index/provenance.jsonl"),
]


# spec 001 / AC 17
@pytest.mark.parametrize(
    ("role", "path"), REFUSED, ids=[f"{role.value}-{path}" for role, path in REFUSED]
)
def test_a_path_outside_the_tool_set_is_refused(role: AgentRole, path: str) -> None:
    with pytest.raises(PermissionDenied) as refused:
        toolset_for(role).authorise(path)
    assert refused.value.status_code == 403
    assert refused.value.context == {"role": role.value, "path": path}


# spec 001 / AC 17
def test_a_role_output_may_add_to_the_queue_but_never_replace_it() -> None:
    writer = toolset_for(AgentRole.WRITER)
    assert writer.authorise("ledger/proposed.yaml", ToolOperation.APPEND).target == (
        "ledger/proposed.yaml"
    )
    with pytest.raises(PermissionDenied) as refused:
        writer.authorise("ledger/proposed.yaml", ToolOperation.WRITE)
    assert refused.value.context == {"role": "writer", "path": "ledger/proposed.yaml"}


# spec 001 / AC 17
def test_a_path_inside_the_tool_set_is_authorised_with_its_tool() -> None:
    assert toolset_for(AgentRole.WRITER).authorise("manuscript/004.md").target == (
        "manuscript/[0-9][0-9][0-9].md"
    )
    assert toolset_for(AgentRole.STYLE_EDITOR).authorise("manuscript/004.md").operation == (
        ToolOperation.WRITE
    )
    assert toolset_for(AgentRole.AUDITOR).authorise("ledger/violations.yaml").operation == (
        ToolOperation.WRITE
    )
    assert toolset_for(AgentRole.CANONISER).authorise("cast/ilan/changes.yaml").target == (
        "cast/**"
    )
    # A write tool may also append: the canoniser's canon tool covers both.
    assert toolset_for(AgentRole.CANONISER).authorise(
        "canon/lexicon.yaml", ToolOperation.APPEND
    ).target == ("canon/**")


# spec 001 / AC 17 (FR-PERM-05: nothing widens a role at runtime)
def test_tool_sets_are_built_once_and_immutable() -> None:
    writer = toolset_for(AgentRole.WRITER)
    assert toolset_for(AgentRole.WRITER) is writer
    assert isinstance(writer.tools, tuple)
    widened = (*writer.tools, Tool(AgentRole.WRITER, "canon/**", ToolOperation.WRITE))
    with pytest.raises(AttributeError):
        setattr(writer, "tools", widened)  # noqa: B010 - mypy rejects the direct form
    assert not toolset_for(AgentRole.WRITER).covers("canon/project.md")
