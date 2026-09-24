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

**One call path for every role** (`call_role`, plan step 17). The four role modules --
`writer`, `style_editor`, `canoniser`, `auditor` -- each gather their Figure 3 inputs through
the owning features' services and hand them here as `RoleInput`s, split into FR-CTX-03's
mandatory and prunable parts. `call_role` checks **every source path of every input** against
the role's `In` row (an entry that folds four cast files into a dossier is four paths, not
one), fits the inputs to the cap with `tokens.fit_to_budget` -- whole inputs, lowest rank
first, mandatory never -- and makes the call with the role's system prompt and DR-12 schema.
It returns what was sent and what was pruned, and it writes nothing: roles never write the
stores, and persisting an output is `app.agents.service`'s, under the role's tool set.
"""

from __future__ import annotations

import hashlib
import pkgutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel

from app.agents.models import RoleCall
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.errors import PermissionDenied
from app.commons.llm import Document, ModelClient
from app.commons.llm.tokens import Entry, fit_to_budget
from app.commons.permissions import AgentRole, may_receive, normalise
from app.scenes.models import ContextEntry

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

MECHANICAL_FINDINGS: Final[str] = "computed/mechanical-findings"
"""FR-AGENT-07. The label of the one document that is not read from a store: the mechanical
audit's findings, handed to the auditor so it does not report them again.

They quote the prose, so they are data and go in a delimited block like every store text,
never in the instruction (FR-PERM-07). The label is what makes that block *labelled* in AC 23's
sense: it says where the text came from -- computed by the mechanical checks of this call's
scene -- as a store path says it for a file. `computed/` is no store family, so the label can
never be mistaken for a path, `may_receive` refuses it for every role, and nothing could be
read from it. `documents_for` accepts it for exactly one role and one label
(`COMPUTED_DOCUMENTS`)."""

COMPUTED_DOCUMENTS: Final[Mapping[str, AgentRole]] = {MECHANICAL_FINDINGS: AgentRole.AUDITOR}
"""Every computed document, and the one role that may receive it. Figure 3's `In` column
cannot list these -- they are not artefacts -- so they are listed here, as narrowly as
possible: one label, one role."""


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
    statement gives instruction authority. They travel under `MECHANICAL_FINDINGS`, accepted
    for the auditor alone; for any other role, or under any other spelling, the label is
    refused like any path outside the row.
    """
    documents: list[Document] = []
    for path, text in sources:
        if COMPUTED_DOCUMENTS.get(path) is role:
            documents.append(Document(path=path, text=text))
            continue
        if not may_receive(role, path):
            message = (
                f"Figure 3's In column does not list {path} for the {role.value} role, so it "
                "may not be placed in that role's prompt (FR-AGENT-09)"
            )
            raise PermissionDenied(message, role=role.value, path=path)
        documents.append(Document(path=normalise(path), text=text))
    return tuple(documents)


@dataclass(frozen=True, slots=True)
class RoleInput:
    """One indivisible document of a role call: kept whole or pruned whole (FR-CTX-03).

    `key` names it in `removed` and `truncated_at` -- `kind:id` for an entity, the path for a
    file. `path` labels the block the model reads. `sources` lists every other store path whose
    content `text` carries, as an assembled dossier carries four cast files: each one is held
    against the role's `In` row, because a document is only as permitted as the least
    permitted file folded into it.
    """

    key: str
    path: str
    text: str
    sources: tuple[str, ...] = ()

    @classmethod
    def of(cls, entry: ContextEntry) -> RoleInput:
        """An entry of the assembled context (FR-OPS-03), with all of its sources."""
        return cls(key=entry.key, path=entry.path, text=entry.text, sources=tuple(entry.sources))

    @property
    def every_source(self) -> tuple[str, ...]:
        """`path` first, then every other source, each once."""
        return (self.path, *(source for source in self.sources if source != self.path))


def check_inputs(role: AgentRole, inputs: Iterable[RoleInput]) -> None:
    """FR-AGENT-09. Every source of every input inside the role's `In` row, or
    `PermissionDenied` naming the first that is not.

    Checked over the whole set handed in, pruned or not: an input from outside the row is an
    orchestration bug whether or not the budget would have dropped it, and a bug the budget
    happened to hide is still a bug.
    """
    for role_input in inputs:
        documents_for(role, [(source, role_input.text) for source in role_input.every_source])


def call_role[T: BaseModel](
    client: ModelClient,
    *,
    role: AgentRole,
    instruction: str,
    mandatory: Sequence[RoleInput],
    prunable: Sequence[RoleInput] = (),
    output_schema: type[T],
    cap: int = CONTEXT_TOKEN_CAP,
    ranked_after: Sequence[str] = (),
) -> RoleCall[T]:
    """FR-AGENT-01..08, FR-CTX-03. One role call: check, fit, call. Nothing is written.

    `prunable` is in rank order, most relevant first. `fit_to_budget` keeps every mandatory
    input and as many prunable ones, in order, as the cap allows with the role's system prompt
    and `instruction` counted (FR-CTX-01); a mandatory part over the cap raises
    `ContextBudgetExceeded` before anything is sent (FR-CTX-05), so the client is never called.
    `ranked_after` names inputs an earlier fit already removed -- the writer's assembly stops
    at the cap itself -- which rank below everything passed here and so are listed after this
    fit's own removals.

    The model call's own errors (FR-LLM-04..08) propagate: a malformed output has already been
    retried once by the client, and a refusal carries its category.
    """
    keys = [role_input.key for role_input in [*mandatory, *prunable]]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated:
        message = f"two inputs of one {role.value} call share a key: {duplicated}"
        raise ValueError(message)
    check_inputs(role, [*mandatory, *prunable])
    system = system_prompt(role)
    fit = fit_to_budget(
        system=system,
        instruction=instruction,
        mandatory=[Entry(key=item.key, text=item.text) for item in mandatory],
        prunable=[Entry(key=item.key, text=item.text) for item in prunable],
        cap=cap,
    )
    kept = [*mandatory, *prunable[: len(fit.kept) - len(mandatory)]]
    documents = documents_for(role, [(item.path, item.text) for item in kept])
    completion = client.complete(
        role=role,
        system=system,
        documents=documents,
        instruction=instruction,
        output_schema=output_schema,
    )
    removed = (*fit.removed, *ranked_after)
    return RoleCall(
        role=role,
        completion=completion,
        documents=documents,
        instruction=instruction,
        removed=removed,
        truncated_at=removed[0] if removed else None,
        prompt_version=prompt_version(role),
    )


__all__ = [
    "COMPUTED_DOCUMENTS",
    "MECHANICAL_FINDINGS",
    "MODEL_ROLES",
    "PROMPTS",
    "PROMPT_PACKAGE",
    "RoleInput",
    "RolePrompt",
    "call_role",
    "check_inputs",
    "documents_for",
    "load_prompts",
    "prompt_from_bytes",
    "prompt_resource",
    "prompt_version",
    "read_prompt_file",
    "role_prompt",
    "system_prompt",
]
