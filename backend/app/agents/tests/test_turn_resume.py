"""Plan step 18 -- AC 24, FR-TURN-09: a turn killed after its write step resumes from its record.

The record is written after every step (FR-TURN-07) and doubles as the turn's cursor, so a turn a
crash interrupted is continued by `POST /agents/turns/{id}/resume` from where it stopped. The kill
is scripted: the fake raises -- an exception that is not a harness error, which the orchestrator
treats as a crash rather than an escalation -- on the first auditor call, after the write step has
landed and been recorded. The resume runs audit onward, and the fake's log shows exactly one
`write` call across both runs.

A process that dies outright leaves the lock file behind; resuming the very turn it names takes
it over, and nothing else does (FR-TURN-05).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents import lock, records
from app.agents.tests.test_turn_happy import (
    HAPPY_STEPS,
    TurnEnv,
    load_script,
    make_turn_env,
    scripted,
    sse_events,
    use,
)
from app.commons.errors import TurnLocked
from app.commons.llm import FakeCall, FakeModelClient, Outcome
from app.commons.permissions import AgentRole
from app.commons.schemas import TurnOutcome, TurnStep
from app.commons.stores import Store


class ProcessKilledError(RuntimeError):
    """Stands for the process dying mid-turn: not a harness error, so not an escalation."""


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def killed_at_first_audit() -> FakeModelClient:
    """The happy script, except that the first auditor call kills the process; the auditor's
    answer is served from the fallback after that."""
    script = load_script("happy_002")
    [clean] = script.pop(AgentRole.AUDITOR)
    killed: list[bool] = []

    def auditor(call: FakeCall) -> Outcome:
        if not killed:
            killed.append(True)
            message = "the process was killed during the audit"
            raise ProcessKilledError(message)
        return clean

    return FakeModelClient(script, fallback=auditor)


def write_calls(client: FakeModelClient) -> list[FakeCall]:
    return [call for call in client.calls if call.output_schema == "WriterOutput"]


# spec 001 / AC 24, FR-TURN-09 -- killed after the write step, resumed: audit onward, one write.
def test_a_turn_killed_after_the_write_step_resumes_without_a_second_write(
    turn_env: TurnEnv,
) -> None:
    client = killed_at_first_audit()
    with pytest.raises(ProcessKilledError):
        turn_env.run(client)

    interrupted = records.load(turn_env.store, "002-1")
    assert interrupted.outcome is TurnOutcome.RUNNING
    assert interrupted.next_step is TurnStep.AUDIT
    assert [step.step for step in interrupted.steps] == [TurnStep.ASSEMBLE, TurnStep.WRITE]
    assert not lock.lock_path(turn_env.store.index_dir).exists()

    record = turn_env.resume(client, "002-1")

    assert record.outcome is TurnOutcome.MERGED
    assert len(write_calls(client)) == 1, "the write step was not run again"
    assert [step.step for step in record.steps] == HAPPY_STEPS
    assert record.selected == interrupted.selected, "selection is not re-run either"
    assert client.pending() == 0


# spec 001 / AC 24, IF-06 -- the resume route streams the remaining steps only.
def test_the_resume_route_streams_the_remaining_steps(
    fixture_client: TestClient, turn_env: TurnEnv
) -> None:
    client = killed_at_first_audit()
    with pytest.raises(ProcessKilledError):
        turn_env.run(client)
    use(fixture_client, client)

    response = fixture_client.post("/agents/turns/002-1/resume")

    assert response.status_code == 200
    events = sse_events(response.text)
    assert [data["step"] for kind, data in events if kind == "step"] == [
        step.value for step in HAPPY_STEPS[2:]
    ]
    assert events[-1][1]["outcome"] == "merged"
    assert len(write_calls(client)) == 1


# spec 001 / FR-TURN-09 -- a turn that ended is not resumable; a missing one is a 404.
def test_only_a_running_turn_can_be_resumed(fixture_client: TestClient, turn_env: TurnEnv) -> None:
    merged = turn_env.run(scripted("happy_002"))
    fake = FakeModelClient()
    use(fixture_client, fake)

    ended = fixture_client.post(f"/agents/turns/{merged.id}/resume")
    assert ended.status_code == 409
    assert ended.json()["error"] == "turn_locked"
    missing = fixture_client.post("/agents/turns/002-5/resume")
    assert missing.status_code == 404
    assert fake.calls == []


# spec 001 / FR-TURN-05, FR-TURN-09 -- the lock a crashed process left behind is taken over by
# resuming the turn it names, and by nothing else.
def test_a_stale_lock_is_taken_over_by_resuming_its_own_turn(turn_env: TurnEnv) -> None:
    client = killed_at_first_audit()
    with pytest.raises(ProcessKilledError):
        turn_env.run(client)
    stale = lock.lock_path(turn_env.store.index_dir)
    stale.write_text("002-1\n", encoding="utf-8")  # what a process killed outright leaves

    with pytest.raises(TurnLocked, match="002-1"):
        turn_env.run(scripted("happy_002"), "006")

    record = turn_env.resume(client, "002-1")
    assert record.outcome is TurnOutcome.MERGED
    assert not stale.exists()


# spec 001 / FR-TURN-05 -- resuming a turn does not take over a lock that names another turn:
# nothing proves that turn is not running, so the resume is refused and the lock stays.
def test_resuming_does_not_take_over_another_turns_lock(turn_env: TurnEnv) -> None:
    client = killed_at_first_audit()
    with pytest.raises(ProcessKilledError):
        turn_env.run(client)
    held = lock.lock_path(turn_env.store.index_dir)
    held.write_text("006-1\n", encoding="utf-8")

    with pytest.raises(TurnLocked, match="006-1"):
        turn_env.resume(client, "002-1")

    assert held.read_text(encoding="utf-8") == "006-1\n"
    assert records.load(turn_env.store, "002-1").next_step is TurnStep.AUDIT
    assert len(write_calls(client)) == 1


# spec 001 / FR-TURN-05 -- a lock held by a turn running in this process is never taken over.
def test_a_running_turn_cannot_be_resumed_beside_itself(turn_env: TurnEnv) -> None:
    refusals: list[TurnLocked] = []
    script = load_script("happy_002")
    written, digested = script.pop(AgentRole.WRITER)

    def writer(call: FakeCall) -> Outcome:
        if call.output_schema != "WriterOutput":
            return digested
        try:
            turn_env.resume(FakeModelClient(), "002-1")
        except TurnLocked as refusal:
            refusals.append(refusal)
        return written

    record = turn_env.run(FakeModelClient(script, fallback=writer))

    assert record.outcome is TurnOutcome.MERGED
    [refusal] = refusals
    assert "running" in refusal.message
