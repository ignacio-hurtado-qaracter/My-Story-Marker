"""The HTTP surface of the scenes feature: IF-03's reads and IF-04's writes, under `/scenes`
and under `/structure`.

**Why one feature holds two prefixes.** `structure/arcs.yaml` and `structure/chapters.yaml`
are the narrative containers the architect writes, and `scenes/NNN.yaml` is what those
containers contain. They are one role's work (Figure 3 gives the architect `structure/**` and
`scenes/**` and nothing else), one concern -- the plan of the book, before a word of it
exists -- and one set of cross-references: a chapter names its scenes in discourse order and
its arc by id. The spec's scope lists six feature folders, `canon/`, `cast/`, `scenes/`,
`manuscript/`, `ledger/`, `agents/`, with no `structure/` among them, so there is no folder
for those two files to live in but this one. Splitting them off would create a feature whose
every record points into this one, and NFR-04 forbids a feature importing a feature: the
`arc` id on a chapter and the scene ids it lists would have to be resolved by a third party
or not at all. Two routers rather than one with two prefixes, because `APIRouter` carries a
single prefix and tags, and `/structure` is a different tag in the committed OpenAPI document
(IF-08); `main.py` mounts both.

Three conventions hold in every handler, each of them a rule from the spec rather than a
style preference:

* **Plain `def`, never `async def`.** Every handler ends in the store layer, which is
  blocking file I/O (FR-STORE-07: temp file, fsync, rename). Declared `async`, it would run
  on the event loop and stall every other request for the duration of an fsync; declared
  `def`, FastAPI runs it in a worker thread.
* **The role comes from the header and nowhere else** (IF-02). `RoleDep` is a 400 when
  `X-Agent-Role` is missing or unknown, and there is no default: the write is then refused or
  allowed by Figure 3 inside `Store.write` (FR-PERM-03), and the provenance line records the
  role that was actually claimed (FR-STORE-04).
* **No `HTTPException`.** Handlers raise the domain errors of `commons.errors`, and the
  handler registered by the app factory maps each to its IF-07 status code, so the status
  table lives in exactly one place.

Writes answer with the provenance line that was appended -- path, role, actor, content hash,
timestamp. A caller that has just written under a role can therefore see what the log will
show, which is the point of a log no caller can skip.

**Deliberately absent, not forgotten.** IF-05's three operations on a scene --
`POST /scenes/{id}/select` (FR-OPS-02), `POST /scenes/{id}/assemble` (FR-OPS-03) and
`POST /scenes/{id}/audit` (FR-AUD) -- arrive at plan steps 11, 12 and 14. They are the
load-bearing calls of this feature and each needs machinery that does not exist yet: the
index and the embedder for selection, the token counter for assembly, the invariant modules
for the audit. Until then this router serves the records those operations will read.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.commons.deps import ActorDep, RoleDep, StoreDep
from app.commons.schemas import SCENE_ID_PATTERN, Scene
from app.commons.stores.provenance import ProvenanceRecord
from app.scenes import service
from app.scenes.models import ArcsFile, ChaptersFile

router = APIRouter(prefix="/scenes", tags=["scenes"])
structure_router = APIRouter(prefix="/structure", tags=["structure"])

SceneIdParam = Annotated[
    str,
    Path(
        pattern=SCENE_ID_PATTERN,
        description=(
            "Stable scene id: `NNN`, three digits. The grammar is FR-STORE-05's, declared "
            "here so a malformed id is a 422 at the edge rather than an exception from the "
            "store layer, and so the committed OpenAPI document (IF-08) states it."
        ),
    ),
]
"""The path parameter of every per-scene route. The store layer checks the same grammar again
when it builds the path (FR-STORE-05); this copy is for the contract and for the error the
client gets, not for the guarantee."""


# --------------------------------------------------------------------------------------
# /scenes
# --------------------------------------------------------------------------------------


@router.get("", summary="List the scene records")
def list_scenes(store: StoreDep) -> list[str]:
    """IF-03, `GET /scenes`. The scene ids, sorted, read from the tree on every call.

    Ids rather than records: the list of scenes in the book is read far more often than any
    one of them, and a route that returned every record would put the whole plan of the novel
    on the wire to answer "which scenes exist".
    """
    return service.list_scenes(store)


@router.get("/{scene}", summary="Read a scene record")
def read_scene(store: StoreDep, scene: SceneIdParam) -> Scene:
    """IF-03, `GET /scenes/{id}`. The whole record.

    Everything the harness does to produce a chapter is a function of this record: selection
    reads it (FR-OPS-02), assembly is anchored to it (FR-OPS-03), and the mechanical
    invariants run over its `story_time`, `location`, `pov` and `participants`.
    """
    return service.read_scene(store, scene)


@router.put("/{scene}", summary="Write a scene record")
def write_scene(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    scene: SceneIdParam,
    record: Scene,
) -> ProvenanceRecord:
    """IF-04, `PUT /scenes/{id}` (architect).

    The architect is a human acting under the role in v1 (spec Decision 5), which changes
    nothing here: the role still arrives in the header and Figure 3 still decides, because a
    human acts under a role rather than beside it.
    """
    return service.save_scene(store, scene, record, role=role, actor=actor)


# --------------------------------------------------------------------------------------
# IF-05's three operations on a scene belong here and are deliberately absent, not
# forgotten:
#
#   POST /scenes/{id}/select     FR-OPS-02, plan step 11 -- needs the index and the embedder
#   POST /scenes/{id}/assemble   FR-OPS-03, plan step 12 -- needs the token counter and the
#                                                           100k cap
#   POST /scenes/{id}/audit      FR-AUD,    plan step 14 -- needs the invariant modules
#
# Each is a step of its own in the plan because each needs machinery that does not exist
# yet. A reader who finds only reads and writes here is looking at an incomplete feature on
# purpose, at the commit the plan puts them at.
# --------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------
# /structure
# --------------------------------------------------------------------------------------


@structure_router.get("/arcs", summary="Read every arc")
def read_arcs(store: StoreDep) -> ArcsFile:
    """IF-03, `GET /structure/arcs`. The largest containers, and pure plan: an arc holds no
    list of its own chapters, because a chapter names its arc instead."""
    return service.read_arcs(store)


@structure_router.put("/arcs", summary="Write every arc")
def write_arcs(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    record: ArcsFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/arcs` (architect). The whole file: the arcs of a book are one
    shape, and the budgets in it only mean anything summed."""
    return service.save_arcs(store, record, role=role, actor=actor)


@structure_router.get("/chapters", summary="Read every chapter")
def read_chapters(store: StoreDep) -> ChaptersFile:
    """IF-03, `GET /structure/chapters`. Each chapter lists its scenes in discourse order --
    the order the reader meets them, which is the axis the tension curve is designed on, and
    which differs from story time the moment the book contains one flashback."""
    return service.read_chapters(store)


@structure_router.put("/chapters", summary="Write every chapter")
def write_chapters(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    record: ChaptersFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /structure/chapters` (architect). The whole file, so that moving a scene
    from one chapter to another cannot leave it in both or in neither."""
    return service.save_chapters(store, record, role=role, actor=actor)


__all__ = ["router", "structure_router"]
