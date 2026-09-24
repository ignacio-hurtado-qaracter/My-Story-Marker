"""Plan step 18 -- AC 32: one provenance line per store write of a turn, under Figure 4's role.

`commons/stores/tests/test_provenance.py` pins the store half: every write appends one line, and
no write can skip it. This is the turn half: after AC 18's fake turn the log holds exactly one line
per store write the turn made, each with the role Figure 4 gives that step and `actor: agent` --
the orchestrator always sends `agent` (Decision R2-7) -- and the turn record lists the same writes,
step by step, with the same content hashes. A `PUT` a person makes with `X-Actor: human` is logged
as `actor: human`, which `GET /agents/provenance` reads back (IF-03).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.tests.test_turn_happy import TurnEnv, make_turn_env, scripted
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Draft, TurnStep
from app.commons.stores import Store, paths

WRITER, AUDITOR, STYLE_EDITOR, CANONISER = (
    AgentRole.WRITER,
    AgentRole.AUDITOR,
    AgentRole.STYLE_EDITOR,
    AgentRole.CANONISER,
)

FIGURE_4_WRITES = [
    (TurnStep.WRITE, "manuscript/002.md", WRITER),
    (TurnStep.WRITE, "ledger/proposed.yaml", WRITER),
    (TurnStep.AUDIT, "ledger/violations.yaml", AUDITOR),
    (TurnStep.POLISH, "manuscript/002.md", STYLE_EDITOR),
    (TurnStep.DIGEST, "manuscript/digests/002.md", WRITER),
    (TurnStep.EXTRACT, "ledger/proposed.yaml", CANONISER),
    (TurnStep.PROMOTE, "cast/vance/dossier.md", CANONISER),
    (TurnStep.PROMOTE, "ledger/proposed.yaml", CANONISER),
    (TurnStep.PROMOTE, "cast/ilan/dossier.md", CANONISER),
    (TurnStep.PROMOTE, "ledger/proposed.yaml", CANONISER),
]
"""The happy turn on scene 002, write by write: the step, the file, and the role Figure 4 gives
the step. The canoniser's extraction queues only ilan's fact -- vance's is the writer's, already
queued under the same id -- and each promotion writes the target record, then the queue."""


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


# spec 001 / AC 32 -- exactly one line per store write, with Figure 4's role and actor agent.
def test_every_store_write_of_a_turn_has_exactly_one_provenance_line(turn_env: TurnEnv) -> None:
    record = turn_env.run(scripted("happy_002"))
    lines = turn_env.store.provenance()

    assert [(line.path, line.role) for line in lines] == [
        (path, role) for _, path, role in FIGURE_4_WRITES
    ]
    assert {line.actor for line in lines} == {Actor.AGENT}

    recorded = [(step.step, write) for step in record.steps for write in step.writes]
    assert [(step, write.path, write.role) for step, write in recorded] == [
        (step, path, role.value) for step, path, role in FIGURE_4_WRITES
    ]
    assert [write.content_hash for _, write in recorded] == [line.content_hash for line in lines]
    assert len({line.content_hash for line in lines if line.path == paths.PROPOSED}) == 4


# spec 001 / AC 32, FR-STORE-04 -- a promotion inside a turn names the scene and the turn.
def test_promotions_name_the_scene_and_the_turn(turn_env: TurnEnv) -> None:
    record = turn_env.run(scripted("happy_002"))
    promoted = [line for line in turn_env.store.provenance() if line.path.startswith("cast/")]

    assert len(promoted) == 2
    assert {(line.scene, line.turn) for line in promoted} == {("002", record.id)}


# spec 001 / AC 32, IF-03 -- a PUT with X-Actor: human is logged as actor human, and the log is
# read back through GET /agents/provenance, filtered by path and by time.
def test_a_human_put_is_logged_as_human_and_read_back(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    draft = fixture_store.read(paths.draft("002"), Draft)
    response = fixture_client.put(
        "/manuscript/002",
        json=draft.model_dump(mode="json"),
        headers={"X-Agent-Role": "writer", "X-Actor": "human"},
    )
    assert response.status_code == 200

    logged = fixture_client.get("/agents/provenance", params={"path": "manuscript/002.md"})
    assert logged.status_code == 200
    [line] = logged.json()
    assert (line["role"], line["actor"], line["path"]) == ("writer", "human", "manuscript/002.md")
    assert fixture_client.get("/agents/provenance", params={"path": "canon/style.md"}).json() == []
    later = fixture_client.get("/agents/provenance", params={"since": "9999-01-01T00:00:00"})
    assert later.json() == []
    assert len(fixture_client.get("/agents/provenance").json()) == 1
