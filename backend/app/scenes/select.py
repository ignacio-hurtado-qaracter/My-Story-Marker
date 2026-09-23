"""FR-OPS-02, `select_entities(scene)`: which entities of the world a scene needs, ranked.

`architecture.md` Operations: the scene record drives the selection, not the prose. The
query is the record's dramatic fields; the answer is identifiers, kinds and scores, **never
text** (AC 11). What the writer finally receives is loaded by the store after selection, as
of the scene's instant (FR-OPS-03), so retrieval can never hand it a version of a record the
scene's instant forbids. The row text stays inside `commons/db`.

Five decisions shape the function, in the order it runs.

* **The index is brought up to date first** (FR-IDX-08, clarified in `8cbee0f`). Every
  selection starts with the incremental update -- which rebuilds instead when FR-IDX-07 says
  it must -- so it sees every store write made before it, whoever made it, including the
  previous turn's promotions (FR-TURN-04). Write routes never load the embedder (FR-EMB-04);
  this is where the re-embedding they defer is paid, before any role call of a turn.
* **Two rankings, fused by reciprocal rank.** BM25 over FTS5 always; cosine over `vec0` when
  the index holds vectors (FR-IDX-03). Reciprocal rank fusion sums `1 / (k + rank)` over the
  lists, so only positions matter and the two scales -- a BM25 score is unbounded, a cosine
  is in [-1, 1] -- never have to be made comparable. Without vectors the fusion runs over one
  list and preserves the BM25 order exactly: FTS5-only selection is the same code (AC 7).
* **Pins first, then tag-scope axioms, then the ranking.** "A rule the scene *must* honour
  is never left to similarity" (`architecture.md` Figure 2). `pins` resolve through the
  index, in the order the record names them; `tags` pin every axiom whose `scope` they
  intersect, matched as `reconcile` matches them (trimmed, case-folded), so the scenes
  reconcile reports for an axiom include every scene whose selection pinned it (AC 14).
* **A pin naming no entity is refused, not skipped.** The pin is the architect saying this
  entity must be in the context; dropping it silently would leave the writer without it and
  the auditor checking invariant 6 against a list that lacks it, with nobody told. The
  refusal is `InvalidRecord` (422) naming `scenes/NNN.yaml` and the `pins.<n>` field,
  because the defect is in the scene record -- FR-STORE-06's shape -- and not a missing
  resource the caller asked for, which is what a 404 would claim.
* **The POV is excluded by identifier.** It enters assembly unconditionally as
  `dossier(pov, at=T)` (FR-OPS-03). Its id is in the query text, so its dossier would
  otherwise rank near the top of every selection and spend a place on something already
  loaded. A pin naming the POV is dropped for the same reason: redundant, not a defect.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from app.canon import service as canon_service
from app.canon.models import Axiom
from app.commons.config import Settings
from app.commons.db import (
    CANON_DIRECTORY_BY_KIND,
    IndexHit,
    IndexKind,
    kinds_of,
    search_text,
    search_vector,
    update,
)
from app.commons.embeddings import Embedder
from app.commons.errors import InvalidRecord
from app.commons.schemas import Scene, SelectedEntity
from app.commons.stores import Store
from app.scenes import repository
from app.scenes.models import Selection

RRF_K: Final[int] = 60
"""The reciprocal-rank-fusion constant: `score = sum(1 / (RRF_K + rank))`, rank from 1.

60 is the value of Cormack, Clarke and Buettcher (SIGIR 2009), who introduced the method and
found it close to the best across collections without tuning. It is also the right shape
here: large enough that first against second place in one list is a small difference
(1/61 against 1/62), so an entity both halves rank well beats one that a single half ranks
first -- agreement between lexical and semantic evidence is what fusion is for. Nothing
in the fixture is tuned to it: a constant fitted to six scenes would be fitted to the
fixture, not to a novel.
"""

DEFAULT_LIMIT: Final[int] = 100
"""How many ranked entries a selection returns beyond the pinned ones.

Selection does not enforce the budget; assembly does, loading in ranking order and stopping
before the 100k cap (FR-OPS-03). So the limit only has to be large enough that the cap,
not the candidate list, is what stops assembly: a hundred records at a few hundred to a
thousand tokens each is the order of the whole cap. Pins and tag-scope axioms do not count
against it, because they enter "regardless of ranking" (FR-OPS-02).
"""


def _folded(value: str) -> str:
    """How a tag meets a scope: trimmed and case-folded, exactly as `canon.service.reconcile`
    matches them, so an axiom selection pinned is an axiom whose reconcile finds the scene."""
    return value.strip().casefold()


def query_text(scene: Scene) -> str:
    """FR-OPS-02's query: `goal`, `conflict`, `value_change`, `pov`, `location`,
    `entry_state`, `exit_state` and `notes`, one per line, empty ones left out.

    `notes` is included because the architect writes there what the structured fields cannot
    hold (`architecture.md` Operations). `tags` and `pins` are not: they pin rather than rank,
    and a tag in the query would let a scope word pull in every record that merely mentions it.
    """
    fields = (
        scene.goal,
        scene.conflict,
        scene.value_change,
        scene.pov,
        scene.location,
        scene.entry_state,
        scene.exit_state,
        scene.notes,
    )
    return "\n".join(value.strip() for value in fields if value is not None and value.strip())


def fuse(*rankings: Sequence[IndexHit], k: int = RRF_K) -> list[IndexHit]:
    """Reciprocal rank fusion of best-first rankings into one, best first.

    Each hit adds `1 / (k + rank)` to the score of its `(kind, entity_id)`. **Ties are
    ordered by kind, then id** -- the tie order both searches already use -- so the same
    rankings always fuse to the same list, whatever order the inputs listed equal hits in.
    Exact ties are common, not a corner case: rank 3 in one list alone scores exactly what
    rank 3 in the other list alone scores.
    """
    scores: dict[tuple[str, str], float] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            key = (hit.kind, hit.entity_id)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [
        IndexHit(entity_id=entity_id, kind=kind, score=score)
        for (kind, entity_id), score in ordered
    ]


def _refuse_unresolved_pins(scene: Scene, kinds: Mapping[str, Sequence[str]]) -> None:
    """`InvalidRecord` when a pin has no kind in the freshly updated index.

    The index is the authority because it is exactly the set of selectable entities: canon
    entities, lexicon terms, characters and chapter digests (FR-IDX-02). A scene or arc digest
    id is therefore refused like a typo -- neither may ever enter a context by selection. An
    id carried by two kinds is two records answering to one name; both are pinned, because a
    pin is a rule the scene must honour and the record does not say which one was meant.
    Every unresolved pin is named in the message; `field` points at the first.
    """
    unresolved = [(position, pin) for position, pin in enumerate(scene.pins) if not kinds[pin]]
    if unresolved:
        path = repository.scene_path(scene.id)
        names = ", ".join(repr(pin) for _, pin in unresolved)
        message = (
            f"{path} pins {names}, which no canon entity, lexicon term, character or chapter "
            "digest carries; a pin must name an entity that exists (FR-OPS-02)"
        )
        raise InvalidRecord(message, file=path, field=f"pins.{unresolved[0][0]}")


def _scoped_axioms(store: Store, tags: Sequence[str]) -> list[str]:
    """Every axiom whose `scope` intersects `tags`, by id. Read through the canon service,
    whose model owns `scope` (NFR-04: scenes reaches canon only through service and models)."""
    wanted = {_folded(tag) for tag in tags if tag.strip()}
    if not wanted:
        return []
    directory = CANON_DIRECTORY_BY_KIND[IndexKind.AXIOM]
    return sorted(
        identifier
        for identifier in canon_service.list_kind(store, directory).ids
        if any(
            _folded(scope) in wanted
            for scope in canon_service.entity(store, directory, identifier, Axiom).scope
        )
    )


def select_entities(
    store: Store,
    embedder: Embedder,
    settings: Settings,
    scene_id: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> Selection:
    """FR-OPS-02, AC 11. The scene's selected entities: pins, tag-scope axioms, then ranking.

    Runs the FR-IDX-08 update before anything is ranked, embeds the query only when the
    index holds vectors, and returns ids, kinds and scores. The embedder is the caller's
    because it is a dependency: the offline suite passes `FakeEmbedder` (NFR-09). The index
    is located by `settings` (FR-IDX-01) and handed to `commons/db` untouched: features hold
    no filesystem types (NFR-04, the import contract), so this module never names a path.
    """
    if limit < 0:
        message = f"a selection limit cannot be negative, got {limit}"
        raise ValueError(message)
    index_path = settings.index_path
    scene = repository.read_scene(store, scene_id)
    report = update(store, embedder, index_path)

    pov = (IndexKind.CHARACTER.value, scene.pov)
    kinds = kinds_of(index_path, scene.pins)
    _refuse_unresolved_pins(scene, kinds)
    pinned: list[tuple[str, str]] = [(kind, pin) for pin in scene.pins for kind in kinds[pin]]
    pinned.extend((IndexKind.AXIOM.value, axiom) for axiom in _scoped_axioms(store, scene.tags))

    # Fetch enough that `limit` ranked entries survive removing the POV and the pinned ones.
    fetch = limit + 1 + len(pinned)
    query = query_text(scene)
    text_hits = search_text(index_path, query, limit=fetch)
    vector_hits: list[IndexHit] = []
    fused = report.vector == "available" and bool(query)
    if fused:
        [embedding] = embedder.embed([query])
        vector_hits = search_vector(
            index_path, embedding, embedding_model=embedder.model_name, limit=fetch
        )
    ranking = fuse(text_hits, vector_hits)
    scores = {(hit.kind, hit.entity_id): hit.score for hit in ranking}

    entities: list[SelectedEntity] = []
    seen: set[tuple[str, str]] = {pov}
    for key in pinned:
        if key in seen:
            continue
        seen.add(key)
        kind, entity_id = key
        entities.append(
            SelectedEntity(entity_id=entity_id, kind=kind, score=scores.get(key, 0.0), pinned=True)
        )
    ranked = 0
    for hit in ranking:
        if ranked >= limit:
            break
        key = (hit.kind, hit.entity_id)
        if key in seen:
            continue
        seen.add(key)
        entities.append(SelectedEntity(entity_id=hit.entity_id, kind=hit.kind, score=hit.score))
        ranked += 1

    return Selection(
        scene=scene.id, pov=scene.pov, fused=fused, entities=entities, index_update=report
    )


__all__ = ["DEFAULT_LIMIT", "RRF_K", "fuse", "query_text", "select_entities"]
