"""The model-invoked roles' system prompts, and the one way a role is handed documents.

Two rules meet here, and this package is where each becomes code rather than a sentence:

* **FR-AGENT-10, plan P10.** A role's system prompt is `agents/prompts/<role>.md`, versioned in
  git, loaded once at import, with a `prompt_version` that is the SHA-256 of its content, for
  the turn record. The hash is taken after line endings are normalised to `\\n`: a git checkout
  on Windows may turn them into `\\r\\n`, and the same commit must name the same prompt on every
  machine -- and send the model the same bytes.
* **FR-PERM-07, FR-AGENT-09.** Nothing read from a store ever reaches the system field. The
  system prompt is the prompt file and nothing else (`system_prompt`); the client appends its
  own fixed data statement (`commons.llm.render_system`, correction C12), which is not store
  content either. Everything read from the stores goes in as a `Document`, labelled with its
  path, and only through `documents_for`, which refuses a path outside the role's `In` row of
  Figure 3 (`INPUT_TABLE`) -- "anything not listed as an input is not available to the agent".

**Why `pkgutil.get_data`.** The prompt files are package data, not a store: no role writes
them, Figure 3 does not govern them, and they live beside the code that uses them rather than
under the store root. They are read through the package's loader, which resolves the name
against `app.agents` and never against the store root, so no identifier can steer it into the
tree, and which also works when the package is installed from a wheel. The file primitives
the boundary rule of AC 3 forbids outside `commons/stores/` (`open`, `read_text`) are exactly
what a store read must not bypass; this read has no store to bypass.

The writes performed with a role's output are the other half of the contract, and live in
`commons.permissions.toolset_for`, derived from the write table (FR-PERM-06).
"""

from __future__ import annotations

import hashlib
import pkgutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from app.commons.errors import PermissionDenied
from app.commons.llm import Document
from app.commons.permissions import AgentRole, may_receive, normalise

MODEL_ROLES: Final[tuple[AgentRole, ...]] = (
    AgentRole.WRITER,
    AgentRole.STYLE_EDITOR,
    AgentRole.AUDITOR,
    AgentRole.CANONISER,
)
"""The roles v1 invokes a model under (FR-AGENT-01..08), one prompt file each. The architect
and the world builder act through their routes with a human behind them (spec Decision 5), so
they have no prompt, and asking for one is a programming error."""

PROMPT_PACKAGE: Final[str] = "app.agents"
"""The package the prompt files belong to; `pkgutil` resolves resource names against it."""


@dataclass(frozen=True, slots=True)
class RolePrompt:
    """One role's system prompt as loaded, and the version the turn record names it by."""

    role: AgentRole
    text: str
    version: str
    """SHA-256, in hex, of `text` encoded as UTF-8 (FR-AGENT-10)."""


def prompt_resource(role: AgentRole) -> str:
    """The prompt file's name inside `PROMPT_PACKAGE`: `prompts/<role>.md` (FR-AGENT-10)."""
    return f"prompts/{role.value}.md"


def read_prompt_file(role: AgentRole) -> bytes:
    """The prompt file's bytes, through the package loader. The one input of `load_prompts`."""
    data = pkgutil.get_data(PROMPT_PACKAGE, prompt_resource(role))
    if data is None:  # pragma: no cover - only a loader without `get_data` returns None
        message = f"the package loader of {PROMPT_PACKAGE} cannot read {prompt_resource(role)}"
        raise RuntimeError(message)
    return data


def prompt_from_bytes(role: AgentRole, data: bytes) -> RolePrompt:
    """Decode, normalise line endings and hash. An empty prompt is refused: a role call with
    no role prompt is a call nobody wrote the brief for."""
    text = data.decode("utf-8").replace("\r\n", "\n")
    if not text.strip():
        message = f"the {role.value} prompt, {prompt_resource(role)}, is empty"
        raise ValueError(message)
    version = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return RolePrompt(role=role, text=text, version=version)


def load_prompts() -> Mapping[AgentRole, RolePrompt]:
    """Every model-invoked role's prompt, read from its file. Run once, at import (P10)."""
    return {role: prompt_from_bytes(role, read_prompt_file(role)) for role in MODEL_ROLES}


PROMPTS: Final[Mapping[AgentRole, RolePrompt]] = load_prompts()
"""Loaded at import, so a missing or empty prompt file stops the backend from starting rather
than failing the first turn that needs it, and every call of a process runs the same version."""


def role_prompt(role: AgentRole) -> RolePrompt:
    """The loaded prompt of a model-invoked role, or `ValueError` for the two that have none."""
    prompt = PROMPTS.get(role)
    if prompt is None:
        message = (
            f"the {role.value} role is not model-invoked in v1 and has no system prompt "
            "(spec Decision 5)"
        )
        raise ValueError(message)
    return prompt


def system_prompt(role: AgentRole) -> str:
    """FR-PERM-07. What a role call passes as `system`: the prompt file, and nothing else.

    It takes no argument that could carry store content, so no document can reach the system
    field through it. The client appends the fixed data statement when it writes the prompt
    file (`render_system`).
    """
    return role_prompt(role).text


def prompt_version(role: AgentRole) -> str:
    """FR-AGENT-10. The version recorded per turn for the role's call."""
    return role_prompt(role).version


def documents_for(role: AgentRole, sources: Iterable[tuple[str, str]]) -> tuple[Document, ...]:
    """FR-AGENT-09, FR-PERM-07. Store texts, as `(store path, text)` pairs, turned into the
    documents a `role` call carries, each labelled with its normalised path.

    A path outside the role's `INPUT_TABLE` row raises `PermissionDenied`, and nothing is
    returned: the whole assembly is refused, not the one document, because a call missing a
    document it was built around is a different call from the one that was planned. It is
    the error the store layer raises when Figure 3 refuses a write, for the same kind of
    reason -- the table's `In` column says no -- and IF-07 lists every error the API returns,
    which a new type would not be. The refusal is always an orchestrator bug, never a caller's
    mistake: roles receive what the orchestrator hands them and ask for nothing.

    The turn's selected-entity list is not a store file: it is identifiers from the turn
    record, has no path to be checked against, and belongs in the instruction. The mechanical
    findings handed to the auditor are not a store file either, but they quote the prose, and
    FR-AGENT-07 puts them in the prompt *as data* -- never in the instruction, which the data
    statement gives instruction authority. How they are labelled, given that no row of the
    auditor's `In` column holds them, is left to the role functions (plan step 17).
    """
    documents: list[Document] = []
    for path, text in sources:
        if not may_receive(role, path):
            message = (
                f"Figure 3's In column does not list {path} for the {role.value} role, so it "
                "may not be placed in that role's prompt (FR-AGENT-09)"
            )
            raise PermissionDenied(message, role=role.value, path=path)
        documents.append(Document(path=normalise(path), text=text))
    return tuple(documents)


__all__ = [
    "MODEL_ROLES",
    "PROMPTS",
    "PROMPT_PACKAGE",
    "RolePrompt",
    "documents_for",
    "load_prompts",
    "prompt_from_bytes",
    "prompt_resource",
    "prompt_version",
    "read_prompt_file",
    "role_prompt",
    "system_prompt",
]
