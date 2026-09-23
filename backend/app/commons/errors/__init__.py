"""The error types of spec 001 and the handlers that map them to IF-07 status codes.

One shape for every error body (IF-07):

    {"error": "<code>", "detail": "<message>", ...context}

The context keys are per error type and are what a caller needs to act: the role and path
for a refused write, the file and field for a record that failed validation, the refusal
category for a model that declined. Nothing else is added, and no traceback ever leaves the
process in a response body.

These are domain errors, not HTTP errors. A feature raises them; only the handlers here
know what status code each becomes, so the status code table lives in exactly one place.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ErrorContextValue = str | int | float | bool | None
"""What may appear in an error body beside `error` and `detail`. Deliberately not a free
object type: an error body is read by a client, not a debugger."""


class HarnessError(Exception):
    """Base of every error the harness raises deliberately.

    Subclasses set `code` and `status_code`; an unhandled subclass would surface as a 500,
    which is the correct outcome for a bug and the wrong one for a domain refusal.
    """

    code: str = "harness_error"
    status_code: int = 500

    def __init__(self, message: str, **context: ErrorContextValue) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, ErrorContextValue] = dict(context)

    def as_body(self) -> dict[str, ErrorContextValue]:
        """IF-07. `error` and `detail` first, then the per-type context."""
        body: dict[str, ErrorContextValue] = {"error": self.code, "detail": self.message}
        body.update(self.context)
        return body


class InvalidRecord(HarnessError):
    """FR-STORE-06. A store file does not match its model.

    Never repaired and never partially returned: naming the file and the field is the whole
    contract, because a record the system silently fixed is a record nobody can trust.
    """

    code = "invalid_record"
    status_code = 422

    def __init__(self, message: str, *, file: str, field: str | None = None) -> None:
        super().__init__(message, file=file, field=field)


class NotFound(HarnessError):
    """No record with that identifier. Distinct from an identifier that is malformed, which
    is a `ValueError` inside the store layer and never reaches a path (FR-STORE-05)."""

    code = "not_found"
    status_code = 404

    def __init__(
        self, message: str, *, kind: str | None = None, identifier: str | None = None
    ) -> None:
        super().__init__(message, kind=kind, id=identifier)


class InvalidRole(HarnessError):
    """IF-02. The `X-Agent-Role` header is missing or names no role.

    A 400 rather than a 403: the caller has not been refused, it has not said who it is. The
    distinction matters because a 403 is a fact about Figure 3 and this is a fact about the
    request, and conflating them would make a malformed client look like a permission
    problem in the logs.

    There is no default role. Guessing one would mean the provenance log recorded a guess
    (FR-STORE-04), and a log that records guesses is not evidence.
    """

    code = "invalid_role"
    status_code = 400

    def __init__(self, message: str, *, supplied: str | None = None) -> None:
        super().__init__(message, supplied=supplied)


class PermissionDenied(HarnessError):
    """FR-STORE-03, IF-02. Figure 3 forbids this role on this path.

    Raised before any byte touches disk. This is the load-bearing wall of the design, so the
    body names both halves of the decision and nothing else.
    """

    code = "permission_denied"
    status_code = 403

    def __init__(self, message: str, *, role: str, path: str) -> None:
        super().__init__(message, role=role, path=path)


class IndexBusy(HarnessError):
    """FR-IDX-06. SQLITE_BUSY survived the busy timeout and the retries."""

    code = "index_busy"
    status_code = 503


class TurnLocked(HarnessError):
    """FR-TURN-05. Another turn holds the lock, or this scene has a ruling pending."""

    code = "turn_locked"
    status_code = 409

    def __init__(self, message: str, *, scene: str | None = None) -> None:
        super().__init__(message, scene=scene)


class ContextBudgetExceeded(HarnessError):
    """FR-LLM-07, FR-CTX-05, NFR-05. The input was estimated above the 100k cap, so the call
    was not made and no process was spawned.

    Stopped and traced, never silently truncated. `counted` is the pre-call estimate of what
    the system sends (FR-CTX-02); the CLI's own overhead is never part of it (R3-5).
    """

    code = "context_budget_exceeded"
    status_code = 422

    def __init__(self, message: str, *, counted: int, cap: int) -> None:
        super().__init__(message, counted=counted, cap=cap)


class MalformedModelOutput(HarnessError):
    """FR-LLM-04. The response failed its DR-12 schema twice. Rejected, not repaired.

    The message names the failing fields and error types only, never the values: the value
    is model output, often draft prose, and NFR-10 keeps prose out of logs and error bodies.
    """

    code = "malformed_model_output"
    status_code = 502

    def __init__(self, message: str, *, role: str | None = None) -> None:
        super().__init__(message, role=role)


class ModelRefused(HarnessError):
    """FR-LLM-06. `stop_reason: refusal`. Carries the category when the provider gives one
    (the envelope's `stop_details.category`); not retried, and not retried against a
    different model in v1. The turn escalates with the category (AC 21)."""

    code = "model_refused"
    status_code = 502

    def __init__(
        self, message: str, *, category: str | None = None, role: str | None = None
    ) -> None:
        super().__init__(message, category=category, role=role)


class OutputTruncated(HarnessError):
    """FR-LLM-06. `stop_reason: max_tokens`. Retried once as it was sent -- the CLI exposes
    no output-length setting the backend controls -- and reaching the caller means the retry
    was truncated too."""

    code = "output_truncated"
    status_code = 502

    def __init__(self, message: str, *, role: str | None = None) -> None:
        super().__init__(message, role=role)


class ModelCallFailed(HarnessError):
    """FR-LLM-08, IF-07. The model call failed for a reason that is neither a refusal nor
    malformed output: the Claude Code CLI is missing, it exited without a readable result,
    it timed out, or the provider answered with an API error status.

    A 502 like the other model errors in IF-07, because the backend is the gateway and the
    fault is upstream of it. `reason` is a short machine-readable code (`cli_missing`,
    `timeout`, `unparseable`, `cli_error`, `rate_limited`, `api_error`, ...) and `status` is
    the provider's status when there was one. A step that fails this way escalates; it is
    never swallowed into an empty draft.
    """

    code = "model_call_failed"
    status_code = 502

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        role: str | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message, reason=reason, role=role, status=status)


async def harness_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Single handler for the whole hierarchy: each type carries its own status code, so
    adding an error type never means editing a dispatch table."""
    del request
    if not isinstance(exc, HarnessError):  # pragma: no cover - defensive, Starlette-typed
        raise exc
    return JSONResponse(status_code=exc.status_code, content=exc.as_body())


def register_exception_handlers(app: FastAPI) -> None:
    """Mount the handler. Called by the app factory, never at import time."""
    app.add_exception_handler(HarnessError, harness_error_handler)


__all__ = [
    "ContextBudgetExceeded",
    "ErrorContextValue",
    "HarnessError",
    "IndexBusy",
    "InvalidRecord",
    "InvalidRole",
    "MalformedModelOutput",
    "ModelCallFailed",
    "ModelRefused",
    "NotFound",
    "OutputTruncated",
    "PermissionDenied",
    "TurnLocked",
    "harness_error_handler",
    "register_exception_handlers",
]
