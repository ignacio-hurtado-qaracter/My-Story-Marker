"""DR-01, DR-02. The two Markdown records of a character: `cast/{id}/dossier.md` and
`cast/{id}/voice.md`.

They are owned by one feature, so DR-01 keeps them here rather than in `commons/schemas/`.
The other two per-character files are not: `knowledge.yaml` (DR-04) and `changes.yaml`
(DR-08) are read by the auditor and written by the canoniser as well, and
`cast/relationships.yaml` is read by half the system, so all three live in
`commons/schemas/`. This module imports from `app.commons.schemas` and no feature at all.

`TrimmedDossier` is the odd one out: it is not a file. It is what FR-OPS-01's
`dossier(character, at)` answers, assembled from the four files above and never written
anywhere, which is why it is a `HarnessModel` with no `schema_version` rather than a
`StoreDocument`.

Dossier and voice are two files rather than one for a reason that is about when they are
read, not about size: the dossier is assembled into the context of every scene this
character is in, while the voice is consulted when dialogue is written and when style is
audited. Merging them would put the dialogue samples into every context that needs only the
arc, and would make the style editor read a record it has no business reading.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas import DatedValence, KnowledgeState
from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    SceneId,
    StoreDocument,
    StoryHours,
)


class ArcEntry(HarnessModel):
    """One state of a character, anchored to the scene it holds from.

    **Failure mode** (`definitions.md` Character): an arc written as a prose summary. A
    paragraph of development cannot answer "where is she at chapter 19?", and that is the
    only question the assembler ever asks of an arc: FR-OPS-01 takes the entry anchored to
    the latest scene with `story_time <= at` and nothing later. A summary has no such entry
    to take, so either the whole arc goes into the context - telling the writer how the
    character will end before she has got there - or none of it does.
    """

    scene: SceneId = Field(
        description="The scene this state holds from; the anchor FR-OPS-01 orders the arc by.",
    )
    state: str = Field(
        min_length=1,
        description="Where the character is at that point: what she now believes, wants or"
        " admits that she did not before.",
    )


class Character(StoreDocument):
    """DR-01, DR-02, DR-10. The whole of `cast/{id}/dossier.md`: identity, body, architecture.

    The *wants / needs / lies* triple is not psychological decoration. `needs` usually
    contradicts `wants` - the conscious goal is the wrong one - and that contradiction is
    what decides which way the character goes at each fork, which is precisely what the
    writer has to resolve on the page. `lies` is the false belief about the self that keeps
    the contradiction alive; the arc is the record of it giving way.

    `immutable_physical` is the anchor of invariant 3: these attributes do not change without
    a registered ChangeEvent in `cast/{id}/changes.yaml`. FR-AGENT-06 checks the prose
    against this map, and finds a violation when a physical attribute in the draft differs
    from the value here with no ChangeEvent at or before the scene. Without the register, a
    scar that appears in chapter nine and a continuity error look identical on the page.

    **A dossier is never loaded whole.** FR-OPS-01 trims it to the instant of the scene: the
    arc entry anchored at or before `story_time`, the knowledge rows acquired by then, the
    latest valence of each relationship dated by then. The trim is not an optimisation. A
    writer handed the complete record will use facts the character has not yet learned,
    because nothing in the text marks them as future - the record reads as true, and
    everything true in the context is fair to write.
    """

    id: EntityId = Field(
        description="Stable identifier; it names the `cast/{id}/` directory and keys the index"
        " row. The backend never renames (DR-08): renaming breaks every edge pointing here.",
    )
    name: str = Field(
        min_length=1,
        description="What the character is called in the prose.",
    )
    immutable_physical: dict[str, str] = Field(
        default_factory=dict,
        description="Attributes that do not change without a registered ChangeEvent (invariant"
        " 3). A map because FR-AGENT-06 compares the prose against it key by key, and a"
        " ChangeEvent names the key it changed.",
    )
    wants: str = Field(
        min_length=1,
        description="The conscious goal pursued in scenes: what the character would say she"
        " is doing.",
    )
    needs: str = Field(
        min_length=1,
        description="What is actually missing. Usually contradicts `wants`, and that"
        " contradiction is what decides the choice at each fork.",
    )
    lies: str = Field(
        description="The false belief about the self that sustains the arc, and that the arc"
        " is the record of losing.",
    )
    arc: list[ArcEntry] = Field(
        default_factory=list,
        description="Successive states, each anchored to a scene. Ordered by the story axis at"
        " read time, never assumed sorted on disk.",
    )
    competences: list[str] = Field(
        default_factory=list,
        description="What the character can do. This bounds what she can solve: a problem"
        " outside this list has to be solved by somebody else or not at all.",
    )
    body: str = Field(
        description="The Markdown body: the character at the length a writer needs, for"
        " everything the structured fields above cannot carry.",
    )


class VoiceProfile(StoreDocument):
    """DR-01, DR-02, DR-10. The whole of `cast/{id}/voice.md`: how this person sounds.

    Kept out of the dossier because it is consulted at a different moment - when dialogue is
    written, and when style is audited - and by a different role: the style editor reads
    `cast/{id}/voice.md` and never the dossier.

    A voice is defined mostly **by negation**, and `never_says` is the most useful field in
    the whole record, because it is the only part of voice a machine can check. FR-AUD-07
    searches the POV's `never_says` in the draft and reports invariant 9 as `reviewable`
    (Decision 13) - the POV only, because that is the character whose interiority and speech
    the scene is actually written in.

    **Failure mode** (`definitions.md` VoiceProfile): describing a voice with adjectives -
    "ironic, dry" - instead of samples. Adjectives are not imitable: two models, or the same
    model twice, will read "dry" differently, and neither reading can be compared with the
    other. `sample` is imitable, which is why it carries most of the weight here.
    """

    id: EntityId = Field(
        description="The character this voice belongs to; the same id as the dossier.",
    )
    own_lexicon: list[str] = Field(
        default_factory=list,
        description="Words only this person uses. The positive half of the profile, and the"
        " weaker half: it suggests rather than constrains.",
    )
    syntax: str = Field(
        description="Long or clipped, subordinated or flat, with or without ellipsis: the shape"
        " of the sentences, not their content.",
    )
    never_says: list[str] = Field(
        default_factory=list,
        description="Words and turns of phrase this character never uses. The most useful field"
        " in the record, and the only one a check can run over: FR-AUD-07 searches it in the"
        " draft for the POV (invariant 9, `reviewable`, Decision 13).",
    )
    under_pressure: str = Field(
        description="How the voice degrades when control is lost. Stated in advance, because"
        " under pressure is exactly where an improvised voice reverts to the model's own.",
    )
    sample: str = Field(
        description="Canonical lines of dialogue to imitate directly - six or so, per"
        " `definitions.md`. This is what replaces adjectives.",
    )
    body: str = Field(
        description="The Markdown body: anything about the voice that the fields above cannot"
        " hold, including longer passages of speech in context.",
    )


class RelationshipAsOf(HarnessModel):
    """FR-OPS-01. One outgoing edge of the character, read at the instant of the dossier.

    `valence` is a single reading, not the series: the latest one whose scene has
    `story_time <= at`. Handing the writer the series would hand it the later readings too,
    and a valence of -3 dated after the scene tells the writer how the pair ends up - which
    is the future fact the trim exists to withhold, in its most tempting form.

    `shared_history` and `unspoken` carry no date, and `Relationship` in
    `commons.schemas.relationship` already rules that they are read as standing context. They
    travel only on an edge that has a reading at or before `at`: an edge whose first reading
    is later is a relationship that has not started yet, and its history would be the first
    thing to leak.
    """

    to: EntityId = Field(
        description="The character the feeling is directed at; the edge is never symmetric.",
    )
    valence: DatedValence = Field(
        description="The latest reading dated at or before `at`, on the story axis.",
    )
    shared_history: str = Field(
        description="Events both remember, possibly differently; standing context, undated.",
    )
    unspoken: str = Field(
        description="What is between them and never gets said; standing context, undated.",
    )


class TrimmedDossier(HarnessModel):
    """FR-OPS-01, AC 10. The character as they were at story hour `at`, and nothing later.

    `docs/architecture.md` Operations: "Returns the character as they were at that instant:
    only the facts already acquired, the valence of their relationships on that date, and the
    corresponding point on their arc." It is the load-bearing call of assembly
    (FR-OPS-03): a writer handed the complete record uses facts the character has not yet
    learned, because nothing in the text marks them as future.

    **What is left out, and why.** The Markdown `body` of `dossier.md` is not here. It is
    undated prose, and a dossier body is exactly where an author writes "until scene 004,
    where for the first time she does not" - the fixture's own dossiers do. A field that
    cannot be shown to hold at or before `at` is not included, which is the same rule that
    excludes a knowledge row whose scene does not exist. `voice.md` is not here either: it is
    read at a different moment, by a different role (see `VoiceProfile`).

    **`immutable_physical` is the as-of body**, not the stored map: registered ChangeEvents
    dated at or before `at` are applied, because `definitions.md` ChangeEvent says "before it,
    the old value holds" - and therefore after it, the new one does.
    """

    id: EntityId = Field(description="The character; the same id as `cast/{id}/`.")
    name: str = Field(description="What the character is called in the prose.")
    at: StoryHours = Field(
        description="The instant this dossier describes: integer hours since `epoch_zero`.",
    )
    immutable_physical: dict[str, str] = Field(
        description="The body at `at`: the stored map with every ChangeEvent dated at or before"
        " `at` applied. An attribute whose change cannot be placed in time is withheld.",
    )
    wants: str = Field(description="The conscious goal pursued in scenes.")
    needs: str = Field(description="What is actually missing; usually contradicts `wants`.")
    lies: str = Field(description="The false belief about the self that sustains the arc.")
    competences: list[str] = Field(description="What the character can do.")
    arc: ArcEntry | None = Field(
        description="The arc entry anchored to the latest scene with `story_time <= at`, or"
        " null when `at` precedes every anchor. One entry, never the arc: the rest of it is"
        " either past (superseded) or future (withheld).",
    )
    knowledge: list[KnowledgeState] = Field(
        description="The rows whose `acquired_in` scene has `story_time <= at` and that no"
        " registered forgetting at or before `at` has erased, ordered on the story axis; the"
        " last row for a `fact_ref` is the state in force.",
    )
    relationships: list[RelationshipAsOf] = Field(
        description="Each edge from this character that has a reading at or before `at`,"
        " with that latest reading; sorted by `to`.",
    )


__all__ = [
    "ArcEntry",
    "Character",
    "RelationshipAsOf",
    "TrimmedDossier",
    "VoiceProfile",
]
