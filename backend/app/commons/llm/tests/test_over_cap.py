"""AC 35: `over_cap` reads the real count with the CLI's overhead subtracted (FR-CTX-06, R3-5).

The cap is whole over what the system sends; what `claude -p` adds to every call (its
structured-output tool, environment details, the organisation's managed instructions) is a
fixed cost outside it. So after a call the real input count -- uncached, cache-read and
cache-creation tokens together, because cached tokens are still context -- is compared to the
cap only once `CLI_OVERHEAD_TOKENS` is subtracted. A real count above 100k but within 100k plus
the overhead is a call that kept the rule; above that, the pre-call estimate was wrong, which is
marked rather than silent. And the estimate itself never carries the overhead: an empty call
estimates at zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.llm.fake import FakeModelClient, Reply
from app.commons.llm.protocol import Usage
from app.commons.llm.tests.test_claude_code_command import (
    DOCUMENTS,
    INSTRUCTION,
    SYSTEM,
    envelope,
    harness,
    writer_payload,
)
from app.commons.llm.tokens import CLI_OVERHEAD_TOKENS, estimate_input
from app.commons.permissions import AgentRole
from app.commons.schemas.role_outputs import WriterOutput

LIMIT = CONTEXT_TOKEN_CAP + CLI_OVERHEAD_TOKENS


def split(total: int) -> dict[str, int]:
    """A real input count spread over the three input fields, the way a cached call reports
    it: most of the context read from cache, some written to it, a little uncached."""
    cache_read = total // 2
    cache_creation = total // 3
    return {
        "input_tokens": total - cache_read - cache_creation,
        "output_tokens": 900,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
    }


def live_over_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real: int) -> bool:
    h = harness(tmp_path, monkeypatch, envelope(usage=split(real)))
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.usage.context_tokens == real
    return completion.over_cap


# spec 001 / AC 35 -- above cap + overhead: marked. Within it, even above 100k: not marked.
@pytest.mark.parametrize(
    ("real", "over"),
    [
        (LIMIT + 1, True),
        (LIMIT + 50_000, True),
        (LIMIT, False),
        (CONTEXT_TOKEN_CAP + 1, False),
        (CONTEXT_TOKEN_CAP, False),
        (2_372, False),
    ],
    ids=["one-over", "far-over", "exactly-cap-plus-overhead", "cap-plus-one", "cap", "empty-call"],
)
def test_over_cap_subtracts_the_cli_overhead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real: int, over: bool
) -> None:
    assert live_over_cap(tmp_path, monkeypatch, real) is over


# spec 001 / AC 35 -- cached tokens are context: a call whose uncached input is tiny but whose
# cache reads carry the context over the limit is still over.
def test_cache_reads_count_toward_the_real_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = {"input_tokens": 3, "output_tokens": 10, "cache_read_input_tokens": LIMIT}
    h = harness(tmp_path, monkeypatch, envelope(usage=usage))
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.over_cap is True


# spec 001 / AC 35, FR-CTX-02 -- the estimate of an empty call is zero, for both clients.
def test_the_estimate_of_an_empty_call_is_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    assert h.client.estimate_input_tokens("", [], "") == 0
    assert FakeModelClient().estimate_input_tokens("", [], "") == 0
    completion = h.client.complete(
        role=AgentRole.WRITER, system="", documents=[], instruction="", output_schema=WriterOutput
    )
    assert completion.estimate == 0


# spec 001 / AC 35, FR-CTX-02 -- the recorded estimate is exactly what the system sends, with
# no overhead added.
def test_the_recorded_estimate_carries_no_overhead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    completion = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    expected = estimate_input(SYSTEM, [d.text for d in DOCUMENTS], INSTRUCTION)
    assert completion.estimate == expected
    assert completion.estimate < CLI_OVERHEAD_TOKENS, "a small call carries no hidden overhead"


# spec 001 / AC 35 -- the fake reads a scripted usage report the same way, so the turn record's
# `over_cap` can be tested at the turn level.
@pytest.mark.parametrize(("real", "over"), [(LIMIT + 1, True), (LIMIT, False)])
def test_the_fake_reads_a_usage_report_the_same_way(real: int, over: bool) -> None:
    fake = FakeModelClient([Reply(writer_payload(), usage=Usage(cache_read_input_tokens=real))])
    completion = fake.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert completion.over_cap is over


# spec 001 / AC 35 -- a client with a lowered cap reads `over_cap` against that cap.
def test_a_lowered_cap_is_the_cap_over_cap_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = {"input_tokens": 1_000 + CLI_OVERHEAD_TOKENS + 1}
    h = harness(tmp_path, monkeypatch, envelope(usage=real), cap=1_000)
    completion = h.client.complete(
        role=AgentRole.WRITER, system="", documents=[], instruction="", output_schema=WriterOutput
    )
    assert completion.over_cap is True
