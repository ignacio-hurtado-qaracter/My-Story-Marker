"""`traced_complete`: one role call, observed (spec 010, O02).

Wraps `ModelClient.complete` (the live `ClaudeCodeModelClient` or the fake) in a
`role:<role>` span and a generation carrying the tokens the CLI reported, the cost from the
pinned price table, the latency and the prompt name and version. Optionally records the call
as an `llm_call` row through any `LlmCallSink` (the `BibleRepository` is one), so totals per
chapter and per novel are queryable without Langfuse.

The retry here is bounded by `max_attempts` and only covers failures a second attempt can
fix (malformed output, truncation, a failed process). A refusal or a context over the cap is
never retried. The client's own internal retry policy still applies inside each attempt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final, Protocol

from pydantic import BaseModel

from app.commons.errors import MalformedModelOutput, ModelCallFailed, OutputTruncated
from app.commons.llm.protocol import Completion, Document, ModelClient
from app.commons.observability.pricing import cost_usd
from app.commons.observability.protocol import Observer, TokenUsage
from app.commons.permissions import AgentRole

RETRYABLE: Final[tuple[type[Exception], ...]] = (
    MalformedModelOutput,
    OutputTruncated,
    ModelCallFailed,
)

MAX_ATTEMPTS_CEILING: Final[int] = 3
"""No caller may ask for more: bounded retries are an exam requirement (H06)."""


@dataclass(frozen=True, slots=True)
class LlmCallRecord:
    """One settled model call, as stored in the `llm_call` table (K1)."""

    role: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int
    cost_usd: float
    latency_s: float
    attempts: int
    novel_id: str | None = None
    version: int | None = None
    chapter: int | None = None
    prompt_name: str | None = None
    prompt_version: str | None = None
    trace_id: str | None = None
    ts: str = ""

    def stamped(self) -> LlmCallRecord:
        if self.ts:
            return self
        return replace(self, ts=datetime.now(UTC).isoformat())


class LlmCallSink(Protocol):
    """Anything that stores an `LlmCallRecord`: `BibleRepository.record_llm_call`."""

    def record_llm_call(self, record: LlmCallRecord) -> int: ...


@dataclass(frozen=True, slots=True)
class CallScope:
    """Where a call belongs, for the `llm_call` row and the span metadata."""

    novel_id: str | None = None
    version: int | None = None
    chapter: int | None = None
    scene: int | None = None


def traced_complete[T: BaseModel](
    client: ModelClient,
    *,
    role: AgentRole,
    system: str,
    documents: Sequence[Document],
    instruction: str,
    output_schema: type[T],
    observer: Observer,
    prompt_name: str | None = None,
    prompt_version: str | None = None,
    max_attempts: int = 2,
    sink: LlmCallSink | None = None,
    scope: CallScope | None = None,
) -> Completion[T]:
    """Run one role call inside a `role:<role>` span and record it. Raises what the client
    raises once the bounded retry is exhausted."""
    if not 1 <= max_attempts <= MAX_ATTEMPTS_CEILING:
        message = f"max_attempts must be 1..{MAX_ATTEMPTS_CEILING}, got {max_attempts}"
        raise ValueError(message)
    where = scope or CallScope()
    metadata: dict[str, object] = {
        "role": role.value,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        "novel_id": where.novel_id,
        "version": where.version,
        "chapter": where.chapter,
        "scene": where.scene,
    }
    with observer.span(f"role:{role.value}", input=instruction, metadata=metadata) as span:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                completion = client.complete(
                    role=role,
                    system=system,
                    documents=documents,
                    instruction=instruction,
                    output_schema=output_schema,
                )
            except RETRYABLE as error:
                last_error = error
                span.update(metadata={f"attempt_{attempt}_error": type(error).__name__})
                continue
            model = completion.model_id or completion.requested_model
            usage = completion.usage
            cost = cost_usd(
                model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read=usage.cache_read_input_tokens,
                cache_creation=usage.cache_creation_input_tokens,
            )
            tokens = TokenUsage(
                input=usage.input_tokens,
                output=usage.output_tokens,
                cache_read=usage.cache_read_input_tokens,
                cache_creation=usage.cache_creation_input_tokens,
            )
            output_json = completion.output.model_dump(mode="json")
            observer.generation(
                f"llm:{role.value}",
                model=model,
                input={"instruction": instruction, "documents": [d.path for d in documents]},
                output=output_json,
                usage=tokens,
                cost_usd=cost,
                latency_s=completion.elapsed_seconds,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                metadata={"attempts": attempt, "client_attempts": completion.attempts},
            )
            span.update(
                output=output_json,
                metadata={"cost_usd": cost, "latency_s": completion.elapsed_seconds},
            )
            if sink is not None:
                sink.record_llm_call(
                    LlmCallRecord(
                        role=role.value,
                        model=model,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cache_read=usage.cache_read_input_tokens,
                        cache_creation=usage.cache_creation_input_tokens,
                        cost_usd=cost,
                        latency_s=completion.elapsed_seconds,
                        attempts=attempt,
                        novel_id=where.novel_id,
                        version=where.version,
                        chapter=where.chapter,
                        prompt_name=prompt_name,
                        prompt_version=prompt_version,
                        trace_id=observer.current_trace_id(),
                    ).stamped()
                )
            return completion
        if last_error is None:  # pragma: no cover - the loop runs at least once
            message = "traced_complete made no attempt"
            raise RuntimeError(message)
        raise last_error


__all__ = [
    "MAX_ATTEMPTS_CEILING",
    "RETRYABLE",
    "CallScope",
    "LlmCallRecord",
    "LlmCallSink",
    "traced_complete",
]
