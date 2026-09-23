"""The canoniser's model call, `extract_facts`, and the merge of its facts with the writer's
(FR-AGENT-05).

Figure 3's canoniser row reads `ledger/proposed.yaml`, `manuscript/NNN.md` and `canon/`. The
call reads the accepted draft -- mandatory -- and the canon documents of the scene's assembled
context, in the assembly's rank order and prunable (FR-CTX-03). "Canon documents" is read
strictly: an entry of the assembly is sent only when **every** file its text carries is inside
the row *and* under `canon/` (`is_canon_entry`), so a character's dossier (four `cast/` files)
never reaches the canoniser, and neither does a term folded into one, a chapter digest, an open
setup or the previous scene's tail -- the row lists `manuscript/NNN.md` for the accepted draft,
not for another scene's prose. The fixed block (`canon/project.md`, `canon/style.md`) is canon
and heads the ranking.

The assembly is made at the full cap with no system prompt, so it is only a source of ranked
documents here; the canoniser fits them to its own call. An entry the assembly itself had to
drop at 100k is listed after the canoniser's own removals when it would have been a canon
document (`CANON_KINDS`), since it is missing from this call too.

**Two roles look for inventions, on purpose.** The writer reports its own as it drafts and the
canoniser reads the accepted prose for what it asserts; `merge_proposals` joins the two lists,
the writer's first, deduplicated by `target_entity + target_field + normalised payload`. The
same key names a proposal in `ledger/proposed.yaml` (`proposal_id`), so the queue never holds
one assertion twice, whichever role queued it first and however often a revision re-proposed it.
Queuing is not done here: roles never write, and `app.agents.service` appends under the role's
tool set.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Final

from app.agents.models import RoleCall
from app.agents.roles import RoleInput, call_role
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.db import IndexKind
from app.commons.llm import ModelClient
from app.commons.permissions import AgentRole, may_receive
from app.commons.schemas import ExtractOutput, ProposedFactDraft, SelectedEntity
from app.commons.stores import Store, paths
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service

ROLE: Final[AgentRole] = AgentRole.CANONISER

CANON_KINDS: Final[frozenset[str]] = frozenset(
    {
        IndexKind.AXIOM,
        IndexKind.TECHNOLOGY,
        IndexKind.LOCATION,
        IndexKind.FACTION,
        IndexKind.HISTORICAL_EVENT,
        IndexKind.TERM,
    }
)
"""The entity kinds whose assembled entry is canon through and through: the record and whatever
is folded into it (a parent location, a bound term) all live under `canon/`. A character, a
chapter digest and a setup are not."""

PROPOSAL_ID_PREFIX: Final[str] = "pf"
PROPOSAL_DIGEST_LENGTH: Final[int] = 12

FactKey = tuple[str, str, str]


def normalise_payload(payload: str) -> str:
    """FR-AGENT-05's "normalised payload": compatibility-normalised, case-folded, whitespace
    collapsed, surrounding punctuation and quotation marks dropped. `Three hours.` and
    `three  hours` are one assertion; `three hours` and `four hours` are two."""
    folded = unicodedata.normalize("NFKC", payload).casefold()
    return " ".join(folded.split()).strip(" .,;:!?\"'")


def fact_key(fact: ProposedFactDraft) -> FactKey:
    """The address and the claim, as FR-AGENT-05 deduplicates them."""
    return (fact.target_entity, fact.target_field, normalise_payload(fact.payload))


def proposal_id(scene_id: str, fact: ProposedFactDraft) -> str:
    """The deterministic id of a proposed fact: `pf-<scene>-<digest of the fact key>`.

    Derived from the key, so the same assertion from the same scene gets the same id whether
    the writer or the canoniser proposed it, and in whichever iteration; `app.agents.service`
    skips a fact whose id the queue already holds rather than queuing it twice."""
    payload = json.dumps([scene_id, *fact_key(fact)], ensure_ascii=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:PROPOSAL_DIGEST_LENGTH]
    return f"{PROPOSAL_ID_PREFIX}-{scene_id}-{digest}"


def merge_proposals(
    writer: Iterable[ProposedFactDraft], extracted: Iterable[ProposedFactDraft]
) -> list[ProposedFactDraft]:
    """FR-AGENT-05. The writer's proposals, then the canoniser's, each assertion once.

    The first occurrence wins, so a fact both roles found keeps the writer's wording and
    evidence -- the author's own quote of what it invented. Pure; the orchestrator of step 18
    persists the result.
    """
    merged: list[ProposedFactDraft] = []
    seen: set[FactKey] = set()
    for fact in [*writer, *extracted]:
        key = fact_key(fact)
        if key not in seen:
            seen.add(key)
            merged.append(fact)
    return merged


def extract_instruction(scene_id: str) -> str:
    """FR-AGENT-05. Which document is the accepted prose; the records are the others."""
    return "\n".join(
        [
            (
                f"Operation: extract the facts the accepted scene {scene_id} asserts about the "
                "story world that the records do not already hold."
            ),
            (
                f"The accepted prose is the document labelled {paths.draft(scene_id)}; the other "
                "documents are the records of the world it was written against."
            ),
            "Return every such assertion in facts, an empty list if there is none.",
        ]
    )


def is_canon_entry(sources: Iterable[str]) -> bool:
    """True when every file an assembled entry carries is a canon file the canoniser may read."""
    listed = list(sources)
    return bool(listed) and all(
        source.partition("/")[0] == paths.CANON and may_receive(ROLE, source) for source in listed
    )


def _is_canon_key(key: str) -> bool:
    kind, _, _ = key.partition(":")
    return kind in CANON_KINDS


def extract_facts(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> RoleCall[ExtractOutput]:
    """FR-AGENT-05. Assertions in the accepted draft that canon does not already hold.

    Mandatory: the draft's prose. Prunable: the assembled context's canon documents, in rank
    order, fitted to `cap` with the canoniser's own prompt and instruction counted.
    """
    draft = paths.draft(scene_id)
    body = manuscript_service.read_draft(store, scene_id).body
    context = scenes_service.assemble_context(store, scene_id, selected)
    canon = [RoleInput.of(entry) for entry in context.entries if is_canon_entry(entry.sources)]
    return call_role(
        client,
        role=ROLE,
        instruction=extract_instruction(scene_id),
        mandatory=[RoleInput(key=draft, path=draft, text=body)],
        prunable=canon,
        output_schema=ExtractOutput,
        cap=cap,
        ranked_after=[key for key in context.removed if _is_canon_key(key)],
    )


__all__ = [
    "CANON_KINDS",
    "ROLE",
    "extract_facts",
    "extract_instruction",
    "fact_key",
    "is_canon_entry",
    "merge_proposals",
    "normalise_payload",
    "proposal_id",
]
