"""AC 21 (envelope half): refusals, truncation and API error statuses, classified before the
structured output is read.

FR-LLM-06: `stop_reason: refusal` fails the step with `ModelRefused` carrying the category and
is never retried; `stop_reason: max_tokens` fails with `OutputTruncated` after one retry.
FR-LLM-08: a rate-limit or overload status is retried with backoff, any other API error status
fails at once. All of it happens before `structured_output` is looked at, so a refusal whose
envelope happens to carry a leftover object is still a refusal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from app.commons.errors import ModelCallFailed, ModelRefused, OutputTruncated
from app.commons.llm.errors import RETRY_ALLOWANCE, RetryKind, backoff_delay
from app.commons.llm.fake import ApiError, FakeModelClient, RateLimited, Refusal, Reply, Truncation
from app.commons.llm.tests.test_claude_code_command import (
    DOCUMENTS,
    INSTRUCTION,
    SYSTEM,
    Harness,
    envelope,
    harness,
    writer_payload,
)
from app.commons.permissions import AgentRole
from app.commons.schemas.role_outputs import WriterOutput


def call(h: Harness) -> WriterOutput:
    return h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    ).output


def fake_call(fake: FakeModelClient) -> WriterOutput:
    return fake.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    ).output


def refusal(category: str | None) -> str:
    details: JsonValue = (
        {"type": "refusal", "category": category, "explanation": "declined"}
        if category is not None
        else None
    )
    return envelope(stop_reason="refusal", stop_details=details)


# spec 001 / AC 21 -- a refusal fails the step with its category, and is not retried.
def test_a_refusal_carries_its_category_and_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, refusal("cyber"), envelope())
    with pytest.raises(ModelRefused) as raised:
        call(h)

    assert raised.value.context["category"] == "cyber"
    assert raised.value.context["role"] == "writer"
    assert raised.value.status_code == 502
    assert raised.value.as_body()["error"] == "model_refused"
    assert len(h.recorder.calls) == 1, "a refusal is never retried"


# spec 001 / AC 21 -- a refusal without a category still refuses; the category is None.
def test_a_refusal_without_a_category(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = harness(tmp_path, monkeypatch, refusal(None))
    with pytest.raises(ModelRefused) as raised:
        call(h)
    assert raised.value.context["category"] is None


# spec 001 / AC 21 -- the refusal is read before the structured output: a leftover object in a
# refused envelope is not accepted as an answer.
def test_a_refusal_wins_over_a_leftover_structured_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused_with_object = envelope(
        writer_payload(),
        stop_reason="refusal",
        stop_details={"type": "refusal", "category": "bio"},
    )
    h = harness(tmp_path, monkeypatch, refused_with_object)
    with pytest.raises(ModelRefused) as raised:
        call(h)
    assert raised.value.context["category"] == "bio"


# spec 001 / AC 21 -- the fake refuses the same way.
def test_the_fake_refuses_with_its_category() -> None:
    fake = FakeModelClient([Refusal("reasoning_extraction"), Reply(writer_payload())])
    with pytest.raises(ModelRefused) as raised:
        fake_call(fake)
    assert raised.value.context["category"] == "reasoning_extraction"
    assert fake.pending() == 1, "not retried"


# spec 001 / AC 21 -- max_tokens: one retry, then OutputTruncated.
def test_a_truncation_is_retried_once_then_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cut = envelope(stop_reason="max_tokens")
    h = harness(tmp_path, monkeypatch, cut, cut, envelope())
    with pytest.raises(OutputTruncated):
        call(h)
    assert len(h.recorder.calls) == 2


# spec 001 / AC 21 -- a truncation followed by a complete answer settles on the retry.
def test_a_single_truncation_is_survived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = harness(tmp_path, monkeypatch, envelope(stop_reason="max_tokens"), envelope())
    assert call(h).body == writer_payload()["body"]
    assert len(h.recorder.calls) == 2


# spec 001 / AC 21 -- the fake's truncation follows the same policy.
def test_the_fake_retries_a_truncation_once() -> None:
    fake = FakeModelClient([Truncation(), Truncation()])
    with pytest.raises(OutputTruncated):
        fake_call(fake)
    assert fake.calls[0].attempts == 2


# spec 001 / AC 21, FR-LLM-08 -- a rate limit or overload is retried with backoff.
@pytest.mark.parametrize("status", [429, 529, "429"], ids=["429", "529", "429-as-text"])
def test_a_rate_limit_is_retried_with_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: JsonValue
) -> None:
    limited = envelope(is_error=True, api_error_status=status, result="rate limited")
    h = harness(tmp_path, monkeypatch, limited, envelope())
    assert call(h).body == writer_payload()["body"]
    assert h.sleeps == [backoff_delay(1)] == [2.0]


# spec 001 / AC 21, FR-LLM-08 -- a rate limit that never lifts fails after the allowance, having
# waited 2, 4 and 8 seconds.
def test_a_persistent_rate_limit_fails_after_its_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowance = RETRY_ALLOWANCE[RetryKind.RATE_LIMITED]
    limited = envelope(is_error=True, api_error_status=429, result="Claude usage limit reached")
    h = harness(tmp_path, monkeypatch, *([limited] * (allowance + 1)), envelope())
    with pytest.raises(ModelCallFailed) as raised:
        call(h)

    assert raised.value.context["reason"] == "rate_limited"
    assert raised.value.context["status"] == 429
    assert "usage limit reached" in raised.value.message, "the CLI's own message is kept"
    assert len(h.recorder.calls) == allowance + 1
    assert h.sleeps == [2.0, 4.0, 8.0]


# spec 001 / AC 21, FR-LLM-08 -- any other API error status fails at once, with the status.
@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
def test_any_other_api_error_fails_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    failed = envelope(is_error=True, api_error_status=status, result="API Error")
    h = harness(tmp_path, monkeypatch, failed, envelope())
    with pytest.raises(ModelCallFailed) as raised:
        call(h)
    assert raised.value.context == {"reason": "api_error", "role": "writer", "status": status}
    assert raised.value.status_code == 502
    assert len(h.recorder.calls) == 1
    assert h.sleeps == []


# spec 001 / AC 21, FR-LLM-08 -- the fake's statuses follow the same policy.
def test_the_fake_statuses_follow_the_same_policy() -> None:
    limited = FakeModelClient([RateLimited(529), Reply(writer_payload())])
    assert fake_call(limited).body == writer_payload()["body"]
    assert limited.sleeps == [2.0]

    failing = FakeModelClient([ApiError(500), Reply(writer_payload())])
    with pytest.raises(ModelCallFailed) as raised:
        fake_call(failing)
    assert raised.value.context["status"] == 500
    assert failing.pending() == 1


# spec 001 / FR-LLM-08 -- the backoff doubles and is capped.
def test_the_backoff_doubles_and_is_capped() -> None:
    assert [backoff_delay(n) for n in range(1, 7)] == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
