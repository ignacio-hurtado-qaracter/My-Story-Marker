"""Plan step 18 -- AC 21 at the turn level: a malformed answer and a refusal end the turn.

`test_roles.py` pins the role half (every role call retries a schema-invalid answer once, then
fails `MalformedModelOutput`, and surfaces a refusal with its category). Here the same failures
arrive in the middle of a turn, and what is checked is what the turn does with them: it ends
`escalated` with the IF-07 category on the record, the step that failed writes nothing -- above
all nothing to `manuscript/` -- and the lock is released. Never an empty draft.
"""

from __future__ import annotations

import pytest

from app.agents import lock
from app.agents.tests.test_turn_happy import (
    TurnEnv,
    load_script,
    make_turn_env,
    scripted,
    scripted_text,
    tree_digest,
)
from app.commons.llm import FakeModelClient, Refusal, Reply
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Draft,
    EscalationCategory,
    StepStatus,
    TurnOutcome,
    TurnStep,
)
from app.commons.stores import Store, paths


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def manuscript(store: Store) -> dict[str, str]:
    return tree_digest(store, paths.MANUSCRIPT)


# spec 001 / AC 21 -- a schema-invalid write: retried once, then MalformedModelOutput; the turn
# escalates and nothing is written to manuscript/.
def test_a_schema_invalid_write_escalates_and_leaves_the_manuscript_untouched(
    turn_env: TurnEnv,
) -> None:
    before = manuscript(turn_env.store)
    client = scripted("malformed_writer")
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.MALFORMED_MODEL_OUTPUT
    assert record.escalation.step is TurnStep.WRITE
    [call] = client.calls
    assert call.attempts == 2, "retried exactly once"
    failed = record.steps[-1]
    assert (failed.step, failed.status, failed.writes) == (TurnStep.WRITE, StepStatus.FAILED, [])
    assert manuscript(turn_env.store) == before
    assert turn_env.store.provenance() == []
    assert not lock.lock_path(turn_env.store.index_dir).exists()


# spec 001 / AC 21 -- a schema-invalid polish: nothing is written to manuscript/ by that step; the
# draft on disk is still the one the writer wrote.
def test_a_schema_invalid_polish_writes_nothing_to_the_manuscript(turn_env: TurnEnv) -> None:
    script = load_script("happy_002")
    script[AgentRole.STYLE_EDITOR] = [Reply(payload={"text": "x"}), Reply(payload={"body": 7})]
    record = turn_env.run(FakeModelClient(script))

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.MALFORMED_MODEL_OUTPUT
    assert record.escalation.step is TurnStep.POLISH
    written = scripted_text("happy_002", AgentRole.WRITER, 0, "body")
    assert turn_env.store.read(paths.draft("002"), Draft).body == written
    polish_lines = [
        line for line in turn_env.store.provenance() if line.role is AgentRole.STYLE_EDITOR
    ]
    assert polish_lines == []


# spec 001 / AC 21, FR-LLM-06 -- a refusal is not retried and the turn escalates with its category.
def test_a_refusal_escalates_with_its_category(turn_env: TurnEnv) -> None:
    before = manuscript(turn_env.store)
    client = scripted("refusal_writer")
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.MODEL_REFUSED
    assert record.escalation.refusal_category == "violent_content"
    assert record.escalation.step is TurnStep.WRITE
    [call] = client.calls
    assert call.attempts == 1, "a refusal is never retried"
    assert manuscript(turn_env.store) == before


# spec 001 / AC 21 -- a refusal with no category still escalates, and says it had none.
def test_a_refusal_without_a_category_escalates(turn_env: TurnEnv) -> None:
    script = load_script("happy_002")
    script[AgentRole.CANONISER] = [Refusal()]
    record = turn_env.run(FakeModelClient(script))

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.MODEL_REFUSED
    assert record.escalation.refusal_category is None
    assert record.escalation.step is TurnStep.EXTRACT
    assert record.escalation.detail == "model_refused role=canoniser"  # NFR-10: no message
