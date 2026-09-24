"""The vocabulary every mechanical check shares: how a finding becomes a `Violation`, what its
evidence carries, and how a check says it could not run.

Three decisions live here because each must hold identically across all eight checks.

**Evidence has two shapes, and they are told apart by the draft itself.** DR-07 gives a
violation `evidence` as a quote and an offset "in the draft". The text checks (FR-AUD-05,
FR-AUD-07) have exactly that: the verbatim span of the draft body and its character offset,
so `draft.body[offset:offset + len(quote)] == quote` always holds. The record checks
(FR-AUD-01 record half, -02, -03, -04, -06, -08) breach a *record*, and there is no draft
span to point at -- the planted transit of scenes 001/003 is, by design, invisible on the page.
For those the quote is a locator plus the offending values, always beginning with the
store path of the record that breaches (`scenes/005.yaml value_change: ...`), and the offset
is `RECORD_OFFSET`, zero. The schema requires both fields and an offset cannot be absent, so
the discriminator is the equality above: it holds for draft evidence and, because the quote
starts with a store path rather than prose, not for record evidence. The revise step
(FR-AGENT-02) must use that test before it treats a quote as a span to rewrite.

**Violation ids are derived, not minted.** A persisted report is merged with the one already
on disk (see `persist.py`), and "re-running must not duplicate" is only checkable if the same
finding gets the same id on every run. The id is a digest of the finding's natural key --
scene, invariant, source, quote, offset -- and deliberately *not* of its severity, because
FR-AUD-02's severity depends on which scene is currently last in discourse order, and a
finding does not become a different finding when a chapter is appended after it. The
model-backed auditor's findings (FR-AGENT-06, plan step 17) take their ids from the same
function with `source: model`, under their own prefix, so a model finding and a mechanical one
can never share an id even when they quote the same span.

**A check that could not run says so.** A check whose input is absent (no draft, no
lexicon, no transit matrix) returns `Skip` with the reason instead of an empty list. The
entry point lists it in `skipped`, beside the model-backed half of FR-AUD-09, for the same
reason FR-AUD-09 exists: the absence of a violation must never be mistaken for a pass.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final

from app.commons.schemas import Evidence, Scene, Severity, Violation, ViolationSource
from app.ledger.audit.material import AuditMaterial

SOURCE: Final[ViolationSource] = ViolationSource.MECHANICAL
"""Every finding produced in this package. DR-07 `source` tells the mechanical checks from the
model-backed auditor so a reader can see which half produced a finding and, by absence, which
half never ran."""

RECORD_OFFSET: Final[int] = 0
"""The offset of record evidence, which has no draft span (see the module docstring)."""

ID_PREFIX: Final[str] = "mech"
MODEL_ID_PREFIX: Final[str] = "model"
ID_PREFIXES: Final[dict[ViolationSource, str]] = {
    ViolationSource.MECHANICAL: ID_PREFIX,
    ViolationSource.MODEL: MODEL_ID_PREFIX,
}
"""One prefix per half of the audit, so the id says at a glance which half made a finding."""
ID_DIGEST_LENGTH: Final[int] = 12
"""48 bits of SHA-256. The ids of one file are compared with each other only, and the merge
refuses a collision rather than overwriting (`persist.merge`), so a collision is loud."""

_TYPOGRAPHIC: Final[dict[int, str]] = str.maketrans(
    {
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{MODIFIER LETTER APOSTROPHE}": "'",
        "\N{LEFT DOUBLE QUOTATION MARK}": '"',
        "\N{RIGHT DOUBLE QUOTATION MARK}": '"',
    }
)
"""Typographic apostrophes and quotation marks folded to their ASCII forms before matching.

Not in the spec, and a decision this step reports. A `never_says` entry written `I'm sorry`
would otherwise miss a draft that typesets it with U+2019, which is what a model or a word
processor emits by default -- a silent miss of exactly the kind FR-AUD-07 exists to catch.
Every replacement is one code point for one code point, so offsets into the folded text are
offsets into the original, and the quote is always cut from the original."""


@dataclass(frozen=True, slots=True)
class Skip:
    """A check that did not run, and why. Listed in the report's `skipped`, never read as a
    pass (FR-AUD-09's rule, applied to the mechanical half as well)."""

    reason: str


type CheckOutcome = list[Violation] | Skip


@dataclass(frozen=True, slots=True)
class MechanicalCheck:
    """One FR-AUD row: its id, the invariant it serves, and the function that runs it."""

    check: str
    invariant: int
    run: Callable[[AuditMaterial], CheckOutcome]


def present(scene: Scene) -> tuple[str, ...]:
    """Everyone in the scene: the POV first, then the participants in record order.

    DR-03 makes `participants` required, possibly empty and disjoint from `pov` precisely so
    that invariants 1, 4 and 5 run over this pair and nothing narrows them silently to the POV.
    """
    return (scene.pov, *scene.participants)


def natural_key(violation: Violation) -> tuple[str, int, str, str, int]:
    """What makes two reports the same finding: where, which invariant, which half, and the
    evidence. Severity is excluded on purpose (see the module docstring)."""
    return (
        violation.scene,
        violation.invariant,
        violation.source.value,
        violation.evidence.quote,
        violation.evidence.offset,
    )


def violation_id(
    *, scene: str, invariant: int, evidence: Evidence, source: ViolationSource = SOURCE
) -> str:
    """The deterministic id of a finding: `mech-<scene>-i<nn>-<digest>` for the mechanical
    half, `model-<scene>-i<nn>-<digest>` for the model-backed one.

    Readable at a glance -- scene and invariant are in the id -- and stable across runs, so a
    re-run persisted over an earlier one finds its own findings instead of adding copies. The
    source is in the digest as well as the prefix, exactly as it is in the natural key.
    """
    payload = json.dumps(
        [scene, invariant, source.value, evidence.quote, evidence.offset],
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:ID_DIGEST_LENGTH]
    return f"{ID_PREFIXES[source]}-{scene}-i{invariant:02d}-{digest}"


def violation(*, scene: str, invariant: int, severity: Severity, evidence: Evidence) -> Violation:
    """A mechanical finding as DR-07 records it: reported, unresolved, never repaired.

    `resolution` is always empty here. Only a human sets it, through the auditor's route with
    `X-Actor: human` (IF-04); an auditor that resolved its own findings would be the
    self-correcting auditor `architecture.md` names as the failure mode of `Violation`.
    """
    return Violation(
        id=violation_id(scene=scene, invariant=invariant, evidence=evidence),
        scene=scene,
        invariant=invariant,
        evidence=evidence,
        severity=severity,
        resolution=None,
        source=SOURCE,
    )


def record_evidence(detail: str) -> Evidence:
    """Evidence for a breach that lives in a record rather than in the draft. `detail` begins
    with the store path of the record, which is what keeps it from reading as a draft span."""
    return Evidence(quote=detail, offset=RECORD_OFFSET)


def occurrences(text: str, needle: str) -> Iterator[Evidence]:
    """Every case-insensitive occurrence of `needle` in `text`, as draft evidence.

    FR-AUD-05 and FR-AUD-07 are both "search the draft" checks and must search the same way.
    Substring, not whole-word: the fixture README states the canonical forms contain no
    forbidden variant as a substring precisely so this search is unambiguous. `re.IGNORECASE`
    rather than `casefold()`, because full case folding can change a string's length and the
    offset would then point at the wrong character. The quote is cut from the original text,
    so it is the draft's own spelling (`Trust me`), not the needle's (`trust me`).

    A blank needle is not searched: it would match at every offset of the draft, which is a
    defect in the record rather than a finding about the prose. The schema allows one; this
    is reported with the step.
    """
    if not needle.strip():
        return
    pattern = re.compile(re.escape(needle.translate(_TYPOGRAPHIC)), re.IGNORECASE)
    for match in pattern.finditer(text.translate(_TYPOGRAPHIC)):
        yield Evidence(quote=text[match.start() : match.end()], offset=match.start())


__all__ = [
    "ID_PREFIXES",
    "MODEL_ID_PREFIX",
    "RECORD_OFFSET",
    "SOURCE",
    "CheckOutcome",
    "MechanicalCheck",
    "Skip",
    "natural_key",
    "occurrences",
    "present",
    "record_evidence",
    "violation",
    "violation_id",
]
