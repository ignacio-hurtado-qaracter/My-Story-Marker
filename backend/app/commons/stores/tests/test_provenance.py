"""AC 32, FR-STORE-04 — one provenance line per store write, naming the role and the actor.

The requirement is not "provenance is appended somewhere"; it is that **no write can skip
it**, which is why the store layer appends the line itself rather than trusting a caller. So
the tests below check the coupling as much as the content: a write always logs, a refused
write never does, and the hash on the line is the hash of what actually landed.

`actor` is the other half. A human acts *under* a role rather than beside it (Decision 5), so
the log records `writer` plus `human` rather than a seventh role. That is what makes it
possible to ask, later, whether a given change was the model's idea.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.commons.errors import PermissionDenied
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas.common import Outcome
from app.commons.schemas.draft import Draft
from app.commons.schemas.scene import Scene
from app.commons.stores import Store
from app.commons.stores.provenance import PROVENANCE_FILE


@pytest.fixture
def store(tmp_path: Path) -> Store:
    root = tmp_path / "story"
    (root / "canon").mkdir(parents=True)
    return Store(root=root, index_dir=tmp_path / ".index")


def a_scene() -> Scene:
    return Scene(
        id="014",
        pov="mara",
        participants=[],
        story_time=120,
        discourse_order=14,
        location="hab-ring",
        goal="g",
        conflict="c",
        outcome=Outcome.YES,
        value_change="a -> b",
        entry_state="e",
        exit_state="x",
        tags=[],
        notes=None,
        budget=1800,
    )


# spec 001 / AC 32
def test_one_line_per_write(store: Store) -> None:
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    assert len(store.provenance()) == 2


# spec 001 / AC 32 — role and actor, with `agent` the default.
def test_the_line_names_the_role_and_defaults_to_agent(store: Store) -> None:
    line = store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    assert line.role is AgentRole.ARCHITECT
    assert line.actor is Actor.AGENT
    assert line.path == "scenes/014.yaml"


# spec 001 / AC 32 — a human acting under a role is recorded as such.
def test_a_human_write_is_marked_human(store: Store) -> None:
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT, actor=Actor.HUMAN)
    assert store.provenance()[0].actor is Actor.HUMAN


# spec 001 / AC 32 — scene and turn travel with the line when the write is inside a turn.
def test_scene_and_turn_are_recorded_when_supplied(store: Store) -> None:
    draft = Draft(scene_ref="014", words=2, literal_tail="the end", body="The end.\n")
    store.write("manuscript/014.md", draft, role=AgentRole.WRITER, scene="014", turn="014-1")
    line = store.provenance()[0]
    assert line.scene == "014"
    assert line.turn == "014-1"


# spec 001 / AC 32 — a refused write logs nothing. There was no write to attribute.
def test_a_refused_write_logs_nothing(store: Store) -> None:
    with pytest.raises(PermissionDenied):
        store.write("scenes/014.yaml", a_scene(), role=AgentRole.WRITER)
    assert store.provenance() == []


# spec 001 / AC 31, AC 32 — the log lives under `.index/`, outside the store tree. Nothing
# under `.index/` is a store, and no agent reads it.
def test_the_log_is_outside_the_tree(store: Store) -> None:
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    assert (store.index_dir / PROVENANCE_FILE).is_file()
    assert not list(store.root.rglob(PROVENANCE_FILE))


# spec 001 / AC 32 — JSON Lines, one object per line, appended and never rewritten.
def test_the_log_is_append_only_json_lines(store: Store) -> None:
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    first = (store.index_dir / PROVENANCE_FILE).read_text(encoding="utf-8")
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    second = (store.index_dir / PROVENANCE_FILE).read_text(encoding="utf-8")

    assert second.startswith(first), "an earlier line was rewritten"
    lines = [line for line in second.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        parsed = json.loads(line)
        assert set(parsed) == {"path", "role", "actor", "content_hash", "at", "scene", "turn"}


# spec 001 / AC 32 — IF-03: the log filters by path and by time.
def test_the_log_filters(store: Store) -> None:
    draft = Draft(scene_ref="014", words=2, literal_tail="x", body="x\n")
    store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    store.write("manuscript/014.md", draft, role=AgentRole.WRITER)

    only_scene = store.provenance(path="scenes/014.yaml")
    assert [line.path for line in only_scene] == ["scenes/014.yaml"]

    everything = store.provenance()
    assert len(store.provenance(since=everything[-1].at)) >= 1
    assert store.provenance(since="9999-01-01T00:00:00+00:00") == []


# spec 001 / AC 32 — the hash identifies the bytes, so two different contents differ.
def test_the_hash_changes_with_the_content(store: Store) -> None:
    first = store.write("scenes/014.yaml", a_scene(), role=AgentRole.ARCHITECT)
    changed = a_scene()
    changed.goal = "something else"
    second = store.write("scenes/014.yaml", changed, role=AgentRole.ARCHITECT)
    assert first.content_hash != second.content_hash
