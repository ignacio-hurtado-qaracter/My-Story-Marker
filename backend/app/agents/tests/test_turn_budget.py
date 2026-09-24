"""Plan step 18 -- AC 22 at the turn level: an estimate over the cap makes no call.

The cap is lowered, never raised (NFR-05, plan P7), in the two places a turn can meet it: the
turn's own cap, which the assembly checks with the writer's real system prompt and instruction
before any call (FR-OPS-03, FR-CTX-05), and the client's, which refuses a call over it before it
is made (FR-LLM-07). Either way the fake's log holds **zero** completed calls and the turn ends
`escalated` with `context_budget_exceeded`, the estimate on the record.
"""

from __future__ import annotations

import pytest

from app.agents.tests.test_turn_happy import TurnEnv, make_turn_env, scripted
from app.commons.llm import FakeModelClient
from app.commons.schemas import EscalationCategory, StepStatus, TurnOutcome, TurnStep
from app.commons.stores import Store


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


# spec 001 / AC 22, FR-CTX-05 -- the turn's cap below the writer's mandatory part: assembly stops
# the turn before any call.
def test_a_context_over_the_turn_cap_escalates_with_no_call(turn_env: TurnEnv) -> None:
    client = FakeModelClient()
    record = turn_env.run(client, cap=500)

    assert client.calls == []
    assert client.refused_over_cap == []
    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.CONTEXT_BUDGET_EXCEEDED
    assert record.escalation.step is TurnStep.ASSEMBLE
    [assemble] = record.steps
    assert assemble.status is StepStatus.FAILED
    assert assemble.estimate is not None and assemble.estimate > 500
    assert record.selected, "the selected list was recorded before the budget stopped the turn"


# spec 001 / AC 22, FR-LLM-07 -- the client's cap below the call: the call is refused before it is
# made, and it is not in the log of calls made.
def test_a_call_over_the_client_cap_is_never_made(turn_env: TurnEnv) -> None:
    client = scripted("happy_002", cap=1_000)
    record = turn_env.run(client)

    assert client.calls == []
    [refused] = client.refused_over_cap
    assert refused.estimate > 1_000
    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.CONTEXT_BUDGET_EXCEEDED
    assert record.escalation.step is TurnStep.WRITE
    assert record.steps[-1].estimate == refused.estimate
