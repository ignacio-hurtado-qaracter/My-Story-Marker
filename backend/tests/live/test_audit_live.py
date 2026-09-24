"""AC 26, the auditor's half (D) -- a live audit catches breaches planted in a draft of scene 006.

Run it yourself, from `backend/` (it runs with the other live tests when you pass the folder):

    uv run pytest tests/live --live -s

Skipped without `--live` (NFR-09): one `claude -p` call under your Claude Code login, no API key
(FR-LLM-01), and the real embedder for the selection, as AC 26 asks.

Why it exists. The turn test (`test_turn_live.py`) cannot tell a blind auditor from an obedient
writer: when a real writer leaves the breach out, there is nothing to flag. This test removes the
writer. On a private copy of the fixture novel it writes a hand-authored draft of scene 006
through `app.agents.service.persist_draft` under the writer role, as a turn's write step would,
takes the scene's real selection (FR-OPS-02) and runs the combined audit (FR-AGENT-07) with the
production client. The draft plants, each in sentences of its own, what the fixture README's
"The tempting scene - 006" section sets up:

* **(a)** the POV sees the seal ring across the open brine by lamplight, well past the four
  metres the pinned axiom `ax_brine_dark` allows -- an invariant-6 breach;
* **(b)** Ilan, a participant, swims out to the cradle with no rig and breathes the brine, which
  his unmodified lungs rule out and no ChangeEvent registers -- an invariant-3 breach;
* **(c)** Ilan's steel graft hand on the latch -- a change registered at scene 002, before 006,
  so it must NOT be flagged.

The report -- every model finding with its invariant, severity, quote and explanation, and which
planted sentence each one hits -- goes to `last_run.md` before anything is asserted. A finding
"hits" a planted sentence when its quote and the sentence share a run of at least
`OVERLAP_CHARS` characters, or one contains the other. The draft is test data, not store text a
prompt could copy: it lives in this module and reaches the model only as the labelled document
`manuscript/006.md` (FR-PERM-07).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents import service
from app.agents.roles import auditor
from app.commons.permissions import AgentRole
from app.commons.schemas import Violation, ViolationSource
from app.commons.stores import paths
from app.scenes import service as scenes_service
from tests.live.support import Progress, append_section, live_env, mark

SCENE = "006"
PINNED_AXIOM = "ax_brine_dark"
OVERLAP_CHARS = 20

SEEING = (
    "From the ledge she raised her lamp and saw the seal ring plainly across the open water, "
    "eleven metres out, every bolt on it lit and whole."
)
"""(a) Sight by lamplight far past four metres: contradicts `ax_brine_dark` (invariant 6)."""

SWIMMING = (
    (
        "Ilan pushed off from the ledge with no rig at all and swam out through the open water "
        "to the cradle, one long stroke after another."
    ),
    (
        "Halfway across he opened his mouth and drew the brine deep into his chest, breathing "
        "it as easily as the gallery air behind the throat."
    ),
)
"""(b) A body with unmodified lungs swimming out rigless and breathing brine (invariant 3)."""

GRAFT = (
    "Ilan set his steel graft hand on the latch and turned it, and nothing came back to him "
    "through the steel fingers."
)
"""(c) The registered left-hand change, shown as registered: must not be flagged."""

SEEN = "(a) seeing past four metres"
SWUM = "(b) rigless swim, breathing brine"
HAND = "(c) registered graft hand"

PLANTED: dict[str, tuple[int, tuple[str, ...]]] = {
    SEEN: (6, (SEEING,)),
    SWUM: (3, SWIMMING),
    HAND: (3, (GRAFT,)),
}
"""Each planted sentence group, with the invariant a finding on it would carry."""

WANTED: dict[str, bool] = {SEEN: True, SWUM: True, HAND: False}
"""Whether the audit must flag the group (a breach) or must not (the registered change)."""

DRAFT = "\n\n".join(
    [
        (
            "The throat sealed behind them, and Vance felt it in her teeth. She checked her rig. "
            "Hose seated. Mask clear. The hard line coiled at her hip. Ilan folded himself down "
            "beside her on the ledge and said nothing."
        ),
        SEEING,
        '"It is there," she said. "The ring is there."',
        f"Ilan did not answer. {SWIMMING[0]} {SWIMMING[1]}",
        (
            "Vance paid out slack on the wire. Procedure. The hours left on the window. The order "
            "of a seating. She did not use his name, and she did not call him back."
        ),
        f"{GRAFT} He waited with it there, the way he waited on everything.",
        (
            '"Ring is whole," he said over the wire. His voice came small and flat along it. '
            "Vance wrote the hour on her slate. Known, now. Not guessed."
        ),
    ]
)


def overlaps(quote: str, sentence: str) -> bool:
    """A finding's quote hits a planted sentence: one contains the other, or they share a run of
    at least `OVERLAP_CHARS` characters (whitespace collapsed, so a quote re-wrapped across a
    line break still counts)."""
    left = " ".join(quote.split())
    right = " ".join(sentence.split())
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    return any(
        left[start : start + OVERLAP_CHARS] in right
        for start in range(len(left) - OVERLAP_CHARS + 1)
    )


def labels_hit(quote: str) -> list[str]:
    """The planted groups a quote hits, whatever the invariant it was reported under."""
    return [
        label
        for label, (_, sentences) in PLANTED.items()
        if any(overlaps(quote, sentence) for sentence in sentences)
    ]


def hits(findings: list[Violation], invariant: int, sentences: tuple[str, ...]) -> list[Violation]:
    """The findings of `invariant` whose quote hits any of `sentences`."""
    return [
        finding
        for finding in findings
        if finding.invariant == invariant
        and any(overlaps(finding.evidence.quote, sentence) for sentence in sentences)
    ]


# spec 001 / AC 26 -- the planted draft is shaped so that the live assertions can hold at once:
# every planted sentence is in the draft, and no sentence of one group overlaps another group's,
# so a quote cannot hit (b) and (c) by sharing text rather than by being about them.
def test_the_planted_draft_keeps_its_three_breaches_apart() -> None:
    groups = list(PLANTED.values())
    for _, sentences in groups:
        for sentence in sentences:
            assert sentence in DRAFT, sentence
            assert len(sentence) >= OVERLAP_CHARS
    for index, (_, mine) in enumerate(groups):
        for _, theirs in groups[index + 1 :]:
            for left in mine:
                for right in theirs:
                    assert not overlaps(left, right), (left, right)
    # (c) is not next to (b): a quote spanning adjacent sentences cannot reach both.
    assert DRAFT.index(GRAFT) - (DRAFT.index(SWIMMING[1]) + len(SWIMMING[1])) > 100


# spec 001 / AC 26 -- the overlap rule the live assertions use.
def test_overlap_is_a_shared_run_or_containment() -> None:
    assert overlaps("saw the seal ring plainly", SEEING)
    assert overlaps(f"{SWIMMING[1]} {SWIMMING[0]}", SWIMMING[0])
    assert overlaps("the open water to\nthe cradle, one long stroke", SWIMMING[0])
    assert not overlaps("the steel fingers and the latch", SEEING)
    assert not overlaps("", SEEING)


# spec 001 / AC 26 -- demonstrated run; the evidence goes to tests/live/last_run.md.
@pytest.mark.live
def test_a_live_audit_catches_the_planted_breaches(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = live_env(fixture_root, monkeypatch)
    progress = Progress("audit")
    progress.start(f"audit of a planted draft of scene {SCENE}", "select")
    selection = scenes_service.select_entities(env.store, env.embedder, env.settings, SCENE)
    selected = selection.entities
    progress.step("select", f"{len(selected)} entities", "write")
    service.persist_draft(env.store, SCENE, DRAFT, role=AgentRole.WRITER)
    progress.step("write", "hand-authored draft persisted under the writer", "audit")
    combined = service.audit(env.store, env.client, SCENE, selected)
    semantic = combined.semantic
    failure = combined.failure
    progress.step("audit", failure.code if failure is not None else "completed")

    findings = [
        finding
        for finding in combined.report.violations
        if finding.scene == SCENE and finding.source is ViolationSource.MODEL
    ]
    found = {
        label: hits(findings, invariant, group) for label, (invariant, group) in PLANTED.items()
    }
    pinned, ranked = auditor.selected_axioms(selected)
    raw = semantic.call.output.violations if semantic is not None else []

    lines = [
        (
            f"- Scene {SCENE}, hand-authored draft written under the writer; draft at "
            f"`{env.root / paths.draft(SCENE)}`"
        ),
        (
            f"- Selected axioms: pinned {', '.join(pinned) or 'none'}; ranked "
            f"{', '.join(ranked) or 'none'}; `{PINNED_AXIOM}` pinned: "
            f"{mark(PINNED_AXIOM in pinned)}"
        ),
        (
            f"- Semantic half failed: {failure.code}"
            if failure is not None
            else "- Semantic half ran"
        ),
    ]
    if semantic is not None:
        completion = semantic.call.completion
        lines.append(
            f"- Model `{completion.model_id}`, estimate {completion.estimate}, input "
            f"{completion.usage.input_tokens}, cache creation "
            f"{completion.usage.cache_creation_input_tokens}, cache read "
            f"{completion.usage.cache_read_input_tokens}, output "
            f"{completion.usage.output_tokens}, over_cap {completion.over_cap}"
        )
        lines.extend(
            f"- Skipped (inv {skip.invariant}): {skip.reason}" for skip in semantic.skipped
        )
        lines.extend(
            f"- Adjusted finding {entry.index} (inv {entry.invariant}): "
            f"{entry.adjustment.value}, {entry.detail}"
            for entry in semantic.adjustments
        )
    lines += [
        "",
        "| Planted | Finding wanted | Findings hitting it | Result |",
        "|---|---|---|---|",
        *[
            f"| {label} | {'' if WANTED[label] else 'no '}inv {invariant} | {len(found[label])} "
            f"| {mark(bool(found[label]) is WANTED[label])} |"
            for label, (invariant, _) in PLANTED.items()
        ],
        "",
        "Every model finding, as the model returned it:",
        *[
            f"- inv {finding.invariant}, {finding.severity.value}: "
            f'"{finding.evidence.quote}" -- {finding.explanation} '
            f"[hits: {', '.join(labels_hit(finding.evidence.quote)) or 'none'}]"
            for finding in raw
        ],
    ]
    if not raw:
        lines.append("- none")
    append_section("AC 26 - live audit of a planted draft (the auditor's half)", lines)

    assert PINNED_AXIOM in pinned, "the scene's pinned axiom must be in the selected list"
    assert failure is None, f"the semantic half did not run: {failure}"
    assert found[SEEN], "no invariant-6 model finding on sentence (a); see last_run.md"
    assert found[SWUM], "no invariant-3 model finding on a sentence of (b); see last_run.md"
    assert not found[HAND], "the registered graft hand was flagged (invariant 3)"
