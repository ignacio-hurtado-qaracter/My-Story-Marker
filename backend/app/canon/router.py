"""The HTTP surface of `canon/`: IF-03's reads and IF-04's writes, and nothing else.

Three things about this file are decisions rather than style.

**Plain `def`, not `async def`.** Every handler here calls the store layer, which is
blocking file I/O. Declared `async`, they would run on the event loop and a slow disk would
stall every other request in the process; declared `def`, FastAPI runs them in a worker
thread. There is no `await` in this feature and there is not meant to be one.

**One typed route per kind, registered in a loop.** The five kinds map to five different
models. A single `/canon/{kind}/{id}` route would have to accept a union body, which means
pydantic guessing which model a `PUT` carries - and a guess that lands on the wrong model
writes a valid-looking file of the wrong kind, which validates cleanly and is wrong for
good. Registering `/canon/axioms/{id}` against `Axiom` alone makes the guess impossible and
makes the exported OpenAPI schema (IF-08, AC 29) say exactly what each path takes and
returns. `_register_kind` takes `kind` and `model` as parameters, so the loop variables are
bound per registration rather than read back at call time.

**No role check in this file.** Writes take `X-Agent-Role` (IF-02) through `RoleDep` and
hand it to the store layer, which calls `may_write` - the single check (FR-PERM-03) - and
refuses with `PermissionDenied`, 403, before any byte touches disk. Figure 3's two inbound
write edges into `canon/` are the world builder and the canoniser; that fact lives in the
permission table and is deliberately not restated as an `if` here, where it could drift.

`POST /canon/reconcile` (IF-05, FR-OPS-08) is the one canon route this file does not carry.
It arrives at plan step 13 with `promote` and `rule`, and is left out rather than stubbed.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from app.canon import service
from app.canon.models import Project, StyleBible
from app.canon.service import CanonEntity
from app.commons.deps import ActorDep, RoleDep, StoreDep
from app.commons.schemas.common import ENTITY_ID_PATTERN
from app.commons.schemas.lexicon import LexiconFile
from app.commons.schemas.time import TemporalSystem
from app.commons.stores import paths
from app.commons.stores.provenance import ProvenanceRecord

EntityIdPath = Annotated[
    str,
    Path(
        alias="id",
        pattern=ENTITY_ID_PATTERN,
        description="Stable entity identifier; the file under `canon/<kind>/` is named after it.",
    ),
]
"""FR-STORE-05's entity grammar, declared on the parameter.

The store layer validates it again and would raise, but that raise would be a 500: an
identifier the client got wrong is the client's error, so the pattern is part of the
contract the OpenAPI document publishes and a bad one is refused with a 422 before any
handler runs.
"""

router = APIRouter(prefix="/canon", tags=["canon"])


# --- Layer 0: the fixed block (read-only over HTTP; IF-04 opens no write route) --------


@router.get("/project")
def read_project(store: StoreDep) -> Project:
    """IF-03. The premise, thesis and genre contract: half of the fixed block (FR-OPS-03)."""
    return service.project(store)


@router.get("/style")
def read_style(store: StoreDep) -> StyleBible:
    """IF-03. The style bible and its canonical sample prose: the other half."""
    return service.style(store)


# --- the two single-file records of canon/ --------------------------------------------


@router.get("/lexicon")
def read_lexicon(store: StoreDep) -> LexiconFile:
    """IF-03. Every canonical term with its forbidden variants (DR-09)."""
    return service.lexicon(store)


@router.put("/lexicon")
def replace_lexicon(
    record: LexiconFile,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> ProvenanceRecord:
    """IF-04. Replace the whole vocabulary; DR-09 keeps it in one file, so a write is total.

    The response is the provenance line that was appended (FR-STORE-04): the path, the role
    the write was recorded under and the hash of the bytes that landed. A caller learns what
    the log now says about it, rather than being handed back the body it just sent.
    """
    return service.replace_lexicon(store, record, role=role, actor=actor)


@router.get("/time")
def read_time(store: StoreDep) -> TemporalSystem:
    """IF-03. Epoch, calendars and the transit matrix invariant 5 is checked against."""
    return service.temporal_system(store)


@router.put("/time")
def replace_time(
    record: TemporalSystem,
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
) -> ProvenanceRecord:
    """IF-04. There is exactly one temporal system per project (DR-09), so likewise total."""
    return service.replace_temporal_system(store, record, role=role, actor=actor)


# --- Layer 1: one typed set of routes per canon kind ----------------------------------


def _register_kind(target: APIRouter, kind: str, model: type[CanonEntity]) -> None:
    """Mount `GET /canon/<kind>`, `GET /canon/<kind>/{id}` and `PUT /canon/<kind>/{id}`.

    The handlers are annotated with `CanonEntity` for the type checker and with the kind's
    own model at runtime: the two assignments below replace the annotations FastAPI reads,
    so `/canon/axioms/{id}` documents and validates `Axiom` and nothing else. The static
    union is never what pydantic sees, which is the point - it exists only so the shared
    body can be typed, since `StoreDocument` has no `id` to compare against the path.
    """

    def list_ids(store: StoreDep) -> service.KindIndex:
        """IF-03. The identifiers of this kind, sorted. Never the records themselves."""
        return service.list_kind(store, kind)

    def read_one(identifier: EntityIdPath, store: StoreDep) -> CanonEntity:
        """IF-03. One record of this kind, validated on read (FR-STORE-06)."""
        return service.entity(store, kind, identifier, model)

    def replace_one(
        identifier: EntityIdPath,
        record: CanonEntity,
        store: StoreDep,
        role: RoleDep,
        actor: ActorDep,
    ) -> ProvenanceRecord:
        """IF-04. Write one record of this kind under the role the request names.

        The body's `id` must equal the path's; the service refuses a mismatch rather than
        picking one (422). The response is the appended provenance line (FR-STORE-04).
        """
        return service.replace_entity(store, kind, identifier, record, role=role, actor=actor)

    read_one.__annotations__["return"] = model
    replace_one.__annotations__["record"] = model

    # The generated operation ids are built from these names, so they read as
    # `read_axioms`, `replace_factions` rather than five operations all called `read_one`.
    list_ids.__name__ = f"list_{kind}"
    read_one.__name__ = f"read_{kind}"
    replace_one.__name__ = f"replace_{kind}"

    target.get(f"/{kind}")(list_ids)
    target.get(f"/{kind}/{{id}}")(read_one)
    target.put(f"/{kind}/{{id}}")(replace_one)


for _kind in paths.CANON_KINDS:
    _register_kind(router, _kind, service.CANON_MODELS[_kind])


__all__ = ["EntityIdPath", "router"]
