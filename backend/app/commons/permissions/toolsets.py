"""Each role's tool set, derived from Figure 3's write table by code (FR-PERM-06, AC 17).

A tool set is **not** something a model holds. The model holds no tools at all (FR-LLM-05,
FR-AGENT-09): it is handed documents and an instruction and it returns one DR-12 object. The
tool set is the other half of that contract, the writes the *orchestrator* may perform with
that object once it comes back: the writer's `WriterOutput` may become `manuscript/NNN.md` and
new entries in `ledger/proposed.yaml`, and nothing else. Asking the tool set before a write is
what stops an output from landing somewhere its role's row does not reach, even when the code
routing it is wrong.

**Why derived, never listed.** The spec says so in one clause -- "derived from FR-PERM-02 by
code, not hand-listed, so the two cannot diverge" -- and the semgrep rule of AC 17 forbids the
alternative under `agents/`. A second list would be correct on the day it was written and
wrong the first time Figure 3 changed, and the failure would be silent: a role keeping a tool
the table had taken away. So every `Tool` here is exactly one `WRITE_TABLE` glob, in the
table's order, and there is no other source.

**Write or append.** A tool names its target glob and one operation. `ledger/proposed.yaml`
is the only append-only target: it is the canonisation queue, and what a role's output may do
to it is add `pending` entries, never rewrite the ones already there -- DR-12 gives
`ProposedFactDraft` no `status`, `conflict` or `ruling` for the same reason. The rule is about
the target, so it holds for the writer and the canoniser alike. `promote` and `rule` also
update that file under the canoniser's row, but they are the backend's own decisions taken
through the store layer's `may_write` (FR-OPS-06, FR-OPS-07), not a write of model output,
and they do not pass through here. Every other target is a whole-file write: a draft is
replaced by its revision, and an audit is merged into `ledger/violations.yaml` and written
back whole (AC 16).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from app.commons.errors import PermissionDenied
from app.commons.permissions.roles import AgentRole
from app.commons.permissions.table import compile_store_glob, normalise, writable_patterns


class ToolOperation(StrEnum):
    """What a tool may do to a file that matches its target."""

    WRITE = "write"
    """Replace the file whole: a draft, a digest, a canon record, the merged violation report."""

    APPEND = "append"
    """Add records to the end of a queue and leave every existing record as it was."""


APPEND_ONLY_TARGETS: Final[frozenset[str]] = frozenset({"ledger/proposed.yaml"})
"""The targets a role's output may only add to (see the module docstring). A property of the
file, not of a role, so it cannot quietly give one role a stronger tool than another on the
same path."""


def operation_for(target: str) -> ToolOperation:
    """The operation a tool on `target` carries: append for the canonisation queue, write for
    everything else."""
    return ToolOperation.APPEND if target in APPEND_ONLY_TARGETS else ToolOperation.WRITE


@dataclass(frozen=True, slots=True)
class Tool:
    """One write the orchestrator may perform with a role's output: one `WRITE_TABLE` glob and
    its operation (FR-PERM-06)."""

    role: AgentRole
    target: str
    """The glob exactly as `WRITE_TABLE` spells it, so a reader can match it against Figure 3."""
    operation: ToolOperation
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_pattern", compile_store_glob(self.target))

    def matches(self, path: str) -> bool:
        """True when `path` is one of this tool's targets. Normalised first, with the same
        rules as `may_write`, so a traversal cannot reach a target by spelling."""
        try:
            candidate = normalise(path)
        except ValueError:
            return False
        return self._pattern.match(candidate) is not None

    def allows(self, operation: ToolOperation) -> bool:
        """A write tool may also append -- a role that may replace a file may add to it -- but
        an append tool may never replace."""
        return self.operation is ToolOperation.WRITE or operation is ToolOperation.APPEND


@dataclass(frozen=True, slots=True)
class ToolSet:
    """Every tool of one role, in `WRITE_TABLE` order. Frozen, and built once at import: FR-PERM-05
    leaves no code path that widens a role at runtime, and a mutable tool set would be one."""

    role: AgentRole
    tools: tuple[Tool, ...]

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(tool.target for tool in self.tools)

    def tool_for(self, path: str) -> Tool | None:
        """The tool whose target `path` is, or None when no tool of this role reaches it."""
        return next((tool for tool in self.tools if tool.matches(path)), None)

    def covers(self, path: str) -> bool:
        return self.tool_for(path) is not None

    def authorise(self, path: str, operation: ToolOperation = ToolOperation.WRITE) -> Tool:
        """FR-PERM-06: the tool the orchestrator uses to write `path`, or `PermissionDenied`.

        The same error the store layer raises when Figure 3 refuses a write (FR-STORE-03, a 403
        in IF-07), because it is the same table saying no: a path outside the set, or a
        replacement of the append-only queue, is refused before anything is written. It is not
        a new error type because IF-07 lists every error the API returns, and this refusal is
        already one of them.
        """
        tool = self.tool_for(path)
        if tool is None:
            message = (
                f"the {self.role.value} role's tool set has no tool for {path}: Figure 3 does "
                f"not let the orchestrator write it with {self.role.value} output (FR-PERM-06)"
            )
            raise PermissionDenied(message, role=self.role.value, path=path)
        if not tool.allows(operation):
            message = (
                f"the {self.role.value} role's tool for {path} may only {tool.operation.value}, "
                f"not {operation.value}: a role's output adds to the canonisation queue and "
                "never rewrites it (FR-PERM-06, FR-AGENT-01)"
            )
            raise PermissionDenied(message, role=self.role.value, path=path)
        return tool


def _derive(role: AgentRole) -> ToolSet:
    """The only construction of a tool set: one tool per glob of the role's `WRITE_TABLE` row."""
    return ToolSet(
        role=role,
        tools=tuple(
            Tool(role=role, target=target, operation=operation_for(target))
            for target in writable_patterns(role)
        ),
    )


_TOOLSETS: Final[Mapping[AgentRole, ToolSet]] = {role: _derive(role) for role in AgentRole}


def toolset_for(role: AgentRole) -> ToolSet:
    """FR-PERM-06, AC 17. The tool set of `role`, derived from `WRITE_TABLE`.

    Defined for all six roles because the derivation is the same for each; in v1 only the
    writer, style editor, auditor and canoniser are model-invoked, and the architect and world
    builder act through their routes with a human behind them (spec Decision 5).
    """
    return _TOOLSETS[role]


__all__ = [
    "APPEND_ONLY_TARGETS",
    "Tool",
    "ToolOperation",
    "ToolSet",
    "operation_for",
    "toolset_for",
]
