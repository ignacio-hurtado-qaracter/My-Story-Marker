"""Plan step 18 -- FR-AGENT-11: roles exchange work through the stores, never through messages.

`architecture.md` ("Memory and context budget"): the writer and the auditor communicate through
`manuscript/NNN.md` and `ledger/violations.yaml`, never by passing messages. So the checks here
are made *at the moment of each call*, from inside the fake's answer, against the tree as it is
then:

* the audit call's draft document is `manuscript/NNN.md` as the writer's step wrote it -- the
  last provenance line of that file is the writer's, and its hash is the file's;
* the revise call's violations document is `ledger/violations.yaml` as the auditor's step wrote
  it -- the scene's open blocking findings read back from that file, whose last provenance line
  is the auditor's;
* the orchestrator's step inputs are identifiers: a step receives the turn context and nothing
  else, and the record it carries holds no text a role produced.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect

import pytest

from app.agents import records, turn
from app.agents.tests.test_turn_escalation import FIVE_SENTENCES, always_blocking, write
from app.agents.tests.test_turn_happy import TurnEnv, make_turn_env
from app.commons.llm import FakeCall, FakeModelClient, Outcome
from app.commons.permissions import AgentRole
from app.commons.schemas import Draft, Severity, TurnOutcome, ViolationsFile
from app.commons.stores import Store, paths
from app.scenes import service as scenes_service


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def _document(call: FakeCall, path: str) -> str:
    [text] = [document.text for document in call.documents if document.path == path]
    return text


def _last_writer_of(store: Store, path: str) -> tuple[AgentRole, str]:
    """The role of the last write to `path`, and whether its hash is the file's hash now."""
    line = store.provenance(path=path)[-1]
    current = hashlib.sha256(store.read_raw(path).encode("utf-8")).hexdigest()
    return line.role, "current" if line.content_hash == current else "stale"


# spec 001 / FR-AGENT-11 -- the audit reads the draft from manuscript/ after the writer's write,
# and the revision reads the blocking violations from ledger/ after the auditor's.
def test_every_hand_off_is_the_file_the_previous_role_wrote(turn_env: TurnEnv) -> None:
    store = turn_env.store
    checked: list[str] = []

    def observing(call: FakeCall) -> Outcome:
        if call.role is AgentRole.AUDITOR:
            draft = paths.draft("002")
            assert _document(call, draft) == store.read(draft, Draft).body
            expected_writer = AgentRole.WRITER
            assert _last_writer_of(store, draft) == (expected_writer, "current")
            checked.append("audit")
        elif call.output_schema == "ReviseOutput":
            on_file = store.read(paths.VIOLATIONS, ViolationsFile).violations
            blocking = [
                finding
                for finding in on_file
                if finding.scene == "002"
                and finding.severity is Severity.BLOCKING
                and finding.resolution is None
            ]
            rendered = scenes_service.render_record(ViolationsFile(violations=blocking))
            assert _document(call, paths.VIOLATIONS) == rendered
            assert _last_writer_of(store, paths.VIOLATIONS) == (AgentRole.AUDITOR, "current")
            assert _document(call, paths.draft("002")) == store.read(paths.draft("002"), Draft).body
            checked.append("revise")
        return always_blocking(call)

    client = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=observing)
    record = turn_env.run(client)

    assert record.outcome is TurnOutcome.ESCALATED
    assert checked == ["audit", "revise"] * 3 + ["audit"]
    first_audit = next(call for call in client.calls if call.role is AgentRole.AUDITOR)
    assert _document(first_audit, paths.draft("002")) == FIVE_SENTENCES


# spec 001 / FR-AGENT-11 -- a step's inputs are identifiers: it receives the turn context and a
# timestamp, and the context carries the record and the dependencies, no content.
def test_step_inputs_are_identifiers_only() -> None:
    names = [field.name for field in dataclasses.fields(turn.TurnContext)]
    assert names == ["store", "client", "embedder", "settings", "record", "cap"]
    for step, function in turn.STEPS.items():
        assert list(inspect.signature(function).parameters) == ["ctx", "started"], step


# spec 001 / FR-AGENT-11, NFR-10 -- the record carried between steps holds no text a role
# produced: not the draft, not a finding's quote, not a model's explanation.
def test_the_carried_record_holds_no_role_output(turn_env: TurnEnv) -> None:
    client = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=always_blocking)
    record = turn_env.run(client)
    text = records.record_path(turn_env.store.index_dir, record.id).read_text("utf-8")

    for sentence in FIVE_SENTENCES.split(". "):
        assert sentence.strip(".") not in text
    assert "contradicts the axiom" not in text
    blocking = record.iterations[-1].blocking
    assert blocking
    assert all(identifier in text for identifier in blocking)
