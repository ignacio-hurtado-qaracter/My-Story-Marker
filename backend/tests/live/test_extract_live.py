"""AC 27 (D) -- a live extraction finds the two facts Draft A invents.

Run it yourself, from `backend/` (it runs with the turn test when you pass the folder):

    uv run pytest tests/live --live -s

Skipped without `--live` (NFR-09): one `claude -p` call under your Claude Code login, no API
key (FR-LLM-01). On a private copy of the fixture novel, the canoniser reads the accepted draft
of scene 002 (`manuscript/002.md`, Draft A) with the canon documents the scene's assembly
selects, and must return at least the two inventions the fixture README labels by hand ("The two
invented facts"):

* **F1** -- the throat releases only from the vault side: `pump_vault`, `geometry`;
* **F2** -- a cold soak may be cut to four hours on an indemnity dive: `ax_cold_soak`,
  `exceptions`.

Nothing is written: the role returns its output and this test reads it (roles never write,
FR-TURN-06). The report goes to `last_run.md` before the assertion, as for AC 26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.roles import canoniser
from app.scenes import service as scenes_service
from tests.live.support import append_section, live_env, mark

pytestmark = pytest.mark.live

SCENE = "002"
EXPECTED = {
    "F1": ("pump_vault", "geometry"),
    "F2": ("ax_cold_soak", "exceptions"),
}


# spec 001 / AC 27 -- demonstrated run; the evidence goes to tests/live/last_run.md.
def test_a_live_extraction_finds_the_two_invented_facts(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = live_env(fixture_root, monkeypatch)
    selection = scenes_service.select_entities(env.store, env.embedder, env.settings, SCENE)
    call = canoniser.extract_facts(env.store, env.client, SCENE, selection.entities)
    facts = call.output.facts
    found = {(fact.target_entity, fact.target_field) for fact in facts}
    hits = {label: target in found for label, target in EXPECTED.items()}

    lines = [
        (
            f"- Extraction on scene {SCENE} (Draft A): {len(facts)} fact(s), model "
            f"`{call.completion.model_id}`, estimate {call.completion.estimate}, input "
            f"{call.completion.usage.input_tokens}, cache read "
            f"{call.completion.usage.cache_read_input_tokens}, over_cap "
            f"{call.completion.over_cap}"
        ),
        "",
        "| Hand-labelled fact | Target | Found |",
        "|---|---|---|",
        *[
            f"| {label} | `{entity}`.`{field}` | {mark(hits[label])} |"
            for label, (entity, field) in EXPECTED.items()
        ],
        "",
        "Every fact returned:",
        *[
            f"- `{fact.target_entity}`.`{fact.target_field}`: \"{fact.payload}\""
            for fact in facts
        ],
    ]
    append_section("AC 27 - live extraction on Draft A", lines)

    missing = [label for label, hit in hits.items() if not hit]
    assert not missing, f"the live extraction missed {missing}; see tests/live/last_run.md"
