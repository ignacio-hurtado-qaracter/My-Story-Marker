"""DR-11. The digest record: `manuscript/digests/NNN.md`.

Digests are the ladder that keeps the cost of assembling scene 200 close to that of scene
20: scene digests roll up into chapter digests and chapter digests into arc digests, and
apart from the previous scene's `literal_tail` they are the only form in which past prose
reaches a later scene.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import DigestLevel, EntityId, StoreDocument, Words


class SceneDigest(StoreDocument):
    """DR-11. The whole of `manuscript/digests/NNN.md`: what one scene, chapter or arc changed.

    `povs` is not a credit list, it is the filter, and it is the reason this record can be
    put in front of a writer at all. FR-OPS-03 labels a digest whose `povs` does not
    include the scene's POV as events the POV did not witness, so the field decides whether
    what it says arrives as something the POV knows or as something that merely happened.
    A name wrongly present in `povs` hands the POV knowledge nobody gave them, which is
    invariant 1 broken by bookkeeping rather than by the prose; a name wrongly absent loses
    a thread the POV lived through. The assembler has nothing else to go on: it never reads
    the prose the digest was made from.

    `level` decides how the digest travels. Only **chapter** level is indexed for retrieval
    (FR-IDX-02); scene- and arc-level digests exist and are read by reference, but they are
    not rows in the entity index, so a scene digest is never selected into a context by
    ranking. A chapter digest is loaded only when every scene it covers is at or before the
    story time being assembled, which is why `scene_ref` must state the whole range covered
    and not merely where the digest starts.

    **Failure mode** (`architecture.md` SceneDigest): treating the digest as canon. A digest
    records what the prose *said*; whether that becomes true of the world is decided by
    `promote`, not by summarisation. It is derived, regenerable and never authoritative.
    """

    scene_ref: str = Field(
        min_length=1,
        description=(
            "The scene this summarises, as a `NNN` scene id; at chapter and arc level, the "
            "range of scenes covered. Not a `SceneId`, because a range is not one scene."
        ),
    )
    level: DigestLevel = Field(
        description="`scene`, `chapter` or `arc`. Only `chapter` is indexed (FR-IDX-02).",
    )
    povs: list[EntityId] = Field(
        description=(
            "Whose scenes are covered. FR-OPS-03 filters by it: a digest that does not "
            "name the assembling scene's POV is labelled as events the POV did not witness."
        ),
    )
    delta: str = Field(
        description=(
            "What changed in the world, who learned what, which setups were paid. The "
            "compressed content itself, not a pointer to it."
        ),
    )
    words: Words = Field(
        description=(
            "Length of `delta`, derived on write: roughly 100 at scene level, 250 at "
            "chapter, 400 at arc. The turn records it against its level target."
        ),
    )


__all__ = ["SceneDigest"]
