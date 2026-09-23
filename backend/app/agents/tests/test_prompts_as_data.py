"""AC 23, at assembly level -- store text reaches a role only as labelled data, never as system.

FR-PERM-07 has two halves and both are checked here against the whole fixture novel, read
through a `Store` and never written:

* **Nothing from the stores in the system field.** The system prompt of each model-invoked
  role is its prompt file and nothing else, and neither it nor what the client actually writes
  to `--system-prompt-file` (`render_system`: the prompt plus the fixed data statement) shares
  a run of `TRIVIAL` characters with any file in the fixture tree. Short shared runs are
  English ("the prose is written in" is the longest today, at 24); a shared clause is a copy.
* **Every document delimited and labelled.** Store text assembled through `documents_for` and
  rendered by the client's own `render_prompt` parses back into exactly the (path, text) pairs
  that were read, each between its BEGIN and END lines, with the instruction last.

The turn-level half -- every recorded call of whole turns (plan step 18) -- is at the end of
this file; before it, the assembly those calls are built from, and every role call of plan
step 17 one by one: the prompt file as system, no store text
in the instruction beyond the language name, every document a labelled block. The
prompt checks at the end are the ones Figure 2 and "A warning about over-constraint" ask of the
writer and FR-AGENT-06 of the auditor; `prompt_version` is FR-AGENT-10.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from importlib import resources

import pytest
from pydantic import BaseModel, JsonValue

from app.agents import roles
from app.agents.roles import (
    MECHANICAL_FINDINGS,
    MODEL_ROLES,
    PROMPTS,
    documents_for,
    prompt_version,
    system_prompt,
)
from app.agents.tests.test_roles import CALL_NAMES, ROLE_CALLS
from app.agents.tests.test_turn_escalation import FIVE_SENTENCES, always_blocking, write
from app.agents.tests.test_turn_happy import make_turn_env, scripted
from app.commons.llm import (
    DATA_STATEMENT,
    FakeCall,
    FakeModelClient,
    Reply,
    render_prompt,
    render_system,
)
from app.commons.llm.protocol import INSTRUCTION_HEADER
from app.commons.permissions import AgentRole, may_receive
from app.commons.schemas import (
    ExtractOutput,
    PolishOutput,
    Scene,
    SemanticAuditOutput,
    SetupsFile,
    WriterOutput,
)
from app.commons.stores import Store

TRIVIAL = 40
"""A shared run this long, after whitespace is collapsed and case folded, is a copied clause
rather than common English. About seven words; the longest run the four prompts share with the
fixture today is 24 characters."""

INSTRUCTION = "Write the scene."

OUTPUTS: Mapping[AgentRole, BaseModel] = {
    AgentRole.WRITER: WriterOutput(body="The scene.", proposed_facts=[]),
    AgentRole.STYLE_EDITOR: PolishOutput(body="The scene, polished."),
    AgentRole.AUDITOR: SemanticAuditOutput(violations=[]),
    AgentRole.CANONISER: ExtractOutput(facts=[]),
}

STORE_FAMILIES = frozenset({"canon", "cast", "structure", "scenes", "manuscript", "ledger"})
"""The six store roots of the storage layout: a document labelled under one was read from it."""

BLOCK = re.compile(
    r"^=== BEGIN DOCUMENT (?P<boundary>[0-9a-f]+) path=(?P<path>[^\n]*) ===\n"
    r"(?P<text>.*?)\n"
    r"=== END DOCUMENT (?P=boundary) ===$",
    re.DOTALL | re.MULTILINE,
)


def _prompt_file(role: AgentRole) -> str:
    """The prompt file read independently of the loader under test, line endings normalised
    the way FR-AGENT-10's version is taken."""
    data = (resources.files("app.agents") / "prompts" / f"{role.value}.md").read_bytes()
    return data.decode("utf-8").replace("\r\n", "\n")


def _walk(store: Store, directory: str = ".") -> list[str]:
    """Every file under `directory`, store-relative, through the store's own listing."""
    found = list(store.list_files(directory, ""))
    for name in store.list_subdirectories(directory):
        found.extend(_walk(store, name if directory == "." else f"{directory}/{name}"))
    return found


def _fixture_texts(store: Store) -> dict[str, str]:
    return {path: store.read_raw(path) for path in _walk(store)}


def _flatten(text: str) -> str:
    return " ".join(text.split()).casefold()


def _runs(texts: Mapping[str, str]) -> dict[str, str]:
    """Every `TRIVIAL`-character run of every text, mapped to the first path it occurs in."""
    index: dict[str, str] = {}
    for path, text in texts.items():
        flat = _flatten(text)
        for start in range(len(flat) - TRIVIAL + 1):
            index.setdefault(flat[start : start + TRIVIAL], path)
    return index


def _shared(system: str, index: Mapping[str, str]) -> list[tuple[str, str]]:
    """The runs of `system` found in the fixture, each with the file it came from."""
    flat = _flatten(system)
    runs = (flat[start : start + TRIVIAL] for start in range(len(flat) - TRIVIAL + 1))
    return [(run, index[run]) for run in runs if run in index]


@pytest.fixture
def fixture_texts(fixture_store: Store) -> dict[str, str]:
    texts = _fixture_texts(fixture_store)
    assert len(texts) > 40, "the walk must reach the whole fixture tree"
    return texts


# spec 001 / AC 23
@pytest.mark.parametrize("role", MODEL_ROLES, ids=[role.value for role in MODEL_ROLES])
def test_the_system_prompt_is_the_prompt_file(role: AgentRole) -> None:
    assert system_prompt(role) == _prompt_file(role)


# spec 001 / AC 23
@pytest.mark.parametrize("role", MODEL_ROLES, ids=[role.value for role in MODEL_ROLES])
def test_no_store_text_reaches_the_system_field(
    role: AgentRole, fixture_texts: dict[str, str]
) -> None:
    index = _runs(fixture_texts)
    assert _shared(system_prompt(role), index) == []
    assert _shared(render_system(system_prompt(role)), index) == []


# spec 001 / AC 23 (the check above has teeth)
def test_a_store_passage_planted_in_a_system_prompt_is_found(
    fixture_texts: dict[str, str],
) -> None:
    passage = "The slot board took a fresh sheet every shift, and Vance had learned to read it"
    assert passage in fixture_texts["canon/style.md"]
    planted = f"{system_prompt(AgentRole.STYLE_EDITOR)}\n\nExample of the voice:\n{passage}\n"
    found = _shared(planted, _runs(fixture_texts))
    assert found
    assert {path for _, path in found} == {"canon/style.md"}


# spec 001 / AC 23
@pytest.mark.parametrize("role", MODEL_ROLES, ids=[role.value for role in MODEL_ROLES])
def test_documents_render_as_labelled_delimited_blocks(
    role: AgentRole, fixture_texts: dict[str, str]
) -> None:
    sources = [(path, text) for path, text in fixture_texts.items() if may_receive(role, path)]
    assert sources, f"the fixture holds nothing in the {role.value} row"
    rendered = render_prompt(documents_for(role, sources), INSTRUCTION)
    blocks = [(match["path"], match["text"]) for match in BLOCK.finditer(rendered)]
    assert blocks == sources
    assert rendered.endswith(f"{INSTRUCTION_HEADER}\n{INSTRUCTION}\n")


# spec 001 / AC 23, FR-AGENT-09
@pytest.mark.parametrize("role", MODEL_ROLES, ids=[role.value for role in MODEL_ROLES])
def test_a_recorded_call_carries_the_prompt_as_system_and_store_text_as_documents(
    role: AgentRole, fixture_store: Store, fixture_texts: dict[str, str]
) -> None:
    sources = [(path, text) for path, text in fixture_texts.items() if may_receive(role, path)]
    client = FakeModelClient({role: [Reply.of(OUTPUTS[role])]})
    client.complete(
        role=role,
        system=system_prompt(role),
        documents=documents_for(role, sources),
        instruction=INSTRUCTION,
        output_schema=type(OUTPUTS[role]),
    )
    [call] = client.calls
    assert call.system == _prompt_file(role)
    assert _shared(render_system(call.system), _runs(fixture_texts)) == []
    assert DATA_STATEMENT not in call.system, "the client appends it, the role does not"
    assert [document.path for document in call.documents] == [path for path, _ in sources]
    for document in call.documents:
        assert may_receive(role, document.path), document.path
        assert document.text == fixture_store.read_raw(document.path)


# spec 001 / AC 23 (Figure 2: setups are offered, not assigned)
def test_the_writer_prompt_offers_setups_and_requires_none(fixture_store: Store) -> None:
    prompt = system_prompt(AgentRole.WRITER)
    flat = _flatten(prompt)
    assert "setup" in flat
    assert "may collect" in flat
    assert re.search(r"\bnone\b[^.]*\brequired\b", flat), "the prompt must say none is required"
    obligation = r"\b(must|required to|have to|has to|need to|needs to)\s+(collect|pay)"
    assert re.search(obligation, flat) is None
    for setup in fixture_store.read("ledger/setups.yaml", SetupsFile).setups:
        assert setup.id not in prompt
        assert _flatten(setup.promise) not in flat


# spec 001 / AC 23 ("A warning about over-constraint": function fixed, execution free)
def test_the_writer_prompt_fixes_the_function_and_frees_the_execution() -> None:
    flat = _flatten(system_prompt(AgentRole.WRITER))
    for field in ("wants", "stands in the way", "how it comes out", "which value moves"):
        assert field in flat, field
    assert "everything else is yours" in flat


# spec 001 / AC 23 (FR-AGENT-06: invariants 3, 6 and the prose halves of 1 and 8, only)
def test_the_auditor_prompt_checks_its_four_invariants_and_nothing_else() -> None:
    prompt = system_prompt(AgentRole.AUDITOR)
    named = {int(number) for number in re.findall(r"\bInvariant (\d+)\b", prompt)}
    assert named == {1, 3, 6, 8}
    flat = _flatten(prompt)
    assert "you never repair" in flat
    assert "quoted verbatim" in flat
    assert "offset" in flat
    assert "do not report them again" in flat


# spec 001 / FR-AGENT-10
@pytest.mark.parametrize("role", MODEL_ROLES, ids=[role.value for role in MODEL_ROLES])
def test_prompt_version_is_the_sha256_of_the_prompt_file(role: AgentRole) -> None:
    expected = hashlib.sha256(_prompt_file(role).encode("utf-8")).hexdigest()
    assert prompt_version(role) == expected


# spec 001 / FR-AGENT-10
def test_prompt_version_changes_when_the_file_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    original = roles.read_prompt_file
    before = {role: PROMPTS[role].version for role in MODEL_ROLES}

    def edited(role: AgentRole) -> bytes:
        data = original(role)
        return data + b"\nOne more sentence.\n" if role is AgentRole.WRITER else data

    monkeypatch.setattr(roles, "read_prompt_file", edited)
    reloaded = roles.load_prompts()
    assert reloaded[AgentRole.WRITER].version != before[AgentRole.WRITER]
    assert reloaded[AgentRole.WRITER].text.endswith("One more sentence.\n")
    for role in MODEL_ROLES:
        if role is not AgentRole.WRITER:
            assert reloaded[role].version == before[role], role
    # Loaded once, at import: the running process keeps the version it started with.
    assert prompt_version(AgentRole.WRITER) == before[AgentRole.WRITER]


# spec 001 / FR-AGENT-10
def test_prompt_version_does_not_depend_on_the_checkout_line_endings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = roles.read_prompt_file

    def crlf(role: AgentRole) -> bytes:
        return original(role).replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    monkeypatch.setattr(roles, "read_prompt_file", crlf)
    reloaded = roles.load_prompts()
    assert {role: reloaded[role] for role in MODEL_ROLES} == dict(PROMPTS)


# spec 001 / FR-AGENT-10
@pytest.mark.parametrize("role", [AgentRole.ARCHITECT, AgentRole.WORLD_BUILDER])
def test_a_role_with_no_model_has_no_prompt(role: AgentRole) -> None:
    with pytest.raises(ValueError, match="not model-invoked"):
        system_prompt(role)


# spec 001 / FR-AGENT-10
def test_an_empty_prompt_file_is_refused() -> None:
    with pytest.raises(ValueError, match="empty"):
        roles.prompt_from_bytes(AgentRole.WRITER, b" \r\n\n")


# --- plan step 17: every role call, as the fake recorded it ---------------------------------


def _recorded(name: str, store: Store) -> FakeCall:
    case = ROLE_CALLS[name]
    client = FakeModelClient({case.role: [Reply.of(case.output)]})
    case.run(store, client)
    [call] = client.calls
    return call


# spec 001 / AC 23, FR-AGENT-10 -- each role call's system is its prompt file, and nothing else.
@pytest.mark.parametrize("name", CALL_NAMES)
def test_every_role_call_sends_its_prompt_file_as_system(
    name: str, fixture_store: Store, fixture_texts: dict[str, str]
) -> None:
    call = _recorded(name, fixture_store)
    assert call.system == _prompt_file(call.role)
    assert _shared(render_system(call.system), _runs(fixture_texts)) == []


# spec 001 / AC 23, FR-PERM-07, FR-LLM-10 -- the instruction carries no store text; the prose
# language is the one name that crosses, and it is too short to count as a copied clause.
@pytest.mark.parametrize("name", CALL_NAMES)
def test_no_role_call_carries_store_text_in_its_instruction(
    name: str, fixture_store: Store, fixture_texts: dict[str, str]
) -> None:
    call = _recorded(name, fixture_store)
    assert _shared(call.instruction, _runs(fixture_texts)) == []
    scene = fixture_store.read("scenes/003.yaml", Scene)
    for field in (scene.goal, scene.conflict, scene.value_change, scene.notes or scene.goal):
        assert _flatten(field) not in _flatten(call.instruction)


# spec 001 / AC 23 -- every document of every role call is a delimited block labelled with its
# path, and the computed findings block with its own label, exactly as it was sent.
@pytest.mark.parametrize("name", CALL_NAMES)
def test_every_role_call_renders_as_labelled_blocks(name: str, fixture_store: Store) -> None:
    call = _recorded(name, fixture_store)
    rendered = render_prompt(call.documents, call.instruction)
    blocks = [(match["path"], match["text"]) for match in BLOCK.finditer(rendered)]
    assert blocks == [(document.path, document.text) for document in call.documents]
    assert rendered.endswith(f"{INSTRUCTION_HEADER}\n{call.instruction}\n")
    labels = [path for path, _ in blocks]
    assert (MECHANICAL_FINDINGS in labels) is (call.role is AgentRole.AUDITOR)


# --- plan step 18: every call of a whole turn, as the fake recorded it -----------------------


def _strings(value: JsonValue) -> list[str]:
    """Every string inside a scripted payload: the texts a role call produced."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return []


def _outputs(call: FakeCall) -> list[str]:
    """The lines, long enough to be prose rather than a word, of what a call answered."""
    texts = [
        text
        for outcome in call.outcomes
        if isinstance(outcome, Reply)
        for text in _strings(outcome.payload)
    ]
    return [line for text in texts for line in text.splitlines() if len(line) > TRIVIAL]


def _turn_calls(store: Store) -> list[FakeCall]:
    """The calls of three turns: a clean one on 002, one on 006 (whose writer is offered an open
    setup), and one on 002 whose finding never goes away (three revisions)."""
    env = make_turn_env(store)
    happy = scripted("happy_002")
    env.run(happy)
    tempting = scripted("happy_002")
    env.run(tempting, "006")
    blocked = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=always_blocking)
    env.run(blocked)
    calls = [*happy.calls, *tempting.calls, *blocked.calls]
    assert {call.output_schema for call in calls} >= {
        "WriterOutput",
        "ReviseOutput",
        "SemanticAuditOutput",
        "PolishOutput",
        "DigestOutput",
        "ExtractOutput",
    }
    return calls


# spec 001 / AC 23 -- no recorded call of a turn carries store text in its system field.
def test_no_turn_call_carries_store_text_in_the_system_field(
    fixture_store: Store, fixture_texts: dict[str, str]
) -> None:
    index = _runs(fixture_texts)
    for call in _turn_calls(fixture_store):
        assert call.system == _prompt_file(call.role)
        assert _shared(render_system(call.system), index) == []


# spec 001 / AC 23 -- every document of every turn call is a delimited block labelled with its path.
def test_every_turn_call_renders_as_labelled_blocks(fixture_store: Store) -> None:
    for call in _turn_calls(fixture_store):
        rendered = render_prompt(call.documents, call.instruction)
        blocks = [(match["path"], match["text"]) for match in BLOCK.finditer(rendered)]
        assert blocks == [(document.path, document.text) for document in call.documents]
        assert rendered.endswith(f"{INSTRUCTION_HEADER}\n{call.instruction}\n")


# spec 001 / AC 23, FR-AGENT-11 -- no call carries an earlier call's output except as a document
# read back from the store it was written to: never in the instruction or the system field, never
# in the one computed document, and never at all when no store holds it (the auditor's
# explanation, which DR-07 does not store, reaches no later call).
def test_no_turn_call_carries_an_earlier_output_except_through_a_store(
    fixture_store: Store,
) -> None:
    calls = _turn_calls(fixture_store)
    explanation = "The seating contradicts the axiom in force."
    assert any(explanation in _outputs(call) for call in calls)
    for index, call in enumerate(calls):
        earlier = {line for previous in calls[:index] for line in _outputs(previous)}
        for line in earlier:
            assert line not in call.instruction, call.output_schema
            assert line not in call.system
            for document in call.documents:
                if line in document.text:
                    assert document.path != MECHANICAL_FINDINGS, line
                    assert document.path.split("/")[0] in STORE_FAMILIES, document.path
                    assert line != explanation


# spec 001 / AC 23 (Figure 2) -- the writer's instruction names no setup, let alone as required;
# an open setup reaches the writer as a document offered under "may collect".
def test_the_writers_instruction_names_no_setup_as_required(fixture_store: Store) -> None:
    setups = fixture_store.read("ledger/setups.yaml", SetupsFile).setups
    writes = [call for call in _turn_calls(fixture_store) if call.output_schema == "WriterOutput"]
    offered = 0
    for call in writes:
        flat = _flatten(call.instruction)
        for setup in setups:
            assert setup.id not in call.instruction
            assert _flatten(setup.promise) not in flat
        assert re.search(r"\b(must|required to|have to|need to)\s+(collect|pay)", flat) is None
        for document in call.documents:
            if document.path == "ledger/setups.yaml":
                offered += 1
                assert "may collect" in _flatten(document.text)
    assert offered >= 1, "scene 006 is offered su_readkey, so the label was seen"
