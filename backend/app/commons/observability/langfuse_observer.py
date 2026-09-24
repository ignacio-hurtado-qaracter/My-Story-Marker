"""K2 over Langfuse (spec 010). Coded against the installed SDK, `langfuse==4.15.6`.

SDK facts this module relies on (read from the package source, not recalled):

* `Langfuse(public_key=, secret_key=, base_url=)` builds an OpenTelemetry-backed client;
  `start_as_current_observation(as_type="span", ...)` is a context manager that makes the
  new observation current, so later observations nest under it.
* Trace-level attributes (`session_id`, the trace name) are set with the module-level
  `langfuse.propagate_attributes(...)`, entered around the root span so every child
  inherits them.
* `create_score(name=, value=, trace_id=, session_id=, comment=, data_type=)` scores a trace.
* `create_prompt(name=, prompt=, labels=[...])` publishes a new prompt version;
  `get_prompt(name, label=)` returns a `PromptClient` with `.version` and `.prompt`.

Every SDK call is wrapped: a Langfuse failure logs a warning and never fails the caller.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from types import TracebackType

from langfuse import Langfuse, LangfuseGeneration, LangfuseSpan, propagate_attributes
from langfuse.model import PromptClient

from app.commons.observability.protocol import Metadata, SpanHandle, TokenUsage, TraceHandle

logger = logging.getLogger(__name__)


def _warn(action: str, error: Exception) -> None:
    # Never log the exception's args wholesale: an HTTP error can echo request headers.
    logger.warning("langfuse %s failed: %s", action, type(error).__name__)


def _exit(
    manager: AbstractContextManager[object] | None,
    error: BaseException | None,
) -> None:
    if manager is None:
        return
    traceback: TracebackType | None = error.__traceback__ if error is not None else None
    try:
        manager.__exit__(type(error) if error is not None else None, error, traceback)
    except Exception as exc:  # the tracing backend must not fail the caller
        _warn("close", exc)


@dataclass(slots=True)
class LangfuseObserver:
    """K2 on Langfuse Cloud. Build with `LangfuseObserver.from_keys(...)` or `get_observer()`."""

    client: Langfuse
    prompt_clients: dict[tuple[str, str], PromptClient] = field(default_factory=dict)
    _sessions: list[str] = field(default_factory=list)

    @classmethod
    def from_keys(cls, *, public_key: str, secret_key: str, base_url: str) -> LangfuseObserver:
        return cls(client=Langfuse(public_key=public_key, secret_key=secret_key, base_url=base_url))

    # ----------------------------------------------------------------------------------
    # K2
    # ----------------------------------------------------------------------------------

    def start_session(self, novel_id: str) -> str:
        return novel_id

    @contextmanager
    def trace(
        self, name: str, session_id: str, metadata: Metadata | None = None
    ) -> Iterator[TraceHandle]:
        propagation: AbstractContextManager[object] | None = None
        root: AbstractContextManager[LangfuseSpan] | None = None
        trace_id = uuid.uuid4().hex
        try:
            propagation = propagate_attributes(session_id=session_id, trace_name=name)
            propagation.__enter__()
            root = self.client.start_as_current_observation(
                as_type="span", name=name, metadata=dict(metadata or {})
            )
            span = root.__enter__()
            trace_id = span.trace_id
        except Exception as exc:
            _warn("trace open", exc)
            _exit(propagation, None)
            propagation, root = None, None
        self._sessions.append(session_id)
        handle = TraceHandle(id=trace_id, name=name, session_id=session_id)
        try:
            yield handle
        except BaseException as error:
            _exit(root, error)
            _exit(propagation, error)
            raise
        finally:
            self._sessions.pop()
        _exit(root, None)
        _exit(propagation, None)

    @contextmanager
    def span(
        self, name: str, input: object = None, metadata: Metadata | None = None
    ) -> Iterator[SpanHandle]:
        manager: AbstractContextManager[LangfuseSpan] | None = None
        observation: LangfuseSpan | None = None
        try:
            manager = self.client.start_as_current_observation(
                as_type="span", name=name, input=input, metadata=dict(metadata or {})
            )
            observation = manager.__enter__()
        except Exception as exc:
            _warn("span open", exc)
            manager = None
        handle = SpanHandle(
            id=observation.id if observation is not None else uuid.uuid4().hex[:16],
            name=name,
            trace_id=observation.trace_id if observation is not None else None,
            metadata=dict(metadata or {}),
        )
        try:
            yield handle
        except BaseException as error:
            self._finish(observation, handle, error)
            _exit(manager, error)
            raise
        self._finish(observation, handle, None)
        _exit(manager, None)

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
        details: dict[str, object] = {
            **dict(metadata or {}),
            "latency_s": round(latency_s, 3),
            "prompt_name": prompt_name,
            "prompt_version": prompt_version,
        }
        prompt = (
            self.prompt_clients.get((prompt_name, prompt_version))
            if prompt_name is not None and prompt_version is not None
            else None
        )
        try:
            generation = self._backdated_generation(name, latency_s)
            generation.update(
                input=input,
                output=output,
                model=model,
                usage_details=usage.as_dict(),
                cost_details={"total": cost_usd},
                metadata=details,
                prompt=prompt,
            )
            generation.end()
        except Exception as exc:
            _warn("generation", exc)
            return None
        return generation.id

    def score(
        self,
        name: str,
        value: float,
        comment: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        target = trace_id or self.current_trace_id()
        try:
            self.client.create_score(
                name=name,
                value=float(value),
                trace_id=target,
                session_id=None if target else (self._sessions[-1] if self._sessions else None),
                comment=comment,
                data_type="NUMERIC",
            )
        except Exception as exc:
            _warn("score", exc)

    def current_trace_id(self) -> str | None:
        try:
            return self.client.get_current_trace_id()
        except Exception as exc:
            _warn("current trace", exc)
            return None

    def flush(self) -> None:
        try:
            self.client.flush()
        except Exception as exc:
            _warn("flush", exc)

    # ----------------------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------------------

    def _backdated_generation(self, name: str, latency_s: float) -> LangfuseGeneration:
        """A generation whose start is `latency_s` before now, so its duration in the UI is
        the call's real latency. The public API has no start-time parameter; the OTel
        tracer the client wraps does, so the span is opened on it and wrapped in the SDK's
        own class. Falls back to a zero-length generation if the internals move."""
        start_ns = time.time_ns() - int(max(latency_s, 0.0) * 1_000_000_000)
        try:
            otel_span = self.client._otel_tracer.start_span(name=name, start_time=start_ns)
            return LangfuseGeneration(
                otel_span=otel_span,
                langfuse_client=self.client,
                environment=self.client._environment,
                release=self.client._release,
            )
        except (AttributeError, TypeError) as exc:
            _warn("backdated generation", exc)
            return self.client.start_observation(as_type="generation", name=name)

    @staticmethod
    def _finish(
        observation: LangfuseSpan | None, handle: SpanHandle, error: BaseException | None
    ) -> None:
        if observation is None:
            return
        try:
            if error is None:
                observation.update(output=handle.output, metadata=handle.metadata or None)
            else:
                observation.update(
                    output=handle.output,
                    metadata=handle.metadata or None,
                    level="ERROR",
                    status_message=type(error).__name__,
                )
        except Exception as exc:
            _warn("span update", exc)


__all__ = ["LangfuseObserver"]
