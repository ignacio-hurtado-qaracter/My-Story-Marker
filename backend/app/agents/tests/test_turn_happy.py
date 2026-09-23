"""Plan step 18 -- the happy path of a turn (AC 18, FR-TURN-01, -04, -07, -10, IF-06, NFR-10).

A whole turn on a private copy of the fixture, with the scripted `FakeModelClient` of
`scripts/happy_002.yaml` and the `FakeEmbedder`; no model is ever reached (NFR-06). Scene 002 is
the fixture's clean control: every role answers once, nothing blocks, and the turn ends `merged`
with the draft, the digest, the proposed facts and the turn record on disk under the roles
Figure 4 gives them. Scene 003 follows it in discourse order, so its assembly after the turn is
where "canon is updated before the next scene is assembled" becomes observable.

The helpers at the top are the ones every turn suite shares: the script loader, the turn
environment, the tree digest and the SSE parser.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import resources

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import JsonValue, TypeAdapter

from app.agents import records, turn
from app.commons.config import CONTEXT_TOKEN_CAP, Settings, get_settings
from app.commons.deps import get_model_client
from app.commons.embeddings import FakeEmbedder
from app.commons.llm import (
    FakeCall,
    FakeModelClient,
    Outcome,
    ProcessFailure,
    Refusal,
    Reply,
    Truncation,
    Usage,
)
from app.commons.llm.tokens import CLI_OVERHEAD_TOKENS
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Draft,
    FactStatus,
    ProposedFile,
    SceneDigest,
    StepStatus,
    TurnOutcome,
    TurnRecord,
    TurnStep,
)
from app.commons.stores import Store, paths
from app.scenes.models import AssembledContext

SCRIPTS = resources.files("app.agents.tests") / "scripts"
"""The scripted fake responses, read as package data: the store-boundary contract keeps
`pathlib` out of `app/agents/` (NFR-04), tests included."""

ScriptData = dict[str, list[dict[str, JsonValue]]]
_SCRIPT = TypeAdapter(ScriptData)


def script_data(name: str) -> ScriptData:
    """`scripts/<name>.yaml`, validated as role -> list of one-key outcome mappings."""
    return _SCRIPT.validate_python(yaml.safe_load((SCRIPTS / f"{name}.yaml").read_text("utf-8")))


def _outcome(entry: Mapping[str, JsonValue]) -> Outcome:
    [(kind, value)] = entry.items()
    details = value if isinstance(value, dict) else {}
    if kind == "reply":
        return Reply(payload=value)
    if kind == "refusal":
        category = details.get("category")
        return Refusal(category=category if isinstance(category, str) else None)
    if kind == "truncation":
        return Truncation()
    if kind == "process_failure":
        reason = details.get("reason")
        return ProcessFailure(reason=reason if isinstance(reason, str) else "timeout")
    message = f"unknown scripted outcome {kind!r}"
    raise ValueError(message)


def load_script(name: str) -> dict[AgentRole, list[Outcome]]:
    """One queue of outcomes per role, as `FakeModelClient` takes a per-role script."""
    return {
        AgentRole(role): [_outcome(entry) for entry in entries]
        for role, entries in script_data(name).items()
    }


def scripted(
    name: str,
    *,
    cap: int = CONTEXT_TOKEN_CAP,
    fallback: Callable[[FakeCall], Outcome] | None = None,
) -> FakeModelClient:
    return FakeModelClient(load_script(name), cap=cap, fallback=fallback)


def scripted_text(name: str, role: AgentRole, index: int, field: str) -> str:
    """A text field of the `index`-th scripted reply of `role`: what a step wrote."""
    entry = script_data(name)[role.value][index]["reply"]
    assert isinstance(entry, dict)
    text = entry[field]
    assert isinstance(text, str)
    return text


@dataclass(frozen=True, slots=True)
class TurnEnv:
    """The store copy and the two dependencies a turn takes besides the model client."""

    store: Store
    settings: Settings
    embedder: FakeEmbedder

    def run(
        self, client: FakeModelClient, scene: str = "002", *, cap: int = CONTEXT_TOKEN_CAP
    ) -> TurnRecord:
        return turn.run_turn(self.store, client, self.embedder, self.settings, scene, cap=cap)

    def resume(self, client: FakeModelClient, turn_id: str) -> TurnRecord:
        return turn.resume(self.store, client, self.embedder, self.settings, turn_id)

    def dry_run(self, scene: str) -> AssembledContext:
        return turn.dry_run(self.store, self.embedder, self.settings, scene)


def make_turn_env(store: Store) -> TurnEnv:
    """The environment over a fixture copy; each turn suite wraps it in its own `turn_env`
    fixture, since a fixture imported from another module is a name the linter cannot see used."""
    return TurnEnv(store=store, settings=get_settings(), embedder=FakeEmbedder())


@pytest.fixture
def turn_env(fixture_store: Store) -> TurnEnv:
    return make_turn_env(fixture_store)


def tree_digest(store: Store, directory: str = ".") -> dict[str, str]:
    """Store path to content hash for every file under `directory`, walked through the store."""
    found = {
        path: hashlib.sha256(store.read_raw(path).encode("utf-8")).hexdigest()
        for path in store.list_files(directory, "")
    }
    for name in store.list_subdirectories(directory):
        found.update(tree_digest(store, name if directory == "." else f"{directory}/{name}"))
    return found


def use(client: TestClient, fake: FakeModelClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_model_client] = lambda: fake


def sse_events(text: str) -> list[tuple[str, dict[str, JsonValue]]]:
    """`(event, data)` for every event of an SSE body."""
    events: list[tuple[str, dict[str, JsonValue]]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "data" in fields:
            data = json.loads(fields["data"])
            assert isinstance(data, dict)
            events.append((fields.get("event", "message"), data))
    return events


HAPPY_STEPS = [
    TurnStep.ASSEMBLE,
    TurnStep.WRITE,
    TurnStep.AUDIT,
    TurnStep.POLISH,
    TurnStep.RECHECK,
    TurnStep.DIGEST,
    TurnStep.EXTRACT,
    TurnStep.PROMOTE,
]

FIGURE_4_ROLES = {
    TurnStep.ASSEMBLE: None,
    TurnStep.WRITE: "writer",
    TurnStep.AUDIT: "auditor",
    TurnStep.REVISE: "writer",
    TurnStep.POLISH: "style_editor",
    TurnStep.RECHECK: "auditor",
    TurnStep.DIGEST: "writer",
    TurnStep.EXTRACT: "canoniser",
    TurnStep.PROMOTE: "canoniser",
}

VANCE_FACT = "hears a failing exchanger through the hull"
ILAN_FACT = "finds a cradle seating by feel alone"


# spec 001 / AC 18 -- a full fake turn on the fixture ends merged, with every artefact on disk.
def test_a_full_turn_on_the_fixture_ends_merged(turn_env: TurnEnv) -> None:
    client = scripted("happy_002")
    record = turn_env.run(client)
    store = turn_env.store

    assert record.outcome is TurnOutcome.MERGED
    assert record.escalation is None
    assert [step.step for step in record.steps] == HAPPY_STEPS
    assert all(step.status is StepStatus.COMPLETED for step in record.steps)
    assert client.pending() == 0, "every scripted answer was used"

    polished = scripted_text("happy_002", AgentRole.STYLE_EDITOR, 0, "body")
    assert store.read(paths.draft("002"), Draft).body == polished
    digest = store.read(paths.digest("002"), SceneDigest)
    assert digest.delta == scripted_text("happy_002", AgentRole.WRITER, 1, "delta")
    assert digest.povs == ["ilan"]

    queue = {fact.id: fact for fact in store.read(paths.PROPOSED, ProposedFile).proposed}
    assert [fact.fact_id for fact in record.facts] == list(queue)[-2:]
    for fact in record.facts:
        assert queue[fact.fact_id].status is FactStatus.PROMOTED
        assert fact.status is FactStatus.PROMOTED
        assert fact.reconciled_scenes, "reconcile ran after the promotion (FR-TURN-04)"
    vance, ilan = record.facts
    assert vance.proposed_by == ["writer", "canoniser"], "merged by key, queued once"
    assert ilan.proposed_by == ["canoniser"]
    assert "003" in vance.written_scenes

    on_disk = records.load(store, record.id)
    assert on_disk == record
    assert records.record_path(store.index_dir, "002-1").is_file()


# spec 001 / AC 18, FR-TURN-07 -- the record's figures: roles, models, words against budgets.
def test_the_record_carries_what_fr_turn_07_lists(turn_env: TurnEnv) -> None:
    record = turn_env.run(scripted("happy_002"))

    for step in record.steps:
        assert step.role == FIGURE_4_ROLES[step.step], step.step
        if step.step not in {TurnStep.RECHECK, TurnStep.PROMOTE}:
            assert step.estimate is not None
            assert step.estimate > 0
    calls = [step for step in record.steps if step.call is not None]
    assert [step.step for step in calls] == [
        TurnStep.WRITE,
        TurnStep.AUDIT,
        TurnStep.POLISH,
        TurnStep.DIGEST,
        TurnStep.EXTRACT,
    ]
    for step in calls:
        assert step.call is not None
        assert step.call.model_id == "fake-model"
        assert step.call.requested_model == "fake-model"
        assert len(step.call.prompt_version) == 64
        assert step.call.attempts == 1
        assert step.call.cli_version == "fake"
        assert step.call.over_cap is False

    assert [entity.entity_id for entity in record.selected][:3] == [
        "ax_cold_soak",
        "ax_indemnity_burn",
        "lx_soak",
    ]
    assert all(isinstance(entity.score, float) for entity in record.selected)
    assert [iteration.iteration for iteration in record.iterations] == [0]
    assert record.iterations[0].blocking == []
    assert record.draft is not None
    assert record.draft.budget == 1100
    assert record.draft.words == len(
        scripted_text("happy_002", AgentRole.STYLE_EDITOR, 0, "body").split()
    )
    [digest] = record.digests
    assert (digest.digest_id, digest.level.value, digest.target) == ("002", "scene", 100)
    assert digest.words > 0
    assert record.chapter == "ch01"
    assert record.closes_chapter is False, "ch01 ends with 003"
    assert record.rollup_ready is False, "scene 001 has no digest yet"
    assert record.started_at is not None
    assert record.ended_at is not None
    assert record.next_step is TurnStep.DONE


# spec 001 / FR-TURN-07, FR-CTX-06, AC 35 -- the token figures the CLI reported are the ones on
# the record, and a real count over the cap once the overhead is subtracted marks the step
# `over_cap`, while a call within it does not.
def test_the_record_carries_the_reported_token_figures_and_over_cap(turn_env: TurnEnv) -> None:
    over = Usage(
        input_tokens=CONTEXT_TOKEN_CAP + CLI_OVERHEAD_TOKENS - 999,
        output_tokens=1_234,
        cache_read_input_tokens=1_000,
        cache_creation_input_tokens=7,
    )
    within = Usage(input_tokens=4_321, output_tokens=210, cache_read_input_tokens=3_000)
    script = load_script("happy_002")
    written, digested = script[AgentRole.WRITER]
    assert isinstance(written, Reply)
    assert isinstance(digested, Reply)
    script[AgentRole.WRITER] = [
        Reply(payload=written.payload, usage=over),
        Reply(payload=digested.payload, usage=within),
    ]
    record = turn_env.run(FakeModelClient(script))

    assert record.outcome is TurnOutcome.MERGED
    figures = {
        step.step: step.call
        for step in record.steps
        if step.call is not None and step.step in {TurnStep.WRITE, TurnStep.DIGEST}
    }
    write, digest = figures[TurnStep.WRITE], figures[TurnStep.DIGEST]
    assert write is not None
    assert digest is not None
    assert (
        write.input_tokens,
        write.output_tokens,
        write.cache_read_input_tokens,
        write.cache_creation_input_tokens,
        write.over_cap,
    ) == (over.input_tokens, 1_234, 1_000, 7, True)
    assert (
        digest.input_tokens,
        digest.output_tokens,
        digest.cache_read_input_tokens,
        digest.over_cap,
    ) == (4_321, 210, 3_000, False)


# spec 001 / FR-TURN-04 -- of the scenes `reconcile` returns for a promoted fact, the record names
# as already written exactly those that have a draft: the retroactive change, named when made.
def test_the_record_names_the_already_written_scenes_reconcile_returned(
    turn_env: TurnEnv,
) -> None:
    record = turn_env.run(scripted("happy_002"))

    unwritten_seen = False
    for fact in record.facts:
        drafted = [
            scene for scene in fact.reconciled_scenes if turn_env.store.exists(paths.draft(scene))
        ]
        assert fact.written_scenes == drafted, fact.fact_id
        unwritten_seen = unwritten_seen or drafted != fact.reconciled_scenes
    assert unwritten_seen, "some dependent scene has no draft yet, so the filter is exercised"


# spec 001 / FR-TURN-07 -- the chapter hint on the scene that closes its chapter.
def test_the_record_says_when_the_scene_closes_its_chapter(turn_env: TurnEnv) -> None:
    client = scripted("happy_002")
    record = turn_env.run(client, "006")

    assert record.outcome is TurnOutcome.MERGED
    assert (record.chapter, record.closes_chapter) == ("ch02", True)
    assert record.rollup_ready is False, "004 and 005 have no scene digest"


# spec 001 / AC 18 -- provenance names a role for every file the turn changed.
def test_provenance_names_a_role_for_every_changed_file(turn_env: TurnEnv) -> None:
    before = tree_digest(turn_env.store)
    turn_env.run(scripted("happy_002"))
    after = tree_digest(turn_env.store)

    changed = {path for path in after if after[path] != before.get(path)}
    assert changed == {
        "manuscript/002.md",
        "manuscript/digests/002.md",
        "ledger/proposed.yaml",
        "ledger/violations.yaml",
        "cast/vance/dossier.md",
        "cast/ilan/dossier.md",
    }
    logged = {line.path: line for line in turn_env.store.provenance()}
    for path in changed:
        assert path in logged, path
        assert logged[path].role in set(AgentRole)


# spec 001 / AC 18, FR-TURN-04 -- canon is updated before the next scene is assembled.
def test_the_next_scene_in_discourse_order_sees_the_promoted_fact(turn_env: TurnEnv) -> None:
    def pov_dossier(context: AssembledContext) -> str:
        [entry] = [entry for entry in context.entries if entry.key == "character:vance"]
        return entry.text

    assert VANCE_FACT not in pov_dossier(turn_env.dry_run("003"))
    turn_env.run(scripted("happy_002"))
    assert VANCE_FACT in pov_dossier(turn_env.dry_run("003"))


# spec 001 / FR-TURN-07 -- the record is written after every step, not only at the end.
def test_the_record_is_saved_after_every_step(
    turn_env: TurnEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: list[tuple[TurnStep, int]] = []
    real_save = records.save

    def spy(store: Store, record: TurnRecord) -> None:
        saved.append((record.next_step, len(record.steps)))
        real_save(store, record)

    monkeypatch.setattr(records, "save", spy)
    record = turn_env.run(scripted("happy_002"))

    after_step = [steps for _, steps in saved]
    for count in range(1, len(record.steps) + 1):
        assert count in after_step, f"no save after step {count}"
    assert saved[0] == (TurnStep.ASSEMBLE, 0), "the record exists before the first step"
    assert saved[-1] == (TurnStep.DONE, len(HAPPY_STEPS))


# spec 001 / NFR-10 -- no prompt, document or draft text in the turn record.
def test_the_record_holds_no_prompt_or_draft_text(turn_env: TurnEnv) -> None:
    client = scripted("happy_002")
    record = turn_env.run(client)
    text = records.record_path(turn_env.store.index_dir, record.id).read_text("utf-8")

    for call in client.calls:
        for sentence in call.instruction.split("\n"):
            if len(sentence) > 40:
                assert sentence not in text
        for document in call.documents:
            for line in document.text.splitlines():
                if len(line) > 40:
                    assert line not in text, document.path
    for role, index, field in [
        (AgentRole.WRITER, 0, "body"),
        (AgentRole.STYLE_EDITOR, 0, "body"),
        (AgentRole.WRITER, 1, "delta"),
    ]:
        for line in scripted_text("happy_002", role, index, field).splitlines():
            if len(line) > 40:
                assert line not in text


# spec 001 / IF-06 -- the route streams one event per step and a final outcome event.
def test_the_turn_route_streams_one_event_per_step(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    use(fixture_client, scripted("happy_002"))
    response = fixture_client.post("/agents/turns", json={"scene_id": "002"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    assert [kind for kind, _ in events] == ["step"] * len(HAPPY_STEPS) + ["outcome"]
    assert [data["step"] for _, data in events[:-1]] == [step.value for step in HAPPY_STEPS]
    assert all(data["turn_id"] == "002-1" for _, data in events)
    _, final = events[-1]
    assert final["outcome"] == "merged"
    assert final["next_step"] == "done"

    record = fixture_client.get("/agents/turns/002-1")
    assert record.status_code == 200
    assert record.json()["outcome"] == "merged"
    listed = fixture_client.get("/agents/turns").json()
    assert [entry["id"] for entry in listed] == ["002-1"]
    assert not (fixture_store.index_dir / "turn.lock").exists()


# spec 001 / IF-07 -- a scene with no record is refused before the stream starts.
def test_a_turn_on_a_missing_scene_is_404(fixture_client: TestClient) -> None:
    response = fixture_client.post("/agents/turns", json={"scene_id": "099"})
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert fixture_client.get("/agents/turns").json() == []


# spec 001 / IF-07 -- a turn record that does not exist is a 404.
def test_reading_a_missing_turn_is_404(fixture_client: TestClient) -> None:
    response = fixture_client.get("/agents/turns/002-7")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# spec 001 / FR-TURN-10 -- dry_run assembles and answers the context, and calls no model.
def test_dry_run_answers_the_assembled_context_without_a_call(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    fake = FakeModelClient()
    use(fixture_client, fake)
    response = fixture_client.post("/agents/turns?dry_run=true", json={"scene_id": "002"})

    assert response.status_code == 200
    context = AssembledContext.model_validate(response.json())
    assert context.scene == "002"
    assert 0 < context.estimate <= CONTEXT_TOKEN_CAP
    assert [entity.entity_id for entity in context.selected][:2] == [
        "ax_cold_soak",
        "ax_indemnity_burn",
    ]
    assert context.entries[0].key == paths.scene("002")
    assert fake.calls == []
    assert fake.refused_over_cap == []
    assert fixture_store.turn_records() == []
    assert fixture_store.provenance() == []


# spec 001 / FR-OPS-05 -- the selected list is on the record the moment it exists: a turn that
# dies during the assembly that follows selection still leaves it on disk.
def test_the_selected_list_is_recorded_before_the_assembly(
    turn_env: TurnEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    def dies(*args: object, **kwargs: object) -> AssembledContext:
        message = "the process died while assembling"
        raise RuntimeError(message)

    monkeypatch.setattr(turn, "writer_context", dies)
    with pytest.raises(RuntimeError, match="assembling"):
        turn_env.run(scripted("happy_002"))

    record = records.load(turn_env.store, "002-1")
    assert record.selected
    assert record.next_step is TurnStep.ASSEMBLE
    assert record.steps == []


# spec 001 / NFR-10 -- one structured log line per step: role, model id, prompt version, token
# counts and elapsed, and no prompt, document or draft text.
def test_every_step_logs_its_figures_and_no_text(
    turn_env: TurnEnv, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.agents.turn")
    client = scripted("happy_002")
    record = turn_env.run(client)

    lines = [entry for entry in caplog.records if entry.name == "app.agents.turn"]
    assert [entry.__dict__["step"] for entry in lines] == [step.value for step in HAPPY_STEPS]
    write = lines[1].__dict__
    assert (write["role"], write["model_id"], write["turn"]) == ("writer", "fake-model", record.id)
    written = record.steps[1].call
    assert written is not None
    assert write["prompt_version"] == written.prompt_version
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "elapsed_seconds"):
        assert key in write
    logged = " ".join(entry.getMessage() + repr(entry.__dict__) for entry in lines)
    for call in client.calls:
        for document in call.documents:
            for line in document.text.splitlines():
                if len(line) > 40:
                    assert line not in logged
