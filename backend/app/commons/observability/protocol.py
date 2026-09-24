"""Contract K2: what every block emits through (spec 010).

Session = novel (interview, generation, regenerations). Trace = one generation or one
regeneration. Spans are named `role:<role>` for a role call and `tool:<name>` for a tool
call; a generation records one model call with tokens, cost and latency; a score attaches a
validator result (K3) or any other measurement to a trace.

Two implementations: `LangfuseObserver` and `NoopObserver`. Neither ever raises into the
caller because of the tracing backend: observability must not fail a generation.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Protocol

Metadata = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """The `usage` of a generation, in the four counts the CLI reports."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_creation: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input": self.input,
            "output": self.output,
            "cache_read_input_tokens": self.cache_read,
            "cache_creation_input_tokens": self.cache_creation,
        }


@dataclass(slots=True)
class TraceHandle:
    """An open trace. `id` is the Langfuse trace id (32 hex), or a local one under Noop."""

    id: str
    name: str
    session_id: str


@dataclass(slots=True)
class SpanHandle:
    """An open span. `update` records its output or metadata before it closes."""

    id: str
    name: str
    trace_id: str | None
    output: object = None
    metadata: dict[str, object] = field(default_factory=dict)

    def update(self, *, output: object = None, metadata: Metadata | None = None) -> None:
        if output is not None:
            self.output = output
        if metadata:
            self.metadata.update(metadata)


class Observer(Protocol):
    """K2. Every block depends on this protocol, never on the Langfuse SDK."""

    def start_session(self, novel_id: str) -> str:
        """Return the session id for a novel (the novel id itself)."""
        ...

    def trace(
        self, name: str, session_id: str, metadata: Metadata | None = None
    ) -> AbstractContextManager[TraceHandle]:
        """Open one trace (a generation or regeneration) inside a session."""
        ...

    def span(
        self, name: str, input: object = None, metadata: Metadata | None = None
    ) -> AbstractContextManager[SpanHandle]:
        """Open a span under the current observation: `role:<role>` or `tool:<name>`."""
        ...

    def generation(
        self,
        name: str,
        *,
        model: str,
        input: object,
        output: object,
        usage: TokenUsage,
        cost_usd: float,
        latency_s: float,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        metadata: Metadata | None = None,
    ) -> str | None:
        """Record one finished model call under the current span; returns its id."""
        ...

    def score(
        self,
        name: str,
        value: float,
        comment: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Attach a numeric score to `trace_id`, or to the current trace when None."""
        ...

    def current_trace_id(self) -> str | None:
        """The id of the innermost open trace, if any."""
        ...

    def flush(self) -> None:
        """Send everything buffered. Call before a short-lived process exits."""
        ...


__all__ = ["Metadata", "Observer", "SpanHandle", "TokenUsage", "TraceHandle"]
