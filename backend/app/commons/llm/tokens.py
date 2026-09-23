"""The input-token estimate and the budget every model call must fit (FR-CTX, FR-LLM-07).

The Claude Code CLI has no counting call, so the cap is enforced on an estimate made before
the call (spec decision R3-2, the user's rule): only **input** tokens count, and a call whose
estimate exceeds the cap is not made. Three things follow, and this module is all three:

* **The estimate is deliberately pessimistic.** `ceil(characters / 3)` overestimates English
  prose, which runs nearer four characters to a token. For a hard cap the only safe error is
  counting too many; the real count the CLI reports afterwards is recorded beside it
  (FR-CTX-06), and a real count above the cap is what says this divisor must grow.
* **The cap is over what the system sends, and nothing else** (spec decision R3-5,
  `architecture.md` "Memory and context budget"). Every `claude -p` call also carries its own
  structured-output tool, environment details and the organisation's managed instructions,
  measured at about 2 500 tokens on 2026-09-23. The system neither writes nor can remove
  them, so they are a fixed cost accepted outside the budget: a real call may carry about
  102 500 input tokens. `CLI_OVERHEAD_TOKENS` exists only to read the real count afterwards.
* **Pruning removes whole entries, lowest rank first, and says what it removed.** Never a cut
  inside an entry (FR-OPS-03): half an axiom states a rule it does not state. Never silently:
  the removed keys and the first one removed (`truncated_at`) go on the turn record. And never
  the mandatory part: if that alone does not fit, the call is refused with
  `ContextBudgetExceeded`, because the fault is a record that is too large and the fix belongs
  in that record (FR-CTX-05).

Pure functions, no I/O and no subprocess: the assembler (step 12) and the orchestrator
(step 18) both use them, and the client uses the same estimate before every call, so there
is exactly one definition of "fits".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.errors import ContextBudgetExceeded

CHARACTERS_PER_TOKEN: Final[int] = 3
"""FR-CTX-02. Pessimistic on purpose; see the module docstring."""

CLI_OVERHEAD_TOKENS: Final[int] = 2_500
"""FR-CTX-02, FR-CTX-06. What `claude -p` adds to every call regardless of the prompt:
measured at 2 372 and 2 470 input tokens for two near-empty probes on 2026-09-23, rounded up.
A module constant, not a setting, re-measured when the CLI is upgraded.

Used **only** by `is_over_cap`, to read the real count the CLI reports. It is never part of
the estimate or of pruning: the cap is over what the system sends (R3-5)."""


def estimate_tokens(text: str) -> int:
    """FR-CTX-02 for one text. Empty text costs nothing; any other text costs at least one."""
    return math.ceil(len(text) / CHARACTERS_PER_TOKEN)


def estimate_input(system: str, documents: Sequence[str], instruction: str) -> int:
    """FR-LLM-07. Everything the system sends -- and only that. The CLI's own overhead is
    outside the cap (R3-5), so an empty call estimates at zero."""
    return (
        estimate_tokens(system)
        + sum(estimate_tokens(document) for document in documents)
        + estimate_tokens(instruction)
    )


@dataclass(frozen=True, slots=True)
class Entry:
    """One indivisible piece of a role's input: a document, identified by `key` (its source
    path or entity id), which pruning either keeps whole or removes whole."""

    key: str
    text: str

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


@dataclass(frozen=True, slots=True)
class BudgetFit:
    """The outcome of fitting a role's input to the cap. Everything here goes on the turn
    record, so what entered a context -- and what was left out -- is always recoverable."""

    kept: list[Entry]
    removed: list[str] = field(default_factory=list)
    truncated_at: str | None = None
    estimate: int = 0


def fit_to_budget(
    *,
    system: str,
    instruction: str,
    mandatory: Sequence[Entry],
    prunable: Sequence[Entry],
    cap: int = CONTEXT_TOKEN_CAP,
) -> BudgetFit:
    """FR-CTX-03. Keep every mandatory entry and as many prunable ones, in rank order, as fit.

    `prunable` is ordered most relevant first. Entries are taken in that order until the next
    one would cross the cap; that one and every one after it are removed -- a lower-ranked
    entry is not slipped in behind a larger one it happens to fit beside, because the order is
    the ranking's judgement and loading must be reproducible from it.

    Raises `ContextBudgetExceeded` when the mandatory part alone does not fit. The caller
    escalates the turn; nothing is shortened to make it fit (FR-CTX-05).
    """
    base = estimate_input(system, [entry.text for entry in mandatory], instruction)
    if base > cap:
        message = (
            f"the mandatory input alone is estimated at {base} tokens, over the {cap}-token "
            "cap; a record is too large and has to be fixed at the source"
        )
        raise ContextBudgetExceeded(message, counted=base, cap=cap)

    kept = list(mandatory)
    total = base
    for index, entry in enumerate(prunable):
        if total + entry.tokens > cap:
            removed = [later.key for later in prunable[index:]]
            return BudgetFit(kept=kept, removed=removed, truncated_at=entry.key, estimate=total)
        kept.append(entry)
        total += entry.tokens
    return BudgetFit(kept=kept, estimate=total)


def is_over_cap(real_input_tokens: int, cap: int = CONTEXT_TOKEN_CAP) -> bool:
    """FR-CTX-06. Whether a call already made carried more system context than the cap.

    The CLI reports the real input count including its own overhead, which is outside the
    cap. Subtracting the measured overhead before comparing is the user's choice (R3-5): the
    alternative would flag every call between 97 500 and 100 000 tokens of system context,
    none of which broke the rule. A true result means the pre-call estimate was wrong -- the
    signal to make `CHARACTERS_PER_TOKEN` more conservative -- and goes on the turn record
    as `over_cap: true`, visible rather than silent.
    """
    return real_input_tokens - CLI_OVERHEAD_TOKENS > cap


def require_within_cap(estimate: int, cap: int = CONTEXT_TOKEN_CAP) -> None:
    """FR-LLM-07. The last check before a call is made: an estimate over the cap is refused."""
    if estimate > cap:
        message = f"input estimated at {estimate} tokens, over the {cap}-token cap"
        raise ContextBudgetExceeded(message, counted=estimate, cap=cap)


__all__ = [
    "CHARACTERS_PER_TOKEN",
    "CLI_OVERHEAD_TOKENS",
    "BudgetFit",
    "Entry",
    "estimate_input",
    "estimate_tokens",
    "fit_to_budget",
    "is_over_cap",
    "require_within_cap",
]
