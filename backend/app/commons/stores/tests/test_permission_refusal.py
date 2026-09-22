"""AC 2, the integration half — a forbidden write changes nothing on disk.

FR-STORE-03 says the check happens "before any byte touches disk", and that ordering is the
whole claim. A system that wrote the file and then rolled back would pass a test that only
looked at the final state, and would still have had the wrong bytes on disk, still have
fsynced them, and still have raced anything reading concurrently.

So these tests hash the whole tree before and after. AC 16 measures the auditor the same way,
for the same reason.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.commons.errors import PermissionDenied
from app.commons.permissions import AgentRole
from app.commons.schemas.common import Outcome
from app.commons.schemas.scene import Scene
from app.commons.stores import Store


def tree_hash(root: Path) -> str:
    """One hash over every path and every byte under the root."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def store(tmp_path: Path) -> Store:
    root = tmp_path / "story"
    (root / "canon").mkdir(parents=True)
    (root / "canon" / "project.md").write_text("# Project\n", encoding="utf-8")
    return Store(root=root, index_dir=tmp_path / ".index")


@pytest.fixture
def a_scene() -> Scene:
    return Scene(
        id="014",
        pov="mara",
        participants=["ilan"],
        story_time=120,
        discourse_order=14,
        location="hab-ring",
        goal="Reach the fold gate before the window closes.",
        conflict="The gate is held by someone who knows her.",
        outcome=Outcome.YES_BUT,
        value_change="safety -> exposure",
        entry_state="Mara believes the crossing is routine.",
        exit_state="Mara knows she was expected.",
        tags=[],
        notes=None,
        budget=1800,
    )


# spec 001 / AC 2 — every role Figure 3 forbids, against the same path.
@pytest.mark.parametrize(
    "role",
    [AgentRole.WRITER, AgentRole.STYLE_EDITOR, AgentRole.AUDITOR, AgentRole.CANONISER],
)
def test_a_forbidden_write_is_refused(store: Store, a_scene: Scene, role: AgentRole) -> None:
    with pytest.raises(PermissionDenied) as raised:
        store.write("scenes/014.yaml", a_scene, role=role)
    body = raised.value.as_body()
    assert body["error"] == "permission_denied"
    assert body["role"] == role.value
    assert body["path"] == "scenes/014.yaml"


# spec 001 / AC 2 — and leaves the tree byte-identical.
@pytest.mark.parametrize(
    "role",
    [AgentRole.WRITER, AgentRole.STYLE_EDITOR, AgentRole.AUDITOR, AgentRole.CANONISER],
)
def test_a_forbidden_write_leaves_the_tree_untouched(
    store: Store, a_scene: Scene, role: AgentRole
) -> None:
    before = tree_hash(store.root)
    with pytest.raises(PermissionDenied):
        store.write("scenes/014.yaml", a_scene, role=role)
    assert tree_hash(store.root) == before
    assert not (store.root / "scenes").exists()


# spec 001 / AC 2 — no temporary file is left behind either.
def test_a_forbidden_write_leaves_no_temporary(store: Store, a_scene: Scene) -> None:
    with pytest.raises(PermissionDenied):
        store.write("scenes/014.yaml", a_scene, role=AgentRole.WRITER)
    assert not list(store.root.rglob("*.tmp"))


# spec 001 / AC 32 — and writes no provenance line, because nothing happened.
def test_a_forbidden_write_is_not_logged(store: Store, a_scene: Scene) -> None:
    with pytest.raises(PermissionDenied):
        store.write("scenes/014.yaml", a_scene, role=AgentRole.WRITER)
    assert store.provenance() == []


# spec 001 / AC 2 — the role Figure 3 allows does write.
def test_the_permitted_role_writes(store: Store, a_scene: Scene) -> None:
    store.write("scenes/014.yaml", a_scene, role=AgentRole.ARCHITECT)
    assert store.read("scenes/014.yaml", Scene) == a_scene


# spec 001 / AC 2, AC 13 — the writer cannot reach canon through the store layer either.
def test_the_writer_cannot_write_canon(store: Store, a_scene: Scene) -> None:
    for path in ("canon/axioms/fold-drive.md", "canon/lexicon.yaml", "cast/mara/dossier.md"):
        with pytest.raises(PermissionDenied):
            store.write(path, a_scene, role=AgentRole.WRITER)


# spec 001 / AC 2 — `.index/` is not a store and no role writes it through this door.
def test_no_role_can_write_the_index_through_the_store(store: Store, a_scene: Scene) -> None:
    for role in AgentRole:
        with pytest.raises(PermissionDenied):
            store.write(".index/turns/014-1.yaml", a_scene, role=role)


# spec 001 / AC 2 — a path that escapes the root is refused as a permission failure, not as
# a crash, and certainly not as a write.
def test_escaping_paths_are_refused(store: Store, a_scene: Scene) -> None:
    for escape in ("../outside.yaml", "canon/../../outside.yaml", "/etc/passwd"):
        with pytest.raises(PermissionDenied):
            store.write(escape, a_scene, role=AgentRole.ARCHITECT)
