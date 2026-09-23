"""The model client (spec 001 FR-LLM, FR-CTX): the one door from the backend to a model.

Import from here. `ModelClient` is the contract; `ClaudeCodeModelClient` runs each role call
as a `claude -p` subprocess under the user's Claude Code login, with no Anthropic API key
anywhere (decision R3-1); `FakeModelClient` is its scripted stand-in for every offline test
(NFR-06). The input-token estimate and the cap live in `tokens`, one definition of "fits" for
the assembler, the orchestrator and both clients (plan P7).
"""

from __future__ import annotations

from app.commons.llm.claude_code_client import ClaudeCodeModelClient, Runner, RunResult
from app.commons.llm.errors import (
    ContextBudgetExceeded,
    MalformedModelOutput,
    ModelCallFailed,
    ModelRefused,
    OutputTruncated,
)
from app.commons.llm.fake import (
    ApiError,
    FakeCall,
    FakeModelClient,
    FakeScriptExhaustedError,
    Outcome,
    ProcessFailure,
    RateLimited,
    Refusal,
    Reply,
    Truncation,
)
from app.commons.llm.protocol import (
    DATA_STATEMENT,
    Completion,
    Document,
    ModelClient,
    Usage,
    render_prompt,
    render_system,
)

__all__ = [
    "DATA_STATEMENT",
    "ApiError",
    "ClaudeCodeModelClient",
    "Completion",
    "ContextBudgetExceeded",
    "Document",
    "FakeCall",
    "FakeModelClient",
    "FakeScriptExhaustedError",
    "MalformedModelOutput",
    "ModelCallFailed",
    "ModelClient",
    "ModelRefused",
    "Outcome",
    "OutputTruncated",
    "ProcessFailure",
    "RateLimited",
    "Refusal",
    "Reply",
    "RunResult",
    "Runner",
    "Truncation",
    "Usage",
    "render_prompt",
    "render_system",
]
