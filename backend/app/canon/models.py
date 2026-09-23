"""DR-01, DR-02. The canon records: Layer 0 (`canon/project.md`, `canon/style.md`) and the
Layer 1 world entities under `canon/axioms/`, `canon/technology/`, `canon/factions/`,
`canon/locations/` and `canon/history/`.

These models are owned by one feature, so DR-01 puts them here rather than in
`commons/schemas/`. They import their bases and enums from `app.commons.schemas.common` and
import no other feature: `canon` is what the rest of the system reads, never the reverse.

Every record here is a Markdown-with-frontmatter file (DR-02). The frontmatter is what can
be queried and checked; the body is what the writer is meant to feel. One model declares
both halves, and the store layer is what splits the file and joins it again - a model that
carried only the frontmatter would quietly make the prose half of canon invisible to
everything that validates it.

`canon/lexicon.yaml` and `canon/time.yaml` are not here. Both are read by the style editor
and the auditor as well as by this feature, so DR-01 puts them in `commons/schemas/`.

The last section holds the wire shapes of `POST /canon/reconcile` (FR-OPS-08). They are not
store records, but the orchestrator of plan step 18 records `reconcile`'s answer on the turn
record after every promotion, so the answer is part of this feature's public surface.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    SceneId,
    StoreDocument,
    StoryHours,
)

StyleMetric = Annotated[float, Field(strict=True)]
"""A target prose metric, strict for the same reason every integer in a store record is
(`commons/schemas/common.py`): pydantic's lax mode reads `true` as `1.0`, and a
`mean_sentence_length: true` that silently becomes a one-word target is exactly the quiet
nonsense strictness exists to catch. `commons` has no float alias - these two fields and
`TemporalSystem.dilation_factor` are the only floats in the stores - so it is declared here.
Strict still admits an integer literal, so `variance: 4` in a YAML file is read as `4.0`.
"""

# --------------------------------------------------------------------------------------
# Layer 0 - the project. Present in every call, without filtering.
# --------------------------------------------------------------------------------------


class Premise(HarnessModel):
    """The dramatic question of the book, as a value inside `canon/project.md`.

    It is not a summary. It is the test that decides whether a scene belongs to *this* novel
    rather than to some adjacent one, which is why `definitions.md` Premise asks for one
    sentence with protagonist, desire and obstacle and nothing else.

    **Failure mode** (`definitions.md` Premise): a three-paragraph premise. A filter that
    long stops discriminating - everything passes it - and the writer, handed a paragraph
    where it expected a test, ignores it.
    """

    statement: str = Field(
        min_length=1,
        description="One sentence with protagonist, desire and obstacle; no chained clauses.",
    )
    dramatic_question: str = Field(
        min_length=1,
        description="What the reader wants to know, phrased as the question the book answers.",
    )
    answer: str = Field(
        min_length=1,
        description="How it resolves. Decided before writing starts, not found in chapter thirty.",
    )


class ThematicThesis(HarnessModel):
    """What the novel argues, as a value inside `canon/project.md`.

    A thesis is arguable or it is nothing: it has to be the sort of claim a character can
    defend the opposite of and sometimes win with, because that disagreement is what orders
    scenes. `test_scenes` holds scene ids rather than prose so the claim is anchored to the
    plan and can be checked against it.

    **Failure mode** (`definitions.md` ThematicThesis): confusing thesis with theme.
    "Identity" is a subject, not a proposition - nobody can disagree with it, so it orders
    nothing and selects nothing.
    """

    proposition: str = Field(
        min_length=1,
        description="The arguable claim the book makes, stated so that one can disagree with it.",
    )
    antithesis: str = Field(
        min_length=1,
        description="Who defends the opposite, and how strongly; the counterargument must be able"
        " to win sometimes or the thesis is never really tested.",
    )
    test_scenes: list[SceneId] = Field(
        default_factory=list,
        description="Scenes where the thesis is put under real pressure. Scene ids, not prose, so"
        " the argument is anchored to the plan rather than asserted about it.",
    )


class GenrePromise(HarnessModel):
    """One promise made to the reader, with the scene intended to pay it.

    Kept as a pair rather than as a sentence because a promise with no named payoff is
    indistinguishable from an intention, and `definitions.md` GenreContract asks for each
    promise with its intended payoff scene.
    """

    promise: str = Field(
        min_length=1,
        description="What the reader is promised by the genre this book declares itself to be.",
    )
    payoff_scene: SceneId | None = Field(
        default=None,
        description="Where it is intended to be paid; `None` while the plan has not placed it.",
    )


class GenreContract(HarnessModel):
    """The explicit promises of the book, as a value inside `canon/project.md`.

    It fixes the level of scientific rigour, what the mystery owes the reader, how much of
    the violence or intimacy happens on the page, and what this novel will never do. Those
    are decisions, and writing them down is what makes a departure from them detectable.

    **Failure mode** (`definitions.md` GenreContract): leaving it undeclared. The prose
    drifts from thriller to space opera and nothing catches it, because with no contract
    there is no rule to break - the drift is not a violation of anything, only a surprise.
    """

    subgenre: str = Field(
        min_length=1,
        description="Hard SF, space opera, social SF - the shelf this book asks to be read on.",
    )
    rigour: str = Field(
        min_length=1,
        description="What may be hand-waved and what may not; the standard axioms are held to.",
    )
    promises: list[GenrePromise] = Field(
        default_factory=list,
        description="Each promise made to the reader, with its intended payoff scene.",
    )
    limits: str = Field(
        min_length=1,
        description="What this novel will never do. The half of the contract that forbids, and"
        " therefore the half that can be violated.",
    )


class Project(StoreDocument):
    """DR-01, DR-02, DR-10. The whole of `canon/project.md`: premise, thesis, genre contract.

    This is the **fixed block**. FR-OPS-03 loads it, with `canon/style.md`, at the head of
    every assembled context, unfiltered, for the length of the book - so it is the one record
    whose cost is paid on every single call. That is why FR-OPS-04 raises
    `fixed_block_over_budget` above 800 tokens, and the warning is about quality before it is
    about money: at three paragraphs the premise has stopped working as a filter, and a
    writer handed a paragraph where it expected a test ignores it.

    Three values rather than one flat sheet of fields, because the three answer different
    questions - what the book is about, what it argues, what it owes the reader - and a scene
    is judged against each of them separately.
    """

    premise: Premise = Field(
        description="The dramatic question; the test for whether a scene belongs to this novel.",
    )
    thesis: ThematicThesis = Field(
        description="What the novel argues, with the counterargument that is allowed to win.",
    )
    genre_contract: GenreContract = Field(
        description="The promises to the reader, their payoffs, and what this book never does.",
    )
    body: str = Field(
        description="The Markdown body of the file: what the structured fields cannot hold. It"
        " is part of the fixed block too, so it counts against the 800-token warning.",
    )


class StyleMetrics(HarnessModel):
    """Target prose metrics, as a value inside `canon/style.md`.

    Numbers rather than adjectives, because these are the only part of style a check can
    measure without a model. Both are optional: a project that has not decided a target is
    better represented by an absent number than by an invented one, which something would
    later report the prose as deviating from.
    """

    mean_sentence_length: StyleMetric | None = Field(
        default=None,
        description="Target mean sentence length in words; `None` when no target was set.",
    )
    variance: StyleMetric | None = Field(
        default=None,
        description="Target variance of sentence length. Uniform sentences read as machine prose,"
        " which is what a variance target exists to prevent; `None` when no target was set.",
    )


class StyleBible(StoreDocument):
    """DR-01, DR-02, DR-10. The whole of `canon/style.md`: the rules of the textual surface.

    The cheapest layer to maintain and the one that prevents the most drift, because readers
    notice a change of voice long before they notice a change of plot. It is the second half
    of the fixed block (FR-OPS-03), and the style editor and the auditor read it as well as
    the writer.

    **Failure mode** (`definitions.md` StyleBible): writing it abstractly. A rule such as
    "dense but not ornate" is not imitable; two or three paragraphs of canonical sample prose
    are, because the writer can copy the cadence directly instead of inferring it from an
    adjective. That sample is what `body` holds, and it is the reason this record is a
    Markdown file rather than a YAML one.

    `language` is here rather than in configuration because the prose language is a fact
    about this novel, not about this deployment. FR-LLM-10 and Decision R2-9 read it from
    this file: role prompts stay in English, and the writer and the style editor are told in
    their instruction which language to write the prose in.
    """

    # `register` is the field name `definitions.md` gives and the key the file carries on
    # disk, and it is also an attribute of the model base (`ABCMeta.register`), which pydantic
    # warns about shadowing. The attribute is named for what it holds and the wire name is
    # restored by alias, exactly as the keyword collisions elsewhere in the stores are.
    model_config = ConfigDict(populate_by_name=True)

    tense: str = Field(
        min_length=1,
        description="Past or present; never mixed without a stated cause.",
    )
    pov_policy: str = Field(
        min_length=1,
        description="Third limited, one POV per scene, no internal head-hopping - or whatever"
        " this book decided instead.",
    )
    prose_register: str = Field(
        alias="register",
        min_length=1,
        description="Lexical density, jargon tolerance, narrative distance.",
    )
    metrics: StyleMetrics = Field(
        default_factory=StyleMetrics,
        description="Target mean sentence length and variance: the measurable part of style.",
    )
    forbidden: list[str] = Field(
        default_factory=list,
        description="Tics, verbal crutches and images already spent in this book. These are"
        " stylistic rather than canonical, which is why they live here and not among the"
        " `forbidden_variants` of `canon/lexicon.yaml`.",
    )
    exposition_policy: str = Field(
        min_length=1,
        description="How much backstory per scene, and through which vehicle.",
    )
    language: str = Field(
        min_length=1,
        description="The language the prose is written in. Role prompts are English (FR-LLM-10,"
        " Decision R2-9); this is what the writer and the style editor are told to write in.",
    )
    body: str = Field(
        description="The canonical sample prose: the Markdown body of the file. It works far"
        " better than the abstract rules above, because the writer can imitate it directly.",
    )


# --------------------------------------------------------------------------------------
# Layer 1 - the world. Loaded by selection, or pinned through a scene's `tags`.
# --------------------------------------------------------------------------------------


class Axiom(StoreDocument):
    """DR-01, DR-02, DR-10. One rule of the universe: `canon/axioms/<id>.md`.

    In science fiction this is the highest-leverage record in the ontology, and invariant 6
    is stated over it: no scene violates an axiom selected for its context. "Selected" is
    exact - the axioms in force for a scene are the ones the turn recorded, whether pinned
    through the scene's `tags` or retrieved by `select_entities` - and `scope` is the set
    a scene's `tags` intersect to pin this one in.

    **Failure mode** (`definitions.md` Axiom), in two halves. An axiom with no declared
    `consequences` is the origin of most plot holes: the rule is stated once, nobody derives
    what it forbids, and three hundred pages later something impossible happens that no check
    can name. And an axiom that declares the capability while forgetting the limit drains the
    tension from every scene it touches, because a rule that only permits creates no
    obstacle. `consequences`, `exceptions` and `cost` are what make the rule cost something;
    `exceptions` is closed and enumerated, or they are not exceptions.
    """

    id: EntityId = Field(
        description="Stable identifier; the file is named after it and the index keys a row on it.",
    )
    statement: str = Field(
        min_length=1,
        description="The rule, phrased positively: what is the case in this universe.",
    )
    scope: list[str] = Field(
        default_factory=list,
        description="Domain tags. A scene whose `tags` intersect this list pins the axiom into"
        " context regardless of ranking (FR-OPS-02), which is how a rule reaches the scene"
        " that is about to break it.",
    )
    consequences: list[str] = Field(
        default_factory=list,
        description="What necessarily follows, and what becomes impossible. This is what the"
        " auditor reasons against for invariant 6; empty means the rule forbids nothing"
        " anybody can check.",
    )
    exceptions: list[str] = Field(
        default_factory=list,
        description="Closed and enumerated. An open-ended exception is not an exception, it is a"
        " way for the rule never to apply.",
    )
    cost: str = Field(
        description="What it costs to use this. Conflict comes from here: a capability with no"
        " price generates no scene.",
    )
    body: str = Field(
        description="The Markdown body: the rule explained at the length a writer needs.",
    )


class Technology(StoreDocument):
    """DR-01, DR-02, DR-10. One artifact or system: `canon/technology/<id>.md`.

    A technology derives from one or more axioms and inherits their restrictions, which is
    what `derives_from` records: not a citation, but the edge along which an axiom's
    `consequences` reach the machine, so that a rule pinned into a scene also constrains the
    devices used in it.

    `cannot` is the field that actually matters. `can` is easy to write and easy for a model
    to honour; the limits are what make a scene hard, and a technology with an empty `cannot`
    quietly solves every problem the plot has.

    **Failure mode** (`definitions.md` Technology): no `sensory` field. The writer improvises
    the texture each time and the ship sounds different in every chapter - a drift no
    invariant catches, because nothing about it is false, only inconsistent.
    """

    id: EntityId = Field(
        description="Stable identifier; the file is named after it and the index keys a row on it.",
    )
    derives_from: list[EntityId] = Field(
        default_factory=list,
        description="Axiom ids that license it; their restrictions are inherited here. An empty"
        " list is a machine that answers to no rule of the universe.",
    )
    can: str = Field(
        min_length=1,
        description="Capabilities, with magnitudes. A capability without a magnitude is not one.",
    )
    cannot: str = Field(
        min_length=1,
        description="The operating limits: the field that actually matters, because it is what"
        " keeps the technology from solving the plot.",
    )
    failure_mode: str = Field(
        description="How it breaks and what happens then; where most of its scenes come from.",
    )
    who_has_it: list[EntityId] = Field(
        default_factory=list,
        description="Factions and characters with access. Who does *not* have it is the other"
        " half of the same fact, and is read off this list.",
    )
    sensory: str = Field(
        description="How it sounds, smells and feels in use, so the texture is decided once"
        " rather than improvised per chapter.",
    )
    body: str = Field(
        description="The Markdown body: the technology at the length a writer needs.",
    )


class FactionStance(HarnessModel):
    """One faction's relation to another, dated to the scene where it took this shape.

    Dated for the same reason a relationship valence is: a stance stated once is a fact about
    the setting, while a stance with a scene attached is a fact about the story, and only the
    second can change later without becoming a contradiction.
    """

    faction: EntityId = Field(description="The other faction this stance is directed at.")
    stance: str = Field(
        min_length=1,
        description="What this faction is to that one: allied, at war, dependent, infiltrated.",
    )
    since: SceneId | None = Field(
        default=None,
        description="Scene from which the stance holds; `None` when it predates page one.",
    )


class Faction(StoreDocument):
    """DR-01, DR-02, DR-10. One collective agent: `canon/factions/<id>.md`.

    A faction exists so that pressure on the characters has an origin and a direction. The
    split between `wants` and `actual_goal` is what makes it usable: a faction whose stated
    goal is its real one can only ever do what it says, and nothing it does can surprise.

    **Failure mode** (`definitions.md` Faction): monolithic factions. With no internal dissent
    they generate no scenes, only geopolitical scenery - there is nobody inside to disagree
    with, so every encounter with them is an encounter with a weather system. `register` is
    where the internal texture starts, and it feeds the lexicon: a term's `used_by` is what
    keeps that jargon in this faction's mouths and out of everyone else's.
    """

    # `register` shadows an attribute of the model base (`ABCMeta.register`), as it does on
    # `StyleBible`; the wire name `definitions.md` gives is restored by alias.
    model_config = ConfigDict(populate_by_name=True)

    id: EntityId = Field(
        description="Stable identifier; the file is named after it and the index keys a row on it.",
    )
    wants: str = Field(
        min_length=1,
        description="The stated goal: what it says in public it is trying to achieve.",
    )
    actual_goal: str = Field(
        description="What it is actually after. The gap between this and `wants` is where its"
        " scenes come from; equal to `wants` only for a faction that never lies.",
    )
    resources: str = Field(
        description="What it can mobilise, and how fast. A threat with no stated reach can be"
        " neither escaped nor outrun in any checkable way.",
    )
    stance: list[FactionStance] = Field(
        default_factory=list,
        description="Relations to other factions, each dated to the scene it holds from.",
    )
    speech_register: str = Field(
        alias="register",
        description="How its members speak; feeds the lexicon and the voice profiles.",
    )
    body: str = Field(
        description="The Markdown body, including the internal dissent that keeps the faction"
        " from being scenery.",
    )


class LocationAccess(HarnessModel):
    """One way into a location, and how long it takes to arrive that way.

    The duration is in the unit `Scene.story_time` is counted in - integer hours since
    `epoch_zero` - because invariant 5 subtracts the two, and a travel time in any other unit
    could not be compared with them. The authoritative `transit_matrix` lives in
    `canon/time.yaml`, which is what FR-AUD-04 runs over; this field states the same quantity
    where a writer reads it, next to the place it applies to.
    """

    # `from` is the field name `definitions.md` gives and the key the file carries on disk,
    # and it is a Python keyword. The attribute is named for what it holds and the wire name
    # is restored by alias, with `populate_by_name` so code can construct by field name.
    model_config = ConfigDict(populate_by_name=True)

    from_location: EntityId = Field(
        alias="from",
        description="The location one can arrive from.",
    )
    hours: StoryHours = Field(
        description="Travel time in hours, the unit `story_time` is counted in, so the two can"
        " be subtracted directly by the transit check.",
    )


class Location(StoreDocument):
    """DR-01, DR-02, DR-10. One place: `canon/locations/<id>.md`.

    Locations are hierarchical - system, body, settlement, enclosure - and context is
    inherited downward: loading a cabin implies loading its ship and its orbit. FR-OPS-03
    does exactly that, walking `parent` upward and loading the whole chain, which is why
    `parent` is a reference rather than a sentence of prose. A scene's `location` is a leaf
    of this tree.

    **Failure mode** (`definitions.md` Location): no explicit geometry. Two scenes set in the
    same room end up with incompatible floor plans - one has a door behind the desk, the next
    has a window there - and nothing detects it, because neither scene is wrong on its own.
    `geometry` decides the blocking once, for every scene that will ever be set here.
    """

    id: EntityId = Field(
        description="Stable identifier; the file is named after it and the index keys a row on it.",
    )
    parent: EntityId | None = Field(
        default=None,
        description="The level above in the hierarchy; `None` only at the root. FR-OPS-03 loads"
        " the whole parent chain, so context is inherited downward rather than restated.",
    )
    sensory_palette: str = Field(
        description="Light, sound, smell, gravity, temperature: what the place is like to be in.",
    )
    geometry: str = Field(
        description="What constrains blocking: exits, heights, cover, sightlines. Decided here"
        " once, so two scenes in this room cannot contradict each other.",
    )
    access: list[LocationAccess] = Field(
        default_factory=list,
        description="Where one can arrive from, and how long it takes.",
    )
    body: str = Field(
        description="The Markdown body: the place at the length a writer needs.",
    )


class HistoricalEvent(StoreDocument):
    """DR-01, DR-02, DR-10. One fact predating page one: `canon/history/<id>.md`.

    What distinguishes it from a scene beat is that nobody witnesses it on the page: it is
    only remembered, argued about, or lied about. `date` is therefore in the same hours since
    `epoch_zero` as a scene's `story_time`, normally negative, and the event reaches a scene
    only through somebody who holds a version of it.

    **Failure mode** (`definitions.md` HistoricalEvent): a single version. Without the gap
    between `official_version` and `actual_version` the past generates no plot - there is
    nothing to discover and nobody is lying, so the event is set dressing rather than
    pressure. `actual_version` may never be revealed on the page and still has to be decided
    here, because the characters who know it speak differently from the ones who do not.
    """

    id: EntityId = Field(
        description="Stable identifier; the file is named after it and the index keys a row on it.",
    )
    date: StoryHours = Field(
        description="When it happened, in hours since `epoch_zero`. Negative for anything before"
        " the book begins, which is most history.",
    )
    official_version: str = Field(
        min_length=1,
        description="What is said in public: the version a character can repeat without risk.",
    )
    actual_version: str = Field(
        min_length=1,
        description="What actually happened. May never be revealed on the page, and still has to"
        " be decided here - the gap between the two versions is the plot the event carries.",
    )
    who_knows_what: list[EntityId] = Field(
        default_factory=list,
        description="Characters holding a position on this event. Their exact certainty and the"
        " scene each learnt it in live in `cast/{id}/knowledge.yaml` (DR-04), which is what"
        " invariant 1 runs over; this list is the edge, not the state.",
    )
    body: str = Field(
        description="The Markdown body: the event at the length a writer needs.",
    )


# --------------------------------------------------------------------------------------
# reconcile (FR-OPS-08) - which written work depended on an entity
# --------------------------------------------------------------------------------------


class DependencyReason(StrEnum):
    """Why a scene or a turn depends on the entity. One value per edge FR-OPS-08 names.

    A code rather than a sentence, because the consumer is the orchestrator (plan step 18) as
    much as a person: a turn record that says `location_ancestor` can be filtered, and one that
    says "set somewhere inside it" cannot.
    """

    POV = "pov"
    PARTICIPANT = "participant"
    LOCATION = "location"
    LOCATION_ANCESTOR = "location_ancestor"
    PINNED = "pinned"
    TAG_SCOPE = "tag_scope"
    KNOWLEDGE = "knowledge"
    SELECTED = "selected"


class DependencyEdge(BaseModel):
    """One reason, with the detail that makes it checkable against the files."""

    code: DependencyReason = Field(description="Which kind of reference this is.")
    detail: str = Field(
        description="The specifics: which location the ancestor was reached through, which"
        " tags matched the scope, which character acquired knowledge, which turn selected it.",
    )


class Dependent(BaseModel):
    """One scene or turn that depends on the entity, with every reason, deduplicated.

    One entry per id rather than one per reason: a scene that has the entity as POV *and* in
    its pins is one scene to re-read, and listing it twice would make the count of affected
    work -- the number a late decision is weighed by -- wrong.
    """

    id: str = Field(description="The scene id (`NNN`) or the turn record id (`NNN-<n>`).")
    reasons: list[DependencyEdge] = Field(
        description="Every distinct reason, sorted by code then detail. Never empty.",
    )


class ReconcileRequest(BaseModel):
    """The body of `POST /canon/reconcile`. Unknown fields are refused rather than ignored."""

    model_config = ConfigDict(extra="forbid")

    entity_id: EntityId = Field(
        description="The entity that changed: a canon entity of any kind, a character, or a"
        " lexicon term.",
    )


class Reconciliation(BaseModel):
    """FR-OPS-08. Which written work depended on the entity, so a late decision does not force
    a re-read of the entire book.

    `architecture.md` Operations: "Without this operation, every late decision forces a re-read
    of the entire book, which in practice means late decisions stop being made." The answer is
    deliberately a **superset** (AC 14): an extra scene costs one re-read, while a missed one
    is a contradiction nobody is told about, so every ambiguous edge is resolved towards
    inclusion.
    """

    entity_id: EntityId = Field(description="The entity reconciled.")
    defined_in: list[str] = Field(
        description="The store files that define it, sorted. More than one means two records"
        " claim the id, which is itself worth knowing before deciding anything.",
    )
    scenes: list[Dependent] = Field(
        description="Every scene that references the entity, sorted by scene id.",
    )
    turns: list[Dependent] = Field(
        description="Every turn record whose selected list contains it, sorted by turn id.",
    )


__all__ = [
    "Axiom",
    "DependencyEdge",
    "DependencyReason",
    "Dependent",
    "Faction",
    "FactionStance",
    "GenreContract",
    "GenrePromise",
    "HistoricalEvent",
    "Location",
    "LocationAccess",
    "Premise",
    "Project",
    "ReconcileRequest",
    "Reconciliation",
    "StyleBible",
    "StyleMetric",
    "StyleMetrics",
    "Technology",
    "ThematicThesis",
]
