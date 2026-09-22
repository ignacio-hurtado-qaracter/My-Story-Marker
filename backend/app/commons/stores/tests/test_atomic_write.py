"""FR-STORE-07 — writes are atomic per file, and the store layer never runs git.

Atomicity here means a reader sees the old file or the new one, never half of either. The
tree is a git working tree that a human commits, and a half-written `manuscript/014.md`
committed by a human who did not notice is a corruption that outlives the process that made
it.

The failure injected below is a crash between the temporary file and the rename, which is
the only window where the guarantee could break.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commons.permissions import AgentRole
from app.commons.schemas.common import Outcome
from app.commons.schemas.scene import Scene
from app.commons.stores import Store, writer


@pytest.fixture
def store(tmp_path: Path) -> Store:
    root = tmp_path / "story"
    (root / "canon").mkdir(parents=True)
    return Store(root=root, index_dir=tmp_path / ".index")


def scene_with(goal: str) -> Scene:
    return Scene(
        id="014",
        pov="mara",
        participants=[],
        story_time=120,
        discourse_order=14,
        location="hab-ring",
        goal=goal,
        conflict="The gate is held.",
        outcome=Outcome.NO,
        value_change="hope -> doubt",
        entry_state="before",
        exit_state="after",
        tags=[],
        notes=None,
        budget=1800,
    )


# spec 001 / AC 4 — the ordinary case, and the parent directory is created.
def test_a_write_creates_the_file_and_its_directory(store: Store) -> None:
    store.write("scenes/014.yaml", scene_with("first"), role=AgentRole.ARCHITECT)
    assert (store.root / "scenes" / "014.yaml").is_file()
    assert store.read("scenes/014.yaml", Scene).goal == "first"


# spec 001 / AC 4 — a second write replaces, and leaves nothing behind.
def test_a_rewrite_replaces_the_file_and_leaves_no_temporary(store: Store) -> None:
    store.write("scenes/014.yaml", scene_with("first"), role=AgentRole.ARCHITECT)
    store.write("scenes/014.yaml", scene_with("second"), role=AgentRole.ARCHITECT)
    assert store.read("scenes/014.yaml", Scene).goal == "second"
    assert sorted(p.name for p in (store.root / "scenes").iterdir()) == ["014.yaml"]


# spec 001 / AC 4 — a crash between the temporary file and the rename leaves the OLD file
# intact, which is the entire point of writing through a temporary.
def test_a_crash_before_the_rename_leaves_the_previous_content(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.write("scenes/014.yaml", scene_with("survivor"), role=AgentRole.ARCHITECT)
    original = (store.root / "scenes" / "014.yaml").read_bytes()

    def explode(self: Path, target: Path) -> Path:
        del self, target
        message = "crash between temp and rename"
        raise OSError(message)

    monkeypatch.setattr(Path, "replace", explode)
    with pytest.raises(OSError, match="crash between temp and rename"):
        store.write("scenes/014.yaml", scene_with("never written"), role=AgentRole.ARCHITECT)

    assert (store.root / "scenes" / "014.yaml").read_bytes() == original
    assert store.read("scenes/014.yaml", Scene).goal == "survivor"


# spec 001 / AC 4 — and cleans up its temporary rather than littering the tree, which would
# otherwise be indexed, committed or read as a store file.
def test_a_crash_removes_the_temporary(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    store.write("scenes/014.yaml", scene_with("survivor"), role=AgentRole.ARCHITECT)

    def explode(self: Path, target: Path) -> Path:
        del self, target
        message = "crash"
        raise OSError(message)

    monkeypatch.setattr(Path, "replace", explode)
    with pytest.raises(OSError, match="crash"):
        store.write("scenes/014.yaml", scene_with("never"), role=AgentRole.ARCHITECT)

    leftovers = [p.name for p in (store.root / "scenes").iterdir() if p.name != "014.yaml"]
    assert leftovers == []


# spec 001 / AC 4 — the bytes on disk are the bytes that were hashed for provenance.
def test_the_logged_hash_is_the_hash_of_what_landed(store: Store) -> None:
    import hashlib

    line = store.write("scenes/014.yaml", scene_with("first"), role=AgentRole.ARCHITECT)
    on_disk = (store.root / "scenes" / "014.yaml").read_bytes()
    assert line.content_hash == hashlib.sha256(on_disk).hexdigest()


# spec 001 / AC 4 — DR-02: a Markdown store file round-trips frontmatter and body.
def test_markdown_files_keep_their_frontmatter_and_body(store: Store) -> None:
    from app.commons.schemas.draft import Draft

    draft = Draft(
        scene_ref="014",
        words=3,
        literal_tail="the gate held",
        body="The gate held.\n\nShe counted the seconds and did not move.\n",
    )
    store.write("manuscript/014.md", draft, role=AgentRole.WRITER)
    text = (store.root / "manuscript" / "014.md").read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "scene_ref: '014'" in text or 'scene_ref: "014"' in text
    assert "The gate held." in text
    assert store.read("manuscript/014.md", Draft) == draft


# spec 001 / AC 4 — FR-STORE-08: no cache, so an external edit is seen immediately.
def test_an_external_edit_is_seen_on_the_next_read(store: Store) -> None:
    store.write("scenes/014.yaml", scene_with("first"), role=AgentRole.ARCHITECT)
    assert store.read("scenes/014.yaml", Scene).goal == "first"

    target = store.root / "scenes" / "014.yaml"
    target.write_text(
        target.read_text(encoding="utf-8").replace("goal: first", "goal: edited by hand"),
        encoding="utf-8",
    )
    assert store.read("scenes/014.yaml", Scene).goal == "edited by hand"


# spec 001 / AC 4 — the store layer never runs git, whatever else it does.
def test_the_store_layer_does_not_run_git(store: Store) -> None:
    store.write("scenes/014.yaml", scene_with("first"), role=AgentRole.ARCHITECT)
    assert not (store.root / ".git").exists()
    source = (Path(writer.__file__)).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "git" not in source.replace("git working tree", "").replace("never runs git", "")
