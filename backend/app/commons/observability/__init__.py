"""Contract K2: observability (spec 010).

Usage. Every block emits through this API, never through the Langfuse SDK directly:

from app.commons.observability import get_observer, traced_complete, load_prompt

observer = get_observer()
session = observer.start_session(novel_id)
with observer.trace("generation", session_id=session, metadata={"version": 1}) as trace:
    with observer.span("tool:query_story_bible", input=query) as span:
        span.update(output=rows)
    prompt = load_prompt("writer", observer)
    completion = traced_complete(client, role=AgentRole.WRITER, ..., observer=observer,
                                 prompt_name=prompt.name, prompt_version=prompt.version,
                                 sink=repo, scope=CallScope(novel_id, 1, chapter=3))
    observer.score("validator:chapter_length", 1.0, comment="1 234 words")
observer.flush()
"""

from __future__ import annotations

from functools import lru_cache

from app.commons.config import get_settings
from app.commons.observability.langfuse_observer import LangfuseObserver
from app.commons.observability.noop import NoopObserver, RecordedGeneration, RecordedScore
from app.commons.observability.pricing import PRICES, ModelPrice, cost_usd, price_for
from app.commons.observability.prompts import PromptRef, content_hash, load_prompt
from app.commons.observability.protocol import (
    Metadata,
    Observer,
    SpanHandle,
    TokenUsage,
    TraceHandle,
)
from app.commons.observability.traced import (
    MAX_ATTEMPTS_CEILING,
    CallScope,
    LlmCallRecord,
    LlmCallSink,
    traced_complete,
)


@lru_cache(maxsize=1)
def get_observer() -> Observer:
    """Langfuse when both keys are set and `LANGFUSE_ENABLED` is not 0; Noop otherwise.

    Cached: one client per process, so spans nest across modules. Tests that change the
    environment call `get_observer.cache_clear()` (and `get_settings.cache_clear()`).
    """
    settings = get_settings()
    if not settings.langfuse_active:
        return NoopObserver()
    public_key = settings.langfuse_public_key
    secret_key = settings.langfuse_secret_key
    if public_key is None or secret_key is None:  # pragma: no cover - langfuse_active checks
        return NoopObserver()
    try:
        return LangfuseObserver.from_keys(
            public_key=public_key, secret_key=secret_key, base_url=settings.langfuse_base_url
        )
    except Exception:  # an unusable backend degrades to offline, never fails startup
        return NoopObserver()


__all__ = [
    "MAX_ATTEMPTS_CEILING",
    "PRICES",
    "CallScope",
    "LangfuseObserver",
    "LlmCallRecord",
    "LlmCallSink",
    "Metadata",
    "ModelPrice",
    "NoopObserver",
    "Observer",
    "PromptRef",
    "RecordedGeneration",
    "RecordedScore",
    "SpanHandle",
    "TokenUsage",
    "TraceHandle",
    "content_hash",
    "cost_usd",
    "get_observer",
    "load_prompt",
    "price_for",
    "traced_complete",
]
