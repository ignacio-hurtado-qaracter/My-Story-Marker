"""AC 21 (structured output half): validated, never repaired, retried exactly once.

FR-LLM-04: the CLI's `structured_output` is validated against the role's DR-12 model; an
output that fails is rejected, the call is retried once, and then the step fails with
`MalformedModelOutput`. The same holds for the process-level failures FR-LLM-08 retries once
(no readable envelope, a timeout, an error envelope). And the envelope is read for what the
turn record needs: the real model id from `modelUsage` (FR-LLM-03) and every usage field,
cache reads included (FR-LLM-09).

Run against the live client with a recorder in place of the subprocess, and against the fake,
which settles its scripts through the same policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import JsonValue

from app.commons.errors import MalformedModelOutput, ModelCallFailed
from app.commons.llm.claude_code_client import RunResult
from app.commons.llm.fake import FakeModelClient, ProcessFailure, Reply
from app.commons.llm.protocol import Usage
from app.commons.llm.tests.test_claude_code_command import (
    DOCUMENTS,
    INSTRUCTION,
    REAL_MODEL,
    SYSTEM,
    Harness,
    envelope,
    harness,
    writer_payload,
)
from app.commons.permissions import AgentRole
from app.commons.schemas.role_outputs import WriterOutput

SECRET_PROSE = "PROSE-THAT-MUST-NOT-LEAK"


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


INVALID_OUTPUTS: list[JsonValue] = [
    {"body": SECRET_PROSE},
    {"body": "", "proposed_facts": []},
    {"body": SECRET_PROSE, "proposed_facts": [], "status": "promoted"},
    {"body": SECRET_PROSE, "proposed_facts": [{"target_entity": "Not An Id"}]},
    "just a string",
    [],
]
INVALID_IDS = ["missing-field", "empty-body", "extra-key", "bad-nested", "string", "list"]


# spec 001 / AC 21 -- a valid output is returned, with the real model id and every usage field.
def test_a_valid_output_is_read_with_model_id_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = {
        "input_tokens": 7,
        "output_tokens": 420,
        "cache_read_input_tokens": 3000,
        "cache_creation_input_tokens": 1200,
    }
    h = harness(tmp_path, monkeypatch, envelope(usage=usage))
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )

    assert completion.output == WriterOutput.model_validate(writer_payload())
    assert completion.model_id == REAL_MODEL
    assert completion.requested_model == "claude-haiku-4-5"
    assert completion.usage == Usage(**usage)
    assert completion.usage.context_tokens == 7 + 3000 + 1200
    assert completion.attempts == 1
    assert completion.num_turns == 2
    assert completion.role is AgentRole.WRITER
    assert completion.elapsed_seconds >= 0


# spec 001 / AC 21 -- schema-invalid twice: exactly one retry, then MalformedModelOutput. The
# error names fields, never the model's text (NFR-10).
@pytest.mark.parametrize("invalid", INVALID_OUTPUTS, ids=INVALID_IDS)
def test_invalid_output_is_retried_once_then_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: JsonValue
) -> None:
    h = harness(tmp_path, monkeypatch, envelope(invalid), envelope(invalid), envelope())
    with pytest.raises(MalformedModelOutput) as raised:
        call(h)

    assert len(h.recorder.calls) == 2, "one call and exactly one retry"
    assert len(h.recorder.responses) == 1, "the third response was never asked for"
    assert raised.value.status_code == 502
    assert raised.value.context["role"] == "writer"
    assert SECRET_PROSE not in raised.value.message


# spec 001 / AC 21 -- invalid once, valid on the retry: the call settles on attempt two.
def test_invalid_then_valid_settles_on_the_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope({"body": SECRET_PROSE}), envelope())
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.attempts == 2
    assert completion.output.body == writer_payload()["body"]


# spec 001 / AC 21 -- an envelope with no structured output at all is malformed, not empty.
def test_a_missing_structured_output_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = envelope(omit_structured_output=True, result="Here is your scene...")
    h = harness(tmp_path, monkeypatch, missing, missing)
    with pytest.raises(MalformedModelOutput):
        call(h)
    assert len(h.recorder.calls) == 2


# spec 001 / AC 21, FR-LLM-04 -- the CLI's own `--json-schema` validation rejecting every output
# (`error_max_structured_output_retries`, Claude Code 2.1.273) is malformed output: one retry,
# then MalformedModelOutput, not a generic CLI error.
def test_a_cli_rejected_structured_output_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejected = envelope(
        subtype="error_max_structured_output_retries",
        is_error=True,
        stop_reason="end_turn",
        omit_structured_output=True,
        result=SECRET_PROSE,
    )
    h = harness(tmp_path, monkeypatch, rejected, rejected, envelope())
    with pytest.raises(MalformedModelOutput) as raised:
        call(h)
    assert len(h.recorder.calls) == 2, "one call and exactly one retry"
    assert "WriterOutput" in raised.value.message
    assert SECRET_PROSE not in raised.value.message


# spec 001 / AC 21 -- never repaired: a key the schema forbids is not dropped to make it fit.
def test_an_extra_key_is_rejected_rather_than_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra: JsonValue = {**writer_payload(), "status": "promoted"}
    h = harness(tmp_path, monkeypatch, envelope(extra), envelope(extra))
    with pytest.raises(MalformedModelOutput, match="status"):
        call(h)


# spec 001 / AC 21 -- the fake applies the same policy to a scripted invalid output.
def test_the_fake_retries_an_invalid_output_once_then_fails() -> None:
    fake = FakeModelClient([Reply({"body": SECRET_PROSE}), Reply({"body": SECRET_PROSE})])
    with pytest.raises(MalformedModelOutput):
        fake_call(fake)
    [logged] = fake.calls
    assert logged.attempts == 2


# spec 001 / AC 21 -- and settles when the retry is valid.
def test_the_fake_settles_on_a_valid_retry() -> None:
    fake = FakeModelClient([Reply({"body": SECRET_PROSE}), Reply(writer_payload())])
    assert fake_call(fake).body == writer_payload()["body"]
    assert fake.calls[0].attempts == 2


# spec 001 / AC 21, FR-LLM-03 -- with more than one model in `modelUsage`, the one that wrote
# the answer (the most output) is recorded.
def test_the_model_that_wrote_the_answer_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_usage = {
        "claude-haiku-4-5-20251001": {"inputTokens": 900, "outputTokens": 800},
        "claude-other-helper": {"inputTokens": 50, "outputTokens": 5},
    }
    h = harness(tmp_path, monkeypatch, envelope(model_usage=model_usage))
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.model_id == "claude-haiku-4-5-20251001"


# spec 001 / AC 21, FR-LLM-03 -- a CLI that reports no model leaves the id unknown, visibly,
# rather than recording the requested alias as if it had been confirmed.
def test_no_model_usage_leaves_the_model_id_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope(model_usage={}))
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.model_id is None
    assert completion.requested_model == "claude-haiku-4-5"


# spec 001 / AC 21, FR-LLM-08 -- no readable envelope, a timeout or a failed exit: retried once,
# then ModelCallFailed naming the reason.
@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (RunResult(returncode=0, stdout="not json", stderr=""), "unparseable"),
        (RunResult(returncode=0, stdout="", stderr=""), "unparseable"),
        (RunResult(returncode=0, stdout='{"level": "warn"}', stderr=""), "unparseable"),
        (RunResult(returncode=1, stdout="", stderr="Error: not logged in"), "exit_status"),
        (RunResult(returncode=None, stdout="", stderr="", timed_out=True), "timeout"),
        (
            RunResult(
                returncode=1,
                stdout=envelope(is_error=True, subtype="error_during_execution"),
                stderr="",
            ),
            "cli_error",
        ),
        (RunResult(returncode=1, stdout=envelope(), stderr=""), "cli_error"),
    ],
    ids=[
        "garbage",
        "empty",
        "not-a-result-object",
        "exit-1",
        "timeout",
        "error-envelope",
        "success-but-exit-1",
    ],
)
def test_process_failures_are_retried_once_then_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: RunResult, reason: str
) -> None:
    h = harness(tmp_path, monkeypatch, result, result, envelope())
    with pytest.raises(ModelCallFailed) as raised:
        call(h)
    assert raised.value.context["reason"] == reason
    assert len(h.recorder.calls) == 2


# spec 001 / AC 21, NFR-10 -- a failed call quotes the CLI's error text, never the model's
# answer: `result` is error text only when `is_error` is set.
def test_a_process_failure_never_quotes_the_model_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answered = RunResult(returncode=1, stdout=envelope(result=SECRET_PROSE), stderr="boom")
    h = harness(tmp_path, monkeypatch, answered, answered)
    with pytest.raises(ModelCallFailed) as raised:
        call(h)
    assert SECRET_PROSE not in raised.value.message
    assert "boom" in raised.value.message

    limit = envelope(is_error=True, result="Claude AI usage limit reached")
    second = tmp_path / "second"
    second.mkdir()
    h = harness(second, monkeypatch, limit, limit)
    with pytest.raises(ModelCallFailed) as raised:
        call(h)
    assert "usage limit reached" in raised.value.message


# spec 001 / AC 21, FR-LLM-08 -- one process failure followed by a good call settles.
def test_a_single_process_failure_is_survived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeout = RunResult(returncode=None, stdout="", stderr="", timed_out=True)
    h = harness(tmp_path, monkeypatch, timeout, envelope())
    assert call(h).body == writer_payload()["body"]


# spec 001 / AC 21, FR-LLM-08 -- the fake's process failure follows the same policy.
def test_the_fake_retries_a_process_failure_once() -> None:
    fake = FakeModelClient([ProcessFailure("timeout"), ProcessFailure("timeout")])
    with pytest.raises(ModelCallFailed) as raised:
        fake_call(fake)
    assert raised.value.context["reason"] == "timeout"


# spec 001 / AC 21 -- an envelope preceded by stray output lines is still read.
def test_an_envelope_after_stray_lines_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    noisy = "warning: something the CLI printed first\n" + envelope()
    h = harness(tmp_path, monkeypatch, noisy)
    assert call(h).body == writer_payload()["body"]
