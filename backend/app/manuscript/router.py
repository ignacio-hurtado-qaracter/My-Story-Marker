"""The HTTP surface of `manuscript/`: IF-03's two reads and IF-04's two writes, and nothing
else.

Four things about this file are decisions rather than style.

**Plain `def`, not `async def`.** Every handler here ends in the store layer, which is
blocking file I/O (FR-STORE-07: temp file, fsync, rename). Declared `async`, a handler would
run on the event loop and stall every other request in the process for the length of an
fsync; declared `def`, FastAPI runs it in a worker thread. There is no `await` in this feature
and there is not meant to be one.

**The digest routes are declared first.** `/manuscript/digests/{id}` is two path segments and
`/manuscript/{id}` is one, and a Starlette path parameter does not cross `/`, so today the
literal cannot be swallowed by the parameter whatever the order. The order is kept anyway,
because it stops being free the moment anything under `/manuscript` takes a path converter or
a second literal, and a reader looking for the rule should find it written down rather than
have to derive it from the router's matching behaviour.

**No role check in this file.** Writes take `X-Agent-Role` through `RoleDep` (IF-02) and hand
it to the store layer, which calls `may_write` -- the single check (FR-PERM-03) -- and refuses
with `PermissionDenied`, 403, before any byte touches disk. Figure 3 gives the draft to the
writer and the style editor and the digest to the writer alone; that fact lives in the
permission table and is deliberately not restated as an `if` here, where it could drift.

**Nothing in a request body decides `words` or `literal_tail`.** Both are measured from the
prose in `service.measure_prose` and overwrite whatever arrived (DR-11, FR-AGENT-03). The
request models still declare them because they are fields of the stored record; a caller that
sends them is not refused, it is simply not believed.

Writes answer with the provenance line that was appended -- path, role, actor, content hash,
timestamp -- so a caller that has just written under a role can see what the log will show.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.commons.deps import ActorDep, RoleDep, StoreDep
from app.commons.schemas import SCENE_ID_PATTERN, Draft, SceneDigest
from app.commons.stores.provenance import ProvenanceRecord
from app.manuscript import service

router = APIRouter(prefix="/manuscript", tags=["manuscript"])

SceneIdPath = Annotated[
    str,
    Path(
        alias="id",
        pattern=SCENE_ID_PATTERN,
        description=(
            "Stable scene id: `NNN`, three digits. Both files of a scene are named after it, "
            "at every digest level (DR-11)."
        ),
    ),
]
"""The path parameter of every route here. The store layer checks the same grammar again when
it builds the path (FR-STORE-05); this copy exists so a malformed id is a 422 at the edge
rather than an exception from inside the store layer, and so the committed OpenAPI document
(IF-08) states the grammar."""


# --------------------------------------------------------------------------------------
# /manuscript/digests -- declared before /manuscript/{id}
# --------------------------------------------------------------------------------------


@router.get("/digests/{id}", summary="Read a digest")
def read_digest(identifier: SceneIdPath, store: StoreDep) -> SceneDigest:
    """IF-03, `GET /manuscript/digests/{id}`. One digest, at whichever level it was written.

    Digests are how a scene reaches everything after it: apart from the previous scene's
    `literal_tail`, they are the only form in which past prose enters a later context at all
    (`architecture.md` SceneDigest).
    """
    return service.read_digest(store, identifier)


@router.put("/digests/{id}", summary="Write a digest")
def write_digest(
    identifier: SceneIdPath,
    record: SceneDigest,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/digests/{id}` (writer).

    `words` is measured from `delta` and replaces whatever the body carried. `povs` is not
    measurable and is taken as given: it is the filter FR-OPS-03 applies, so a name wrongly
    present there hands a later POV knowledge nobody gave them -- invariant 1 broken by
    bookkeeping rather than by the prose, and a question for the audit rather than for a
    write route.
    """
    return service.save_digest(store, identifier, record, role=role, actor=actor)


# --------------------------------------------------------------------------------------
# /manuscript
# --------------------------------------------------------------------------------------


@router.get("/{id}", summary="Read a draft")
def read_draft(identifier: SceneIdPath, store: StoreDep) -> Draft:
    """IF-03, `GET /manuscript/{id}`. The prose of one scene, whole.

    This route is for a reader -- a human, the frontend, the export -- and not for context
    assembly: raw draft prose never enters a model's context except as the previous scene's
    `literal_tail` (FR-OPS-03). A route that returns the manuscript is not a route that puts
    it in front of an agent.
    """
    return service.read_draft(store, identifier)


@router.put("/{id}", summary="Write a draft")
def write_draft(
    identifier: SceneIdPath,
    record: Draft,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/{id}` (writer, style_editor).

    The two roles that may write here reach it for different reasons -- the writer drafts,
    the style editor polishes -- and the route does not tell them apart: which of them the
    request claims is `X-Agent-Role`'s answer, and whether that claim is allowed is Figure
    3's. Both are recorded on the provenance line, so a change of voice in a scene can be
    traced to the role that made it.
    """
    return service.save_draft(store, identifier, record, role=role, actor=actor)


__all__ = ["SceneIdPath", "router"]
