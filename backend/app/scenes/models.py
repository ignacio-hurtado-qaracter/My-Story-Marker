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

`Selection` and `AssembledContext` are the two models here that are not store records: they
are what `POST /scenes/{id}/select` and `POST /scenes/{id}/assemble` answer (IF-05). They
are shaped by opposite rules. A selection is identifiers, kinds and scores, **never text**
(FR-OPS-02); its entries are `commons.schemas`' `SelectedEntity`, the model the turn record
persists (FR-OPS-05), so what the route answers and what a turn records cannot drift into two
shapes. An assembled context is **the text**, loaded as of the scene's instant (FR-OPS-03),
and every entry of it says which store paths it was read from, so the orchestrator can hold
each one against the writer's row of Figure 3's `In` column (FR-AGENT-09).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from app.commons.db import IndexReport
from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    SceneId,
    StoreDocument,
    StoryHours,
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


# --------------------------------------------------------------------------------------
# FR-OPS-03 -- the assembled context
# --------------------------------------------------------------------------------------


class ContextPart(StrEnum):
    """Which of Figure 2's blocks an entry belongs to, in the order they are loaded.

    `role_input` and the three after it are the mandatory part of the writer's input
    (FR-CTX-03): what the calling role adds, the fixed block, the POV's as-of dossier and the
    previous scene's tail. The last three are the prunable part, removed whole from the end
    when the estimate would cross the cap.
    """

    ROLE_INPUT = "role_input"
    """A document the calling role adds to its own mandatory part, placed first: the scene
    record for `write`, the draft and the blocking violations for `revise` (FR-CTX-03). The
    text is the caller's, verbatim, with no label in front of it -- a violation's offset
    counts characters of the draft, and a heading would move every one of them. The route
    never adds one."""
    FIXED = "fixed"
    POV = "pov"
    LITERAL_TAIL = "literal_tail"
    LEXICON = "lexicon"
    """Terms bound to the POV through `used_by`. The POV outranks every selected entity --
    it is loaded unconditionally -- so what it binds heads the prunable part."""
    SELECTED = "selected"
    SETUP = "setup"


class TailState(StrEnum):
    """What happened to the previous scene's `literal_tail` (FR-OPS-03, DR-11).

    Stated on the result rather than left to be inferred from a missing entry: a context
    without a tail because the previous scene has no draft yet and one without a tail because
    the scene opens the book are different situations, and neither is repaired by inventing
    a passage.
    """

    LOADED = "loaded"
    NO_DRAFT = "no_draft"
    NO_PREVIOUS_SCENE = "no_previous_scene"


class AssemblyWarning(StrEnum):
    """FR-OPS-04. A warning is carried on the response, never raised: the call still runs."""

    FIXED_BLOCK_OVER_BUDGET = "fixed_block_over_budget"


class ContextEntry(BaseModel):
    """One indivisible document of the writer's context: kept whole or removed whole.

    `text` is exactly what the writer receives, label first, and `tokens` is FR-CTX-02's
    estimate of it. `path` is the store path the entry is read from and labels the document
    in the prompt; `sources` is every store path whose content the text carries, `path`
    first. They differ only for an entry that folds several records into one: a dossier (the
    four cast files), a location with its parent chain, an entity with the terms bound to it.
    """

    key: str = Field(
        description="Unique within the context. `kind:id` for an entity (`axiom:ax_brine_dark`,"
        " `character:vance`, `setup:su_readkey`), the store path for the fixed block and the"
        " tail. The names in `removed` and `truncated_at` are these keys.",
    )
    part: ContextPart = Field(description="The block of Figure 2 the entry belongs to.")
    label: str = Field(
        description="The heading the writer reads above the record: what it is, as of when,"
        " and for a digest or a setup how it may be used (not witnessed; may collect).",
    )
    path: str = Field(description="The store path the entry is read from.")
    sources: list[str] = Field(
        description="Every store path whose content the text carries, `path` first. Each is"
        " checked against the writer's `INPUT_TABLE` row before the call (FR-AGENT-09).",
    )
    carries: list[str] = Field(
        description="The entities the text loads, as `kind:id`: the entry's own, then the"
        " parent chain or the bound terms folded into it. Empty for the fixed block and the"
        " tail, which are not entities.",
    )
    mandatory: bool = Field(
        description="True for the role's own inputs, the fixed block, the POV dossier and the"
        " tail (FR-CTX-03)."
        " Pruning never removes a mandatory entry; if they alone do not fit the call is"
        " refused with `ContextBudgetExceeded` (FR-CTX-05).",
    )
    text: str = Field(description="What the writer receives: the label, then the record.")
    tokens: int = Field(ge=0, description="FR-CTX-02's estimate of `text`.")


class WithheldEntity(BaseModel):
    """A selected entity that its as-of form keeps out of this scene's context.

    Not a pruning removal: the budget had nothing to do with it. A chapter digest covering a
    scene later than the scene's instant, a historical event dated after it, a location
    parent that has no record -- each is named with the reason, so the absence is visible
    rather than silent.
    """

    key: str = Field(description="The entity, as `kind:id`.")
    reason: str = Field(description="Why its as-of form does not load at this instant.")


class AssembledContext(BaseModel):
    """FR-OPS-03, IF-05. The writer's documents for one scene, as of the scene's instant.

    `entries` is in loading order: the fixed block, the POV's dossier, the previous scene's
    tail, then the prunable part -- terms bound to the POV, the selected entities in ranking
    order, the open setups. What did not fit is named in `removed`, first entry removed in
    `truncated_at`; nothing is ever cut inside an entry. `estimate` counts the caller's
    system prompt and instruction too, because the cap is over the whole call (FR-CTX-01).
    """

    scene: SceneId = Field(description="The scene assembled for.")
    pov: EntityId = Field(description="Its POV, loaded unconditionally as its as-of dossier.")
    story_time: StoryHours = Field(
        description="T, the instant every as-of form is read at: the scene's `story_time`.",
    )
    previous_scene: SceneId | None = Field(
        description="The scene before this one in discourse order, or null for the first.",
    )
    literal_tail: TailState = Field(
        description="Whether the previous scene's tail was loaded, and if not why not.",
    )
    selected: list[SelectedEntity] = Field(
        description="The selected list the context was assembled from, as received. The turn"
        " record persists this list and the auditor reads it back (FR-OPS-05).",
    )
    entries: list[ContextEntry] = Field(description="What the writer receives, in order.")
    removed: list[str] = Field(
        description="Keys of the prunable entries that did not fit, in rank order: the entry"
        " named in `truncated_at` and every one ranked after it (FR-CTX-03).",
    )
    truncated_at: str | None = Field(
        description="The first prunable entry that would have crossed the cap, or null when"
        " everything fit.",
    )
    withheld: list[WithheldEntity] = Field(
        description="Selected entities whose as-of form excludes them at this instant.",
    )
    estimate: int = Field(
        ge=0,
        description="FR-CTX-02's estimate of the call: system prompt, every kept entry and"
        " instruction. Never the CLI's own overhead (R3-5).",
    )
    cap: int = Field(ge=0, description="The cap the context was fitted to.")
    fixed_block_tokens: int = Field(
        ge=0,
        description="The estimate of the fixed block alone, against FR-OPS-04's 800.",
    )
    warnings: list[AssemblyWarning] = Field(
        description="`fixed_block_over_budget` when the fixed block exceeds 800 tokens"
        " (FR-OPS-04); the context is still assembled.",
    )


__all__ = [
    "Arc",
    "ArcsFile",
    "AssembledContext",
    "AssemblyWarning",
    "Chapter",
    "ChaptersFile",
    "ContextEntry",
    "ContextPart",
    "Selection",
    "StructureNode",
    "TailState",
    "Tension",
    "WithheldEntity",
]
