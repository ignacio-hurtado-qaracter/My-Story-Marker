"""The offline observer (spec 010): sends nothing, remembers everything.

Used by every test and by offline runs. It keeps the same nesting semantics as the Langfuse
observer (a current trace, a stack of spans) and records scores and generations in memory,
so a test can assert on what a block *would* have sent.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.commons.observability.protocol import Metadata, SpanHandle, TokenUsage, TraceHandle


@dataclass(frozen=True, slots=True)
class RecordedScore:
    name: str
    value: float
    comment: str | None
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class RecordedGeneration:
    id: str
    name: str
    model: str
    usage: TokenUsage
    cost_usd: float
    latency_s: float
    prompt_name: str | None
    prompt_version: str | None
    trace_id: str | None
    parent: str | None


@dataclass(slots=True)
class NoopObserver:
    """K2 without a backend. Satisfies `Observer`."""

    scores: list[RecordedScore] = field(default_factory=list)
    generations: list[RecordedGeneration] = field(default_factory=list)
    spans: list[str] = field(default_factory=list)
    traces: list[TraceHandle] = field(default_factory=list)
    _trace_stack: list[TraceHandle] = field(default_factory=list)
    _span_stack: list[SpanHandle] = field(default_factory=list)

    def start_session(self, novel_id: str) -> str:
        return novel_id

    @contextmanager
    def trace(
        self, name: str, session_id: str, metadata: Metadata | None = None
    ) -> Iterator[TraceHandle]:
        del metadata
        handle = TraceHandle(id=uuid.uuid4().hex, name=name, session_id=session_id)
        self.traces.append(handle)
        self._trace_stack.append(handle)
        try:
            yield handle
        finally:
            self._trace_stack.pop()

    @contextmanager
    def span(
        self, name: str, input: object = None, metadata: Metadata | None = None
    ) -> Iterator[SpanHandle]:
        del input
        handle = SpanHandle(
            id=uuid.uuid4().hex[:16],
            name=name,
            trace_id=self.current_trace_id(),
            metadata=dict(metadata or {}),
        )
        self.spans.append(name)
        self._span_stack.append(handle)
        try:
            yield handle
        finally:
            self._span_stack.pop()

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
        del input, output, metadata
        generation_id = uuid.uuid4().hex[:16]
        self.generations.append(
            RecordedGeneration(
                id=generation_id,
                name=name,
                model=model,
                usage=usage,
                cost_usd=cost_usd,
                latency_s=latency_s,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                trace_id=self.current_trace_id(),
                parent=self._span_stack[-1].name if self._span_stack else None,
            )
        )
        return generation_id

    def score(
        self,
        name: str,
        value: float,
        comment: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.scores.append(
            RecordedScore(
                name=name,
                value=value,
                comment=comment,
                trace_id=trace_id or self.current_trace_id(),
            )
        )

    def current_trace_id(self) -> str | None:
        return self._trace_stack[-1].id if self._trace_stack else None

    def flush(self) -> None:
        return None


__all__ = ["NoopObserver", "RecordedGeneration", "RecordedScore"]
