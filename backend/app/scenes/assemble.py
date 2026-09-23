"""FR-OPS-03, `assemble_context(scene)`: the writer's documents, loaded as of the scene's instant.

`architecture.md` Operations: assembly is two operations, not one. `select_entities` decides
which entities a scene needs and returns identifiers; this module loads each of them through
the store **as of the scene's story time T**, in ranking order, until the 100k cap. Keeping
the two apart is what lets retrieval find what the tags would have missed without letting it
leak a fact the POV has not yet learned: the index never hands over text, and every text
handed over here is read in the form the instant allows.

**The loading order** (FR-OPS-03, Figure 2). The fixed block (`canon/project.md`,
`canon/style.md`); `dossier(pov, at=T)`; the `literal_tail` of the previous scene in
discourse order; then the prunable part: the terms bound to the POV, each selected entity in
ranking order, and the open setups. The first three are mandatory (FR-CTX-03); the rest is
removed whole from the end when the estimate would cross the cap.

**As-of forms.** A character is `dossier(id, at=T)`. An axiom, technology, faction or
historical event is its full record -- a historical event only when dated at or before T,
since an event after the instant has not happened yet. A location is its full record with its
parent chain. A chapter digest loads only when every scene its `scene_ref` covers exists and
has `story_time <= T`, and is labelled as events the POV did not witness when its `povs` lacks
the POV. A term loads as its full record, when selected or when bound through `used_by` to an
entity already loaded. A setup is offered when open at T -- `paid_in` and `resolution` empty,
`planted_in` at or before T, `due_by` at or after T -- under a *may collect* label that never
assigns one. What its as-of form excludes is named in `withheld`, never dropped silently.

**What never enters.** Raw `manuscript/NNN.md` prose, except the previous scene's
`literal_tail`, which is read as the field DR-11 derives on every write and nothing else of
the draft. Paid setups, resolved violations and closed threads "leave the working tier as they
close": a closed setup is filtered out, and violations and threads are not read at all -- the
writer's row of Figure 3 lists `ledger/violations.yaml` only on revision, where FR-AGENT-02
hands over the blocking ones itself, and does not list `ledger/threads.yaml`.

**Indivisible entries.** Pruning keeps whole entries or removes them (FR-OPS-03, `tokens`), so
what must travel together is folded into one entry:

* A location's parent chain is part of the location's entry. An ancestor already carried by
  an earlier entry is not repeated: pruning only ever removes a suffix of the ranking, so an
  earlier entry is present whenever a later one is, and the chain stays complete in every
  context that keeps the location.
* A term bound through `used_by` is folded into the entry of the first loaded entity that
  binds it, so it can never be present without the entity it explains, nor that entity without
  it. The one exception is the POV: its dossier is mandatory and FR-CTX-03 fixes the mandatory
  part, so the terms bound to it are entries of their own at the head of the prunable part --
  the POV outranks every selected entity, and it is always present, so no term there can
  outlive its binder either.

**The budget.** The estimate is `commons.llm.tokens`', the single definition of "fits" that
the orchestrator and both model clients also use (P7), and the fit is its `fit_to_budget`. The
caller's system prompt and instruction are counted in the mandatory part, because the cap is
over the whole call (FR-CTX-01): assembly stops where the writer's call would, which is why
FR-CTX-03 is "the same rule seen from the call". A mandatory part over the cap raises
`ContextBudgetExceeded` (FR-CTX-05).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel

from app.canon import service as canon_service
from app.canon.models import HistoricalEvent, Location
from app.cast import service as cast_service
from app.commons.config import CONTEXT_TOKEN_CAP, FIXED_BLOCK_TOKEN_BUDGET
from app.commons.db import CANON_DIRECTORY_BY_KIND, IndexKind
from app.commons.errors import InvalidRecord, NotFound
from app.commons.llm.tokens import Entry, estimate_tokens, fit_to_budget
from app.commons.schemas import CanonicalTerm, DigestLevel, Scene, SceneDigest, SelectedEntity
from app.commons.stores import Store, paths
from app.commons.stores.frontmatter import BODY_FIELD, render_markdown, render_yaml
from app.ledger import service as ledger_service
from app.manuscript import service as manuscript_service
from app.scenes import repository
from app.scenes.models import (
    AssembledContext,
    AssemblyWarning,
    ContextEntry,
    ContextPart,
    TailState,
    WithheldEntity,
)

MAY_COLLECT: Final[str] = "may collect"
"""The label every open setup is offered under (FR-OPS-03, `architecture.md` Figure 2). The
writer's prompt names it: a setup under it is offered, never assigned."""

NOT_WITNESSED: Final[str] = "did not witness"
"""The phrase that marks a chapter digest whose `povs` lacks the scene's POV: the writer
knows those events, the character does not (FR-OPS-03, SceneDigest)."""

FILE_FORMAT_FIELDS: Final[frozenset[str]] = frozenset({"schema_version"})
"""Fields that describe the file rather than the story, left out of a rendered record. The
version of a file's format is nothing a writer can use, and every token of it is paid on
every call."""

_KIND_TITLES: Final[Mapping[IndexKind, str]] = {
    IndexKind.AXIOM: "Axiom",
    IndexKind.TECHNOLOGY: "Technology",
    IndexKind.LOCATION: "Location",
    IndexKind.FACTION: "Faction",
    IndexKind.HISTORICAL_EVENT: "Historical event",
    IndexKind.TERM: "Term",
    IndexKind.CHARACTER: "Character",
    IndexKind.CHAPTER_DIGEST: "Chapter digest",
}

_LOCATIONS: Final[str] = CANON_DIRECTORY_BY_KIND[IndexKind.LOCATION]
_HISTORY: Final[str] = CANON_DIRECTORY_BY_KIND[IndexKind.HISTORICAL_EVENT]


def entity_key(kind: str, identifier: str) -> str:
    """`kind:id`, the key of an entity's entry. The kind is part of it because one id may be
    carried by two kinds (a pin resolves to both, `select.py`), and `removed` must say which
    was removed."""
    return f"{kind}:{identifier}"


def render_record(record: BaseModel) -> str:
    """A record as the writer reads it: the store's own rendering, minus the file format.

    Markdown-backed records keep their frontmatter-and-body shape, everything else is YAML,
    both through `commons.stores.frontmatter`, so a record reads in the context as it reads
    in the tree. Rendered from the validated model rather than copied from the file, so what
    enters a context is exactly what FR-STORE-06 accepted.
    """
    payload = record.model_dump(mode="json", by_alias=True, exclude=set(FILE_FORMAT_FIELDS))
    text = render_markdown(payload) if BODY_FIELD in payload else render_yaml(payload)
    return text.rstrip("\n")


def covered_scenes(scene_ref: str) -> list[str]:
    """The scene ids a digest's `scene_ref` covers: `NNN`, or every id of `NNN-NNN` inclusive.

    DR-11 gives the field a grammar precisely so this can be decided at assembly time. A
    reversed range covers nothing, and "every covered scene is at or before T" would then be
    vacuously true of it; it is refused instead of loaded.
    """
    first, _, last = scene_ref.partition("-")
    start, end = int(first), int(last or first)
    return [f"{number:03d}" for number in range(start, end + 1)]


def _index_kind(kind: str) -> IndexKind:
    """The loadable kind of a selected entry. Any other value is not something selection can
    return, so a list carrying one did not come from `select_entities`."""
    try:
        return IndexKind(kind)
    except ValueError:
        message = f"a selected entity of kind {kind!r} has no as-of form to load"
        raise ValueError(message) from None


@dataclass(slots=True)
class _Builder:
    """An entry being put together: one record, and whatever is folded into it."""

    key: str
    part: ContextPart
    label: str
    path: str
    record: str
    mandatory: bool = False
    sources: list[str] = field(default_factory=list)
    carries: list[str] = field(default_factory=list)
    folded: list[str] = field(default_factory=list)

    def fold(self, *, label: str, path: str, record: str, carried: str) -> None:
        """Add a record that must travel with this one: a parent location, a bound term."""
        self.folded.append(f"{label}\n\n{record}")
        if path != self.path and path not in self.sources:
            self.sources.append(path)
        self.carries.append(carried)

    def build(self) -> ContextEntry:
        text = "\n\n".join([f"{self.label}\n\n{self.record}", *self.folded])
        return ContextEntry(
            key=self.key,
            part=self.part,
            label=self.label,
            path=self.path,
            sources=[self.path, *self.sources],
            carries=list(self.carries),
            mandatory=self.mandatory,
            text=text,
            tokens=estimate_tokens(text),
        )


def _scene_records(store: Store) -> dict[str, Scene]:
    """Every scene record, keyed by the id of its file: the clock every as-of decision here
    is read against (`story_time`) and the axis the previous scene is found on
    (`discourse_order`)."""
    return {
        identifier: repository.read_scene(store, identifier)
        for identifier in repository.list_scene_ids(store)
    }


class _Assembly:
    """The loads of one assembly, and what they have already loaded.

    `loaded` is the set of entity keys already in the context, so nothing is loaded twice: the
    POV named again by a selection, a location's ancestor that is also selected, a term bound
    to two entities. Whatever carried it first is earlier in the order and so is present
    whenever the later occurrence would have been.
    """

    def __init__(self, store: Store, scene: Scene, scenes: Mapping[str, Scene]) -> None:
        self.store = store
        self.scene = scene
        self.at = scene.story_time
        self.scenes = scenes
        self.terms: list[CanonicalTerm] = canon_service.lexicon(store).terms
        self.loaded: set[str] = set()
        self.withheld: list[WithheldEntity] = []

    def withhold(self, key: str, reason: str) -> None:
        self.withheld.append(WithheldEntity(key=key, reason=reason))

    # --- the mandatory part -------------------------------------------------------------

    def fixed_block(self) -> list[ContextEntry]:
        """`canon/project.md` and `canon/style.md`, whole: paid on every call for the length
        of the book, which is why FR-OPS-04 watches their size."""
        project = _Builder(
            key=paths.PROJECT,
            part=ContextPart.FIXED,
            label="Fixed block: the project -- premise, thesis and genre contract",
            path=paths.PROJECT,
            record=render_record(canon_service.project(self.store)),
            mandatory=True,
        )
        style = _Builder(
            key=paths.STYLE,
            part=ContextPart.FIXED,
            label="Fixed block: the style bible and its canonical sample",
            path=paths.STYLE,
            record=render_record(canon_service.style(self.store)),
            mandatory=True,
        )
        return [project.build(), style.build()]

    def dossier(self, character: str, *, part: ContextPart, label: str) -> _Builder:
        """`dossier(character, at=T)` (FR-OPS-01): the character as they were at T. Its text
        carries the four cast files the trim reads, and they are all named as sources."""
        key = entity_key(IndexKind.CHARACTER, character)
        self.loaded.add(key)
        return _Builder(
            key=key,
            part=part,
            label=label,
            path=paths.cast_file(character, "dossier"),
            record=render_record(cast_service.dossier(self.store, character, self.at)),
            mandatory=part is ContextPart.POV,
            sources=[
                paths.cast_file(character, "knowledge"),
                paths.cast_file(character, "changes"),
                paths.RELATIONSHIPS,
            ],
            carries=[key],
        )

    def pov_dossier(self) -> ContextEntry:
        """Loaded by identifier, unconditionally: the POV never goes through selection."""
        pov = self.scene.pov
        label = f"Point-of-view character {pov}, as of story hour {self.at}"
        return self.dossier(pov, part=ContextPart.POV, label=label).build()

    def literal_tail(self) -> tuple[str | None, TailState, ContextEntry | None]:
        """The previous scene in discourse order, and its `literal_tail` if it has a draft.

        The tail is the stored field -- derived from the body on every write by the
        manuscript feature (DR-11) -- and nothing else of the draft is read into the context.
        No draft means no tail, said so on the result; a passage is never made up to fill it.
        """
        earlier = [
            (record.discourse_order, identifier)
            for identifier, record in self.scenes.items()
            if record.discourse_order < self.scene.discourse_order
        ]
        if not earlier:
            return None, TailState.NO_PREVIOUS_SCENE, None
        _, previous = max(earlier)
        try:
            draft = manuscript_service.read_draft(self.store, previous)
        except NotFound:
            return previous, TailState.NO_DRAFT, None
        path = paths.draft(previous)
        label = f"The closing passage of the previous scene, {previous}, verbatim"
        text = f"{label}\n\n{draft.literal_tail}"
        entry = ContextEntry(
            key=path,
            part=ContextPart.LITERAL_TAIL,
            label=label,
            path=path,
            sources=[path],
            carries=[],
            mandatory=True,
            text=text,
            tokens=estimate_tokens(text),
        )
        return previous, TailState.LOADED, entry

    # --- the prunable part --------------------------------------------------------------

    def pov_terms(self) -> list[ContextEntry]:
        """The terms bound to the POV through `used_by`, in lexicon order, one entry each."""
        entries: list[ContextEntry] = []
        pov = self.scene.pov
        for term in self.terms:
            key = entity_key(IndexKind.TERM, term.id)
            if pov not in term.used_by or key in self.loaded:
                continue
            self.loaded.add(key)
            builder = _Builder(
                key=key,
                part=ContextPart.LEXICON,
                label=f"Term {term.id}, used by the point-of-view character {pov}",
                path=paths.LEXICON,
                record=render_record(term),
                carries=[key],
            )
            entries.append(builder.build())
        return entries

    def selected(self, entity: SelectedEntity) -> ContextEntry | None:
        """One selected entity in its as-of form, with what must travel with it folded in.
        None when it is already loaded or its as-of form excludes it at T."""
        kind = _index_kind(entity.kind)
        key = entity_key(kind, entity.entity_id)
        if key in self.loaded:
            return None
        pinned = " (pinned by the scene record)" if entity.pinned else ""
        builder = self._load(kind, entity.entity_id, pinned)
        if builder is None:
            return None
        self._bind_terms(builder)
        return builder.build()

    def _load(self, kind: IndexKind, identifier: str, pinned: str) -> _Builder | None:
        key = entity_key(kind, identifier)
        title = _KIND_TITLES[kind]
        if kind is IndexKind.CHARACTER:
            label = f"{title} {identifier}, as of story hour {self.at}{pinned}"
            return self.dossier(identifier, part=ContextPart.SELECTED, label=label)
        if kind is IndexKind.TERM:
            return self._term(key, identifier, f"{title} {identifier}{pinned}")
        if kind is IndexKind.CHAPTER_DIGEST:
            return self._digest(key, identifier, pinned)
        if kind is IndexKind.LOCATION:
            return self._location(key, identifier, pinned)
        if kind is IndexKind.HISTORICAL_EVENT:
            event = canon_service.entity(self.store, _HISTORY, identifier, HistoricalEvent)
            if event.date > self.at:
                self.withhold(key, f"dated story hour {event.date}, after {self.at}")
                return None
            record = render_record(event)
            directory = _HISTORY
        else:
            directory = CANON_DIRECTORY_BY_KIND[kind]
            model = canon_service.CANON_MODELS[directory]
            record = render_record(canon_service.entity(self.store, directory, identifier, model))
        self.loaded.add(key)
        return _Builder(
            key=key,
            part=ContextPart.SELECTED,
            label=f"{title} {identifier}{pinned}",
            path=paths.canon_entity(directory, identifier),
            record=record,
            carries=[key],
        )

    def _term(self, key: str, identifier: str, label: str) -> _Builder:
        term = next((candidate for candidate in self.terms if candidate.id == identifier), None)
        if term is None:
            message = f"{paths.LEXICON} has no term {identifier!r}"
            raise NotFound(message, kind="term", identifier=identifier)
        self.loaded.add(key)
        return _Builder(
            key=key,
            part=ContextPart.SELECTED,
            label=label,
            path=paths.LEXICON,
            record=render_record(term),
            carries=[key],
        )

    def _digest(self, key: str, identifier: str, pinned: str) -> _Builder | None:
        """A chapter digest, only when every scene it covers is at or before T.

        A covered scene with no record cannot be shown to be at or before T, and is treated
        as not: withholding is the direction of error the as-of rule is built on.
        """
        digest: SceneDigest = manuscript_service.read_digest(self.store, identifier)
        path = paths.digest(identifier)
        if digest.level is not DigestLevel.CHAPTER:
            self.withhold(key, f"a {digest.level.value} digest; only chapter digests are loaded")
            return None
        covered = covered_scenes(digest.scene_ref)
        if not covered:
            message = f"{path} covers the reversed range {digest.scene_ref!r} (DR-11)"
            raise InvalidRecord(message, file=path, field="scene_ref")
        for scene_id in covered:
            record = self.scenes.get(scene_id)
            if record is None:
                reason = f"covers scene {scene_id}, which has no record to place it in time"
                self.withhold(key, reason)
                return None
            if record.story_time > self.at:
                hour = record.story_time
                self.withhold(key, f"covers scene {scene_id} at story hour {hour}, after {self.at}")
                return None
        pov = self.scene.pov
        heading = f"Chapter digest {identifier} (scenes {digest.scene_ref}){pinned}"
        if pov in digest.povs:
            label = f"{heading}, told from the point of view of {', '.join(digest.povs)}"
        else:
            label = (
                f"{heading}: events the point-of-view character, {pov}, {NOT_WITNESSED}; "
                "the writer knows them, the character does not"
            )
        self.loaded.add(key)
        return _Builder(
            key=key,
            part=ContextPart.SELECTED,
            label=label,
            path=path,
            record=render_record(digest),
            carries=[key],
        )

    def _location(self, key: str, identifier: str, pinned: str) -> _Builder:
        """A location and its parent chain, nearest first, in one entry.

        The walk stops at a root, at a parent with no record -- named in `withheld`, since the
        chain the writer receives is then shorter than the tree says -- and at the first
        repeat, because a cycle in the tree would otherwise turn a canon fault into a hung
        request.
        """
        location = canon_service.entity(self.store, _LOCATIONS, identifier, Location)
        self.loaded.add(key)
        builder = _Builder(
            key=key,
            part=ContextPart.SELECTED,
            label="",
            path=paths.canon_entity(_LOCATIONS, identifier),
            record=render_record(location),
            carries=[key],
        )
        chain: list[str] = []
        child, parent = identifier, location.parent
        while parent is not None and parent != identifier and parent not in chain:
            parent_key = entity_key(IndexKind.LOCATION, parent)
            try:
                above = canon_service.entity(self.store, _LOCATIONS, parent, Location)
            except NotFound:
                self.withhold(parent_key, f"parent of {child} with no record; the chain stops")
                break
            chain.append(parent)
            if parent_key not in self.loaded:
                self.loaded.add(parent_key)
                builder.fold(
                    label=f"Parent location {parent}, which contains {child}",
                    path=paths.canon_entity(_LOCATIONS, parent),
                    record=render_record(above),
                    carried=parent_key,
                )
            child, parent = parent, above.parent
        title = _KIND_TITLES[IndexKind.LOCATION]
        if chain:
            where = f", inside {' > '.join(chain)}"
        elif location.parent is None:
            where = ", a root of the location tree"
        else:
            # Not a root: its parent could not be loaded, and the writer must not be told the
            # place stands alone. The reason is in `withheld` (or the parent is the place itself).
            where = f", whose parent {location.parent} could not be loaded"
        builder.label = f"{title} {identifier}{where}{pinned}"
        return builder

    def _bind_terms(self, builder: _Builder) -> None:
        """Fold in every term not yet loaded whose `used_by` names an entity this entry
        carries (FR-OPS-03: the lexicon bound to loaded entities)."""
        binders = [carried.partition(":")[2] for carried in builder.carries]
        for term in self.terms:
            key = entity_key(IndexKind.TERM, term.id)
            if key in self.loaded:
                continue
            binder = next((name for name in binders if name in term.used_by), None)
            if binder is None:
                continue
            self.loaded.add(key)
            builder.fold(
                label=f"Term {term.id}, used by {binder}",
                path=paths.LEXICON,
                record=render_record(term),
                carried=key,
            )

    def open_setups(self) -> list[ContextEntry]:
        """The setups open at T, most urgent first, each offered under *may collect*.

        Open is FR-OPS-03's definition: `paid_in` and `resolution` empty, `planted_in` at or
        before T -- a promise not yet made to the reader is not one the writer can keep --
        and `due_by` at or after T, compared on story time as FR-AUD-02 compares it. A setup
        whose scenes have no record cannot be placed and is not offered, and is named in
        `withheld` so its absence is visible, as the audit reports it (FR-AUD-02, a note).
        """
        offered: list[tuple[int, str, str, _Builder]] = []
        for setup in ledger_service.setups(self.store).setups:
            key = entity_key("setup", setup.id)
            if setup.paid_in is not None or setup.resolution is not None or key in self.loaded:
                continue
            planted = self.scenes.get(setup.planted_in)
            due = self.scenes.get(setup.due_by)
            if planted is None or due is None:
                missing = setup.planted_in if planted is None else setup.due_by
                self.withhold(key, f"it names scene {missing}, which has no record to date it by")
                continue
            if planted.story_time > self.at or due.story_time < self.at:
                continue
            self.loaded.add(key)
            label = (
                f"Open setup {setup.id} -- {MAY_COLLECT}: offered, not assigned; collect it "
                "only if this scene affords it"
            )
            builder = _Builder(
                key=key,
                part=ContextPart.SETUP,
                label=label,
                path=paths.SETUPS,
                record=render_record(setup),
                carries=[key],
            )
            offered.append((due.story_time, setup.due_by, setup.id, builder))
        offered.sort(key=lambda item: item[:3])
        return [builder.build() for *_, builder in offered]


def assemble_context(
    store: Store,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    system: str = "",
    instruction: str = "",
    cap: int = CONTEXT_TOKEN_CAP,
) -> AssembledContext:
    """FR-OPS-03, FR-OPS-04, AC 12. The writer's documents for `scene_id`, fitted to the cap.

    `selected` is the list `select_entities` returned -- in a turn, the list the turn record
    persists, so the writer and the auditor work from one list (FR-OPS-05). `system` and
    `instruction` are the writer call's, counted in the mandatory part; the route passes
    neither. `cap` may be lowered, by a test, and never raised: the 100k is a module constant
    precisely so no caller can move it (NFR-05).
    """
    if cap < 0:
        message = f"a context cap cannot be negative, got {cap}"
        raise ValueError(message)
    if cap > CONTEXT_TOKEN_CAP:
        message = f"the cap can be lowered for a test but not raised: {cap} > {CONTEXT_TOKEN_CAP}"
        raise ValueError(message)
    scene = repository.read_scene(store, scene_id)
    assembly = _Assembly(store, scene, _scene_records(store))

    fixed = assembly.fixed_block()
    pov = assembly.pov_dossier()
    previous, tail_state, tail = assembly.literal_tail()
    mandatory = [*fixed, pov, *([tail] if tail is not None else [])]

    prunable = assembly.pov_terms()
    for entity in selected:
        entry = assembly.selected(entity)
        if entry is not None:
            prunable.append(entry)
    prunable.extend(assembly.open_setups())

    fit = fit_to_budget(
        system=system,
        instruction=instruction,
        mandatory=[Entry(key=entry.key, text=entry.text) for entry in mandatory],
        prunable=[Entry(key=entry.key, text=entry.text) for entry in prunable],
        cap=cap,
    )
    kept = prunable[: len(fit.kept) - len(mandatory)]
    fixed_tokens = sum(entry.tokens for entry in fixed)
    warnings = (
        [AssemblyWarning.FIXED_BLOCK_OVER_BUDGET] if fixed_tokens > FIXED_BLOCK_TOKEN_BUDGET else []
    )
    return AssembledContext(
        scene=scene.id,
        pov=scene.pov,
        story_time=scene.story_time,
        previous_scene=previous,
        literal_tail=tail_state,
        selected=list(selected),
        entries=[*mandatory, *kept],
        removed=fit.removed,
        truncated_at=fit.truncated_at,
        withheld=assembly.withheld,
        estimate=fit.estimate,
        cap=cap,
        fixed_block_tokens=fixed_tokens,
        warnings=warnings,
    )


__all__ = [
    "FILE_FORMAT_FIELDS",
    "MAY_COLLECT",
    "NOT_WITNESSED",
    "assemble_context",
    "covered_scenes",
    "entity_key",
    "render_record",
]
