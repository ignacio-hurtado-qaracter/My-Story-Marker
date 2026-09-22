"""DR-08. Directed edges between characters, with valence that moves over time.

`cast/relationships.yaml` is the file this module types - one file for the whole cast, not
one per character, because an edge belongs to neither end of itself. It is a document with
a named key rather than a bare YAML list, because DR-10 puts `schema_version` on the file.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.commons.schemas.common import EntityId, HarnessModel, SceneId, StoreDocument, Valence


class DatedValence(HarnessModel):
    """DR-08. One reading of an edge, anchored to the scene that produced it.

    The anchor is a scene rather than a story time for the same reason `KnowledgeState`
    anchors to one: scenes are re-dated on the story axis during planning, and a valence
    that carried its own timestamp would quietly stop agreeing with the scene it came from.
    """

    scene: SceneId = Field(description="The scene from which this reading holds.")
    value: Valence = Field(description="Where the edge stands after that scene: -3 to +3.")


class Relationship(HarnessModel):
    """DR-08. What one character feels towards another, and how that has moved.

    **Directed on purpose.** A can trust B while B despises A, and that asymmetry is not an
    inconvenience to be averaged away - it is dramatic material, and often the engine of a
    whole subplot. A symmetric edge would make the two indistinguishable. Two rows are
    written when the feeling runs both ways, and they are free to disagree.

    **Failure mode: a single valence value instead of a dated series.** A scalar answers
    "do they get on?" and nothing else. It cannot answer "where were they at chapter
    nineteen?", so there is no queryable evolution, and relationships flatten into fixed
    dispositions - which is precisely what a novel is not about. The dated list is what
    makes a betrayal legible as a movement rather than an inconsistency.

    **FR-OPS-01.** `dossier(character, at=T)` takes the latest entry in `valence` whose
    scene has `story_time <= T`, and nothing later appears. `shared_history` and `unspoken`
    are not dated, so they are read as standing context: `unspoken` in particular is what
    the pair never say to each other, which by construction has no scene to be dated from.
    """

    # `from` and `to` are the names `definitions.md` gives and the keys on disk. `from` is a
    # Python keyword, so the attributes are named for what they hold - a character at each
    # end - and the wire names are restored by alias, with `populate_by_name` so code can
    # construct by field name.
    model_config = ConfigDict(populate_by_name=True)

    from_character: EntityId = Field(
        alias="from",
        description="The character whose feeling this row records.",
    )
    to_character: EntityId = Field(
        alias="to",
        description="The character it is directed at; never symmetric by default.",
    )
    valence: list[DatedValence] = Field(
        default_factory=list,
        description="Dated series, -3 to +3 per scene; empty means nothing has been recorded yet.",
    )
    shared_history: str = Field(
        default="",
        description="Events both remember, possibly differently.",
    )
    unspoken: str = Field(
        default="",
        description="What is between them and never gets said.",
    )


class RelationshipsFile(StoreDocument):
    """DR-08, DR-10. The whole of `cast/relationships.yaml`.

    One file for every edge in the cast. It is not split per character because each edge
    would then have two homes and one of them would fall behind.
    """

    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Every directed edge in the cast; both directions of a pair are separate"
        " rows and may disagree.",
    )


__all__ = [
    "DatedValence",
    "Relationship",
    "RelationshipsFile",
]
