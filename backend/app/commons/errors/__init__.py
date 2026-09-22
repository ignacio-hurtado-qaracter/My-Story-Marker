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
    """FR-LLM-07, NFR-05. The prompt counted above the 100k cap, so the call was not made.

    Stopped and traced, never silently truncated.
    """

    code = "context_budget_exceeded"
    status_code = 422

    def __init__(self, message: str, *, counted: int, cap: int) -> None:
        super().__init__(message, counted=counted, cap=cap)


class MalformedModelOutput(HarnessError):
    """FR-LLM-04. The response failed its DR-12 schema twice. Rejected, not repaired."""

    code = "malformed_model_output"
    status_code = 502

    def __init__(self, message: str, *, role: str | None = None) -> None:
        super().__init__(message, role=role)


class ModelRefused(HarnessError):
    """FR-LLM-06. `stop_reason: refusal`. Carries the category when the provider gives one;
    not retried against a different model in v1."""

    code = "model_refused"
    status_code = 502

    def __init__(
        self, message: str, *, category: str | None = None, role: str | None = None
    ) -> None:
        super().__init__(message, category=category, role=role)


class OutputTruncated(HarnessError):
    """FR-LLM-06. `stop_reason: max_tokens`. Retried once with more headroom; reaching the
    caller means the retry was truncated too."""

    code = "output_truncated"
    status_code = 502

    def __init__(self, message: str, *, role: str | None = None) -> None:
        super().__init__(message, role=role)


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
    "MalformedModelOutput",
    "ModelRefused",
    "NotFound",
    "OutputTruncated",
    "PermissionDenied",
    "TurnLocked",
    "harness_error_handler",
    "register_exception_handlers",
]
