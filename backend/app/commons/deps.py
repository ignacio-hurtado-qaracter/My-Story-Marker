"""The dependencies every feature router shares.

Three of them, and each exists because the alternative is a rule that holds only while
everyone remembers it:

* **`StoreDep`** builds the one `Store` a request may use, from settings. A router that
  constructed its own would be a router that could point at another directory.
* **`RoleDep`** turns `X-Agent-Role` into an `AgentRole` or a 400 (IF-02). There is no
  default. Guessing a role would mean the provenance log recorded a guess (FR-STORE-04), and
  a log that records guesses is not evidence.
* **`ActorDep`** turns `X-Actor` into `agent` or `human` (Decision R2-7). Absent means
  `agent`, and the orchestrator always sends `agent` explicitly: the human gate on collisions
  (FR-OPS-07) means nothing if a process can claim to be a person.

These are FastAPI dependencies, so they live in `commons/` beside the things they wire, and
they know no feature's name (NFR-04).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from app.commons.config import Settings, get_settings
from app.commons.errors import InvalidRole
from app.commons.permissions import Actor, AgentRole
from app.commons.stores import Store

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_store(settings: SettingsDep) -> Store:
    """FR-STORE-01. One store root per process, from configuration, never from the client."""
    return Store(root=settings.story_root, index_dir=settings.index_dir)


StoreDep = Annotated[Store, Depends(get_store)]


def require_role(
    x_agent_role: Annotated[
        str | None,
        Header(
            alias="X-Agent-Role",
            description="The Figure 3 role performing this write. Required on every write.",
        ),
    ] = None,
) -> AgentRole:
    """IF-02. Missing or unknown role is a 400, before anything else happens."""
    if x_agent_role is None:
        message = "X-Agent-Role is required on write routes (IF-02)"
        raise InvalidRole(message)
    try:
        return AgentRole(x_agent_role)
    except ValueError as error:
        known = ", ".join(role.value for role in AgentRole)
        message = f"{x_agent_role!r} is not an agent role; expected one of {known}"
        raise InvalidRole(message, supplied=x_agent_role) from error


RoleDep = Annotated[AgentRole, Depends(require_role)]


def request_actor(
    x_actor: Annotated[
        str | None,
        Header(
            alias="X-Actor",
            description=(
                "`human` when a person is acting under the role, absent or `agent` "
                "otherwise. A human acts under a role, never beside it."
            ),
        ),
    ] = None,
) -> Actor:
    """Decision R2-7. Absent means `agent`; an unknown value is a 400 rather than a shrug."""
    if x_actor is None:
        return Actor.AGENT
    try:
        return Actor(x_actor)
    except ValueError as error:
        known = ", ".join(actor.value for actor in Actor)
        message = f"{x_actor!r} is not an actor; expected one of {known}"
        raise InvalidRole(message, supplied=x_actor) from error


ActorDep = Annotated[Actor, Depends(request_actor)]

__all__ = [
    "ActorDep",
    "RoleDep",
    "SettingsDep",
    "StoreDep",
    "get_store",
    "request_actor",
    "require_role",
]
