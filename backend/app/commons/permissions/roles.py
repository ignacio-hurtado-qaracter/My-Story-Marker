"""The six agent roles, and nothing else.

FR-PERM-01. A closed enum, because "roles are separations of permission" and a role that can
be invented at runtime is not a separation of anything.

There is deliberately **no `human` member**. A human acts *under* a role and the provenance
log records `actor: human` beside it (spec Decision 5, FR-STORE-04). Adding a human row to
Figure 3 would create a seventh set of permissions that the table does not describe, which is
how "the human can just fix it" becomes a write path nobody audits.
"""

from __future__ import annotations

from enum import StrEnum

from app.commons.config import ROLE_NAMES


class AgentRole(StrEnum):
    """FR-PERM-01, transcribed from Figure 3 and in its order."""

    ARCHITECT = "architect"
    WORLD_BUILDER = "world_builder"
    WRITER = "writer"
    STYLE_EDITOR = "style_editor"
    AUDITOR = "auditor"
    CANONISER = "canoniser"


class Actor(StrEnum):
    """IF-02, Decision R2-7. Who is behind a write performed under a role.

    Absent means `agent`; the orchestrator always sends `agent` and never claims to be a
    human, which is what makes the human gate on collisions (FR-OPS-07) mean anything.
    """

    AGENT = "agent"
    HUMAN = "human"


# `commons.config` sits below `commons.permissions` in the import contract, so it cannot
# import this enum to type its per-role settings. It carries the names as plain strings
# instead, and this assertion is what stops the two lists drifting apart unnoticed.
if tuple(role.value for role in AgentRole) != ROLE_NAMES:  # pragma: no cover - import-time
    message = (
        f"AgentRole {[r.value for r in AgentRole]} and config.ROLE_NAMES {list(ROLE_NAMES)} "
        "disagree; one of them was edited without the other"
    )
    raise RuntimeError(message)


__all__ = ["Actor", "AgentRole"]
