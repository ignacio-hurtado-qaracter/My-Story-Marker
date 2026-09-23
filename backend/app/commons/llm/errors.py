"""The typed error chain of a model call, and the one retry policy both clients share.

The public errors live in `app.commons.errors`, because that is where IF-07 maps each one to
a status code; they are re-exported here so a caller of the model client imports from one
place. What this module adds is the **classification** FR-LLM-04, FR-LLM-06 and FR-LLM-08
describe, most specific first:

| Outcome of one attempt, in the order it is checked | Kind | Retries | Then |
|---|---|---|---|
| timeout, or no readable result envelope | `PROCESS` | 1 | `ModelCallFailed` |
| a rate-limit or overload API error status | `RATE_LIMITED` | 3, backoff | `ModelCallFailed` |
| any other API error status | -- | none | `ModelCallFailed` |
| `stop_reason: refusal` | -- | none | `ModelRefused`, with the category |
| `stop_reason: max_tokens` | `TRUNCATED` | 1 | `OutputTruncated` |
| `subtype: error_max_structured_output_retries` | `MALFORMED` | 1 | `MalformedModelOutput` |
| error envelope or non-zero exit without a status | `PROCESS` | 1 | `ModelCallFailed` |
| `structured_output` fails its DR-12 schema | `MALFORMED` | 1 | `MalformedModelOutput` |

An attempt that may be retried raises `RetryableError`, carrying the public error to raise
once that kind's allowance is spent; an attempt that may not raises the public error
directly. `run_attempts` is the loop. The fake client runs the same loop over its scripted
outcomes, so a turn-level test of "retried once, then `MalformedModelOutput`" (AC 21)
exercises this policy and not an imitation of it.

Each kind has its own allowance, so the loop is bounded by their sum plus one: a call can
never spin, which the turn's termination argument (FR-TURN-02) quietly relies on.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, JsonValue, ValidationError

from app.commons.errors import (
    ContextBudgetExceeded,
    HarnessError,
    MalformedModelOutput,
    ModelCallFailed,
    ModelRefused,
    OutputTruncated,
)


class RetryKind(StrEnum):
    """Why an attempt failed, in the terms of the retry policy."""

    MALFORMED = "malformed_output"
    TRUNCATED = "output_truncated"
    PROCESS = "process"
    RATE_LIMITED = "rate_limited"


RETRY_ALLOWANCE: Final[Mapping[RetryKind, int]] = {
    RetryKind.MALFORMED: 1,
    RetryKind.TRUNCATED: 1,
    RetryKind.PROCESS: 1,
    RetryKind.RATE_LIMITED: 3,
}
"""FR-LLM-04 and FR-LLM-06: a malformed or truncated output is retried once. FR-LLM-08: a
failed or unreadable process once; a rate limit or overload with backoff, three times -- the
spec leaves the count open, and three waits (2 s, 4 s, 8 s) outlast a burst limit without
holding a turn for minutes on a quota that is simply spent."""

RATE_LIMIT_STATUSES: Final[frozenset[int]] = frozenset({429, 529})
"""FR-LLM-08. 429 is the rate limit and 529 the provider's overload status; both say "later",
not "never". Every other status fails the step at once."""

BACKOFF_BASE_SECONDS: Final[float] = 2.0
BACKOFF_MAX_SECONDS: Final[float] = 30.0


class RetryableError(Exception):
    """One attempt failed in a way the policy may retry.

    `final` is the public error raised once the allowance for `kind` is spent. It is built at
    the point of failure, where the reason is known, so the loop never has to reconstruct it.
    """

    def __init__(self, kind: RetryKind, final: HarnessError) -> None:
        super().__init__(final.message)
        self.kind = kind
        self.final = final


def backoff_delay(retry_number: int) -> float:
    """FR-LLM-08. Exponential: 2 s before the first retry, then 4, 8, capped at 30."""
    exponent = max(retry_number - 1, 0)
    return float(min(BACKOFF_BASE_SECONDS * 2**exponent, BACKOFF_MAX_SECONDS))


def run_attempts[R](attempt: Callable[[], R], *, sleep: Callable[[float], None]) -> tuple[R, int]:
    """Run `attempt` until it settles; return its result and how many attempts it took.

    A `RetryableError` is retried while its kind has allowance left, sleeping first only
    for a rate limit; once spent, its `final` error is raised. Any other exception -- a
    refusal, a non-retryable API error -- propagates at once.
    """
    used: Counter[RetryKind] = Counter()
    attempts = 0
    while True:
        attempts += 1
        try:
            return attempt(), attempts
        except RetryableError as failure:
            if used[failure.kind] >= RETRY_ALLOWANCE[failure.kind]:
                raise failure.final from None
            used[failure.kind] += 1
            if failure.kind is RetryKind.RATE_LIMITED:
                sleep(backoff_delay(used[failure.kind]))


def validate_output[T: BaseModel](payload: JsonValue, schema: type[T], *, role: str) -> T:
    """FR-LLM-04. Validate a structured output against its DR-12 model, or fail the attempt.

    Validated in JSON mode, from the JSON text of the payload, because that is what the model
    produced: a wire value, not a Python object. Nothing is coerced into shape, no extra key
    is dropped and no missing one defaulted -- the models forbid extras -- so an output that
    is almost right is rejected, retried once, and then fails. The error names fields and
    error types, never the values, which are model output (NFR-10).
    """
    try:
        return schema.model_validate_json(json.dumps(payload))
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['type']}"
            for item in error.errors(include_url=False, include_input=False)
        )
        message = f"the {role} output does not match {schema.__name__}: {problems}"
        raise RetryableError(
            RetryKind.MALFORMED, MalformedModelOutput(message, role=role)
        ) from None


def structured_output_rejected(role: str, schema_name: str) -> RetryableError:
    """FR-LLM-04. The CLI's own `--json-schema` validation rejected every structured output
    the model produced, so the envelope carries none. The same outcome as `validate_output`
    failing, one layer earlier: one retry, then `MalformedModelOutput`, never a generic CLI
    error that would hide from the turn record that the model's output was the problem."""
    message = (
        f"the {role} output does not match {schema_name}: the CLI rejected every structured "
        "output the model produced (error_max_structured_output_retries)"
    )
    return RetryableError(RetryKind.MALFORMED, MalformedModelOutput(message, role=role))


def refused(role: str, category: str | None) -> ModelRefused:
    """FR-LLM-06. Not retried; the turn escalates with the category."""
    shown = category or "unspecified"
    return ModelRefused(
        f"the model refused the {role} call (category: {shown})", category=category, role=role
    )


def truncated(role: str) -> RetryableError:
    """FR-LLM-06. `stop_reason: max_tokens`, retried once."""
    return RetryableError(
        RetryKind.TRUNCATED,
        OutputTruncated(f"the {role} output was cut off at the output-token limit", role=role),
    )


def api_status_failure(
    role: str, status: int | None, detail: str
) -> ModelCallFailed | RetryableError:
    """FR-LLM-08. A rate limit or overload is retried with backoff; any other API error
    status fails the step at once. Returned rather than raised so the caller's `raise`
    shows at the call site which of the two it is."""
    if status in RATE_LIMIT_STATUSES:
        return RetryableError(
            RetryKind.RATE_LIMITED,
            ModelCallFailed(
                f"the {role} call was rate limited or the model was overloaded "
                f"(status {status}), and stayed so after every retry: {detail}",
                reason="rate_limited",
                role=role,
                status=status,
            ),
        )
    return ModelCallFailed(
        f"the {role} call failed with API error status {status}: {detail}",
        reason="api_error",
        role=role,
        status=status,
    )


def process_failure(role: str, reason: str, detail: str) -> RetryableError:
    """FR-LLM-08. A non-zero exit, a timeout or an unreadable result: retried once."""
    return RetryableError(
        RetryKind.PROCESS,
        ModelCallFailed(f"the {role} call failed ({reason}): {detail}", reason=reason, role=role),
    )


__all__ = [
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "RATE_LIMIT_STATUSES",
    "RETRY_ALLOWANCE",
    "ContextBudgetExceeded",
    "MalformedModelOutput",
    "ModelCallFailed",
    "ModelRefused",
    "OutputTruncated",
    "RetryKind",
    "RetryableError",
    "api_status_failure",
    "backoff_delay",
    "process_failure",
    "refused",
    "run_attempts",
    "structured_output_rejected",
    "truncated",
    "validate_output",
]
