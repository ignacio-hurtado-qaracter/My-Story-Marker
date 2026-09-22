"""The scenes feature's one door to the store layer, for `scenes/` and for `structure/`.

FR-STORE-02 puts every file primitive inside `app/commons/stores/`, and FR-STORE-05 puts
every path inside `commons.stores.paths`. This module is where the two rules meet the
feature: a scene id becomes the `Store` call that reads or writes `scenes/NNN.yaml`, and the
two container files of `structure/` are named by the constants the store layer publishes.
Nothing here opens a file and nothing here spells a path.

**What the scene record is for.** It is not a planning note a human reads and then forgets.
FR-OPS-02 builds the selection query out of `goal`, `conflict`, `value_change`, `pov`,
`location`, `entry_state`, `exit_state` and `notes`, and whatever that query retrieves is the
whole world the writer is handed. A record whose conflict is "something goes wrong" matches
nothing in particular, so the ranking falls back to whatever happened to score first, and the
scene is written against generic material. The vagueness does not stay in the record: it
becomes the context, and the context becomes the prose. A vague record produces a vague
selection and a thin world.

No policy lives here. Whether a role may write `scenes/**` or `structure/**` is Figure 3's
answer, given by `may_write` inside `Store.write` (FR-PERM-03), which is why every write below
takes its role from the caller and none of them has a default: a default role would be a
guess, and FR-STORE-04 would then record the guess as provenance.
"""

from __future__ import annotations

from typing import Final

from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Scene
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.scenes.models import ArcsFile, ChaptersFile

YAML_SUFFIX: Final[str] = ".yaml"
"""Scene records are YAML, not Markdown-with-frontmatter: a scene record holds no prose at
all (`definitions.md` Scene), and the prose it plans lives in `manuscript/NNN.md`."""

_DIRECTORY_PROBE: Final[str] = "000"
"""A scene id used only to ask `paths` where scene records live. See `SCENES_DIRECTORY`."""

SCENES_DIRECTORY: Final[str] = paths.scene(_DIRECTORY_PROBE).rsplit("/", 1)[0]
"""The directory holding the scene records, read back off a path the store layer built.

`paths` publishes no directory for `scenes/`, and this feature may not invent one: a literal
`"scenes"` spelled here would be a second place that knows the storage layout, and the first
time the layout moved, the listing route would keep answering from the old one. A
`paths.SCENES_DIR` belongs in `commons/` and is reported with this step rather than added
here, because `paths` is the store layer's file and not this feature's.
"""


# --- paths ----------------------------------------------------------------------------


def scene_path(identifier: str) -> str:
    """`scenes/NNN.yaml`, built and validated by the store layer.

    The single call site for the scene path grammar in this feature, so a malformed id fails
    in one place and with the message `paths` writes.
    """
    return paths.scene(identifier)


ARCS_PATH: Final[str] = paths.ARCS
CHAPTERS_PATH: Final[str] = paths.CHAPTERS
"""The two container files, re-exported from the store layer so the service can name the file
it is refusing (FR-STORE-06) without becoming a second module in this feature that knows where
a store file lives. A feature with two ideas of where the structure sits is a feature that
will eventually write to one and read from the other."""


# --- reads ----------------------------------------------------------------------------


def list_scene_ids(store: Store) -> list[str]:
    """IF-03, `GET /scenes`. The scene ids as the tree has them, sorted, never records.

    Read from the tree on every call: FR-STORE-08 forbids an in-process cache, and a human
    who adds a scene record by hand expects the next request to see it.

    A file whose name is not a scene id raises `InvalidRecord` rather than being skipped. It
    can be addressed by no route at all (FR-STORE-05 rejects the id), so skipping it would
    leave a scene in the tree that nothing can reach and nobody is told about -- the same
    silent repair FR-STORE-06 refuses on a record that fails validation.
    """
    identifiers: list[str] = []
    for relative in store.list_files(SCENES_DIRECTORY, YAML_SUFFIX):
        name = relative.rsplit("/", 1)[-1].removesuffix(YAML_SUFFIX)
        try:
            identifiers.append(paths.scene_id(name))
        except ValueError as error:
            message = f"{relative} cannot be addressed as a scene record: {error}"
            raise InvalidRecord(message, file=relative) from error
    return identifiers


def read_scene(store: Store, identifier: str) -> Scene:
    """IF-03, `GET /scenes/{id}`. The whole record, untrimmed (FR-STORE-06).

    The existence check is here rather than left to the store layer so the 404 names the
    scene the caller asked for instead of the file name it happened to become (IF-07). A
    record that exists but does not validate is a different answer -- `InvalidRecord`, 422,
    naming file and field -- and the two are never merged: a missing scene and a broken one
    call for different repairs.
    """
    relative = scene_path(identifier)
    if not store.exists(relative):
        message = f"no scene record with id {identifier!r}"
        raise NotFound(message, kind="scene", identifier=identifier)
    return store.read(relative, Scene)


def read_arcs(store: Store) -> ArcsFile:
    """IF-03, `GET /structure/arcs`. One file for every arc: they are few and they are read
    together whenever the shape of the novel is in question."""
    return store.read(paths.ARCS, ArcsFile)


def read_chapters(store: Store) -> ChaptersFile:
    """IF-03, `GET /structure/chapters`. The chapter list *is* the discourse order of the
    book, and a question about that order is a question about all of them at once."""
    return store.read(paths.CHAPTERS, ChaptersFile)


# --- writes ---------------------------------------------------------------------------
#
# Every write below names the role it is performed under, and that role arrives from the
# `X-Agent-Role` header (IF-02) rather than from a default here. There is no role argument
# with a value in this file: a default would mean the provenance log recorded this module's
# opinion instead of the caller's claim (FR-STORE-04).
#
# Which role Figure 3 allows -- the architect, for all three files -- is not restated here.
# `Store.write` calls `may_write`, the single check (FR-PERM-03), and refuses with
# `PermissionDenied` before any byte touches disk. A second guard in this feature could only
# ever drift from the table.


def write_scene(
    store: Store,
    identifier: str,
    record: Scene,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /scenes/{id}` (architect). The record the whole turn is a function of."""
    return store.write(scene_path(identifier), record, role=role, actor=actor)


def write_arcs(
    store: Store,
    record: ArcsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/arcs` (architect). The whole file, because the arcs of a book
    are a single shape and a per-arc write would let two halves of it disagree."""
    return store.write(paths.ARCS, record, role=role, actor=actor)


def write_chapters(
    store: Store,
    record: ChaptersFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/chapters` (architect). The whole file, for the same reason and
    one of its own: moving a scene from one chapter to another is one edit to this file, and
    two writes could leave the scene in both chapters or in neither."""
    return store.write(paths.CHAPTERS, record, role=role, actor=actor)


__all__ = [
    "ARCS_PATH",
    "CHAPTERS_PATH",
    "SCENES_DIRECTORY",
    "YAML_SUFFIX",
    "list_scene_ids",
    "read_arcs",
    "read_chapters",
    "read_scene",
    "scene_path",
    "write_arcs",
    "write_chapters",
    "write_scene",
]
