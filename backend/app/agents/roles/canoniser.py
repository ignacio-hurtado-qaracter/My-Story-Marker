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

**A fact names a target that exists** (AC 27, FR-OPS-06). `promote` sets a field on an existing
record and refuses anything else, so a fact addressed to an invented field can never be
promoted. The instruction therefore lists the records a fact may address and, per record type,
the fields `promote` can fill, each with its shape and meaning -- all derived by code from
`app.ledger.service.promotable_targets`, the same tests `promote` applies, so the two cannot
disagree, and rendered by `app.agents.roles.targets`, which the writer's instruction shares.
The records are the canon entities the canon documents carry, the scene's location, and the
characters the scene is about: its POV, its participants and the selected characters. A
character's dossier never reaches the canoniser, so its characters are named as not given.
Only identifiers and code-owned field descriptions enter the instruction, never store text
(FR-PERM-07); identifiers belong in the instruction, as the selected list does (`documents_for`).

Every returned fact is checked against that list (`check_fact`). If any fails, the call is
retried **once** with the failing targets named in the instruction; facts still failing after
the retry are left out of `output.facts` and reported on `ExtractCall.rejected`, never dropped
silently. FR-LLM-04's own retry of a schema-invalid answer happens inside each call, unchanged.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

from app.agents.models import ExtractCall, RejectedFact, RoleCall
from app.agents.roles import RoleInput, call_role
from app.agents.roles.targets import FIELD_RULE, SHAPE_RULES, render_targets
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.db import IndexKind
from app.commons.llm import ModelClient
from app.commons.permissions import AgentRole, may_receive
from app.commons.schemas import ExtractOutput, ProposedFactDraft, SelectedEntity
from app.commons.stores import Store, paths
from app.ledger import service as ledger_service
from app.ledger.service import FieldShape, PromotableTarget
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service
from app.scenes.models import AssembledContext

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

QUOTED_MAX: Final[int] = 60
"""The longest stretch of a rejected target the retry instruction repeats back."""


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


def extract_instruction(scene_id: str, targets: Sequence[PromotableTarget] = ()) -> str:
    """FR-AGENT-05, AC 27. Which document is the accepted prose, what a fact may address, and
    how.

    A listed record whose file the canoniser may not read -- a character's dossier, which
    Figure 3 keeps out of its row -- is named as not given (`render_targets`, `hidden`), derived
    from the target's own path by the same test that admits a canon document (`is_canon_entry`),
    so the instruction never claims the model can see a record it cannot. The closing line asks
    for a pass over every listed record: the first live runs stopped after the first record
    that had something to say."""
    hidden = [target.entity for target in targets if not is_canon_entry((target.path,))]
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
            *render_targets(targets, hidden=hidden),
            (
                "Work through the listed records one at a time: for each, compare what the prose "
                "asserts about it, in narration and in what characters say, with what its "
                "document states, field by field. A scene usually asserts something about more "
                "than one record; do not stop at the first."
            ),
            "Return every such assertion in facts, an empty list if there is none.",
        ]
    )


def _quoted(value: str) -> str:
    """A model-supplied target, repeated back bounded and ASCII-escaped."""
    return json.dumps(value[:QUOTED_MAX], ensure_ascii=True)


def retry_instruction(instruction: str, rejected: Sequence[RejectedFact]) -> str:
    """FR-AGENT-05. The instruction again, with the targets the first answer got wrong named.

    Only the address is repeated -- entity and field, bounded -- never a payload or evidence,
    so the retry carries no prose back into the instruction."""
    named = [
        f"- target_entity {_quoted(item.fact.target_entity)}, target_field "
        f"{_quoted(item.fact.target_field)}: {item.reason}"
        for item in rejected
    ]
    return "\n".join(
        [
            instruction,
            (
                "Your previous answer addressed these facts to targets promotion cannot write, "
                "so they were not kept:"
            ),
            *named,
            (
                "Answer again with the complete list of facts. Address each one to a listed "
                "record and one of the fields listed for it; leave out an assertion that fits "
                "none of them."
            ),
        ]
    )


def check_fact(targets: Mapping[str, PromotableTarget], fact: ProposedFactDraft) -> str | None:
    """FR-AGENT-05, FR-OPS-06. Why `promote` could not write this fact's address, or `None`.

    The entity must be a listed record, the field one `promote` can fill on it
    (`PromotableTarget.field`), and a mapping payload must be written `key: value`
    (`split_mapping_payload`): the tests `promote` applies, from the same module."""
    target = targets.get(fact.target_entity)
    if target is None:
        return "the entity is not one of the listed records"
    field = target.field(fact.target_field)
    if field is None:
        return f"the field is not one of those listed for {target.record_type} records"
    if field.shape is FieldShape.MAPPING and (
        ledger_service.split_mapping_payload(fact.payload) is None
    ):
        return 'the field is a map, so the payload must be written "key: value"'
    return None


def partition_facts(
    targets: Mapping[str, PromotableTarget],
    facts: Sequence[ProposedFactDraft],
    *,
    attempt: int,
) -> tuple[list[ProposedFactDraft], list[RejectedFact]]:
    """The facts whose address is promotable, unchanged and in order, and the others with why."""
    valid: list[ProposedFactDraft] = []
    rejected: list[RejectedFact] = []
    for index, fact in enumerate(facts):
        reason = check_fact(targets, fact)
        if reason is None:
            valid.append(fact)
        else:
            rejected.append(RejectedFact(attempt=attempt, index=index, fact=fact, reason=reason))
    return valid, rejected


def is_canon_entry(sources: Iterable[str]) -> bool:
    """True when every file an assembled entry carries is a canon file the canoniser may read."""
    listed = list(sources)
    return bool(listed) and all(
        source.partition("/")[0] == paths.CANON and may_receive(ROLE, source) for source in listed
    )


def _is_canon_key(key: str) -> bool:
    kind, _, _ = key.partition(":")
    return kind in CANON_KINDS


def fact_targets(
    store: Store,
    scene_id: str,
    context: AssembledContext,
    selected: Sequence[SelectedEntity],
) -> tuple[PromotableTarget, ...]:
    """FR-AGENT-05. The records a fact of this scene may address, as `promote` resolves them.

    In order: every entity a canon document carries (its own record and what is folded into
    it), the scene's location, then its POV, its participants and the selected characters.
    `promotable_targets` keeps each once and drops what `promote` would refuse, such as a
    lexicon term, which has no record of its own."""
    carried = [
        key.partition(":")[2]
        for entry in context.entries
        if is_canon_entry(entry.sources)
        for key in entry.carries
    ]
    scene = scenes_service.read_scene(store, scene_id)
    characters = [
        entity.entity_id for entity in selected if entity.kind == IndexKind.CHARACTER.value
    ]
    entities = [*carried, scene.location, scene.pov, *scene.participants, *characters]
    return ledger_service.promotable_targets(store, entities)


def _settled(
    call: RoleCall[ExtractOutput],
    facts: list[ProposedFactDraft],
    *,
    targets: Sequence[PromotableTarget],
    retried: Sequence[RejectedFact] = (),
    rejected: Sequence[RejectedFact] = (),
    first: RoleCall[ExtractOutput] | None = None,
) -> ExtractCall:
    """The call as the orchestrator reads it: its output holding only the promotable `facts`."""
    completion = dataclasses.replace(call.completion, output=ExtractOutput(facts=facts))
    return ExtractCall(
        role=call.role,
        completion=completion,
        documents=call.documents,
        instruction=call.instruction,
        removed=call.removed,
        truncated_at=call.truncated_at,
        prompt_version=call.prompt_version,
        targets=tuple(target.entity for target in targets),
        retried=tuple(retried),
        rejected=tuple(rejected),
        first=first,
    )


def extract_facts(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> ExtractCall:
    """FR-AGENT-05, AC 27. Assertions in the accepted draft that canon does not already hold,
    each addressed to a field `promote` can write.

    Mandatory: the draft's prose. Prunable: the assembled context's canon documents, in rank
    order, fitted to `cap` with the canoniser's own prompt and instruction counted. The
    instruction lists `fact_targets`; a record whose document the cap prunes stays listed, since
    `promote` can still write it. A first answer with any unpromotable address is retried once
    (`retry_instruction`); see `ExtractCall` for what the result then holds.
    """
    draft = paths.draft(scene_id)
    body = manuscript_service.read_draft(store, scene_id).body
    context = scenes_service.assemble_context(store, scene_id, selected)
    canon = [RoleInput.of(entry) for entry in context.entries if is_canon_entry(entry.sources)]
    targets = fact_targets(store, scene_id, context, selected)
    by_entity = {target.entity: target for target in targets}
    instruction = extract_instruction(scene_id, targets)

    def attempt(text: str) -> RoleCall[ExtractOutput]:
        return call_role(
            client,
            role=ROLE,
            instruction=text,
            mandatory=[RoleInput(key=draft, path=draft, text=body)],
            prunable=canon,
            output_schema=ExtractOutput,
            cap=cap,
            ranked_after=[key for key in context.removed if _is_canon_key(key)],
        )

    first = attempt(instruction)
    valid, retried = partition_facts(by_entity, first.output.facts, attempt=1)
    if not retried:
        return _settled(first, valid, targets=targets)

    second = attempt(retry_instruction(instruction, retried))
    again, rejected = partition_facts(by_entity, second.output.facts, attempt=2)
    return _settled(
        second,
        merge_proposals(valid, again),
        targets=targets,
        retried=retried,
        rejected=rejected,
        first=first,
    )


__all__ = [
    "CANON_KINDS",
    "FIELD_RULE",
    "ROLE",
    "SHAPE_RULES",
    "check_fact",
    "extract_facts",
    "extract_instruction",
    "fact_key",
    "fact_targets",
    "is_canon_entry",
    "merge_proposals",
    "normalise_payload",
    "partition_facts",
    "proposal_id",
    "render_targets",
    "retry_instruction",
]
