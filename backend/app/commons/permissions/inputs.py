"""Figure 3's `In` column, as data.

`In` is a **stricter** statement than the write permissions: a store a role may read is not
necessarily in its context on a given turn. The document puts it in one sentence -- *anything
not listed as an input is not available to the agent* -- and adds the rule that follows from
it: an agent that needs a fact absent from its inputs does not go and fetch it; the contract
is wrong and gets amended.

Writing it down as globs is what makes that checkable rather than aspirational (FR-AGENT-09).
The prompt assembler refuses a document whose source path falls outside the calling role's row
here, and the test that walks every recorded fake call is what proves no role ever received
one.

This is not the same thing as the write table. A role can read far more than it can write --
the writer reads canon and cannot touch it -- so the two tables are kept apart rather than
derived from each other.
"""

from __future__ import annotations

import re
from typing import Final

from app.commons.permissions.roles import AgentRole
from app.commons.permissions.table import SCENE_FILE, compile_store_glob, normalise

INPUT_TABLE: Final[dict[AgentRole, tuple[str, ...]]] = {
    AgentRole.ARCHITECT: (
        "canon/project.md",
        "canon/axioms/**",
        "canon/factions/**",
        "canon/history/**",
        "canon/locations/**",
        "cast/*/dossier.md",
        "ledger/setups.yaml",
        "ledger/threads.yaml",
    ),
    AgentRole.WORLD_BUILDER: (
        "canon/**",
        "structure/**",
    ),
    # The writer's row is `assemble_context(scene)` spelled out: the fixed block, the POV's
    # `cast/{id}/` as-of, the previous scene's tail, and whatever `select_entities` ranked
    # within the cap. `manuscript/NNN.md` is listed because the tail is cut from it -- and
    # only the tail: FR-OPS-03 forbids raw prose in the context by any other route, and that
    # restriction is the assembler's job, not this table's.
    AgentRole.WRITER: (
        "canon/**",
        "cast/**",
        "scenes/**",
        "structure/**",
        "ledger/setups.yaml",
        "ledger/violations.yaml",
        "manuscript/digests/**",
        f"manuscript/{SCENE_FILE}.md",
    ),
    AgentRole.STYLE_EDITOR: (
        f"manuscript/{SCENE_FILE}.md",
        "canon/style.md",
        "canon/lexicon.yaml",
        "cast/*/voice.md",
    ),
    AgentRole.AUDITOR: (
        f"manuscript/{SCENE_FILE}.md",
        f"scenes/{SCENE_FILE}.yaml",
        "canon/axioms/**",
        "canon/time.yaml",
        "canon/lexicon.yaml",
        "cast/*/dossier.md",
        "cast/*/knowledge.yaml",
        "cast/*/changes.yaml",
        "cast/relationships.yaml",
        "ledger/timeline.yaml",
    ),
    AgentRole.CANONISER: (
        "ledger/proposed.yaml",
        f"manuscript/{SCENE_FILE}.md",
        "canon/**",
    ),
}
"""FR-AGENT-09, transcribed from Figure 3's `In` column.

The style editor's row is the one worth reading twice: `manuscript/NNN.md`, `canon/style.md`,
`canon/lexicon.yaml` and the POV's `voice.md`, and nothing else. It polishes a scene without
ever seeing the axioms or the ledger, which is why a voice decision taken there cannot become
a rule about the world.
"""

_COMPILED: Final[dict[AgentRole, tuple[re.Pattern[str], ...]]] = {
    role: tuple(compile_store_glob(pattern) for pattern in patterns)
    for role, patterns in INPUT_TABLE.items()
}


def may_receive(role: AgentRole, path: str) -> bool:
    """True when a document read from `path` may be placed in this role's prompt.

    The auditor's selected-entity list is not a path and so is not checked here: it is handed
    over by the orchestrator from the turn record (FR-OPS-05), which is the point -- writer
    and auditor of one turn see the same list because it is recorded, not re-derived.
    """
    try:
        target = normalise(path)
    except ValueError:
        return False
    return any(pattern.match(target) for pattern in _COMPILED[role])


def readable_patterns(role: AgentRole) -> tuple[str, ...]:
    """FR-PERM-04. The `In` half of what `/permissions` exports."""
    return INPUT_TABLE[role]


__all__ = ["INPUT_TABLE", "may_receive", "readable_patterns"]
