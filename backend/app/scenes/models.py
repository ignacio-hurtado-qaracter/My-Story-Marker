"""DR-01, DR-10. The narrative containers of `structure/`: `arcs.yaml` and `chapters.yaml`.

These are the nested containers of `definitions.md` Layer 3, and they contain no prose at
all. They contribute exactly three things - word budget, dramatic function, and position on
the tension curve - and everything else about a chapter is in the scenes it lists.

**Failure mode** (`definitions.md` Arc/Act/Sequence/Chapter): not budgeting. Act two eats
eighty per cent of the book and the climax arrives compressed, and by the time that is
visible it is visible as a finished manuscript. A budget per container is what makes the
pacing a decision taken in advance rather than an outcome discovered afterwards, and the
turn records each draft's word count against the scene's share of it.

Unlike the rest of this feature's records these are **YAML** files, not
Markdown-with-frontmatter, because there is no prose half to hold: a container with a body
would be a container with an opinion, and the opinions belong in `canon/` and in the scene
records. Each file is a document with a named key rather than a bare list, because DR-10
puts `schema_version` on the file and a top-level list has nowhere to carry one.

The scene record itself is in `commons/schemas/scene.py`: every feature in the system reads
it, so DR-01 makes it shared. The models here are read by this feature and the architect,
and import no other feature.

`Selection` is the one model here that is not a store record: it is what
`POST /scenes/{id}/select` answers (IF-05). A selection is identifiers, kinds and scores,
**never text** (FR-OPS-02); its entries are `commons.schemas`' `SelectedEntity`, the model the
turn record persists (FR-OPS-05), so what the route answers and what a turn records cannot
drift into two shapes.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from app.commons.db import IndexReport
from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    SceneId,
    StoreDocument,
    Words,
)
from app.commons.schemas.turn import SelectedEntity

Tension = Annotated[int, Field(strict=True, ge=0, le=10)]
"""`definitions.md` Layer 3: the tension curve is 0-10, on entry and on exit.

Strict, like every other integer in a store record, so that a `true` in a YAML file is
rejected instead of being read as 1. `commons` has no 0-10 alias - `Invariant` is 1-10 and
means something else entirely - so the range is declared here, where it is the only thing
it could mean.
"""


class StructureNode(HarnessModel):
    """The fields every narrative container has, whatever level it sits at.

    One base rather than two near-identical models, because an arc and a chapter differ in
    what they contain and not in what they promise: both declare a function, a budget, an
    entry and exit tension, and the threads that advance inside them. A level that needed a
    different set of promises would not be a container in this sense.

    `target_tension_in` and `target_tension_out` are two numbers rather than one curve
    because the pair is what makes the shape checkable: a container whose tension enters and
    leaves at the same value has not moved, and one whose `in` does not meet the previous
    container's `out` is a discontinuity somebody chose or forgot.
    """

    id: EntityId = Field(
        description="Stable identifier; scenes and chapters point at it and the backend never"
        " renames (DR-08).",
    )
    function: str = Field(
        min_length=1,
        description="What must have changed by the end of it. The dramatic job of the container,"
        " stated as an outcome rather than as a summary of its contents.",
    )
    budget: Words = Field(
        description="Words assigned; this is what controls global pacing. The sum of the parts"
        " is what keeps act two from eating the book.",
    )
    target_tension_in: Tension = Field(
        description="Target tension on entry, 0-10.",
    )
    target_tension_out: Tension = Field(
        description="Target tension on exit, 0-10. Equal to `target_tension_in` means the"
        " container is designed to leave the reader exactly where it found them.",
    )
    active_threads: list[EntityId] = Field(
        default_factory=list,
        description="Plot lines that advance here. Thread ids from `ledger/threads.yaml`, so"
        " invariant 10 can ask how long it has been since one of them was touched.",
    )


class Arc(StructureNode):
    """One arc of `structure/arcs.yaml`: the largest container, and pure plan.

    It holds no list of its own members. A chapter names its `arc`, so the membership is
    recorded once, on the side that changes when a chapter moves - reordering the book then
    cannot leave an arc claiming a chapter that has left it.
    """


class Chapter(StructureNode):
    """One chapter of `structure/chapters.yaml`: the container the reader actually meets.

    `scenes` is in discourse order, because a chapter is a unit of reading: it is the order
    the reader receives, not the order the world happened in, and the two differ the moment
    the book contains a single flashback. The scene records carry `story_time` for the axis
    every invariant runs over.
    """

    scenes: list[SceneId] = Field(
        default_factory=list,
        description="The scenes of this chapter, in discourse order: the order the reader meets"
        " them, which is the axis tension is designed on.",
    )
    arc: EntityId = Field(
        description="The arc this chapter belongs to. Recorded here rather than as a list on the"
        " arc, so that moving a chapter is one edit and cannot leave a stale membership.",
    )


class ArcsFile(StoreDocument):
    """DR-10. The whole of `structure/arcs.yaml`.

    One file for the book's arcs: they are few, they are read together whenever the shape of
    the novel is in question, and a per-arc file would buy nothing but a directory walk.
    """

    arcs: list[Arc] = Field(
        default_factory=list,
        description="Every arc of the book. Empty is a legitimate state for a project whose"
        " structure has not been planned yet.",
    )


class ChaptersFile(StoreDocument):
    """DR-10. The whole of `structure/chapters.yaml`.

    Kept in one file with the same reasoning as the arcs, and with one of its own: the
    chapter list is what the discourse order of the book *is*, and a question about that
    order is a question about all of them at once.
    """

    chapters: list[Chapter] = Field(
        default_factory=list,
        description="Every chapter of the book, each naming its arc and its scenes in discourse"
        " order.",
    )


class Selection(BaseModel):
    """FR-OPS-02, IF-05. What `select_entities` answers for one scene: ids, kinds and scores.

    **No text field, by construction** (AC 11). What the writer receives is loaded by the
    store after selection, as of the scene's instant (FR-OPS-03); a selection that carried
    record text would be a second way into a context, one that could hand the writer a
    version of a record the scene's instant forbids. `test_select.py` pins the field set.

    `entities` is in the order assembly consumes it: the entities named in `pins`, in the
    order the record names them, then the axioms whose `scope` intersects `tags`, by id, then
    the fused ranking, best first. The POV is absent: it enters assembly by identifier,
    unconditionally, and never competes for a place in the ranking.
    """

    scene: SceneId = Field(description="The scene the selection was made for.")
    pov: EntityId = Field(
        description="The scene's POV, excluded from `entities` by identifier: assembly loads"
        " it unconditionally as `dossier(pov, at=story_time)` (FR-OPS-03).",
    )
    fused: bool = Field(
        description="True when BM25 and vector cosine were fused by reciprocal rank; false when"
        " the ranking is FTS5-only -- `sqlite-vec` unavailable (FR-IDX-03, AC 7) -- or the"
        " record has no text to embed.",
    )
    entities: list[SelectedEntity] = Field(
        description="Pinned entries first (`pinned: true`: `pins` in record order, then the"
        " tag-scope axioms by id), then the ranking, best first, ties by kind and then id. A"
        " pinned entry's `score` is its fused score when the ranking also found it, else 0.",
    )
    index_update: IndexReport = Field(
        description="What the FR-IDX-08 incremental update at the start of this selection"
        " did: a selection sees every store write made before it, whoever made it.",
    )


__all__ = [
    "Arc",
    "ArcsFile",
    "Chapter",
    "ChaptersFile",
    "Selection",
    "StructureNode",
    "Tension",
]
