"""Plan step 18 -- the turns that end `escalated`, and the lock (AC 19, FR-TURN-02, -05,
FR-AGENT-02, -04, FR-LLM-06, -08).

Every path through Figure 4 ends in `merged` or `escalated`, and the revise-audit cycle is bounded
by a constant: that is the turn-termination invariant the spec's state diagram asks for. These
tests walk the escalating edges with scripted fakes -- a blocking finding that never goes away, a
revision that rewrites the scene, a polish that breaks the lexicon, a model step that fails -- and
check that each one leaves the last draft and the findings on disk, names its category on the
record, and releases the turn lock. The lock tests close the file: a second turn while one runs
is a 409, and the lock is released after an escalation and after an exception alike.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from app.agents import lock, records, turn
from app.agents.tests.test_turn_happy import (
    TurnEnv,
    load_script,
    make_turn_env,
    scripted,
    scripted_text,
    use,
)
from app.commons.errors import InvalidRecord, ModelCallFailed, TurnLocked
from app.commons.llm import (
    FakeCall,
    FakeModelClient,
    FakeScriptExhaustedError,
    Outcome,
    ProcessFailure,
    Reply,
    Truncation,
)
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Draft,
    EscalationCategory,
    Evidence,
    PolishOutput,
    ReviseOutput,
    SemanticAuditOutput,
    SemanticViolation,
    Severity,
    StepStatus,
    TurnOutcome,
    TurnStep,
    ViolationsFile,
    ViolationSource,
    WriterOutput,
)
from app.commons.stores import Store, paths

FIVE_SENTENCES = (
    "Ilan came through the throat folded at the waist. Quiej waited on the vault side. "
    "The seating was not where the paper said it was. He found it by feel. "
    "The hand he spliced with did the work."
)
"""A draft of exactly five sentences, so a revision's share of changed sentences is exact."""

THREE_OF_FIVE_CHANGED = (
    "Ilan came through the throat folded at the waist. Quiej waited on the vault side. "
    "The seating had moved since the last survey. His fingers went looking for it. "
    "The graft hand closed on the ring before he told it to."
)
"""60 % of `FIVE_SENTENCES` rewritten: over the 35 % guard of FR-AGENT-02."""


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def draft_document(call: FakeCall, scene: str = "002") -> str:
    [text] = [document.text for document in call.documents if document.path == paths.draft(scene)]
    return text


def blocking_finding(call: FakeCall) -> Outcome:
    """The auditor's answer that never goes away: invariant 6, quoting the draft's first sentence
    where it stands, blocking."""
    first = draft_document(call).split(".")[0]
    finding = SemanticViolation(
        invariant=6,
        evidence=Evidence(quote=first, offset=0),
        severity=Severity.BLOCKING,
        explanation="The seating contradicts the axiom in force.",
    )
    return Reply.of(SemanticAuditOutput(violations=[finding]))


def always_blocking(call: FakeCall) -> Outcome:
    """AC 19: every audit blocks; every revision hands the draft back unchanged, well inside the
    diff guard, so only the revision bound can end the turn."""
    if call.role is AgentRole.AUDITOR:
        return blocking_finding(call)
    if call.output_schema == ReviseOutput.__name__:
        return Reply.of(ReviseOutput(body=draft_document(call)))
    message = f"unexpected {call.role.value} call {call.output_schema}"
    raise AssertionError(message)


def write(body: str) -> Reply:
    return Reply.of(WriterOutput(body=body, proposed_facts=[]))


def calls_of(client: FakeModelClient, schema: str) -> list[FakeCall]:
    return [call for call in client.calls if call.output_schema == schema]


def lock_file(store: Store) -> bool:
    return lock.lock_path(store.index_dir).exists()


# spec 001 / AC 19, FR-TURN-02 -- a finding that never goes away: escalated after exactly three
# revisions, with the last draft and all the violations on disk.
def test_an_always_blocking_audit_escalates_after_exactly_three_revisions(
    turn_env: TurnEnv,
) -> None:
    client = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=always_blocking)
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.REVISION_BOUND
    assert record.escalation.step is TurnStep.AUDIT
    assert record.revisions == 3
    assert len(calls_of(client, "ReviseOutput")) == 3
    assert len(calls_of(client, "SemanticAuditOutput")) == 4
    assert [iteration.iteration for iteration in record.iterations] == [0, 1, 2, 3]
    assert all(iteration.blocking for iteration in record.iterations)
    assert [step.step for step in record.steps] == [
        TurnStep.ASSEMBLE,
        TurnStep.WRITE,
        *[TurnStep.AUDIT, TurnStep.REVISE] * 3,
        TurnStep.AUDIT,
    ]
    assert [step.iteration for step in record.steps if step.step is TurnStep.REVISE] == [1, 2, 3]

    store = turn_env.store
    assert store.read(paths.draft("002"), Draft).body == FIVE_SENTENCES
    on_file = store.read(paths.VIOLATIONS, ViolationsFile).violations
    blocking = [
        finding
        for finding in on_file
        if finding.scene == "002" and finding.severity is Severity.BLOCKING
    ]
    assert [finding.id for finding in blocking] == record.iterations[-1].blocking
    assert blocking[0].source is ViolationSource.MODEL
    assert not lock_file(store)
    assert calls_of(client, "PolishOutput") == [], "an escalated draft is never polished"


# spec 001 / AC 19, FR-AGENT-02 -- a revision that rewrites 60 % of the scene is rejected, retried
# once with the stronger instruction, rejected again, and the turn escalates.
def test_a_revision_that_changes_too_much_is_rejected_twice_then_escalates(
    turn_env: TurnEnv,
) -> None:
    def rewriting(call: FakeCall) -> Outcome:
        if call.role is AgentRole.AUDITOR:
            return blocking_finding(call)
        return Reply.of(ReviseOutput(body=THREE_OF_FIVE_CHANGED))

    client = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=rewriting)
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.REVISE_SCOPE
    assert record.escalation.step is TurnStep.REVISE
    first, second = calls_of(client, "ReviseOutput")
    assert "changed too much" not in first.instruction
    assert "changed too much" in second.instruction, "the retry is the stronger instruction"
    revisions = [step for step in record.steps if step.step is TurnStep.REVISE]
    assert [step.status for step in revisions] == [StepStatus.REJECTED] * 2
    for step in revisions:
        assert step.scope is not None
        assert step.scope.ratio == pytest.approx(0.6)
        assert step.scope.within is False
        assert step.writes == []
    assert record.revisions == 0, "a rejected revision is not one of the three"
    assert turn_env.store.read(paths.draft("002"), Draft).body == FIVE_SENTENCES
    assert not lock_file(turn_env.store)


# spec 001 / FR-AGENT-04 -- a polish that introduces a forbidden variant fails the re-check: the
# turn escalates, the polished draft stays, and the finding is on disk with its offset.
def test_a_polish_that_breaks_the_lexicon_fails_the_recheck(turn_env: TurnEnv) -> None:
    written = scripted_text("happy_002", AgentRole.WRITER, 0, "body")
    polished = f"{written}\n\nNobody had said where the readkey went."
    script = load_script("happy_002")
    script[AgentRole.STYLE_EDITOR] = [Reply.of(PolishOutput(body=polished))]
    client = FakeModelClient(script)
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.POLISH_RECHECK
    assert record.steps[-1].step is TurnStep.RECHECK
    assert record.steps[-1].status is StepStatus.FAILED
    assert [write.role for write in record.steps[-1].writes] == ["auditor"]

    store = turn_env.store
    body = store.read(paths.draft("002"), Draft).body
    assert body == polished, "nothing is reverted"
    [finding] = [
        finding
        for finding in store.read(paths.VIOLATIONS, ViolationsFile).violations
        if finding.scene == "002" and finding.invariant == 7
    ]
    assert finding.evidence.quote == "readkey"
    assert body[finding.evidence.offset :].startswith("readkey")
    assert finding.id in record.escalation.detail
    assert calls_of(client, "DigestOutput") == []
    assert calls_of(client, "ExtractOutput") == []


# spec 001 / FR-AGENT-04 -- a finding the accepted draft already had is not the polish's doing.
def test_a_voice_finding_the_accepted_draft_had_does_not_fail_the_recheck(
    turn_env: TurnEnv,
) -> None:
    written = f"{scripted_text('happy_002', AgentRole.WRITER, 0, 'body')} Obviously."
    polished = f"{scripted_text('happy_002', AgentRole.STYLE_EDITOR, 0, 'body')} Obviously."
    script = load_script("happy_002")
    script[AgentRole.WRITER][0] = Reply.of(WriterOutput(body=written, proposed_facts=[]))
    script[AgentRole.STYLE_EDITOR] = [Reply.of(PolishOutput(body=polished))]
    record = turn_env.run(FakeModelClient(script))

    assert record.outcome is TurnOutcome.MERGED
    [audited] = record.iterations
    assert audited.blocking == []
    recheck = next(step for step in record.steps if step.step is TurnStep.RECHECK)
    assert recheck.status is StepStatus.COMPLETED
    assert recheck.writes == []


# spec 001 / FR-AUD-09 -- in a turn, a semantic half that did not run escalates: the report is
# still written, and the draft is never accepted unjudged.
def test_a_failed_semantic_audit_escalates_with_its_category(turn_env: TurnEnv) -> None:
    script = load_script("happy_002")
    script[AgentRole.AUDITOR] = [ProcessFailure("timeout"), ProcessFailure("timeout")]
    client = FakeModelClient(script)
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is EscalationCategory.MODEL_CALL_FAILED
    assert record.escalation.reason == "timeout"
    audit = record.steps[-1]
    assert (audit.step, audit.status, audit.error) == (
        TurnStep.AUDIT,
        StepStatus.FAILED,
        "model_call_failed",
    )
    assert [write.path for write in audit.writes] == [paths.VIOLATIONS]
    [iteration] = record.iterations
    assert {skip.invariant for skip in iteration.skipped if skip.source == "model"} == {1, 3, 6, 8}
    assert calls_of(client, "PolishOutput") == []


# spec 001 / FR-LLM-06, FR-LLM-08 -- every model failure ends the turn escalated, with its
# category and never an empty draft.
@pytest.mark.parametrize(
    ("outcomes", "category"),
    [
        ([Truncation(), Truncation()], EscalationCategory.OUTPUT_TRUNCATED),
        ([ProcessFailure("unparseable")] * 2, EscalationCategory.MODEL_CALL_FAILED),
    ],
    ids=["truncated", "call-failed"],
)
def test_a_model_failure_at_the_write_step_escalates_with_its_category(
    turn_env: TurnEnv, outcomes: list[Outcome], category: EscalationCategory
) -> None:
    before = turn_env.store.read_raw(paths.draft("002"))
    record = turn_env.run(FakeModelClient({AgentRole.WRITER: outcomes}))

    assert record.outcome is TurnOutcome.ESCALATED
    assert record.escalation is not None
    assert record.escalation.category is category
    assert record.escalation.step is TurnStep.WRITE
    assert record.steps[-1].status is StepStatus.FAILED
    assert record.steps[-1].writes == []
    assert turn_env.store.read_raw(paths.draft("002")) == before
    assert not lock_file(turn_env.store)


# --- the lock (FR-TURN-05) ------------------------------------------------------------------


# spec 001 / AC 20, FR-TURN-05 -- a second turn while one runs is refused with TurnLocked: the
# lock's 409, the one refusal before a turn that add-only promotion leaves.
def test_a_second_turn_while_one_runs_is_refused(turn_env: TurnEnv) -> None:
    refusals: list[TurnLocked] = []
    script = load_script("happy_002")
    written, digested = script.pop(AgentRole.WRITER)

    def writer_starting_a_second_turn(call: FakeCall) -> Outcome:
        if call.output_schema != WriterOutput.__name__:
            return digested
        try:
            second = turn.begin_turn(
                turn_env.store, FakeModelClient(), turn_env.embedder, turn_env.settings, "003"
            )
        except TurnLocked as refusal:
            refusals.append(refusal)
        else:
            second.close()
        return written

    record = turn_env.run(FakeModelClient(script, fallback=writer_starting_a_second_turn))

    assert record.outcome is TurnOutcome.MERGED
    [refusal] = refusals
    assert refusal.status_code == 409
    assert "002-1" in refusal.message
    assert [entry.id for entry in records.list_all(turn_env.store)] == ["002-1"]


# spec 001 / FR-TURN-05, IF-07 -- over HTTP, a held lock is a 409 before any stream starts.
def test_the_turn_route_is_409_while_the_lock_is_held(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    fake = FakeModelClient()
    use(fixture_client, fake)
    handle = lock.acquire(fixture_store.index_dir, "006-1")
    try:
        response = fixture_client.post("/agents/turns", json={"scene_id": "002"})
    finally:
        lock.release(handle)

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "turn_locked"
    assert "006-1" in body["detail"]
    assert fake.calls == []
    assert fixture_store.turn_records() == []


# spec 001 / FR-TURN-05 -- the lock is released when the stream dies before its first event: a
# client gone before the response starts (an ASGI 2.4 server raises OSError on that send) leaves
# the event generator unstarted, so its own `finally` never runs; the response must still close
# the turn, or every later turn on the store root is a 409 until the process restarts.
def test_the_lock_is_released_when_the_client_is_gone_before_the_stream(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    app = fixture_client.app

    async def client_gone(scope: Scope, receive: Receive, send: Send) -> None:
        async def failing(message: Message) -> None:
            if message["type"] == "http.response.start" and scope["path"] == "/agents/turns":
                reason = "the client went away before the response started"
                raise OSError(reason)
            await send(message)

        await app(scope, receive, failing)

    use(fixture_client, FakeModelClient())
    with TestClient(client_gone, raise_server_exceptions=False) as gone:
        refused = gone.post("/agents/turns", json={"scene_id": "002"})
    assert refused.status_code == 500

    assert not lock_file(fixture_store)
    assert records.load(fixture_store, "002-1").outcome is TurnOutcome.RUNNING
    use(fixture_client, scripted("happy_002"))
    again = fixture_client.post("/agents/turns", json={"scene_id": "006"})
    assert again.status_code == 200, again.text


# spec 001 / FR-TURN-05 -- the lock is released after an escalation.
def test_the_lock_is_released_after_an_escalation(turn_env: TurnEnv) -> None:
    record = turn_env.run(FakeModelClient({AgentRole.WRITER: [Truncation(), Truncation()]}))
    assert record.outcome is TurnOutcome.ESCALATED
    assert not lock_file(turn_env.store)
    assert turn_env.run(scripted("happy_002")).outcome is TurnOutcome.MERGED


# spec 001 / FR-TURN-05, FR-TURN-09 -- the lock is released after an exception, and the record
# stays `running` at the step the exception interrupted.
def test_the_lock_is_released_after_an_exception(turn_env: TurnEnv) -> None:
    with pytest.raises(FakeScriptExhaustedError):
        turn_env.run(FakeModelClient())

    assert not lock_file(turn_env.store)
    record = records.load(turn_env.store, "002-1")
    assert record.outcome is TurnOutcome.RUNNING
    assert record.next_step is TurnStep.WRITE
    assert [step.step for step in record.steps] == [TurnStep.ASSEMBLE]
    assert turn_env.run(scripted("happy_002")).id == "002-2"


# spec 001 / NFR-10 -- a turn record says what stopped a step by code and identifying fields,
# never by the error's message: an InvalidRecord from `promote` quotes the model's payload, and
# the record lives outside the store tree, where no draft text may go.
def test_a_record_detail_carries_codes_and_identifiers_never_the_message() -> None:
    quoting = InvalidRecord(
        "the payload 'She saw the ring glint eleven metres out' targets a mapping field",
        file=paths.PROPOSED,
        field="proposed.3.payload",
    )
    detail = turn.safe_detail(quoting)
    assert detail == f"invalid_record file={paths.PROPOSED} field=proposed.3.payload"
    assert "ring" not in detail

    failed = ModelCallFailed("stderr: whatever the CLI printed", reason="timeout", status=529)
    assert turn.safe_detail(failed) == "model_call_failed reason=timeout status=529"
