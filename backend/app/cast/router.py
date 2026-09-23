"""The HTTP surface of the cast: IF-03's reads and IF-04's writes, under `/cast`.

Three conventions hold in every handler and each of them is a rule from the spec rather than
a style preference:

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
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.cast import service
from app.cast.models import Character, TrimmedDossier, VoiceProfile
from app.commons.deps import ActorDep, RoleDep, StoreDep
from app.commons.schemas import (
    ENTITY_ID_PATTERN,
    ChangesFile,
    KnowledgeFile,
    RelationshipsFile,
)
from app.commons.stores.provenance import ProvenanceRecord

router = APIRouter(prefix="/cast", tags=["cast"])

CharacterId = Annotated[
    str,
    Path(
        alias="id",
        pattern=ENTITY_ID_PATTERN,
        min_length=1,
        max_length=120,
        description=(
            "Stable character id; it names the `cast/{id}/` directory. The grammar is "
            "FR-STORE-05's, declared here so a malformed id is a 422 at the edge rather "
            "than an exception from the store layer, and so the committed OpenAPI "
            "document (IF-08) states it."
        ),
    ),
]
"""The path parameter of every per-character route. The store layer checks the same grammar
again when it builds the path (FR-STORE-05); this copy is for the contract and for the error
the client gets, not for the guarantee."""


@router.get("", summary="List the cast")
def list_cast(store: StoreDep) -> list[str]:
    """IF-03, `GET /cast`. The character ids, sorted, read from the tree on every call."""
    return service.list_characters(store)


# --------------------------------------------------------------------------------------
# `cast/relationships.yaml` -- declared BEFORE `/{character}`.
#
# Route order is matching order in Starlette. With `/{character}` first, the literal path
# `/cast/relationships` is captured by the parameter, `relationships` is read as a character
# id, and the request becomes a 404 for `cast/relationships/dossier.md`. It looks exactly
# like a missing file, which is why this comment is here and not in a commit message.
# --------------------------------------------------------------------------------------


@router.get("/relationships", summary="Read every relationship in the cast")
def read_relationships(store: StoreDep) -> RelationshipsFile:
    """IF-03, `GET /cast/relationships`. One file for the whole graph: an edge is directed,
    and the two directions of a pair are separate rows that may disagree."""
    return service.read_relationships(store)


@router.put("/relationships", summary="Write every relationship in the cast")
def write_relationships(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    record: RelationshipsFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/relationships` (canoniser).

    The whole file at once, because an edge belongs to neither end of itself and there is no
    per-character slice of it to write.
    """
    return service.save_relationships(store, record, role=role, actor=actor)


@router.get("/{id}", summary="Read a character's dossier")
def read_character(store: StoreDep, character: CharacterId) -> Character:
    """IF-03, `GET /cast/{id}`. The complete record.

    `GET /cast/{id}/dossier?at=` below is the same record trimmed to an instant (FR-OPS-01),
    and this one is its unsafe sibling: a writer handed the complete dossier uses facts the
    character has not yet learned, because nothing in the text marks them as future. The
    record reads as true, and everything true in the context is fair to write. This route is
    for a human reading their own tree, never for an assembled context.
    """
    return service.read_character(store, character)


StoryInstant = Annotated[
    int,
    Query(
        description=(
            "The story instant to trim to: integer hours since `epoch_zero` (Decision 8), "
            "negative for prequel scenes. Required, because there is no safe default: "
            "'now' on the story axis is whatever the scene being written says it is."
        ),
    ),
]
"""The `at` of FR-OPS-01. A story time, never a scene id: the caller (the assembler, at plan
step 12) already holds the scene's `story_time`, and the operation is defined on it."""


@router.get("/{id}/dossier", summary="Read a character as of a story instant")
def read_dossier_at(
    store: StoreDep,
    character: CharacterId,
    at: StoryInstant,
) -> TrimmedDossier:
    """FR-OPS-01, IF-03 `GET /cast/{id}/dossier?at=`. The character as they were at `at`.

    Only the facts already acquired, the valence of each relationship on that date, the point
    on the arc, and the body with every registered change up to then applied (AC 10). The
    load-bearing call of assembly: withholding a future fact is more reliable than
    instructing the model to ignore it.
    """
    return service.dossier(store, character, at)


@router.get("/{id}/voice", summary="Read a character's voice profile")
def read_voice(store: StoreDep, character: CharacterId) -> VoiceProfile:
    """IF-03, `GET /cast/{id}/voice`. Kept out of the dossier because it is read at a
    different moment, by a different role, and `never_says` is the only part of a voice a
    check can run over (FR-AUD-07, invariant 9)."""
    return service.read_voice(store, character)


@router.get("/{id}/knowledge", summary="Read what a character knows")
def read_knowledge(store: StoreDep, character: CharacterId) -> KnowledgeFile:
    """IF-03, `GET /cast/{id}/knowledge`. Every recorded state, each anchored to the scene it
    was acquired in; deciding which of them a given scene may see is FR-OPS-01's job."""
    return service.read_knowledge(store, character)


@router.get("/{id}/changes", summary="Read a character's registered changes")
def read_changes(store: StoreDep, character: CharacterId) -> ChangesFile:
    """IF-03, `GET /cast/{id}/changes`. The register that tells a scar in chapter nine apart
    from a continuity error (invariant 3)."""
    return service.read_changes(store, character)


@router.put("/{id}/dossier", summary="Write a character's dossier")
def write_dossier(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    character: CharacterId,
    record: Character,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/dossier` (canoniser)."""
    return service.save_dossier(store, character, record, role=role, actor=actor)


@router.put("/{id}/voice", summary="Write a character's voice profile")
def write_voice(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    character: CharacterId,
    record: VoiceProfile,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/voice` (canoniser)."""
    return service.save_voice(store, character, record, role=role, actor=actor)


@router.put("/{id}/knowledge", summary="Write what a character knows")
def write_knowledge(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    character: CharacterId,
    record: KnowledgeFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/knowledge` (canoniser).

    The whole file, not a row: a character holds successive states on the same fact --
    `suspects` at 012, `knows` at 031 -- and an append-one-row route would invite the caller
    to drop the earlier state, which is the history FR-OPS-01 reads as-of.
    """
    return service.save_knowledge(store, character, record, role=role, actor=actor)


@router.put("/{id}/changes", summary="Write a character's registered changes")
def write_changes(
    store: StoreDep,
    role: RoleDep,
    actor: ActorDep,
    character: CharacterId,
    record: ChangesFile,
) -> ProvenanceRecord:
    """IF-04, `PUT /cast/{id}/changes` (canoniser)."""
    return service.save_changes(store, character, record, role=role, actor=actor)


__all__ = ["router"]
