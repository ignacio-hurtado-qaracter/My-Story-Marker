"""FR-AGENT-09 -- a document from outside a role's `In` row is refused at assembly.

Figure 3's `In` column ends with the sentence this test exists for: *anything not listed as an
input is not available to the agent*. `documents_for` is the only door from store text to a
role's prompt, so a planted out-of-row document has to stop there, for every role, with the
Figure 3 refusal (`PermissionDenied`) rather than a quiet drop.

The cases are written out by hand from the table in
`docs/architecture.md#figure-3--agents-and-write-permissions`, not derived from
`INPUT_TABLE`, so the test disagrees with the code when someone edits the table. The turn-level
half -- every document of every recorded fake call inside its role's row -- is plan step 18's.
"""

from __future__ import annotations

import pytest

from app.agents.roles import documents_for
from app.commons.errors import PermissionDenied
from app.commons.llm import Document
from app.commons.permissions import AgentRole

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
    assert set(CASES) == set(AgentRole)


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
