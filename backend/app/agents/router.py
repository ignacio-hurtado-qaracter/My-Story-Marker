"""The HTTP surface of the agents feature, mounted at `/agents` (IF-01, IF-06).

* `POST /agents/digests/rollup` rolls a chapter or an arc up into its digest (FR-AGENT-08).

The turn routes of IF-06 and the agents reads of IF-03 (`/agents/turns...`,
`/agents/provenance`) arrive with the orchestrator at plan step 18.

The conventions of the other feature routers hold: plain `def`, because the handlers block on
store I/O and FastAPI runs them in its threadpool; the role from `X-Agent-Role` and nowhere else
(IF-02); no `HTTPException`, only the domain errors IF-07 maps. Rollup takes no `X-Actor`: what
lands is model output, recorded with `actor: agent` whoever asked for it (Decision R2-7).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agents import service
from app.agents.models import RollupRequest, RollupResponse
from app.commons.deps import ModelClientDep, RoleDep, StoreDep

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/digests/rollup", summary="Roll a chapter or an arc up into its digest")
def rollup_digests(
    store: StoreDep,
    role: RoleDep,
    client: ModelClientDep,
    request: RollupRequest,
) -> RollupResponse:
    """IF-06, FR-AGENT-08. The writer rolls the digests below a chapter or an arc into one.

    A chapter reads the scene digests of its scenes, in discourse order; an arc the chapter
    digests of its chapters. The digest is filed under `manuscript/digests/` as `900 + k` for
    the k-th chapter of `structure/chapters.yaml` and `989 + k` for the k-th arc, with the
    covered range in `scene_ref` and the POVs the scene records name in `povs`.

    Refused before any model call: a role whose tool set does not reach the digest file
    (Figure 3 gives it to the writer alone) is a 403, and a chapter or arc with a digest
    missing is a 404 naming it -- a rollup of a partial set would read as the whole.
    """
    return service.rollup(
        store, client, role=role, chapter_id=request.chapter_id, arc_id=request.arc_id
    )


__all__ = ["router"]
