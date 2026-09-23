"""AC 33, the role half -- FR-CTX-03's split, seen from every role call, with the cap lowered.

`scenes/tests/test_assemble.py` pins the assembly's own stop. This file pins what each role
does with the cap (FR-CTX-03, FR-CTX-04, FR-CTX-05):

* **Whole prunable inputs go, lowest rank first, and none is cut.** Each case first runs the
  call at the full cap, then again with the cap set just below what it needed: the second call
  carries the first call's documents minus a suffix, each byte-identical, and the result names
  what went in `removed`, first in `truncated_at`.
* **Mandatory inputs never go.** A cap below the mandatory part raises `ContextBudgetExceeded`
  and the fake records **no call at all**, neither made nor refused over the cap: the role
  stopped before it reached the client (AC 22's rule, at the role).
* **The auditor says what it did not check.** Every auditor input the cap removed is listed in
  `skipped` under the invariant it serves -- 6 for an axiom, 1 for a knowledge file, 3 for a
  changes file (FR-CTX-04).
* **The turn records it** (plan step 18). With the cap lowered for a whole turn, the removed ids
  and `truncated_at` of the writer, the auditor and the canoniser are on their steps of the turn
  record, the auditor's removals are in the iteration's `skipped`, and a mandatory part over the
  cap at a later role escalates the turn before that role's call is made.

The cap is lowered by argument and never raised (NFR-05); estimates are FR-CTX-02's, the same
function the role and the fake use (plan P7).
"""

from __future__ import annotations

import pytest

from app.agents.roles import MECHANICAL_FINDINGS, auditor, canoniser, style_editor, writer
from app.agents.tests.test_roles import ROLE_CALLS, SELECTED_002, SELECTED_003
from app.commons.errors import ContextBudgetExceeded
from app.commons.llm import FakeModelClient, Reply
from app.commons.llm.tokens import estimate_tokens
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    SemanticAuditOutput,
)
from app.commons.stores import Store
from app.scenes import service as scenes_service

EMPTY_AUDIT = SemanticAuditOutput(violations=[])


def replies(role: AgentRole, count: int = 1) -> FakeModelClient:
    output = EMPTY_AUDIT if role is AgentRole.AUDITOR else None
    case = next(case for case in ROLE_CALLS.values() if case.role is role)
    return FakeModelClient({role: [Reply.of(output or case.output) for _ in range(count)]})


# --- the writer ----------------------------------------------------------------------------


# spec 001 / AC 33 -- the writer's selected entities go whole, from the lowest rank.
def test_the_writer_prunes_whole_entries_from_the_lowest_rank(fixture_store: Store) -> None:
    client = replies(AgentRole.WRITER, 2)
    full = writer.write(fixture_store, client, "003", SELECTED_003)
    first = client.calls[0]
    last = first.documents[-1]
    lowered = writer.write(fixture_store, client, "003", SELECTED_003, cap=first.estimate - 1)
    second = client.calls[1]
    assert second.documents == first.documents[:-1]
    assert full.removed == ()
    assert len(lowered.removed) == 1
    assert lowered.truncated_at == lowered.removed[0]
    context = scenes_service.assemble_context(fixture_store, "003", SELECTED_003)
    [entry] = [entry for entry in context.entries if entry.key == lowered.truncated_at]
    assert entry.text == last.text
    assert not entry.mandatory


# spec 001 / AC 33, FR-CTX-05 -- the writer's mandatory part over the cap: no call.
def test_the_writer_mandatory_part_over_the_cap_makes_no_call(fixture_store: Store) -> None:
    client = FakeModelClient()
    with pytest.raises(ContextBudgetExceeded):
        writer.write(fixture_store, client, "003", SELECTED_003, cap=50)
    assert client.calls == []
    assert client.refused_over_cap == []


# --- the canoniser -------------------------------------------------------------------------


# spec 001 / AC 33 -- the canoniser's canon documents go whole, lowest rank first; the draft
# stays.
def test_the_canoniser_prunes_canon_documents_and_keeps_the_draft(fixture_store: Store) -> None:
    client = replies(AgentRole.CANONISER, 3)
    canoniser.extract_facts(fixture_store, client, "003", SELECTED_003)
    first = client.calls[0]
    one_less = canoniser.extract_facts(
        fixture_store, client, "003", SELECTED_003, cap=first.estimate - 1
    )
    assert client.calls[1].documents == first.documents[:-1]
    assert len(one_less.removed) == 1

    draft = first.documents[0]
    only_draft = first.estimate - sum(estimate_tokens(d.text) for d in first.documents[1:])
    bare = canoniser.extract_facts(fixture_store, client, "003", SELECTED_003, cap=only_draft)
    assert client.calls[2].documents == (draft,)
    assert len(bare.removed) == len(first.documents) - 1
    assert bare.truncated_at == bare.removed[0]
    assert bare.removed[0] == "canon/project.md", "the fixed block heads the canoniser's ranking"

    too_small = FakeModelClient()
    with pytest.raises(ContextBudgetExceeded):
        canoniser.extract_facts(fixture_store, too_small, "003", SELECTED_003, cap=only_draft - 1)
    assert too_small.calls == []
    assert too_small.refused_over_cap == []


# --- the auditor ---------------------------------------------------------------------------


# spec 001 / AC 33, FR-CTX-04 -- the auditor's prunable inputs go whole, lowest rank first,
# and every one that went is in `skipped` under the invariant it serves.
def test_the_auditor_prunes_its_ranked_inputs_and_lists_them_as_skipped(
    fixture_store: Store,
) -> None:
    client = replies(AgentRole.AUDITOR, 3)
    full = auditor.audit_semantic(fixture_store, client, "002", SELECTED_002, [])
    first = client.calls[0]
    assert full.skipped == ()
    paths_sent = [document.path for document in first.documents]
    split = paths_sent.index(MECHANICAL_FINDINGS) + 1
    prunable = first.documents[split:]
    assert [document.path for document in prunable] == [
        "canon/axioms/ax_brine_dark.md",
        "canon/axioms/ax_calving_window.md",
        "cast/quiej/knowledge.yaml",
        "cast/quiej/changes.yaml",
    ]

    one_less = auditor.audit_semantic(
        fixture_store, client, "002", SELECTED_002, [], cap=first.estimate - 1
    )
    assert client.calls[1].documents == first.documents[:-1]
    assert one_less.call.removed == ("cast/quiej/changes.yaml",)
    [skip] = one_less.skipped
    assert skip.invariant == 3
    assert "cast/quiej/changes.yaml" in skip.reason

    mandatory = first.estimate - sum(estimate_tokens(d.text) for d in prunable)
    bare = auditor.audit_semantic(fixture_store, client, "002", SELECTED_002, [], cap=mandatory)
    assert client.calls[2].documents == first.documents[:split]
    assert bare.call.removed == (
        "axiom:ax_brine_dark",
        "axiom:ax_calving_window",
        "cast/quiej/knowledge.yaml",
        "cast/quiej/changes.yaml",
    )
    assert bare.call.truncated_at == "axiom:ax_brine_dark"
    assert [skip.invariant for skip in bare.skipped] == [6, 6, 1, 3]
    assert "axiom ax_brine_dark" in bare.skipped[0].reason


# spec 001 / AC 33, FR-CTX-05 -- the auditor's mandatory part over the cap: no call.
def test_the_auditor_mandatory_part_over_the_cap_makes_no_call(fixture_store: Store) -> None:
    client = FakeModelClient()
    with pytest.raises(ContextBudgetExceeded):
        auditor.audit_semantic(fixture_store, client, "002", SELECTED_002, [], cap=100)
    assert client.calls == []
    assert client.refused_over_cap == []


# --- all mandatory: polish, digest, rollup ---------------------------------------------------


# spec 001 / AC 33 -- polish, digest and rollup are all mandatory: nothing is pruned, and a cap
# they do not fit refuses the call before it reaches the client.
@pytest.mark.parametrize("name", ["polish", "digest", "rollup"])
def test_an_all_mandatory_call_is_refused_whole_over_the_cap(
    name: str, fixture_store: Store
) -> None:
    case = ROLE_CALLS[name]
    client = FakeModelClient({case.role: [Reply.of(case.output)]})
    case.run(fixture_store, client)
    [call] = client.calls
    cap = call.estimate - 1
    too_small = FakeModelClient()
    with pytest.raises(ContextBudgetExceeded):
        if name == "polish":
            style_editor.polish(fixture_store, too_small, "003", cap=cap)
        elif name == "digest":
            writer.digest(fixture_store, too_small, "003", cap=cap)
        else:
            writer.rollup(fixture_store, too_small, arc_id="ar_descent", cap=cap)
    assert too_small.calls == []
    assert too_small.refused_over_cap == []
