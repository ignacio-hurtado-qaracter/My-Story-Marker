"""The auditor's model call, `audit_semantic`, and what code does with its findings (FR-AGENT-06).

The mechanical checks (FR-AUD-01..08) are backend code; this is the other half, the invariants
only a reader can judge: 3 (a body changing with no registered change), 6 (an axiom of the
turn's selected list broken) and the prose halves of 1 (a character using what they do not yet
know) and 8 (the declared value change not delivered). It reports and never repairs: the
output is a list of findings, and the only write they may ever become is
`ledger/violations.yaml`, under the auditor, through `app.agents.service`.

**Inputs, split as FR-CTX-03 splits them.** Mandatory: the draft's prose, the scene record,
the POV's dossier as of the scene, the pinned axioms of the selected list, and the mechanical
findings. Prunable, in this order: the non-pinned selected axioms in rank order, then each
participant's `knowledge.yaml` and `changes.yaml` in the order the record lists participants.
Every input the cap removes is listed in `skipped` under the invariant it serves -- an axiom
under 6, a knowledge file under 1, a changes file under 3 -- so the absence of a finding is
never mistaken for a pass on something that was never checked (FR-CTX-04).

**What is instruction and what is data.** The selected-entity list goes in the instruction as
identifiers (FR-AGENT-06: the axioms it names are the ones in force for invariant 6). The
mechanical findings quote the prose, so they go in as data (FR-AGENT-07), in the one computed
document `MECHANICAL_FINDINGS`, rendered as a violations file renders.

**What code does to a finding.** Each `SemanticViolation` becomes a DR-07 `Violation` with
`source: model` and the deterministic id of `ledger.audit.violation_id`, so a re-audit
recognises its own findings when it is persisted. The evidence is checked against the draft,
because the quote is the only thing anchoring a judgement to the page:

* at its offset -- taken as given;
* elsewhere in the draft -- moved to the occurrence nearest the stated offset (the earlier on a
  tie), so the revise step can find the span;
* nowhere in the draft -- kept, never dropped, with the quote and offset as the model gave
  them, and a `blocking` severity lowered to `reviewable`: a person should judge a finding
  that points at no text, and the writer cannot revise a span that is not there.

A finding for an invariant FR-AGENT-06 does not delegate is not recorded, as DR-12's
`SemanticViolation` says, and the same finding twice is recorded once. Every one of these is
listed in the result's `adjustments`: nothing a model reported disappears without a trace.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel

from app.agents.models import (
    Adjustment,
    FindingAdjustment,
    SemanticAuditResult,
)
from app.agents.roles import MECHANICAL_FINDINGS, RoleInput, call_role
from app.canon import service as canon_service
from app.canon.models import Axiom
from app.cast import service as cast_service
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.db import CANON_DIRECTORY_BY_KIND, IndexKind
from app.commons.deps import SemanticSkip
from app.commons.errors import NotFound
from app.commons.llm import ModelClient
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Evidence,
    SelectedEntity,
    SemanticAuditOutput,
    SemanticViolation,
    Severity,
    Violation,
    ViolationsFile,
    ViolationSource,
)
from app.commons.stores import Store, paths
from app.ledger.audit import violation_id
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service

ROLE: Final[AgentRole] = AgentRole.AUDITOR

REMIT: Final[frozenset[int]] = frozenset({1, 3, 6, 8})
"""FR-AGENT-06, FR-AUD-09: the invariants delegated to the model-backed auditor."""

AXIOM_INVARIANT: Final[int] = 6
KNOWLEDGE_INVARIANT: Final[int] = 1
CHANGES_INVARIANT: Final[int] = 3

_AXIOMS: Final[str] = CANON_DIRECTORY_BY_KIND[IndexKind.AXIOM]


@dataclass(frozen=True, slots=True)
class _Prunable:
    """A prunable input and the invariant its absence weakens (FR-CTX-04)."""

    item: RoleInput
    invariant: int
    what: str


def _axiom_input(store: Store, identifier: str) -> RoleInput:
    record = canon_service.entity(store, _AXIOMS, identifier, Axiom)
    return RoleInput(
        key=f"{IndexKind.AXIOM.value}:{identifier}",
        path=paths.canon_entity(_AXIOMS, identifier),
        text=scenes_service.render_record(record),
    )


def _participant_file(store: Store, participant: str, which: str) -> str | None:
    """A participant's `knowledge.yaml` or `changes.yaml`, rendered, or None when it does not
    exist -- which the caller lists in `skipped` rather than treating as empty."""
    record: BaseModel
    try:
        if which == "knowledge":
            record = cast_service.read_knowledge(store, participant)
        else:
            record = cast_service.read_changes(store, participant)
    except NotFound:
        return None
    return scenes_service.render_record(record)


def selected_axioms(selected: Sequence[SelectedEntity]) -> tuple[list[str], list[str]]:
    """The selected axioms, pinned first and then the rest in rank order, each once.

    Pinned means entered through the record's `pins` or a tag-scope match (FR-OPS-02); those
    are the rules the architect said the scene must honour, and FR-CTX-03 makes them
    mandatory."""
    pinned: list[str] = []
    ranked: list[str] = []
    for entity in selected:
        if entity.kind != IndexKind.AXIOM.value:
            continue
        identifier = entity.entity_id
        if identifier in pinned or identifier in ranked:
            continue
        (pinned if entity.pinned else ranked).append(identifier)
    return pinned, ranked


def audit_instruction(scene_id: str, selected: Sequence[SelectedEntity]) -> str:
    """FR-AGENT-06. The documents by label, and the selected list as identifiers."""
    listed = ", ".join(
        f"{entity.kind}:{entity.entity_id}{' (pinned)' if entity.pinned else ''}"
        for entity in selected
    )
    pinned, ranked = selected_axioms(selected)
    in_force = ", ".join([*pinned, *ranked]) or "none"
    return "\n".join(
        [
            f"Operation: audit scene {scene_id}.",
            (
                f"The prose is the document labelled {paths.draft(scene_id)}; an offset counts "
                "characters from the first character of that document's text. The scene record is "
                f"the document labelled {paths.scene(scene_id)}."
            ),
            (
                f"The findings of the mechanical checks are the document labelled "
                f"{MECHANICAL_FINDINGS}. They are known: do not report them again."
            ),
            f"The turn's selected entities: {listed or 'none'}.",
            (
                f"The rules in force for invariant 6 are the selected axioms: {in_force}. Check "
                "invariant 6 only against those given as documents; one named here without a "
                "document was left out for length and is reported as not checked."
            ),
            "Return your findings in violations, an empty list for a clean scene.",
        ]
    )


def _inputs(
    store: Store, scene_id: str, selected: Sequence[SelectedEntity], mechanical: Sequence[Violation]
) -> tuple[list[RoleInput], list[_Prunable], list[SemanticSkip]]:
    """FR-AGENT-06, FR-CTX-03. The mandatory and the prunable inputs, and what is absent from
    the start (a participant with no knowledge or changes file)."""
    scene = scenes_service.read_scene(store, scene_id)
    render = scenes_service.render_record
    draft = paths.draft(scene_id)
    record = paths.scene(scene_id)
    pov = scene.pov
    dossier = paths.cast_file(pov, "dossier")
    mandatory = [
        RoleInput(key=draft, path=draft, text=manuscript_service.read_draft(store, scene_id).body),
        RoleInput(key=record, path=record, text=render(scene)),
        RoleInput(
            key=dossier,
            path=dossier,
            text=render(cast_service.dossier(store, pov, scene.story_time)),
            sources=(
                paths.cast_file(pov, "knowledge"),
                paths.cast_file(pov, "changes"),
                paths.RELATIONSHIPS,
            ),
        ),
    ]
    pinned, ranked = selected_axioms(selected)
    mandatory.extend(_axiom_input(store, identifier) for identifier in pinned)
    mandatory.append(
        RoleInput(
            key=MECHANICAL_FINDINGS,
            path=MECHANICAL_FINDINGS,
            text=render(ViolationsFile(violations=list(mechanical))),
        )
    )
    prunable = [
        _Prunable(_axiom_input(store, identifier), AXIOM_INVARIANT, f"axiom {identifier}")
        for identifier in ranked
    ]
    absent: list[SemanticSkip] = []
    for participant in scene.participants:
        for which, invariant in (
            ("knowledge", KNOWLEDGE_INVARIANT),
            ("changes", CHANGES_INVARIANT),
        ):
            path = paths.cast_file(participant, which)
            text = _participant_file(store, participant, which)
            if text is None:
                reason = (
                    f"{path} does not exist, so invariant {invariant} was not checked for "
                    f"{participant}"
                )
                absent.append(SemanticSkip(invariant=invariant, reason=reason))
                continue
            item = RoleInput(key=path, path=path, text=text)
            prunable.append(_Prunable(item, invariant, path))
    return mandatory, prunable, absent


def locate(body: str, evidence: Evidence) -> Evidence | None:
    """The evidence as the draft holds it: as given when the quote is at its offset, moved to
    the nearest occurrence when it is elsewhere, None when the draft does not contain it."""
    quote, offset = evidence.quote, evidence.offset
    if body[offset : offset + len(quote)] == quote:
        return evidence
    positions: list[int] = []
    start = body.find(quote)
    while start != -1:
        positions.append(start)
        start = body.find(quote, start + 1)
    if not positions:
        return None
    nearest = min(positions, key=lambda position: (abs(position - offset), position))
    return Evidence(quote=quote, offset=nearest)


def to_violations(
    scene_id: str, body: str, findings: Sequence[SemanticViolation]
) -> tuple[list[Violation], list[FindingAdjustment]]:
    """FR-AGENT-06. Model findings as DR-07 violations, and every adjustment made to them (see
    the module docstring for the rules)."""
    violations: list[Violation] = []
    adjustments: list[FindingAdjustment] = []
    seen: set[str] = set()
    for index, finding in enumerate(findings):
        invariant = finding.invariant
        if invariant not in REMIT:
            detail = f"invariant {invariant} is not delegated to the model (FR-AGENT-06)"
            adjustments.append(FindingAdjustment(index, invariant, Adjustment.OUT_OF_REMIT, detail))
            continue
        evidence = locate(body, finding.evidence)
        severity = finding.severity
        if evidence is None:
            evidence = finding.evidence
            if severity is Severity.BLOCKING:
                severity = Severity.REVIEWABLE
            detail = (
                f"the quote is not in the draft; kept as reported with severity {severity.value}"
            )
            adjustments.append(FindingAdjustment(index, invariant, Adjustment.UNANCHORED, detail))
        elif evidence.offset != finding.evidence.offset:
            detail = f"offset {finding.evidence.offset} moved to {evidence.offset}"
            adjustments.append(FindingAdjustment(index, invariant, Adjustment.RELOCATED, detail))
        identifier = violation_id(
            scene=scene_id, invariant=invariant, evidence=evidence, source=ViolationSource.MODEL
        )
        if identifier in seen:
            detail = f"repeats {identifier}"
            adjustments.append(FindingAdjustment(index, invariant, Adjustment.DUPLICATE, detail))
            continue
        seen.add(identifier)
        violations.append(
            Violation(
                id=identifier,
                scene=scene_id,
                invariant=invariant,
                evidence=evidence,
                severity=severity,
                resolution=None,
                source=ViolationSource.MODEL,
            )
        )
    return violations, adjustments


def audit_semantic(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    mechanical: Sequence[Violation],
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> SemanticAuditResult:
    """FR-AGENT-06. The semantic invariants of one scene, judged over its accepted draft.

    `selected` is the turn's selected list (FR-OPS-05) -- the one the writer received -- and
    `mechanical` the mechanical half's findings, computed first (FR-AGENT-07). The model call's
    errors propagate; the combined audit turns them into FR-AUD-09's `skipped`.
    """
    mandatory, prunable, absent = _inputs(store, scene_id, selected, mechanical)
    call = call_role(
        client,
        role=ROLE,
        instruction=audit_instruction(scene_id, selected),
        mandatory=mandatory,
        prunable=[entry.item for entry in prunable],
        output_schema=SemanticAuditOutput,
        cap=cap,
    )
    removed = set(call.removed)
    skipped = [
        *absent,
        *(
            SemanticSkip(
                invariant=entry.invariant,
                reason=(
                    f"{entry.what} was pruned from the auditor's context by the input cap "
                    f"(FR-CTX-04); invariant {entry.invariant} was not checked against it"
                ),
            )
            for entry in prunable
            if entry.item.key in removed
        ),
    ]
    body = mandatory[0].text
    violations, adjustments = to_violations(scene_id, body, call.output.violations)
    return SemanticAuditResult(
        call=call,
        violations=tuple(violations),
        skipped=tuple(skipped),
        adjustments=tuple(adjustments),
    )


__all__ = [
    "REMIT",
    "ROLE",
    "audit_instruction",
    "audit_semantic",
    "locate",
    "selected_axioms",
    "to_violations",
]
