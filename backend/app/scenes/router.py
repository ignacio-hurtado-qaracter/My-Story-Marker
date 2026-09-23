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

**IF-05's three operations on a scene** -- `POST /scenes/{id}/select` (FR-OPS-02),
`POST /scenes/{id}/assemble` (FR-OPS-03) and `POST /scenes/{id}/audit` (FR-AUD) -- are the
load-bearing calls of this feature, and each needs machinery of its own: the index and the
embedder for selection, the token estimate and the 100k cap for assembly, the invariant
modules for the audit. The audit delegates to `app.ledger.audit`, the ledger's public surface
for it (scenes sits above ledger in NFR-04's layers).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query

from app.commons.deps import (
    ActorDep,
    EmbedderDep,
    RoleDep,
    SettingsDep,
    StoreDep,
    require_role,
)
from app.commons.schemas import SCENE_ID_PATTERN, Scene
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger import audit
from app.scenes import service
from app.scenes.models import ArcsFile, AssembledContext, ChaptersFile, Selection

router = APIRouter(prefix="/scenes", tags=["scenes"])
structure_router = APIRouter(prefix="/structure", tags=["structure"])

SceneIdParam = Annotated[
    str,
    Path(
        alias="id",
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


@router.get("/{id}", summary="Read a scene record")
def read_scene(store: StoreDep, scene: SceneIdParam) -> Scene:
    """IF-03, `GET /scenes/{id}`. The whole record.

    Everything the harness does to produce a chapter is a function of this record: selection
    reads it (FR-OPS-02), assembly is anchored to it (FR-OPS-03), and the mechanical
    invariants run over its `story_time`, `location`, `pov` and `participants`.
    """
    return service.read_scene(store, scene)


@router.put("/{id}", summary="Write a scene record")
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
# IF-05's operations on a scene: select, assemble, audit.
# --------------------------------------------------------------------------------------


@router.post("/{id}/select", summary="Select the entities a scene needs")
def select_entities(
    store: StoreDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    scene: SceneIdParam,
) -> Selection:
    """IF-05, `POST /scenes/{id}/select` (FR-OPS-02, AC 11). Ids, kinds and scores, never text.

    The entities named in `pins` come first, in the record's order, then the axioms whose
    `scope` intersects `tags`, then BM25 and cosine fused by reciprocal rank; the POV is
    absent. The FR-IDX-08 incremental update runs first, so the answer reflects every store
    write made before the call. A pin that names no entity is a 422 naming the `pins` field
    of the scene record, not a silent omission.

    No `X-Agent-Role`: nothing in the stores is written, and the index is not a store (like
    `/index/rebuild`). Plain `def` because it blocks on SQLite and on the embedder.
    """
    return service.select_entities(store, embedder, settings, scene)


@router.post("/{id}/assemble", summary="Assemble the writer's context for a scene")
def assemble_context(
    store: StoreDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    scene: SceneIdParam,
) -> AssembledContext:
    """IF-05, `POST /scenes/{id}/assemble` (FR-OPS-03, FR-OPS-04, AC 12). Selects, then loads.

    The selection is the one `/select` answers, made here first with its FR-IDX-08 update;
    each entry is then loaded as of the scene's story time, in ranking order after the fixed
    block, the POV's dossier and the previous scene's tail, and the context is fitted to the
    100k cap: what did not fit is named in `removed` and `truncated_at`, what its as-of form
    excludes in `withheld`, and nothing is cut inside an entry. `warnings` carries
    `fixed_block_over_budget` when the fixed block exceeds 800 tokens.

    Assembled with **no system prompt and no instruction**, so the estimate here is the
    documents alone. A turn's `dry_run` (plan step 18) assembles with the writer's system
    prompt and instruction counted in the mandatory part, and can therefore stop earlier than
    this route on the same tree. A mandatory part over the cap on its own is a 422
    `ContextBudgetExceeded`: a record is too large and is fixed at the source (FR-CTX-05).

    No `X-Agent-Role`: nothing in the stores is written. Plain `def` because it blocks on
    SQLite, the embedder and the store reads.
    """
    selection = service.select_entities(store, embedder, settings, scene)
    return service.assemble_context(store, scene, selection.entities)


@router.post("/{id}/audit", summary="Audit a scene against the domain invariants")
def audit_scene(
    store: StoreDep,
    actor: ActorDep,
    scene: SceneIdParam,
    semantic: Annotated[
        bool,
        Query(
            description=(
                "Request the model-backed half too (FR-AUD-09: invariants 3 and 6, and the "
                "prose halves of 1 and 8). Until plan step 17 it cannot run, and its "
                "invariants are listed in `skipped`. `false` is the mechanical audit only."
            ),
        ),
    ] = True,
    persist: Annotated[
        bool,
        Query(
            description=(
                "Write the findings into `ledger/violations.yaml`, merged with what is there. "
                "Requires `X-Agent-Role`; Figure 3 lets only the auditor write that file. "
                "Without it nothing is written."
            ),
        ),
    ] = False,
    x_agent_role: Annotated[
        str | None,
        Header(
            alias="X-Agent-Role",
            description=(
                "Required only with `persist=true`, where it must be `auditor`; any other "
                "role is a 403 and leaves the tree byte-identical (AC 16)."
            ),
        ),
    ] = None,
) -> audit.AuditReport:
    """IF-05, `POST /scenes/{id}/audit`. Reports; does not repair (AC 15, AC 16).

    The checks read the scene, the book's other scene records, the draft, the lexicon, the
    time system, the setups, the threads, every knowledge file and the POV's voice, and
    return every finding with the list of checks that ran and those that did not -- so an
    empty list of violations is never read as a pass on a check that was skipped.

    Reading needs no role: without `persist` the route writes nothing and is safe to call
    from anywhere. With `persist`, the role is required before anything runs (IF-02, a 400
    when absent) and the write is decided by Figure 3 inside the store layer, never here. The
    role header is declared on this route rather than taken from `RoleDep` because `RoleDep`
    would make it mandatory for the read-only call as well.
    """
    role = require_role(x_agent_role) if persist else None
    report = audit.audit_scene(store, scene, semantic=semantic)
    if role is None:
        return report
    record = audit.persist(store, report, role=role, actor=actor)
    return report.model_copy(update={"persisted": record})


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
