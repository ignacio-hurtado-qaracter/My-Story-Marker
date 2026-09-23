"""AC 12, the turn half: the selected list on the turn record is the one the auditor receives.

`scenes/tests/test_assemble.py` pins the assembly half of AC 12. Selection is not reproducible
(`architecture.md`, "Memory and context budget"), so "which axioms apply to this scene" must have
one answer per turn: the list `select_entities` returned is written to the turn record at once
(FR-OPS-05), and every later step of the turn reads it from there. Checked against the fake's log
of a whole turn: the auditor's instruction names exactly the recorded list, in order, and the
axioms it is given as documents are exactly the recorded list's axioms that fit; the writer's
context is the one assembled from that same list.

Cross-feature by necessity -- the turn (`agents`), the assembly (`scenes`) and the index
(`commons`) at once -- which is why it lives in `tests/` (`architecture.md`, rule on tests).
"""

from __future__ import annotations

import pytest

from app.agents import turn
from app.agents.roles import auditor
from app.agents.tests.test_turn_happy import make_turn_env, scripted
from app.commons.config import Settings
from app.commons.embeddings import Embedder
from app.commons.permissions import AgentRole
from app.commons.schemas import TurnOutcome
from app.commons.stores import Store, paths
from app.scenes import service as scenes_service
from app.scenes.models import Selection
from app.scenes.select import DEFAULT_LIMIT

SELECTED_LINE = "The turn's selected entities: "


def test_the_recorded_selected_list_is_the_list_the_auditor_receives(
    fixture_store: Store,
) -> None:  # spec 001 / AC 12
    env = make_turn_env(fixture_store)
    client = scripted("happy_002")
    record = env.run(client)
    assert record.outcome is TurnOutcome.MERGED
    assert record.selected, "the turn selected something"

    [audit_call] = [call for call in client.calls if call.role is AgentRole.AUDITOR]
    lines = audit_call.instruction.splitlines()
    [line] = [text for text in lines if text.startswith(SELECTED_LINE)]
    received = line.removeprefix(SELECTED_LINE).rstrip(".").split(", ")
    recorded = [
        f"{entity.kind}:{entity.entity_id}{' (pinned)' if entity.pinned else ''}"
        for entity in record.selected
    ]
    assert received == recorded
    assert audit_call.instruction == auditor.audit_instruction("002", record.selected)

    pinned, ranked = auditor.selected_axioms(record.selected)
    axiom_documents = [
        document.path for document in audit_call.documents if document.path.startswith("canon/")
    ]
    assert axiom_documents == [paths.canon_entity("axioms", axiom) for axiom in [*pinned, *ranked]]


def test_the_writer_is_assembled_from_the_recorded_list(fixture_store: Store) -> None:
    # spec 001 / AC 12
    env = make_turn_env(fixture_store)
    client = scripted("happy_002")
    record = env.run(client)

    [write_call] = [call for call in client.calls if call.output_schema == "WriterOutput"]
    assemble = record.steps[0]
    assert write_call.estimate == assemble.estimate, "the call is the assembly the record names"
    context = turn.writer_context(fixture_store, "002", record.selected, cap=100_000)
    assert context.selected == record.selected
    written = {document.path for document in write_call.documents}
    for entity in record.selected:
        if entity.kind == "axiom":
            assert paths.canon_entity("axioms", entity.entity_id) in written, entity.entity_id


def test_a_selection_that_would_answer_differently_is_made_once_per_turn(
    fixture_store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    # spec 001 / AC 12, FR-OPS-05
    # Selection is not reproducible in production; the fake embedder makes it so here, which
    # would hide a step that selected again. So every selection after the first answers a
    # different list: the writer and the auditor must still receive the recorded one.
    real = scenes_service.select_entities
    made: list[Selection] = []

    def unreproducible(
        store: Store,
        embedder: Embedder,
        settings: Settings,
        identifier: str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> Selection:
        selection = real(store, embedder, settings, identifier, limit=limit)
        made.append(selection)
        if len(made) == 1:
            return selection
        return selection.model_copy(update={"entities": list(reversed(selection.entities))[1:]})

    monkeypatch.setattr(scenes_service, "select_entities", unreproducible)
    env = make_turn_env(fixture_store)
    client = scripted("happy_002")
    record = env.run(client)

    assert record.outcome is TurnOutcome.MERGED
    assert len(made) == 1, "one selection per turn; every later step reads the record"
    assert record.selected == made[0].entities
    [audit_call] = [call for call in client.calls if call.role is AgentRole.AUDITOR]
    assert audit_call.instruction == auditor.audit_instruction("002", record.selected)
    [write_call] = [call for call in client.calls if call.output_schema == "WriterOutput"]
    # The documents' paths, not their text: the turn's promotions have since changed canon.
    context = turn.writer_context(fixture_store, "002", record.selected, cap=100_000)
    assert [document.path for document in write_call.documents] == [
        entry.path for entry in context.entries
    ]
