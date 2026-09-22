"""DR-11. The draft record: `manuscript/NNN.md`.

A Markdown-with-frontmatter file (DR-02), so the model declares both halves: the typed
frontmatter fields and the prose as `body`. Splitting the file and joining it again is the
store layer's job; the model only says what the two halves contain.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import SceneId, StoreDocument, Words


class Draft(StoreDocument):
    """DR-11. The whole of `manuscript/NNN.md`: the prose of one scene, subordinate to canon.

    `words` and `literal_tail` are **derived by code on write and never supplied by a
    model** (FR-AGENT-03). A word count a writer reports about its own output is a claim,
    not a measurement; accepting it would make the budget line of the turn record a check
    on the model's arithmetic rather than on the draft. The same reasoning applies to the
    tail: it must be exactly what the file ends with, not what the model believes it wrote.

    `literal_tail` is the last 500 words, verbatim, and it is the only prose that reaches
    the next scene at all - everything else arrives compressed, as a digest. It exists for
    tonal inertia: a summary preserves what happened and loses how it sounded, so without
    the tail the next scene restarts in the model's default voice instead of continuing in
    the register the book has been building. Because it is verbatim, it is also the one
    place where an earlier scene's exact words can contradict a later record, which is why
    it is carried as a field rather than reconstructed on demand.

    **Failure mode** (`architecture.md` Draft): letting the writer edit canon to justify
    what it has just written. That is the precise mechanism by which drift begins, and it
    is why the writer's Figure 3 row grants `manuscript/` and nothing under `canon/`: an
    invention goes to `ledger/proposed.yaml` as a proposal, and the canoniser decides.

    The `version` column of the `architecture.md` table is not a field here. Versions are
    git history, and DR-11 lists four fields; the backend never writes a version number
    into the record it would then have to keep true.
    """

    scene_ref: SceneId = Field(
        description="The one scene this draft is of. One scene, one file.",
    )
    words: Words = Field(
        description=(
            "Word count of `body`, measured by the store layer on write and checked "
            "against the scene `budget`. Never taken from model output."
        ),
    )
    literal_tail: str = Field(
        description=(
            "The last 500 words of `body`, verbatim, derived on write. The only prose "
            "that reaches the next scene, and the carrier of tonal inertia."
        ),
    )
    body: str = Field(description="The prose of the scene: the Markdown body of the file.")


__all__ = ["Draft"]
