"""The HTTP surface of the agents feature, mounted at `/agents` (IF-01, IF-03, IF-06).

* `POST /agents/turns` `{scene_id}` runs one turn (FR-TURN-01) and streams one Server-Sent
  Event per step, then a final event with the outcome and the record id (IF-06, P5). With
  `?dry_run=true` it runs the assembly alone and answers the `AssembledContext` as JSON, with
  no model call (FR-TURN-10).
* `GET /agents/turns` and `GET /agents/turns/{id}` read the turn records (IF-03, FR-TURN-07).
* `POST /agents/turns/{id}/rulings` hands down a human's rulings on the turn's collisions,
  under `X-Agent-Role: canoniser` and `X-Actor: human` (FR-TURN-08).
* `POST /agents/turns/{id}/resume` continues a turn a crash interrupted, streaming like a new
  turn (FR-TURN-09).
* `GET /agents/provenance?path=&since=` reads the provenance log (IF-03, FR-STORE-04).
* `POST /agents/digests/rollup` rolls a chapter or an arc up into its digest (FR-AGENT-08).

**Refusals come before the stream.** A turn's lock and preconditions are taken in the handler,
so a scene that does not exist is a 404 and a locked store root or a pending ruling a 409, as
IF-07 maps them, before any event is sent. Once the stream has started, the turn's own failures
are its outcome -- `escalated`, with the category -- and never an HTTP error.

**The stream.** The turn is synchronous (P5): each step runs in a worker thread, one at a time,
and its event is sent when it ends. A client that disconnects stops the turn at the end of the
step it is in -- the record says how far it got, and `resume` continues it -- and the lock is
released on that path too: the stream's `finally` closes the turn, shielded from the
cancellation that ended it.

The conventions of the other feature routers hold: plain `def`, because the handlers block on
store I/O and FastAPI runs them in its threadpool; the role from `X-Agent-Role` and nowhere else
(IF-02); no `HTTPException`, only the domain errors IF-07 maps. Starting or resuming a turn takes
no role: the orchestrator holds none, and every write it makes is under the role Figure 4 gives
the step (FR-TURN-06). Rollup takes no `X-Actor`: what lands is model output, recorded with
`actor: agent` whoever asked for it (Decision R2-7).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from typing import Annotated, Final

import anyio
from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse, Response
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.types import Receive, Scope, Send

from app.agents import records, service, turn
from app.agents.models import (
    RollupRequest,
    RollupResponse,
    RulingRequest,
    TurnEvent,
    TurnRequest,
)
from app.commons.deps import (
    ActorDep,
    EmbedderDep,
    ModelClientDep,
    RoleDep,
    SettingsDep,
    StoreDep,
)
from app.commons.schemas import TurnRecord
from app.commons.schemas.turn import TURN_ID_PATTERN
from app.commons.stores.provenance import ProvenanceRecord

router = APIRouter(prefix="/agents", tags=["agents"])

TurnId = Annotated[str, Path(pattern=TURN_ID_PATTERN, description="`NNN-<n>`.")]


class TurnEventStream(EventSourceResponse):
    """`text/event-stream`, declared on the class so the committed OpenAPI document (IF-08)
    lists the stream's media type and its event schema, `TurnEvent`.

    **The response owns the turn's lock from the handler on** (FR-TURN-05). `_stream`'s own
    `finally` covers every path once its first event is asked for, but a response can die
    before that -- a client gone before the headers go out, where an ASGI 2.4 server raises
    `OSError` on the send -- and an async generator that never started never runs its
    `finally`. So the response closes the turn itself when it ends, however it ends; closing
    is idempotent, and a turn stopped before its first step is still `running` and resumable.
    """

    media_type = "text/event-stream"
    _run: turn.TurnRun | None = None

    @classmethod
    def of(cls, run: turn.TurnRun) -> TurnEventStream:
        """The stream of `run`'s events, closing `run` when the response ends. A constructor of
        its own because FastAPI reads the class's `__init__` for the route's default status."""
        response = cls(_stream(run))
        response._run = run
        return response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self._run is not None:
                with anyio.CancelScope(shield=True):
                    self._run.close()


STREAM_DESCRIPTION: Final[str] = (
    "One `TurnEvent` per step as `text/event-stream` (SSE `event: step`), then one with the"
    " outcome (`event: outcome`)."
)

STREAM_RESPONSES: Final[dict[int | str, dict[str, object]]] = {
    200: {
        "model": TurnEvent,
        "description": f"{STREAM_DESCRIPTION} With `dry_run=true`, the `AssembledContext` as"
        " JSON instead.",
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/AssembledContext"}}
        },
    }
}


def _sse(event: TurnEvent, index: int) -> ServerSentEvent:
    return ServerSentEvent(
        data=event.model_dump_json(), event=event.kind, id=f"{event.turn_id}:{index}"
    )


def _next(events: Generator[TurnEvent]) -> TurnEvent | None:
    return next(events, None)


async def _stream(run: turn.TurnRun) -> AsyncIterator[ServerSentEvent]:
    """One SSE per `TurnEvent`, each step run in a worker thread (P5: the turn is synchronous).

    The `finally` is shielded: whatever ended the stream -- the last event, an error, a client
    that went away -- the turn is closed and the lock released (FR-TURN-05).
    """
    events = run.events()
    index = 0
    try:
        while True:
            event = await anyio.to_thread.run_sync(_next, events)
            if event is None:
                return
            yield _sse(event, index)
            index += 1
    finally:
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(events.close)
            run.close()


@router.post(
    "/turns",
    summary="Run one writing turn on a scene, streaming a progress event per step",
    response_class=TurnEventStream,
    response_model=None,
    responses=STREAM_RESPONSES,
)
def start_turn(
    store: StoreDep,
    client: ModelClientDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    request: TurnRequest,
    dry_run: Annotated[
        bool,
        Query(description="Run the assembly only and answer the `AssembledContext` (FR-TURN-10)."),
    ] = False,
) -> Response:
    """FR-TURN-01, IF-06. Figure 4 on one scene: assemble, write, audit, revise while blocking
    violations remain (at most three times), polish, digest, extract, promote.

    Refused before the stream starts: a scene with no record (404), another turn running on
    this store root or a collision of this scene waiting for a ruling (409, FR-TURN-05). The
    final event carries the outcome -- `merged`, `awaiting_ruling` or `escalated` with its
    category -- and the record id; `GET /agents/turns/{id}` has the rest.
    """
    if dry_run:
        context = turn.dry_run(store, embedder, settings, request.scene_id)
        return JSONResponse(context.model_dump(mode="json"))
    run = turn.begin_turn(store, client, embedder, settings, request.scene_id)
    return TurnEventStream.of(run)


@router.get("/turns", summary="List the turn records")
def list_turns(store: StoreDep) -> list[TurnRecord]:
    """IF-03, FR-TURN-07. Every turn record under `.index/turns/`, by scene and attempt."""
    return records.list_all(store)


@router.get("/turns/{turn_id}", summary="Read one turn record")
def read_turn(store: StoreDep, turn_id: TurnId) -> TurnRecord:
    """IF-03, FR-TURN-07. The record of one turn: its steps with their models and token counts,
    the selected list, the violations of each iteration and what became of its facts."""
    return records.load(store, turn_id)


@router.post("/turns/{turn_id}/rulings", summary="Rule on a turn's collided facts")
def rule_on_turn(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    turn_id: TurnId,
    rulings: list[RulingRequest],
) -> TurnRecord:
    """FR-TURN-08, FR-OPS-07. `accept` promotes a collided fact despite the collision, `reject`
    refuses it; each ruling is recorded on the fact with its reason, an accepted fact is
    reconciled, and the turn moves from `awaiting_ruling` to `merged` when none is left.

    The human gate: only the canoniser with `X-Actor: human` gets past the ledger's `rule`
    (403 otherwise). A fact that is not one of this turn's collisions is a 404; a turn that is
    not awaiting a ruling, or another turn running, a 409. The batch is checked before the first
    ruling lands.
    """
    return turn.apply_rulings(store, turn_id, rulings, role=role, actor=actor)


@router.post(
    "/turns/{turn_id}/resume",
    summary="Resume a turn a crash interrupted, streaming a progress event per step",
    response_class=TurnEventStream,
    response_model=None,
    responses={200: {"model": TurnEvent, "description": STREAM_DESCRIPTION}},
)
def resume_turn(
    store: StoreDep,
    client: ModelClientDep,
    embedder: EmbedderDep,
    settings: SettingsDep,
    turn_id: TurnId,
) -> Response:
    """FR-TURN-09. Continue a `running` turn from its record, without re-running the steps it
    records as done. A turn that ended is a 409; a missing record a 404."""
    run = turn.resume_turn(store, client, embedder, settings, turn_id)
    return TurnEventStream.of(run)


@router.get("/provenance", summary="Read the provenance log")
def read_provenance(
    store: StoreDep,
    path: Annotated[
        str | None, Query(description="Only the writes of this store-relative path.")
    ] = None,
    since: Annotated[
        str | None, Query(description="Only the writes at or after this ISO-8601 instant.")
    ] = None,
) -> list[ProvenanceRecord]:
    """IF-03, FR-STORE-04. Who wrote what, under which role, and whether a human was behind it,
    in the order the writes landed. Filters, never aggregates."""
    return store.provenance(path=path, since=since)


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


__all__ = ["TurnEventStream", "router"]
