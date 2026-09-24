"""FR-AGENT-09 -- a document from outside a role's `In` row is refused at assembly.

Figure 3's `In` column ends with the sentence this test exists for: *anything not listed as an
input is not available to the agent*. `documents_for` is the only door from store text to a
role's prompt, so a planted out-of-row document has to stop there, for every role, with the
Figure 3 refusal (`PermissionDenied`) rather than a quiet drop.

The cases are written out by hand from the table in
`docs/architecture.md#figure-3--agents-and-write-permissions`, not derived from
`INPUT_TABLE`, so the test disagrees with the code when someone edits the table. The turn-level
half -- every document of every recorded fake call of whole turns inside its role's row (plan
step 18) -- closes this file, after the role calls of plan step 17 checked one by one, with the
computed document of FR-AGENT-07 and the every-source rule of `call_role`.
"""

from __future__ import annotations

import pytest

from app.agents.roles import MECHANICAL_FINDINGS, RoleInput, call_role, documents_for
from app.agents.tests.test_roles import CALL_NAMES, ROLE_CALLS
from app.agents.tests.test_turn_escalation import FIVE_SENTENCES, always_blocking, write
from app.agents.tests.test_turn_happy import make_turn_env, scripted
from app.commons.errors import PermissionDenied
from app.commons.llm import Document, FakeModelClient, Reply
from app.commons.permissions import AgentRole, may_receive
from app.commons.permissions.roles import GIFT_NOVEL_ROLES
from app.commons.schemas import PolishOutput
from app.commons.stores import Store

TEXT = "Any text; only the path is judged."

# role -> (an in-row path, an out-of-row path), from Figure 3's `In` column.
CASES: dict[AgentRole, list[tuple[str, str]]] = {
    AgentRole.ARCHITECT: [
        ("canon/project.md", "manuscript/002.md"),
        ("ledger/threads.yaml", "cast/ilan/knowledge.yaml"),
    ],
    AgentRole.WORLD_BUILDER: [
        ("structure/arcs.yaml", "ledger/setups.yaml"),
        ("canon/lexicon.yaml", "cast/ilan/dossier.md"),
    ],
    AgentRole.WRITER: [
        ("canon/axioms/ax_cold_soak.md", "ledger/proposed.yaml"),
        ("manuscript/digests/901.md", "ledger/threads.yaml"),
        ("ledger/violations.yaml", "ledger/timeline.yaml"),
    ],
    AgentRole.STYLE_EDITOR: [
        ("canon/style.md", "canon/axioms/x.md"),
        ("cast/vance/voice.md", "cast/vance/knowledge.yaml"),
        ("manuscript/002.md", "manuscript/digests/002.md"),
    ],
    AgentRole.AUDITOR: [
        ("scenes/004.yaml", "ledger/setups.yaml"),
        ("cast/quiej/changes.yaml", "cast/quiej/voice.md"),
        ("canon/axioms/ax_brine_dark.md", "canon/style.md"),
    ],
    AgentRole.CANONISER: [
        ("ledger/proposed.yaml", "cast/x/dossier.md"),
        ("manuscript/003.md", "ledger/violations.yaml"),
        ("canon/technology/te_dive_rig.md", "scenes/004.yaml"),
    ],
}

ACCEPTED = [(role, inside) for role, pairs in CASES.items() for inside, _ in pairs]
REFUSED = [(role, outside) for role, pairs in CASES.items() for _, outside in pairs]

NOT_A_STORE_PATH = [
    ".index/turns/004-1.yaml",
    ".index/provenance.jsonl",
    "CLAUDE.md",
    "../canon/project.md",
    "canon/../ledger/setups.yaml",
    "/canon/project.md",
    "C:/story/canon/project.md",
    "",
]


# spec 001 / FR-AGENT-09
def test_the_cases_cover_every_role() -> None:
    # spec 005: the gift-novel roles have an empty `In` row; no store path reaches them.
    assert set(CASES) == set(AgentRole) - GIFT_NOVEL_ROLES


# spec 001 / FR-AGENT-09
@pytest.mark.parametrize(
    ("role", "path"), ACCEPTED, ids=[f"{role.value}-{path}" for role, path in ACCEPTED]
)
def test_an_in_row_document_is_accepted_and_labelled(role: AgentRole, path: str) -> None:
    assert documents_for(role, [(path, TEXT)]) == (Document(path=path, text=TEXT),)


# spec 001 / FR-AGENT-09
@pytest.mark.parametrize(
    ("role", "path"), REFUSED, ids=[f"{role.value}-{path}" for role, path in REFUSED]
)
def test_a_planted_out_of_row_document_is_refused(role: AgentRole, path: str) -> None:
    with pytest.raises(PermissionDenied) as refused:
        documents_for(role, [(path, TEXT)])
    assert refused.value.status_code == 403
    assert refused.value.context == {"role": role.value, "path": path}


# spec 001 / FR-AGENT-09
@pytest.mark.parametrize("path", NOT_A_STORE_PATH)
@pytest.mark.parametrize("role", list(AgentRole), ids=[role.value for role in AgentRole])
def test_nothing_outside_the_stores_reaches_any_role(role: AgentRole, path: str) -> None:
    with pytest.raises(PermissionDenied):
        documents_for(role, [(path, TEXT)])


# spec 001 / FR-AGENT-09
def test_one_planted_document_refuses_the_whole_assembly() -> None:
    sources = [
        ("manuscript/002.md", "the draft"),
        ("canon/style.md", "the style guide"),
        ("canon/axioms/ax_cold_soak.md", "a rule the style editor must never see"),
        ("cast/vance/voice.md", "the voice"),
    ]
    with pytest.raises(PermissionDenied) as refused:
        documents_for(AgentRole.STYLE_EDITOR, sources)
    assert refused.value.context["path"] == "canon/axioms/ax_cold_soak.md"


# spec 001 / FR-AGENT-09
def test_documents_keep_their_order_and_carry_normalised_paths() -> None:
    sources = [
        ("scenes/004.yaml", "record"),
        ("manuscript\\004.md", "prose"),
        ("./cast/ilan/dossier.md", "dossier"),
    ]
    assert documents_for(AgentRole.AUDITOR, sources) == (
        Document(path="scenes/004.yaml", text="record"),
        Document(path="manuscript/004.md", text="prose"),
        Document(path="cast/ilan/dossier.md", text="dossier"),
    )


# --- plan step 17: the computed document, every source, every role call ---------------------

FINDINGS = "violations: []"


# spec 001 / FR-AGENT-07, FR-AGENT-09 -- the mechanical findings travel under one label, to one
# role.
def test_the_mechanical_findings_label_is_accepted_for_the_auditor_only() -> None:
    assert documents_for(AgentRole.AUDITOR, [(MECHANICAL_FINDINGS, FINDINGS)]) == (
        Document(path=MECHANICAL_FINDINGS, text=FINDINGS),
    )
    for role in AgentRole:
        if role is AgentRole.AUDITOR:
            continue
        with pytest.raises(PermissionDenied):
            documents_for(role, [(MECHANICAL_FINDINGS, FINDINGS)])


# spec 001 / FR-AGENT-09 -- no other computed label, and no other spelling of this one.
@pytest.mark.parametrize(
    "label",
    [
        "computed/other-findings",
        "computed/mechanical-findings/extra",
        "./computed/mechanical-findings",
        r"computed\mechanical-findings",
        "COMPUTED/MECHANICAL-FINDINGS",
    ],
)
def test_no_other_computed_label_reaches_the_auditor(label: str) -> None:
    with pytest.raises(PermissionDenied):
        documents_for(AgentRole.AUDITOR, [(label, FINDINGS)])


# spec 001 / FR-AGENT-09 -- every source of an input is checked, not only the one it is
# labelled with: a voice file carrying a knowledge file is refused to the style editor.
def test_an_input_carrying_an_out_of_row_source_is_refused_before_any_call() -> None:
    carried = RoleInput(
        key="cast/vance/voice.md",
        path="cast/vance/voice.md",
        text="the voice, with the knowledge folded in",
        sources=("cast/vance/knowledge.yaml",),
    )
    client = FakeModelClient()
    with pytest.raises(PermissionDenied) as refused:
        call_role(
            client,
            role=AgentRole.STYLE_EDITOR,
            instruction="Polish.",
            mandatory=[carried],
            output_schema=PolishOutput,
        )
    assert refused.value.context["path"] == "cast/vance/knowledge.yaml"
    assert client.calls == []


# spec 001 / FR-AGENT-09 -- a pruned input is still checked: the budget does not hide a bug.
def test_an_out_of_row_input_is_refused_even_where_the_cap_would_prune_it() -> None:
    inside = RoleInput(key="canon/style.md", path="canon/style.md", text="style")
    outside = RoleInput(key="axiom:x", path="canon/axioms/x.md", text="x" * 3_000)
    client = FakeModelClient()
    with pytest.raises(PermissionDenied):
        call_role(
            client,
            role=AgentRole.STYLE_EDITOR,
            instruction="Polish.",
            mandatory=[inside],
            prunable=[outside],
            output_schema=PolishOutput,
            cap=10,
        )
    assert client.calls == []


# spec 001 / FR-CTX-03 -- two inputs under one key would make `removed` ambiguous.
def test_two_inputs_with_one_key_are_refused() -> None:
    twice = RoleInput(key="canon/style.md", path="canon/style.md", text="style")
    with pytest.raises(ValueError, match="share a key"):
        call_role(
            FakeModelClient(),
            role=AgentRole.STYLE_EDITOR,
            instruction="Polish.",
            mandatory=[twice, twice],
            output_schema=PolishOutput,
        )


# spec 001 / FR-AGENT-09 -- every document of every role call, as the fake recorded it, is
# inside that role's row; the computed label reaches the auditor and nobody else.
@pytest.mark.parametrize("name", CALL_NAMES)
def test_every_role_call_sends_only_documents_from_its_row(name: str, fixture_store: Store) -> None:
    case = ROLE_CALLS[name]
    client = FakeModelClient({case.role: [Reply.of(case.output)]})
    case.run(fixture_store, client)
    [call] = client.calls
    assert call.role is case.role
    assert call.documents
    for document in call.documents:
        computed = document.path == MECHANICAL_FINDINGS and case.role is AgentRole.AUDITOR
        assert computed or may_receive(case.role, document.path), document.path


# spec 001 / FR-AGENT-09 -- every document of every call of whole turns (a clean one, one whose
# writer is offered an open setup, one that revises three times and escalates) is inside the
# calling role's row of Figure 3's `In` column.
def test_every_call_of_a_turn_sends_only_documents_from_its_row(fixture_store: Store) -> None:
    env = make_turn_env(fixture_store)
    clients = [scripted("happy_002"), scripted("happy_002")]
    env.run(clients[0])
    env.run(clients[1], "006")
    blocked = FakeModelClient({AgentRole.WRITER: [write(FIVE_SENTENCES)]}, fallback=always_blocking)
    env.run(blocked)
    calls = [call for client in [*clients, blocked] for call in client.calls]

    assert {call.role for call in calls} == {
        AgentRole.WRITER,
        AgentRole.AUDITOR,
        AgentRole.STYLE_EDITOR,
        AgentRole.CANONISER,
    }
    assert any(call.output_schema == "ReviseOutput" for call in calls)
    for call in calls:
        assert call.documents, call.output_schema
        for document in call.documents:
            computed = document.path == MECHANICAL_FINDINGS and call.role is AgentRole.AUDITOR
            assert computed or may_receive(call.role, document.path), (
                call.role,
                document.path,
            )
