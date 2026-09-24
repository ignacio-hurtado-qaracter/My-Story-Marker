"""AC 26 (D) -- one full turn on the tempting scene, through `claude -p` under your login.

Run it yourself, from `backend/`:

    uv run pytest tests/live --live -s

It is skipped without `--live` (NFR-09): it spends your Claude Code usage -- a turn is several
calls (write, audit, perhaps revise, polish, digest, extract), each estimated below 100k input
tokens. No API key is involved or accepted (FR-LLM-01). The real embedder is used, as AC 26
asks; its model is downloaded once if it is not cached yet.

What it demonstrates, on a private copy of the fixture novel (the committed fixture is never
touched), is what the fixture README's "The tempting scene - 006" section sets up:

* the axiom `ax_brine_dark` is in the turn's selected list (it is pinned), so the auditor can
  hold the prose to it;
* the invariant-6 model findings are counted for a reader to judge against the draft, not
  asserted: whether the writer broke the axiom depends on what it wrote, and a count of any
  invariant-6 finding says nothing about whether the right sentence was caught (the auditor's
  own live test, `test_audit_live.py`, plants the breaches and asserts on them);
* Ilan going under, swimming or breathing the brine -- his lungs are unmodified and no
  ChangeEvent says otherwise -- is flagged as invariant 3 with `source: model`;
* his steel graft hand, a *registered* change (scene 002, before 006), is NOT flagged;
* the turn ends `merged` or `awaiting_ruling`, and its record shows the real model ids the CLI
  reported, input, cache-creation and cache-read tokens, every step's estimate below 100k and
  every real count below 100k once CLI_OVERHEAD_TOKENS is subtracted (FR-CTX-06).

The turn is driven step by step (`turn.begin_turn`, `TurnRun.events`), and each step prints one
line as it ends, so a run under `-s` shows its progress.

The two semantic findings depend on what a real model writes: an obedient writer leaves nothing
to flag, and then their absence is not a miss. The report is written first, with the path of
the draft so a reader can tell the two apart; the structural checks are asserted after it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents import turn
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.llm.tokens import CLI_OVERHEAD_TOKENS
from app.commons.schemas import TurnOutcome, Violation, ViolationSource
from app.commons.stores import paths
from app.ledger import service as ledger_service
from tests.live.support import Progress, append_section, live_env, mark

pytestmark = pytest.mark.live

SCENE = "006"
PINNED_AXIOM = "ax_brine_dark"
REGISTERED_CHANGE_WORDS = ("steel", "graft", "prosthe")
"""Words that place an invariant-3 quote on the registered left-hand change, not on the lungs."""


def _model_findings(violations: list[Violation], invariant: int) -> list[Violation]:
    return [
        finding
        for finding in violations
        if finding.scene == SCENE
        and finding.source is ViolationSource.MODEL
        and finding.invariant == invariant
    ]


def _about_the_registered_change(finding: Violation) -> bool:
    quote = finding.evidence.quote.lower()
    return any(word in quote for word in REGISTERED_CHANGE_WORDS)


# spec 001 / AC 26 -- demonstrated run; the evidence goes to tests/live/last_run.md.
def test_a_live_turn_on_the_tempting_scene(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = live_env(fixture_root, monkeypatch)
    progress = Progress("turn")
    with turn.begin_turn(env.store, env.client, env.embedder, env.settings, SCENE) as run:
        progress.start(f"turn {run.record.id} on scene {SCENE}", run.record.next_step.value)
        for event in run.events():
            if event.kind == "step" and event.step is not None:
                name = event.step.value + (f" #{event.iteration}" if event.iteration else "")
                status = event.status.value if event.status is not None else "none"
                progress.step(name, status, event.next_step.value)
            else:
                progress.step("outcome", event.outcome.value)
        record = run.record
    violations = ledger_service.violations(env.store).violations

    calls = [step for step in record.steps if step.call is not None]
    axiom = _model_findings(violations, 6)
    bodies = _model_findings(violations, 3)
    lungs = [finding for finding in bodies if not _about_the_registered_change(finding)]
    graft = [finding for finding in bodies if _about_the_registered_change(finding)]

    selected = PINNED_AXIOM in {entry.entity_id for entry in record.selected}
    ended_well = record.outcome in {TurnOutcome.MERGED, TurnOutcome.AWAITING_RULING}
    real_ids = bool(calls) and all(
        step.call is not None and step.call.model_id for step in calls
    )
    under_cap = all(
        step.call is not None
        and step.call.estimate <= CONTEXT_TOKEN_CAP
        and not step.call.over_cap
        for step in calls
    )

    lines = [
        f"- Turn `{record.id}` on scene {SCENE}: outcome **{record.outcome.value}**"
        + (
            f", escalated at `{record.escalation.step.value}` "
            f"({record.escalation.category.value}: {record.escalation.detail})"
            if record.escalation is not None
            else ""
        ),
        (
            f"- Draft (stays in the run's private store copy, NFR-10): "
            f"`{env.root / paths.draft(SCENE)}`"
        ),
        f"- Words {record.draft.words} against a budget of {record.draft.budget}"
        if record.draft is not None
        else "- No draft measured",
        f"- Revisions: {record.revisions}; revise rejections: {record.revise_rejections}",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| `{PINNED_AXIOM}` in the selected list | {mark(selected)} |",
        (
            f"| Invariant-6 model findings (a count to judge against the draft; not "
            f"asserted) | {len(axiom)} |"
        ),
        f"| Unregistered body change flagged (inv 3, model, not the hand) | {mark(bool(lungs))} |",
        f"| Registered change (the graft hand) NOT flagged | {mark(not graft)} |",
        f"| Outcome merged or awaiting_ruling | {mark(ended_well)} |",
        f"| Every call reports a real model id | {mark(real_ids)} |",
        f"| Every estimate <= 100k and real - {CLI_OVERHEAD_TOKENS} <= 100k | {mark(under_cap)} |",
        "",
        (
            "| Step | Role | Model id | Estimate | Input | Cache creation | Cache read | Output "
            "| over_cap |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
        *[
            f"| {step.step.value} | {step.role} | {step.call.model_id} | {step.call.estimate} | "
            f"{step.call.input_tokens} | {step.call.cache_creation_input_tokens} | "
            f"{step.call.cache_read_input_tokens} | {step.call.output_tokens} | "
            f"{step.call.over_cap} |"
            for step in calls
            if step.call is not None
        ],
        "",
        "Model findings on scene 006:",
        *[
            f"- inv {finding.invariant}, {finding.severity.value}: \"{finding.evidence.quote}\""
            for finding in violations
            if finding.scene == SCENE and finding.source is ViolationSource.MODEL
        ],
        "",
        (
            "A missing invariant 6 or 3 finding is a miss only if the draft contains the "
            "breach: an obedient writer leaves nothing to flag. Read the draft above to tell "
            "which."
        ),
    ]
    append_section("AC 26 - live turn on the tempting scene", lines)

    assert selected, "the pinned axiom must be in the turn's selected list"
    assert ended_well, f"the turn ended {record.outcome.value}"
    assert real_ids, "every model call must report the model id the CLI used"
    assert under_cap, "every call must stay under the cap (FR-LLM-07, FR-CTX-06)"
    assert not graft, "the registered graft hand must not be flagged"
