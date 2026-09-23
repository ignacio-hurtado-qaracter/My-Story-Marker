"""`FakeModelClient`: scripted outcomes and a call log, for every offline test (FR-LLM-02).

The offline suite never reaches a model (NFR-06) and the turn tests of plan step 18 still have
to drive every branch of Figure 4: a clean draft, a blocking violation that never goes away, a
schema-invalid answer, a refusal, a truncation, a usage report over the cap. So the fake is
scripted per **attempt** with the outcomes a real call can have, and it settles them through
the same code the live client uses:

* the same pre-call estimate and cap check (`protocol.preflight`), so AC 22 is testable at
  the turn level with the real rule -- a call over the cap is refused, is **not** logged as
  made, and consumes no scripted outcome;
* the same retry policy (`errors.run_attempts`) and the same output validation
  (`errors.validate_output`), so "retried once, then `MalformedModelOutput`" (AC 21) means
  the same thing here as against `claude -p`.

Every call that passed the cap is recorded -- role, system prompt, the documents as
structured values, instruction, output schema name, estimate, and the outcomes it consumed --
which is what AC 23 (nothing from the stores in `system`, every document labelled), AC 24 (one
`write` call after a resume) and FR-AGENT-09 (documents inside the role's `INPUT_TABLE` row)
inspect.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel, JsonValue

from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.errors import ContextBudgetExceeded, HarnessError
from app.commons.llm.errors import (
    RetryableError,
    api_status_failure,
    process_failure,
    refused,
    run_attempts,
    truncated,
    validate_output,
)
from app.commons.llm.protocol import (
    Completion,
    Document,
    Usage,
    checked_cap,
    estimate_call,
    preflight,
)
from app.commons.llm.tokens import is_over_cap
from app.commons.permissions import AgentRole

FAKE_MODEL: Final[str] = "fake-model"
FAKE_CLI_VERSION: Final[str] = "fake"


@dataclass(frozen=True, slots=True)
class Reply:
    """The model answered. `payload` is the raw structured output, validated against the
    call's DR-12 schema exactly as the live client validates `structured_output`: a valid
    payload settles the call, an invalid one is a malformed output."""

    payload: JsonValue
    usage: Usage = field(default_factory=Usage)
    model_id: str = FAKE_MODEL

    @classmethod
    def of(
        cls, output: BaseModel, *, usage: Usage | None = None, model_id: str = FAKE_MODEL
    ) -> Reply:
        """A reply carrying a valid output, serialised the way the model would send it."""
        return cls(
            payload=output.model_dump(mode="json"),
            usage=usage or Usage(),
            model_id=model_id,
        )


@dataclass(frozen=True, slots=True)
class Refusal:
    """`stop_reason: refusal`, with the category when the provider gives one."""

    category: str | None = None


@dataclass(frozen=True, slots=True)
class Truncation:
    """`stop_reason: max_tokens`."""


@dataclass(frozen=True, slots=True)
class RateLimited:
    """A rate-limit or overload status: retried with backoff."""

    status: int = 429


@dataclass(frozen=True, slots=True)
class ApiError:
    """Any other API error status: fails the step."""

    status: int = 500


@dataclass(frozen=True, slots=True)
class ProcessFailure:
    """A timeout, a non-zero exit or an unreadable envelope: retried once."""

    reason: str = "timeout"


Outcome = Reply | Refusal | Truncation | RateLimited | ApiError | ProcessFailure


@dataclass(frozen=True, slots=True)
class FakeCall:
    """One `complete` call as the fake received it. `outcomes` grows as attempts consume the
    script, so after a retried call it holds both outcomes in order."""

    role: AgentRole
    system: str
    documents: tuple[Document, ...]
    instruction: str
    output_schema: str
    estimate: int
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return len(self.outcomes)


class FakeScriptExhaustedError(RuntimeError):
    """A test asked for more calls than it scripted. Loud on purpose: a fake that invented a
    default answer would let a test pass on behaviour nobody wrote down."""


Script = Sequence[Outcome] | Mapping[AgentRole, Sequence[Outcome]]


class FakeModelClient:
    """FR-LLM-02's scripted implementation.

    `script` is either one queue consumed in call order, or one queue per role. `fallback`
    answers once the relevant queue is empty -- "always return a blocking violation" (AC 19)
    is a fallback, not a list of three identical replies. Without one, running out of script
    raises `FakeScriptExhaustedError`.
    """

    def __init__(
        self,
        script: Script = (),
        *,
        fallback: Callable[[FakeCall], Outcome] | None = None,
        cap: int = CONTEXT_TOKEN_CAP,
        model: str = FAKE_MODEL,
    ) -> None:
        self._shared: deque[Outcome] = deque()
        self._by_role: dict[AgentRole, deque[Outcome]] = {}
        if isinstance(script, Mapping):
            self._by_role = {role: deque(queue) for role, queue in script.items()}
        else:
            self._shared = deque(script)
        self._fallback = fallback
        self._cap = checked_cap(cap)
        self._model = model
        self.calls: list[FakeCall] = []
        """Every call that passed the cap, in order."""
        self.refused_over_cap: list[FakeCall] = []
        """Calls refused by the cap: never made, so never in `calls` (AC 22)."""
        self.sleeps: list[float] = []
        """The backoff delays the retry policy asked for; nothing actually sleeps."""

    def estimate_input_tokens(
        self, system: str, documents: Sequence[Document], instruction: str
    ) -> int:
        """FR-LLM-07. The same estimate as the live client (plan P7)."""
        return estimate_call(system, documents, instruction)

    def pending(self, role: AgentRole | None = None) -> int:
        """Scripted outcomes not yet consumed, so a test can assert its script was used up."""
        if role is not None:
            return len(self._by_role.get(role, ()))
        return len(self._shared) + sum(len(queue) for queue in self._by_role.values())

    def complete[T: BaseModel](
        self,
        *,
        role: AgentRole,
        system: str,
        documents: Sequence[Document],
        instruction: str,
        output_schema: type[T],
    ) -> Completion[T]:
        """FR-LLM-02. Settle the call from the script, exactly as the live client settles a
        `claude -p` run."""
        call = FakeCall(
            role=role,
            system=system,
            documents=tuple(documents),
            instruction=instruction,
            output_schema=output_schema.__name__,
            estimate=estimate_call(system, documents, instruction),
        )
        try:
            preflight(system, documents, instruction, cap=self._cap)
        except ContextBudgetExceeded:
            self.refused_over_cap.append(call)
            raise
        self.calls.append(call)

        def attempt() -> tuple[T, Reply]:
            outcome = self._next(call)
            call.outcomes.append(outcome)
            return self._settle(outcome, output_schema, role.value)

        (output, reply), attempts = run_attempts(attempt, sleep=self.sleeps.append)
        return Completion(
            output=output,
            role=role,
            model_id=reply.model_id,
            requested_model=self._model,
            usage=reply.usage,
            estimate=call.estimate,
            over_cap=is_over_cap(reply.usage.context_tokens, self._cap),
            attempts=attempts,
            elapsed_seconds=0.0,
            cli_version=FAKE_CLI_VERSION,
            num_turns=1,
        )

    def _next(self, call: FakeCall) -> Outcome:
        queue = self._by_role.get(call.role, self._shared)
        if queue:
            return queue.popleft()
        if self._fallback is not None:
            return self._fallback(call)
        message = (
            f"the fake model has no scripted outcome left for a {call.role.value} call "
            f"({call.output_schema}); script it, or give the fake a fallback"
        )
        raise FakeScriptExhaustedError(message)

    @staticmethod
    def _settle[T: BaseModel](
        outcome: Outcome, output_schema: type[T], role: str
    ) -> tuple[T, Reply]:
        """The fake's side of `claude_code_client.settle`: each scripted outcome raises what
        the corresponding envelope raises there."""
        if isinstance(outcome, Reply):
            return validate_output(outcome.payload, output_schema, role=role), outcome
        failure: HarnessError | RetryableError
        if isinstance(outcome, Refusal):
            failure = refused(role, outcome.category)
        elif isinstance(outcome, Truncation):
            failure = truncated(role)
        elif isinstance(outcome, RateLimited | ApiError):
            failure = api_status_failure(role, outcome.status, "scripted by the fake model")
        else:
            failure = process_failure(role, outcome.reason, "scripted by the fake model")
        raise failure


__all__ = [
    "FAKE_CLI_VERSION",
    "FAKE_MODEL",
    "ApiError",
    "FakeCall",
    "FakeModelClient",
    "FakeScriptExhaustedError",
    "Outcome",
    "ProcessFailure",
    "RateLimited",
    "Refusal",
    "Reply",
    "Script",
    "Truncation",
]
