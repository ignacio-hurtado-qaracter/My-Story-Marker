"""The manuscript feature's one door to the store layer, for `manuscript/` and its digests.

FR-STORE-02 puts every file primitive inside `app/commons/stores/` and FR-STORE-05 puts every
path inside `commons.stores.paths`. This module is where both rules meet the feature: a scene
id becomes the `Store` call that reads or writes `manuscript/NNN.md` or
`manuscript/digests/NNN.md`. Nothing here opens a file and nothing here spells a path.

**Why the two files are one feature.** `manuscript/NNN.md` is the prose and
`manuscript/digests/NNN.md` is what survives of it. The draft never enters a later context at
all, except as its own `literal_tail`; the digest is how the scene reaches everything after it
(`architecture.md` SceneDigest). They are written in the same breath by the same role -- the
writer's Figure 3 row grants both paths -- and separating them would put the prose and the
only summary of it in two features that NFR-04 forbids from importing each other.

No policy lives here. Whether the writer or the style editor may write a given path is
Figure 3's answer, given by `may_write` inside `Store.write` (FR-PERM-03). Every write below
therefore takes its role from the caller and none of them has a default: a default role would
be a guess, and FR-STORE-04 would record the guess as provenance.
"""

from __future__ import annotations

from app.commons.errors import NotFound
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import Draft, SceneDigest
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord

# --- paths ----------------------------------------------------------------------------


def draft_path(identifier: str) -> str:
    """`manuscript/NNN.md`, built and validated by the store layer.

    The single call site for the draft path grammar in this feature, so a malformed id fails
    in one place and with the message `paths` writes.
    """
    return paths.draft(identifier)


def digest_path(identifier: str) -> str:
    """`manuscript/digests/NNN.md`.

    The file is named by an id even at chapter and arc level; the range it covers lives in the
    record's `scene_ref` (DR-11). Two grammars for one directory would mean a chapter digest
    addressable by a route and an arc digest addressable by none.
    """
    return paths.digest(identifier)


# --- reads ----------------------------------------------------------------------------


def read_draft(store: Store, identifier: str) -> Draft:
    """IF-03, `GET /manuscript/{id}`. The whole record, validated (FR-STORE-06).

    The existence check is here rather than left to the store layer so the 404 names the scene
    the caller asked for instead of the file name it happened to become (IF-07). A file that
    exists but does not validate is a different answer -- `InvalidRecord`, 422, naming file and
    field -- and the two are never merged: a scene not yet drafted and a draft that is broken
    call for different repairs, and only one of them is a turn that has not run yet.
    """
    relative = draft_path(identifier)
    if not store.exists(relative):
        message = f"no draft for scene {identifier!r}"
        raise NotFound(message, kind="draft", identifier=identifier)
    return store.read(relative, Draft)


def read_digest(store: Store, identifier: str) -> SceneDigest:
    """IF-03, `GET /manuscript/digests/{id}`. The whole record, validated (FR-STORE-06).

    A missing digest is a 404 and never an empty one. A digest is derived and regenerable
    (`architecture.md` SceneDigest), so an empty record would be indistinguishable from a
    scene that genuinely changed nothing -- and assembly reads digests to decide what a later
    POV knows, so "nothing happened" is not a safe stand-in for "not summarised yet".
    """
    relative = digest_path(identifier)
    if not store.exists(relative):
        message = f"no digest for scene {identifier!r}"
        raise NotFound(message, kind="digest", identifier=identifier)
    return store.read(relative, SceneDigest)


# --- writes ---------------------------------------------------------------------------
#
# Both writes name the role they are performed under, and that role arrives from the
# `X-Agent-Role` header (IF-02) rather than from a default here. There is no role argument
# with a value in this file.
#
# Which roles Figure 3 allows -- the writer on both paths, the style editor on the draft
# alone -- is not restated here. `Store.write` calls `may_write`, the single check
# (FR-PERM-03), and refuses with `PermissionDenied` before any byte touches disk. A second
# guard in this feature could only ever drift from the table, and the distinction it would be
# copying is a fine one: the style editor polishes prose and may not restate what the scene
# meant, because the digest is what the rest of the book reads instead of the prose.
#
# Neither write names a scene or a turn on the provenance line. Those two fields mean "this
# write happened inside a turn" (FR-STORE-04), and a `PUT` from a client did not; the turn
# orchestrator passes them when it writes through the same functions at plan step 18.


def write_draft(
    store: Store,
    identifier: str,
    record: Draft,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/{id}` (writer, style_editor). The prose of one scene."""
    return store.write(draft_path(identifier), record, role=role, actor=actor)


def write_digest(
    store: Store,
    identifier: str,
    record: SceneDigest,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/digests/{id}` (writer). What survives the scene."""
    return store.write(digest_path(identifier), record, role=role, actor=actor)


__all__ = [
    "digest_path",
    "draft_path",
    "read_digest",
    "read_draft",
    "write_digest",
    "write_draft",
]
