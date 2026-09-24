"""The dependencies every feature router shares.

Three of them, and each exists because the alternative is a rule that holds only while
everyone remembers it:

* **`StoreDep`** builds the one `Store` a request may use, from settings. A router that
  constructed its own would be a router that could point at another directory.
* **`RoleDep`** turns `X-Agent-Role` into an `AgentRole` or a 400 (IF-02). There is no
  default. Guessing a role would mean the provenance log recorded a guess (FR-STORE-04), and
  a log that records guesses is not evidence.
* **`ActorDep`** turns `X-Actor` into `agent` or `human` (Decision R2-7). Absent means
  `agent`, and the orchestrator always sends `agent` explicitly: a human ruling (FR-OPS-07),
  the one path that can overwrite canon, means nothing if a process can claim to be a person.

A fourth, **`EmbedderDep`**, gives the index routes the embedder. It is a dependency rather
than a construction inside the route so the offline suite can override it with
`FakeEmbedder` and never load a model or reach the network (NFR-06, NFR-09).

Two more are the model's, and both exist so no route builds its own door to a model:

* **`ModelClientDep`** gives a route the model client (FR-LLM-02), `ClaudeCodeModelClient`
  from settings. The offline suite overrides it with `FakeModelClient`, so no test can reach
  the CLI however a route is called (NFR-06, NFR-09).
* **`SemanticAuditorDep`** gives the audit route the model-backed half of the audit
  (FR-AUD-09, FR-AGENT-06) -- or `None`. The route lives in `scenes`, the auditor role in
  `agents`, and NFR-04's layers put `agents` above `scenes`: the route may not import the
  role. So the dependency is inverted here. `SemanticAuditor` is a protocol over commons types
  only (a `Store`, a scene id and the mechanical findings in; model findings and the
  accounting out), `get_semantic_auditor` answers `None`, and the app factory substitutes the
  one `app.agents.service` provides. Nothing wired means the semantic halves are listed as
  skipped, exactly as they were before any auditor existed.

These are FastAPI dependencies, so they live in `commons/` beside the things they wire, and
they know no feature's name (NFR-04).
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Protocol

from fastapi import Depends, Header

from app.commons.config import Settings, get_settings
from app.commons.embeddings import Embedder, FastEmbedEmbedder
from app.commons.errors import InvalidRole
from app.commons.llm import ClaudeCodeModelClient, ModelClient
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Violation
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

_EmbedderKey = tuple[str, str, str, bool]
_EMBEDDERS: dict[_EmbedderKey, Embedder] = {}
_EMBEDDERS_LOCK = threading.Lock()


def get_embedder(settings: SettingsDep) -> Embedder:
    """FR-EMB-02, -03. The production embedder, built once per configuration.

    Cached because loading the ONNX model costs seconds and a rebuild should not pay it on
    every request; keyed on the settings that choose the model, so a test that moves
    `EMBED_MODEL` gets a different embedder rather than a stale one. The lock keeps two
    concurrent first requests from loading the model twice. Tests override this dependency
    with `FakeEmbedder`.
    """
    key: _EmbedderKey = (
        settings.embed_model,
        settings.embed_fallback_model,
        str(settings.model_cache_dir),
        settings.embed_offline,
    )
    with _EMBEDDERS_LOCK:
        embedder = _EMBEDDERS.get(key)
        if embedder is None:
            embedder = FastEmbedEmbedder(settings)
            _EMBEDDERS[key] = embedder
    return embedder


EmbedderDep = Annotated[Embedder, Depends(get_embedder)]


def get_model_client(settings: SettingsDep) -> ModelClient:
    """FR-LLM-02. The live model client: every role call one `claude -p` subprocess under the
    user's Claude Code login (decision R3-1).

    Built per request. Construction touches nothing -- the executable and its version are
    resolved on the first call that passes the cap -- so a request that never calls the model
    never spawns a process. The offline suite overrides this dependency with `FakeModelClient`.
    """
    return ClaudeCodeModelClient(settings)


ModelClientDep = Annotated[ModelClient, Depends(get_model_client)]


@dataclass(frozen=True, slots=True)
class SemanticSkip:
    """One model-backed check, or one input of it, that did not run (FR-AUD-09, FR-CTX-04).

    `invariant` is the invariant whose judgement the absence weakens; `reason` says what was
    missing -- the model step that failed, or the input the cap pruned -- so the absence of a
    finding is never read as a pass on something that was never checked.
    """

    invariant: int
    reason: str


@dataclass(frozen=True, slots=True)
class SemanticFindings:
    """What the model-backed half of an audit answers, in commons types only.

    `violations` are DR-07 records with `source: model`. `checked` names the invariants the
    model step judged -- empty when it did not run -- and `skipped` what it could not judge,
    whole invariants or pruned inputs. The report is assembled from the three by the ledger's
    audit package, which owns its shape.
    """

    violations: tuple[Violation, ...]
    checked: tuple[int, ...]
    skipped: tuple[SemanticSkip, ...]


class SemanticAuditor(Protocol):
    """FR-AGENT-06, FR-AGENT-07. The model-backed half of `audit(scene)`, callable by the audit
    route without importing the role that implements it.

    `mechanical` holds the mechanical half's findings, computed first: they go into the model's
    prompt as data, so the model does not report them again. A model step that fails is not an
    exception here but an answer -- every semantic invariant in `skipped`, with the reason
    (FR-AUD-09) -- because the mechanical half has already run and must still be reported.
    """

    def __call__(
        self, store: Store, scene_id: str, mechanical: Sequence[Violation], /
    ) -> SemanticFindings:
        """Judge the scene's draft for the semantic invariants and account for what ran."""
        ...


def get_semantic_auditor() -> SemanticAuditor | None:
    """None: no model-backed auditor in this process. `main.py` substitutes the one
    `app.agents.service` provides -- a dependency override, which is exactly what an override
    is: another provider of the same dependency -- so a bare app still serves the mechanical
    audit and reports the semantic halves as skipped."""
    return None


SemanticAuditorDep = Annotated[SemanticAuditor | None, Depends(get_semantic_auditor)]

__all__ = [
    "ActorDep",
    "EmbedderDep",
    "ModelClientDep",
    "RoleDep",
    "SemanticAuditor",
    "SemanticAuditorDep",
    "SemanticFindings",
    "SemanticSkip",
    "SettingsDep",
    "StoreDep",
    "get_embedder",
    "get_model_client",
    "get_semantic_auditor",
    "get_store",
    "request_actor",
    "require_role",
]
