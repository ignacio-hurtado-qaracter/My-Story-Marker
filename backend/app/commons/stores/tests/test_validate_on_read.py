"""AC 4, the read half — FR-STORE-06: a file that fails validation raises `InvalidRecord`
naming file and field, and is never repaired or partially returned.

The temptation this refuses is filling in a missing field with a default. A record the
system quietly fixed is a record whose author and whose reader believe different things, and
nothing downstream can tell which of the two is in the context of a given call. Refusing is
noisier and correct.

The tree-wide half of AC 4 -- every fixture file validates -- lives in
`backend/tests/test_fixture_validates.py`, because it needs the feature-owned models as well
as the shared ones and a test inside `app/commons/` may not import a feature (NFR-04).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import AgentRole
from app.commons.schemas.common import DigestLevel
from app.commons.schemas.digest import SceneDigest
from app.commons.schemas.draft import Draft
from app.commons.schemas.scene import Scene
from app.commons.stores import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    root = tmp_path / "story"
    (root / "scenes").mkdir(parents=True)
    (root / "manuscript").mkdir(parents=True)
    return Store(root=root, index_dir=tmp_path / ".index")


VALID_SCENE = """\
schema_version: 1
id: '014'
pov: mara
participants: []
story_time: 120
discourse_order: 14
location: hab-ring
goal: Reach the gate.
conflict: It is held.
outcome: yes-but
value_change: safety -> exposure
entry_state: before
exit_state: after
tags: []
notes: null
budget: 1800
"""


def write_raw(store: Store, relative: str, text: str) -> None:
    """Deliberately bypasses the store layer: these tests are about what happens when a file
    on disk does not match its model, and the store layer would never have written one."""
    target = store.root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


# spec 001 / AC 4 — the control: a good file reads.
def test_a_valid_file_reads(store: Store) -> None:
    write_raw(store, "scenes/014.yaml", VALID_SCENE)
    assert store.read("scenes/014.yaml", Scene).pov == "mara"


# spec 001 / AC 4 — a missing file is NotFound, which is a different thing from invalid.
def test_a_missing_file_is_not_found(store: Store) -> None:
    with pytest.raises(NotFound):
        store.read("scenes/999.yaml", Scene)


# spec 001 / AC 4 — a type-mutated copy is rejected naming the file and the field.
@pytest.mark.parametrize(
    ("mutation", "replacement", "field"),
    [
        ("story_time: 120", "story_time: 'soon'", "story_time"),
        ("story_time: 120", "story_time: true", "story_time"),
        ("story_time: 120", "story_time: 120.5", "story_time"),
        ("outcome: yes-but", "outcome: maybe", "outcome"),
        ("outcome: yes-but", "outcome: true", "outcome"),
        ("discourse_order: 14", "discourse_order: 0", "discourse_order"),
        ("budget: 1800", "budget: -1", "budget"),
        ("pov: mara", "pov: Mara", "pov"),
        ("id: '014'", "id: '14'", "id"),
        ("participants: []", "participants: 'ilan'", "participants"),
    ],
    ids=lambda value: str(value)[:28],
)
def test_a_mutated_field_is_rejected_naming_file_and_field(
    store: Store, mutation: str, replacement: str, field: str
) -> None:
    write_raw(store, "scenes/014.yaml", VALID_SCENE.replace(mutation, replacement))
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)

    body = raised.value.as_body()
    assert body["error"] == "invalid_record"
    assert body["file"] == "scenes/014.yaml"
    assert body["field"] == field, f"expected the error to name {field}, got {body['field']}"


# spec 001 / AC 4 — a missing required field is named too.
def test_a_missing_required_field_is_named(store: Store) -> None:
    without_pov = "\n".join(
        line for line in VALID_SCENE.splitlines() if not line.startswith("pov:")
    )
    write_raw(store, "scenes/014.yaml", without_pov + "\n")
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)
    assert raised.value.as_body()["field"] == "pov"


# spec 001 / AC 4 — an unknown field is a rejection, not a shrug. A store file with a field
# nobody modelled is a record whose author believed something the system does not.
def test_an_unknown_field_is_rejected(store: Store) -> None:
    write_raw(store, "scenes/014.yaml", VALID_SCENE + "mood: tense\n")
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)
    assert "mood" in str(raised.value.as_body()["field"])


# spec 001 / AC 4 — DR-10: an unknown schema version fails validation rather than being read
# optimistically.
@pytest.mark.parametrize("version", ["2", "0", "'1'"], ids=repr)
def test_an_unknown_schema_version_is_rejected(store: Store, version: str) -> None:
    mutated = VALID_SCENE.replace("schema_version: 1", f"schema_version: {version}")
    write_raw(store, "scenes/014.yaml", mutated)
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)
    assert raised.value.as_body()["field"] == "schema_version"


# spec 001 / AC 4 — nothing is partially returned: a failed read leaves no object behind and
# the file is untouched.
def test_a_failed_read_neither_repairs_nor_rewrites(store: Store) -> None:
    broken = VALID_SCENE.replace("outcome: yes-but", "outcome: maybe")
    write_raw(store, "scenes/014.yaml", broken)
    with pytest.raises(InvalidRecord):
        store.read("scenes/014.yaml", Scene)
    assert (store.root / "scenes" / "014.yaml").read_text(encoding="utf-8") == broken


# spec 001 / AC 4 — a file that is not YAML at all fails as InvalidRecord, not as a crash.
def test_unparseable_yaml_is_an_invalid_record(store: Store) -> None:
    write_raw(store, "scenes/014.yaml", "- this is a list\n- not a mapping\n")
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)
    assert raised.value.as_body()["file"] == "scenes/014.yaml"


# spec 001 / AC 4 — DR-02, the Markdown side: frontmatter is validated like any other record.
def test_markdown_frontmatter_is_validated(store: Store) -> None:
    write_raw(
        store,
        "manuscript/014.md",
        "---\nscene_ref: '14'\nwords: 2\nliteral_tail: x\n---\n\nThe gate held.\n",
    )
    with pytest.raises(InvalidRecord) as raised:
        store.read("manuscript/014.md", Draft)
    assert raised.value.as_body()["field"] == "scene_ref"


# spec 001 / AC 4 — and a good one reads, body included.
def test_a_valid_markdown_record_reads(store: Store) -> None:
    store.write(
        "manuscript/014.md",
        Draft(scene_ref="014", words=3, literal_tail="the gate held", body="The gate held.\n"),
        role=AgentRole.WRITER,
    )
    assert store.read("manuscript/014.md", Draft).body == "The gate held.\n"


# spec 001 / AC 4 — regression. Every Markdown-backed model must survive the *store's* round
# trip, not only `model_dump`. `SceneDigest` is all frontmatter -- its prose is `delta`
# (DR-11) -- so the body `parse_markdown` always produces had nowhere to go and every digest
# file failed on read. The round-trip property in `commons/schemas/tests` could not see it:
# it never goes through the Markdown path.
@pytest.mark.parametrize(
    ("relative", "record"),
    [
        (
            "manuscript/digests/014.md",
            SceneDigest(
                scene_ref="014",
                level=DigestLevel.SCENE,
                povs=["mara"],
                delta="Mara learns the gate was held for her.",
                words=8,
            ),
        ),
        (
            "manuscript/014.md",
            Draft(scene_ref="014", words=3, literal_tail="the gate held", body="The gate held.\n"),
        ),
    ],
    ids=["digest-without-body", "draft-with-body"],
)
def test_markdown_records_survive_the_store_round_trip(
    store: Store, relative: str, record: BaseModel
) -> None:
    role = AgentRole.WRITER
    store.write(relative, record, role=role)
    assert store.read(relative, type(record)) == record


# spec 001 / AC 4 — but prose that has nowhere to go is refused, not dropped. Text someone
# wrote that the system would never read is the divergence FR-STORE-06 exists to surface.
def test_prose_under_a_model_with_no_body_is_refused(store: Store) -> None:
    write_raw(
        store,
        "manuscript/digests/014.md",
        "---\nschema_version: 1\nscene_ref: '014'\nlevel: scene\npovs: [mara]\n"
        "delta: Something changed.\nwords: 3\n---\n\nProse nobody modelled.\n",
    )
    with pytest.raises(InvalidRecord, match="no `body` field"):
        store.read("manuscript/digests/014.md", SceneDigest)


# spec 001 / AC 5, DR-10 — regression. `Literal[1]` alone accepts `True`, because `True == 1`.
# YAML `schema_version: true` would have been read as version 1.
@pytest.mark.parametrize("value", ["true", "false"], ids=repr)
def test_a_boolean_schema_version_is_rejected(store: Store, value: str) -> None:
    mutated = VALID_SCENE.replace("schema_version: 1", f"schema_version: {value}")
    write_raw(store, "scenes/014.yaml", mutated)
    with pytest.raises(InvalidRecord) as raised:
        store.read("scenes/014.yaml", Scene)
    assert raised.value.as_body()["field"] == "schema_version"
