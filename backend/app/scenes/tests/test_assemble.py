"""FR-OPS-03, `assemble_context` -- AC 12's assembly half (nothing after the scene's instant,
stop before the cap, never cut inside an entry), AC 33 for the writer's pruning, and FR-OPS-04.

Every test runs on a private copy of the fixture novel (NFR-09). Most hand `assemble_context` a
selected list built here rather than one ranked by the index: the as-of rules are about what is
loaded for an id, whoever chose it, and a fixed list makes each case certain instead of a
consequence of how `FakeEmbedder` happens to rank. `FULL` names every selectable entity of the
fixture, so each scene is assembled with the whole world offered and the as-of form is the only
thing deciding what enters. The route tests run the real selection.

The fixture's shape for this step (README "Digests and the as-of rule", "Closed things leave the
working tier"): chapter digest 901 covers 001-003 with `povs: [vance, ilan]`, so it loads for
005 (T = 318) as events quiej did not witness; 902 covers 004-006, two of them at 318, so it
must not load for 006 (T = 310) although 006 is one of its scenes. `su_readkey` is open and
`su_graft` is paid. Scenes 002 and 003 carry the only drafts.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import yaml
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.canon.models import HistoricalEvent, Location, Project, StyleBible
from app.cast.models import TrimmedDossier
from app.commons.config import CONTEXT_TOKEN_CAP, FIXED_BLOCK_TOKEN_BUDGET, get_settings
from app.commons.embeddings import FakeEmbedder
from app.commons.errors import ContextBudgetExceeded, InvalidRecord
from app.commons.llm.tokens import estimate_input, estimate_tokens
from app.commons.permissions import Actor, AgentRole, may_receive
from app.commons.schemas import (
    CanonicalTerm,
    Draft,
    LexiconFile,
    Scene,
    SceneDigest,
    SelectedEntity,
    SetupResolution,
    SetupsFile,
)
from app.commons.stores import Store, paths
from app.commons.stores.writer import serialise
from app.scenes import service
from app.scenes.assemble import MAY_COLLECT, NOT_WITNESSED, covered_scenes
from app.scenes.models import (
    AssembledContext,
    AssemblyWarning,
    ContextEntry,
    ContextPart,
    TailState,
)

SCENES = ("001", "002", "003", "004", "005", "006")
DRAFTS = ("002", "003")


def chosen(kind: str, entity_id: str, *, pinned: bool = False) -> SelectedEntity:
    return SelectedEntity(entity_id=entity_id, kind=kind, score=1.0, pinned=pinned)


FULL = (
    chosen("axiom", "ax_brine_dark"),
    chosen("axiom", "ax_calving_window"),
    chosen("axiom", "ax_cold_soak"),
    chosen("axiom", "ax_indemnity_burn"),
    chosen("location", "pump_vault"),
    chosen("location", "kestrel_deep"),
    chosen("character", "vance"),
    chosen("character", "ilan"),
    chosen("character", "quiej"),
    chosen("chapter_digest", "901"),
    chosen("chapter_digest", "902"),
    chosen("faction", "kestrel_coop"),
    chosen("faction", "divers_register"),
    chosen("historical_event", "hi_exchanger_fire"),
    chosen("historical_event", "hi_shaft_capping"),
    chosen("technology", "te_dive_rig"),
    chosen("technology", "te_hand_sonar"),
    chosen("term", "lx_readkey"),
)
"""Every entity the index can return for the fixture: the canon records, the characters, the
two chapter digests and one term, in an order that puts a location before its parent."""


def assemble(
    store: Store,
    scene: str,
    selected: tuple[SelectedEntity, ...] = FULL,
    **options: str | int,
) -> AssembledContext:
    system = str(options.get("system", ""))
    instruction = str(options.get("instruction", ""))
    cap = int(options.get("cap", CONTEXT_TOKEN_CAP))
    return service.assemble_context(
        store, scene, selected, system=system, instruction=instruction, cap=cap
    )


def by_key(context: AssembledContext) -> dict[str, ContextEntry]:
    return {entry.key: entry for entry in context.entries}


def record_of(entry: ContextEntry) -> str:
    """The rendered record under an entry's label (the label is the first paragraph)."""
    return entry.text.split("\n\n", 1)[1]


def dossiers(context: AssembledContext) -> Iterator[TrimmedDossier]:
    """Every dossier the writer receives, read back from the entry text itself -- the record
    before any term folded in after it."""
    for entry in context.entries:
        if entry.key.startswith("character:"):
            record = record_of(entry).split("\n\nTerm ", 1)[0]
            yield TrimmedDossier.model_validate(yaml.safe_load(record))


def story_clock(store: Store) -> dict[str, int]:
    return {
        identifier: service.read_scene(store, identifier).story_time
        for identifier in service.list_scenes(store)
    }


def rewrite_scene(store: Store, identifier: str, **changes: int) -> None:
    """A variant of a fixture scene in the private copy, written as the architect."""
    scene = store.read(paths.scene(identifier), Scene)
    changed = scene.model_copy(update=changes)
    store.write(paths.scene(identifier), changed, role=AgentRole.ARCHITECT, actor=Actor.HUMAN)


def write_canon(store: Store, relative: str, record: Project | StyleBible | Location) -> None:
    store.write(relative, record, role=AgentRole.WORLD_BUILDER, actor=Actor.HUMAN)


def all_text(context: AssembledContext) -> str:
    return "\n".join(entry.text for entry in context.entries)


# --------------------------------------------------------------------------------------
# The loading order and the mandatory part
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- FR-OPS-03's order: fixed block, POV dossier, previous tail, then the
# prunable part (POV-bound terms, the selection in ranking order, open setups); exactly the
# first four are mandatory (FR-CTX-03).
def test_the_loading_order_is_fixed_pov_tail_then_the_ranking(fixture_store: Store) -> None:
    context = assemble(fixture_store, "004")
    parts = [entry.part for entry in context.entries]
    keys = [entry.key for entry in context.entries]

    assert keys[:4] == [paths.PROJECT, paths.STYLE, "character:vance", paths.draft("003")]
    assert parts[:4] == [
        ContextPart.FIXED,
        ContextPart.FIXED,
        ContextPart.POV,
        ContextPart.LITERAL_TAIL,
    ]
    assert [entry.mandatory for entry in context.entries] == [True] * 4 + [False] * (len(keys) - 4)
    order = [ContextPart.LEXICON, ContextPart.SELECTED, ContextPart.SETUP]
    prunable = [order.index(part) for part in parts[4:]]
    assert prunable == sorted(prunable)
    assert set(parts[4:]) == set(order)

    selected = [entry.key for entry in context.entries if entry.part is ContextPart.SELECTED]
    ranking = [f"{entity.kind}:{entity.entity_id}" for entity in FULL]
    assert selected == [key for key in ranking if key in selected]


# spec 001 / AC 12 -- the POV enters by identifier and only once, even when a selection names it.
@pytest.mark.parametrize("scene", SCENES)
def test_the_pov_dossier_is_loaded_once_as_of_the_scene(fixture_store: Store, scene: str) -> None:
    record = service.read_scene(fixture_store, scene)
    context = assemble(fixture_store, scene)
    pov_key = f"character:{record.pov}"

    assert [entry.key for entry in context.entries].count(pov_key) == 1
    pov = by_key(context)[pov_key]
    assert pov.part is ContextPart.POV
    assert pov.mandatory
    assert yaml.safe_load(record_of(pov))["at"] == record.story_time
    assert context.story_time == record.story_time


# spec 001 / AC 12 -- the previous scene in discourse order: its tail when it has a draft, and
# otherwise the reason on the result, never an invented passage.
@pytest.mark.parametrize(
    ("scene", "previous", "state"),
    [
        ("001", None, TailState.NO_PREVIOUS_SCENE),
        ("002", "001", TailState.NO_DRAFT),
        ("003", "002", TailState.LOADED),
        ("004", "003", TailState.LOADED),
        ("005", "004", TailState.NO_DRAFT),
        ("006", "005", TailState.NO_DRAFT),
    ],
)
def test_the_literal_tail_is_the_previous_scenes_or_its_absence_is_stated(
    fixture_store: Store, scene: str, previous: str | None, state: TailState
) -> None:
    context = assemble(fixture_store, scene)
    tails = [entry for entry in context.entries if entry.part is ContextPart.LITERAL_TAIL]

    assert context.previous_scene == previous
    assert context.literal_tail is state
    if state is not TailState.LOADED:
        assert tails == []
        return
    assert previous is not None
    [tail] = tails
    draft = fixture_store.read(paths.draft(previous), Draft)
    assert tail.path == paths.draft(previous)
    assert tail.sources == [paths.draft(previous)]
    assert record_of(tail) == draft.literal_tail


# --------------------------------------------------------------------------------------
# As-of forms -- AC 12, "never includes a fact acquired after the scene"
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- no KnowledgeState acquired after the scene's story time, and no valence or
# arc anchored after it, in any dossier entry (the POV's and every selected character's).
@pytest.mark.parametrize("scene", SCENES)
def test_no_dossier_entry_holds_a_fact_acquired_after_the_scene(
    fixture_store: Store, scene: str
) -> None:
    at = service.read_scene(fixture_store, scene).story_time
    clock = story_clock(fixture_store)
    context = assemble(fixture_store, scene)
    found = list(dossiers(context))

    assert {dossier.id for dossier in found} == {"vance", "ilan", "quiej"}
    for dossier in found:
        assert dossier.at == at
        assert all(clock[row.acquired_in] <= at for row in dossier.knowledge)
        assert all(clock[edge.valence.scene] <= at for edge in dossier.relationships)
        assert dossier.arc is None or clock[dossier.arc.scene] <= at


# spec 001 / AC 12 -- the property above is not vacuous: at 006 (T = 310) quiej's row acquired
# at 004 (hour 318) is on disk and must be absent, while vance's row at 006 itself is present.
def test_a_later_knowledge_row_is_withheld_and_a_same_instant_row_kept(
    fixture_store: Store,
) -> None:
    context = assemble(fixture_store, "006")
    rows = {
        (dossier.id, row.fact_ref, row.acquired_in)
        for dossier in dossiers(context)
        for row in dossier.knowledge
    }

    assert ("quiej", "ax_brine_dark", "004") not in rows
    assert ("vance", "ax_brine_dark", "006") in rows


# spec 001 / AC 12 -- property: whatever the scene's story time, nothing dated after it enters.
# Scene 006 is moved along the story axis and assembled with the whole world offered; every
# dossier, digest and setup that loads must be at or before the new instant.
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(hour=st.integers(min_value=-50, max_value=450))
def test_nothing_after_the_instant_enters_at_any_story_time(
    fixture_store: Store, hour: int
) -> None:
    rewrite_scene(fixture_store, "006", story_time=hour)
    clock = story_clock(fixture_store)
    context = assemble(fixture_store, "006")

    for dossier in dossiers(context):
        assert dossier.at == hour
        assert all(clock[row.acquired_in] <= hour for row in dossier.knowledge)
        assert all(clock[edge.valence.scene] <= hour for edge in dossier.relationships)
    setups = fixture_store.read(paths.SETUPS, SetupsFile).setups
    for entry in context.entries:
        if entry.part is ContextPart.SETUP:
            [setup] = [item for item in setups if f"setup:{item.id}" == entry.key]
            assert clock[setup.planted_in] <= hour <= clock[setup.due_by]
        if entry.key.startswith("chapter_digest:"):
            digest = fixture_store.read(paths.digest(entry.key.split(":")[1]), SceneDigest)
            assert all(clock[scene] <= hour for scene in covered_scenes(digest.scene_ref))


# spec 001 / AC 12 -- 901 loads for 005 (every covered scene <= 318) and is labelled as events
# quiej did not witness; 902 loads for 005 too, and names quiej, so it carries no such label.
def test_digest_901_loads_for_005_labelled_not_witnessed(fixture_store: Store) -> None:
    context = assemble(fixture_store, "005")
    entries = by_key(context)

    unwitnessed = entries["chapter_digest:901"]
    assert NOT_WITNESSED in unwitnessed.label
    assert "quiej" in unwitnessed.label
    assert unwitnessed.path == paths.digest("901")
    delta = fixture_store.read(paths.digest("901"), SceneDigest).delta
    assert SceneDigest.model_validate(yaml.safe_load(record_of(unwitnessed))).delta == delta
    assert NOT_WITNESSED not in entries["chapter_digest:902"].label


# spec 001 / AC 12 -- the label follows `povs`: at 004 vance is in 901's list, so 901 is not
# labelled as unwitnessed there.
def test_a_digest_naming_the_pov_is_not_labelled_unwitnessed(fixture_store: Store) -> None:
    entry = by_key(assemble(fixture_store, "004"))["chapter_digest:901"]

    assert NOT_WITNESSED not in entry.label
    assert "vance" in entry.label


# spec 001 / AC 12 -- 902 covers 004 and 005 at hour 318; at 006 (T = 310) it must not load,
# although 006 is one of its scenes. It is named in `withheld`, not silently missing.
def test_digest_902_does_not_load_for_006(fixture_store: Store) -> None:
    context = assemble(fixture_store, "006")
    delta = fixture_store.read(paths.digest("902"), SceneDigest).delta

    assert "chapter_digest:902" not in by_key(context)
    assert "chapter_digest:901" in by_key(context)
    [withheld] = [item for item in context.withheld if item.key == "chapter_digest:902"]
    assert "318" in withheld.reason
    assert delta[:80] not in all_text(context)
    assert "chapter_digest:902" not in context.removed


# spec 001 / AC 12 -- a covered scene with no record cannot be shown to be at or before T, so
# the digest is withheld rather than loaded.
def test_a_digest_covering_an_unrecorded_scene_is_withheld(fixture_store: Store) -> None:
    digest = fixture_store.read(paths.digest("902"), SceneDigest)
    stray = digest.model_copy(update={"scene_ref": "006-007"})
    fixture_store.write(paths.digest("903"), stray, role=AgentRole.WRITER, actor=Actor.HUMAN)
    context = assemble(fixture_store, "006", (chosen("chapter_digest", "903"),))

    assert "chapter_digest:903" not in by_key(context)
    [withheld] = context.withheld
    assert withheld.key == "chapter_digest:903"
    assert "007" in withheld.reason


# spec 001 / AC 12 -- a reversed range covers nothing, and "every covered scene is <= T" would
# then be vacuously true; it is refused naming the file and field.
def test_a_reversed_digest_range_is_refused(fixture_store: Store) -> None:
    digest = fixture_store.read(paths.digest("901"), SceneDigest)
    reversed_range = digest.model_copy(update={"scene_ref": "003-001"})
    fixture_store.write(
        paths.digest("903"), reversed_range, role=AgentRole.WRITER, actor=Actor.HUMAN
    )

    with pytest.raises(InvalidRecord) as caught:
        assemble(fixture_store, "006", (chosen("chapter_digest", "903"),))
    assert caught.value.context == {"file": paths.digest("903"), "field": "scene_ref"}


# spec 001 / AC 12 -- only chapter digests enter by selection; a scene digest named in a list is
# withheld, so a hand-built or stale list cannot smuggle past prose in.
def test_a_scene_level_digest_is_withheld(fixture_store: Store) -> None:
    context = assemble(fixture_store, "004", (chosen("chapter_digest", "002"),))

    assert "chapter_digest:002" not in by_key(context)
    assert [item.key for item in context.withheld] == ["chapter_digest:002"]


# spec 001 / AC 12 -- a historical event dated after the instant has not happened yet.
def test_a_historical_event_after_the_instant_is_withheld(fixture_store: Store) -> None:
    event = fixture_store.read(paths.canon_entity("history", "hi_exchanger_fire"), HistoricalEvent)
    later = event.model_copy(update={"id": "hi_late_flood", "date": 400})
    fixture_store.write(
        paths.canon_entity("history", "hi_late_flood"),
        later,
        role=AgentRole.WORLD_BUILDER,
        actor=Actor.HUMAN,
    )
    selected = (chosen("historical_event", "hi_late_flood"),)
    before = assemble(fixture_store, "006", selected)
    rewrite_scene(fixture_store, "006", story_time=400)
    at_the_hour = assemble(fixture_store, "006", selected)

    assert "historical_event:hi_late_flood" not in by_key(before)
    assert [item.key for item in before.withheld] == ["historical_event:hi_late_flood"]
    assert "historical_event:hi_late_flood" in by_key(at_the_hour)
    assert at_the_hour.withheld == []


# --------------------------------------------------------------------------------------
# Closed things leave the working tier; raw prose never enters
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- `su_graft` is paid and never enters; `su_readkey` is open from its planted
# scene (001, hour 300) and offered under *may collect* wherever T is within [300, 318].
@pytest.mark.parametrize("scene", SCENES)
def test_open_setups_are_offered_under_may_collect_and_paid_ones_never(
    fixture_store: Store, scene: str
) -> None:
    context = assemble(fixture_store, scene)
    setups = [entry for entry in context.entries if entry.part is ContextPart.SETUP]
    graft = next(
        item
        for item in fixture_store.read(paths.SETUPS, SetupsFile).setups
        if item.id == "su_graft"
    )

    assert "setup:su_graft" not in by_key(context)
    assert graft.promise not in all_text(context)
    expected = [] if scene == "002" else ["setup:su_readkey"]
    assert [entry.key for entry in setups] == expected
    for entry in setups:
        assert MAY_COLLECT in entry.label
        assert "not assigned" in entry.label
        imperative = ("must", "required", "pay it", "pay this", "collect it now", "you have to")
        assert not any(phrase in entry.label.lower() for phrase in imperative)
        assert entry.path == paths.SETUPS


# spec 001 / AC 12 -- a setup whose `due_by` scene is earlier than the instant is no longer
# collectable here: moving scene 005 to hour 305 puts `su_readkey`'s deadline before 006's 310.
def test_a_setup_past_its_due_scene_is_not_offered(fixture_store: Store) -> None:
    assert "setup:su_readkey" in by_key(assemble(fixture_store, "006"))
    rewrite_scene(fixture_store, "005", story_time=305)

    assert "setup:su_readkey" not in by_key(assemble(fixture_store, "006"))


# spec 001 / AC 12 -- "open" is `paid_in` *and* `resolution` empty (FR-OPS-03): either one set
# closes the debt. The fixture's paid setup has both, so each half is shown on its own here by
# closing `su_readkey` one way at a time. `ledger/setups.yaml` has no writer in Figure 3, so
# the private copy is hand-edited, as `test_audit_02.py` does.
@pytest.mark.parametrize(
    ("paid_in", "resolution"),
    [
        (None, SetupResolution.DELIBERATELY_ABANDONED),
        (None, SetupResolution.SUBVERTED),
        ("004", None),
    ],
)
def test_a_setup_closed_by_either_field_is_not_offered(
    fixture_store: Store, paid_in: str | None, resolution: SetupResolution | None
) -> None:
    assert "setup:su_readkey" in by_key(assemble(fixture_store, "004"))
    record = fixture_store.read(paths.SETUPS, SetupsFile)
    closed = [
        setup.model_copy(update={"paid_in": paid_in, "resolution": resolution})
        if setup.id == "su_readkey"
        else setup
        for setup in record.setups
    ]
    edited = record.model_copy(update={"setups": closed})
    (fixture_store.root / paths.SETUPS).write_text(
        serialise(paths.SETUPS, edited), encoding="utf-8"
    )
    context = assemble(fixture_store, "004")

    assert [entry for entry in context.entries if entry.part is ContextPart.SETUP] == []


# spec 001 / AC 12 -- a setup whose deadline names a scene with no record cannot be placed on
# the story axis: it is not offered, and it is named in `withheld` rather than dropped silently.
def test_an_unplaceable_setup_is_withheld_not_dropped(fixture_store: Store) -> None:
    record = fixture_store.read(paths.SETUPS, SetupsFile)
    moved = [
        setup.model_copy(update={"due_by": "099"}) if setup.id == "su_readkey" else setup
        for setup in record.setups
    ]
    (fixture_store.root / paths.SETUPS).write_text(
        serialise(paths.SETUPS, record.model_copy(update={"setups": moved})), encoding="utf-8"
    )
    context = assemble(fixture_store, "004")

    assert "setup:su_readkey" not in by_key(context)
    [withheld] = [item for item in context.withheld if item.key == "setup:su_readkey"]
    assert "099" in withheld.reason


# spec 001 / AC 12 -- the resolved violation and the resolved thread never enter; nothing is read
# from `ledger/violations.yaml` or `ledger/threads.yaml` for a write at all (Figure 3's writer
# row lists violations only on revision, and threads not at all).
@pytest.mark.parametrize("scene", SCENES)
def test_no_resolved_violation_and_no_closed_thread_enters(
    fixture_store: Store, scene: str
) -> None:
    context = assemble(fixture_store, scene)
    text = all_text(context)
    sources = {source for entry in context.entries for source in entry.sources}

    assert "A cold soak may be cut to four hours on a co-op indemnity dive," not in text
    assert "vi_001" not in text
    assert "accept_with_reason" not in text
    assert "th_graft" not in text
    assert paths.VIOLATIONS not in sources
    assert paths.THREADS not in sources


# spec 001 / AC 12 -- raw `manuscript/NNN.md` prose never enters except the previous scene's
# tail: the part of a draft before its tail is nowhere, and a draft that is not the previous
# scene's is nowhere at all.
@pytest.mark.parametrize("scene", SCENES)
def test_no_manuscript_prose_enters_but_the_previous_tail(fixture_store: Store, scene: str) -> None:
    context = assemble(fixture_store, scene)
    text = all_text(context)
    drafted = {entry.path for entry in context.entries if entry.part is ContextPart.LITERAL_TAIL}
    prose_sources = {
        source
        for entry in context.entries
        for source in entry.sources
        if source.startswith(f"{paths.MANUSCRIPT}/") and not source.startswith(paths.DIGESTS)
    }

    assert prose_sources == drafted
    for identifier in DRAFTS:
        draft = fixture_store.read(paths.draft(identifier), Draft)
        assert draft.body.endswith(draft.literal_tail)
        is_previous = paths.draft(identifier) in drafted
        withheld = draft.body[: len(draft.body) - len(draft.literal_tail)]
        lines = (withheld if is_previous else draft.body).splitlines()
        leaked = [line for line in lines if len(line.strip()) >= 40 and line.strip() in text]
        assert leaked == []


# --------------------------------------------------------------------------------------
# Indivisible entries, and the writer's input row
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- a location carries its parent chain inside its own entry; the parent,
# selected again later, is not loaded twice.
def test_a_location_carries_its_parent_chain_in_one_entry(fixture_store: Store) -> None:
    context = assemble(fixture_store, "006")
    vault = by_key(context)["location:pump_vault"]

    assert vault.carries[:2] == ["location:pump_vault", "location:kestrel_deep"]
    assert vault.sources[:2] == [
        paths.canon_entity("locations", "pump_vault"),
        paths.canon_entity("locations", "kestrel_deep"),
    ]
    assert "kestrel_deep" in vault.label
    assert "Parent location kestrel_deep" in vault.text
    assert "location:kestrel_deep" not in by_key(context)
    carried = [key for entry in context.entries for key in entry.carries]
    assert len(carried) == len(set(carried))


# spec 001 / AC 12 -- a parent with no record stops the chain and is named; a cycle in the tree
# stops at the first repeat instead of hanging the request.
def test_a_broken_location_chain_stops_and_is_named(fixture_store: Store) -> None:
    vault = fixture_store.read(paths.canon_entity("locations", "pump_vault"), Location)
    write_canon(
        fixture_store,
        paths.canon_entity("locations", "cradle_bay"),
        vault.model_copy(update={"id": "cradle_bay", "parent": "no_such_place"}),
    )
    write_canon(
        fixture_store,
        paths.canon_entity("locations", "loop_a"),
        vault.model_copy(update={"id": "loop_a", "parent": "loop_b"}),
    )
    write_canon(
        fixture_store,
        paths.canon_entity("locations", "loop_b"),
        vault.model_copy(update={"id": "loop_b", "parent": "loop_a"}),
    )
    selected = (chosen("location", "cradle_bay"), chosen("location", "loop_a"))
    context = assemble(fixture_store, "006", selected)
    entries = by_key(context)

    assert entries["location:cradle_bay"].carries == ["location:cradle_bay"]
    assert "root" not in entries["location:cradle_bay"].label
    assert "no_such_place" in entries["location:cradle_bay"].label
    root = assemble(fixture_store, "006", (chosen("location", "kestrel_deep"),))
    assert "a root of the location tree" in by_key(root)["location:kestrel_deep"].label
    assert [item.key for item in context.withheld] == ["location:no_such_place"]
    assert entries["location:loop_a"].carries == ["location:loop_a", "location:loop_b"]


# spec 001 / AC 12 -- the parent chain is the whole chain to the root, not the first parent: a
# cell inside pump_vault carries pump_vault and kestrel_deep. An ancestor an earlier entry
# already carries is not folded in again, and the label still names the whole chain.
def test_a_deep_location_carries_its_whole_chain_once(fixture_store: Store) -> None:
    vault = fixture_store.read(paths.canon_entity("locations", "pump_vault"), Location)
    write_canon(
        fixture_store,
        paths.canon_entity("locations", "brine_cell"),
        vault.model_copy(update={"id": "brine_cell", "parent": "pump_vault"}),
    )
    alone = by_key(assemble(fixture_store, "006", (chosen("location", "brine_cell"),)))
    cell = alone["location:brine_cell"]

    assert cell.carries == ["location:brine_cell", "location:pump_vault", "location:kestrel_deep"]
    assert "pump_vault > kestrel_deep" in cell.label

    root_first = (chosen("location", "kestrel_deep"), chosen("location", "brine_cell"))
    later = by_key(assemble(fixture_store, "006", root_first))["location:brine_cell"]
    assert later.carries == ["location:brine_cell", "location:pump_vault"]
    assert "pump_vault > kestrel_deep" in later.label
    assert "Parent location kestrel_deep" not in later.text


# spec 001 / AC 12 -- a parent folded into a location's entry is a loaded entity too, so a term
# bound to it through `used_by` travels in that same entry (FR-OPS-03: lexicon bound to loaded
# entities).
def test_a_term_bound_to_a_parent_location_travels_with_the_chain(fixture_store: Store) -> None:
    lexicon = fixture_store.read(paths.LEXICON, LexiconFile)
    term = CanonicalTerm.model_validate(
        {
            "id": "lx_deep",
            "canonical_form": "the Deep",
            "forbidden_variants": [],
            "used_by": ["kestrel_deep"],
        }
    )
    fixture_store.write(
        paths.LEXICON,
        lexicon.model_copy(update={"terms": [*lexicon.terms, term]}),
        role=AgentRole.WORLD_BUILDER,
        actor=Actor.HUMAN,
    )
    context = assemble(fixture_store, "006", (chosen("location", "pump_vault"),))
    vault = by_key(context)["location:pump_vault"]

    assert vault.carries == ["location:pump_vault", "location:kestrel_deep", "term:lx_deep"]
    assert "Term lx_deep, used by kestrel_deep" in vault.text


# spec 001 / AC 12, AC 33 -- a term bound through `used_by` is folded into the entry of the first
# loaded entity that binds it, so pruning that entity removes the term with it. At 002 the POV
# is ilan, who binds lx_soak and lx_vault; lx_calving and lx_readkey are bound to quiej.
def test_bound_terms_travel_inside_their_binders_entry(fixture_store: Store) -> None:
    selected = (chosen("axiom", "ax_cold_soak"), chosen("character", "quiej"))
    context = assemble(fixture_store, "002", selected)
    entries = by_key(context)

    assert [entry.key for entry in context.entries if entry.part is ContextPart.LEXICON] == [
        "term:lx_soak",
        "term:lx_vault",
    ]
    quiej = entries["character:quiej"]
    assert quiej.carries == ["character:quiej", "term:lx_calving", "term:lx_readkey"]
    assert paths.LEXICON in quiej.sources
    assert "Term lx_calving, used by quiej" in quiej.text

    cap = context.estimate - 1
    pruned = assemble(fixture_store, "002", selected, cap=cap)
    carried = {key for entry in pruned.entries for key in entry.carries}
    assert pruned.truncated_at == "character:quiej"
    assert not carried & {"character:quiej", "term:lx_calving", "term:lx_readkey"}


# spec 001 / FR-AGENT-09 -- every store path any entry is read from is inside the writer's row of
# Figure 3's `In` column, which the orchestrator checks before the call (plan step 18).
@pytest.mark.parametrize("scene", SCENES)
def test_every_source_is_in_the_writers_input_row(fixture_store: Store, scene: str) -> None:
    context = assemble(fixture_store, scene)

    for entry in context.entries:
        assert entry.sources[0] == entry.path
        assert all(may_receive(AgentRole.WRITER, source) for source in entry.sources), entry.key


# --------------------------------------------------------------------------------------
# The budget -- AC 12 "stops before 100k, never truncates inside an entry", AC 33
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- the estimate is `commons.llm.tokens`' estimate of what is kept, system
# prompt and instruction included, and each entry's count is that estimate of its text.
def test_the_estimate_is_the_token_estimate_of_what_is_kept(fixture_store: Store) -> None:
    system, instruction = "You write scenes." * 20, "Write scene 004." * 10
    context = assemble(fixture_store, "004", system=system, instruction=instruction)
    texts = [entry.text for entry in context.entries]

    assert context.estimate == estimate_input(system, texts, instruction)
    assert all(entry.tokens == estimate_tokens(entry.text) for entry in context.entries)
    assert context.cap == CONTEXT_TOKEN_CAP
    assert context.removed == []
    assert context.truncated_at is None


# spec 001 / AC 12, AC 33 -- with the cap lowered, the lowest-ranked entries are removed whole
# and named, `truncated_at` is the first of them, and no kept entry is cut.
@pytest.mark.parametrize("dropped", [1, 2, 5])
def test_a_lowered_cap_removes_the_lowest_ranked_entries_whole(
    fixture_store: Store, dropped: int
) -> None:
    full = assemble(fixture_store, "004")
    last = full.entries[-dropped:]
    cap = full.estimate - sum(entry.tokens for entry in last) + last[0].tokens - 1
    pruned = assemble(fixture_store, "004", cap=cap)

    assert pruned.removed == [entry.key for entry in last]
    assert pruned.truncated_at == last[0].key
    assert pruned.entries == full.entries[:-dropped]
    assert pruned.estimate <= cap
    assert all(not entry.mandatory for entry in last)


# spec 001 / AC 12, AC 33 -- a lower-ranked entry is never slipped in behind a larger one it
# happens to fit beside: the ranking decides, so everything after the first misfit goes.
def test_nothing_ranked_below_the_cut_is_kept(fixture_store: Store) -> None:
    full = assemble(fixture_store, "004")
    prunable = [entry for entry in full.entries if not entry.mandatory]
    largest = max(prunable[:-1], key=lambda entry: entry.tokens)
    position = full.entries.index(largest)
    before = sum(entry.tokens for entry in full.entries[:position])
    pruned = assemble(fixture_store, "004", cap=before + largest.tokens - 1)

    assert pruned.truncated_at == largest.key
    assert pruned.entries == full.entries[:position]
    assert pruned.removed == [entry.key for entry in full.entries[position:]]


# spec 001 / AC 12, AC 33 -- a cap that holds the mandatory part and nothing more keeps every
# mandatory entry and removes the whole prunable part, starting with the first of it.
def test_a_cap_equal_to_the_mandatory_part_keeps_only_it(fixture_store: Store) -> None:
    full = assemble(fixture_store, "004")
    mandatory = [entry for entry in full.entries if entry.mandatory]
    prunable = [entry for entry in full.entries if not entry.mandatory]
    pruned = assemble(fixture_store, "004", cap=sum(entry.tokens for entry in mandatory))

    assert pruned.entries == mandatory
    assert pruned.truncated_at == prunable[0].key
    assert pruned.removed == [entry.key for entry in prunable]


# spec 001 / AC 12, AC 33 -- a mandatory part over the cap on its own is `ContextBudgetExceeded`:
# the fixed block, the POV dossier and the tail are never pruned (FR-CTX-05).
def test_a_mandatory_part_over_the_cap_raises(fixture_store: Store) -> None:
    full = assemble(fixture_store, "004")
    mandatory = sum(entry.tokens for entry in full.entries if entry.mandatory)

    with pytest.raises(ContextBudgetExceeded) as caught:
        assemble(fixture_store, "004", cap=mandatory - 1)
    assert caught.value.context == {"counted": mandatory, "cap": mandatory - 1}


# spec 001 / AC 12, AC 33 -- the caller's system prompt and instruction are part of the
# mandatory count, so a system prompt that alone fills the cap refuses the call at 100k.
def test_the_system_prompt_counts_in_the_mandatory_part(fixture_store: Store) -> None:
    roomy = assemble(fixture_store, "004")
    mandatory = sum(entry.tokens for entry in roomy.entries if entry.mandatory)
    room = CONTEXT_TOKEN_CAP - mandatory
    tight = assemble(fixture_store, "004", instruction="x" * (3 * room))

    assert roomy.removed == []
    assert tight.entries == [entry for entry in roomy.entries if entry.mandatory]
    assert tight.estimate == CONTEXT_TOKEN_CAP
    with pytest.raises(ContextBudgetExceeded):
        assemble(fixture_store, "004", system="x", instruction="x" * (3 * room))


# spec 001 / NFR-05 -- the cap is lowered by tests, never raised or made negative.
@pytest.mark.parametrize("cap", [CONTEXT_TOKEN_CAP + 1, -1])
def test_the_cap_cannot_be_raised(fixture_store: Store, cap: int) -> None:
    with pytest.raises(ValueError, match="cap"):
        assemble(fixture_store, "004", cap=cap)


# spec 001 / AC 12 -- a kind that selection cannot return has no as-of form and is refused.
def test_an_unknown_kind_is_refused(fixture_store: Store) -> None:
    with pytest.raises(ValueError, match="banana"):
        assemble(fixture_store, "004", (chosen("banana", "ax_brine_dark"),))


# --------------------------------------------------------------------------------------
# FR-OPS-04 -- the fixed-block warning
# --------------------------------------------------------------------------------------


def small_fixed_block(store: Store) -> StyleBible:
    """Shrink project.md and style.md in the copy to a fixed block well under 800 tokens, and
    return the small style bible for the caller to pad."""
    project = store.read(paths.PROJECT, Project)
    small_project = project.model_copy(
        update={
            "premise": project.premise.model_copy(
                update={"statement": "A diver.", "dramatic_question": "Up?", "answer": "Yes."}
            ),
            "thesis": project.thesis.model_copy(
                update={"proposition": "Owed.", "antithesis": "Signed.", "test_scenes": []}
            ),
            "genre_contract": project.genre_contract.model_copy(
                update={"subgenre": "SF.", "rigour": "Hard.", "promises": [], "limits": "None."}
            ),
            "body": "Short.",
        }
    )
    write_canon(store, paths.PROJECT, small_project)
    style = store.read(paths.STYLE, StyleBible)
    small_style = style.model_copy(
        update={
            "tense": "Past.",
            "pov_policy": "Close third.",
            "prose_register": "Plain.",
            "forbidden": [],
            "exposition_policy": "Sparse.",
            "body": "x",
        }
    )
    write_canon(store, paths.STYLE, small_style)
    return small_style


# spec 001 / FR-OPS-04 -- the warning is on the response exactly when the fixed block's estimate
# exceeds 800 tokens: at 800 there is none, one character more and there is.
def test_the_fixed_block_warning_fires_just_over_800_tokens(fixture_store: Store) -> None:
    style = small_fixed_block(fixture_store)
    quiet = assemble(fixture_store, "004")
    assert quiet.warnings == []
    assert quiet.fixed_block_tokens < FIXED_BLOCK_TOKEN_BUDGET

    fixed = [entry for entry in quiet.entries if entry.part is ContextPart.FIXED]
    project_tokens, style_entry = fixed[0].tokens, fixed[1]
    target = 3 * (FIXED_BLOCK_TOKEN_BUDGET - project_tokens) - len(style_entry.text)
    write_canon(fixture_store, paths.STYLE, style.model_copy(update={"body": "x" * (1 + target)}))
    at_budget = assemble(fixture_store, "004")
    write_canon(fixture_store, paths.STYLE, style.model_copy(update={"body": "x" * (2 + target)}))
    over = assemble(fixture_store, "004")

    assert at_budget.fixed_block_tokens == FIXED_BLOCK_TOKEN_BUDGET
    assert at_budget.warnings == []
    assert over.fixed_block_tokens == FIXED_BLOCK_TOKEN_BUDGET + 1
    assert over.warnings == [AssemblyWarning.FIXED_BLOCK_OVER_BUDGET]


# spec 001 / FR-OPS-04 -- an oversized style.md warns and the context is still assembled whole.
def test_an_oversized_style_bible_warns_and_still_assembles(fixture_store: Store) -> None:
    style = small_fixed_block(fixture_store)
    write_canon(fixture_store, paths.STYLE, style.model_copy(update={"body": "word " * 1000}))
    context = assemble(fixture_store, "004")

    assert context.warnings == [AssemblyWarning.FIXED_BLOCK_OVER_BUDGET]
    assert context.fixed_block_tokens > FIXED_BLOCK_TOKEN_BUDGET
    assert context.removed == []
    assert "word word word" in by_key(context)[paths.STYLE].text


# --------------------------------------------------------------------------------------
# IF-05 -- POST /scenes/{id}/assemble
# --------------------------------------------------------------------------------------


# spec 001 / AC 12 -- the route selects then assembles: it answers what the function answers for
# the selection the route itself makes, the pinned axiom of 006 is in it, and 902 is not.
def test_the_route_assembles_the_selection(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    response = fixture_client.post("/scenes/006/assemble")
    assert response.status_code == 200
    answered = AssembledContext.model_validate(response.json())

    selection = service.select_entities(fixture_store, FakeEmbedder(), get_settings(), "006")
    expected = service.assemble_context(fixture_store, "006", selection.entities)
    assert answered == expected
    assert answered.selected == selection.entities
    entries = by_key(answered)
    assert "(pinned" in entries["axiom:ax_brine_dark"].label
    assert "chapter_digest:902" not in entries


# spec 001 / AC 12 -- a missing scene is a 404 before anything is selected or loaded.
def test_the_route_404s_for_a_missing_scene(fixture_client: TestClient) -> None:
    response = fixture_client.post("/scenes/099/assemble")

    assert response.status_code == 404


# --- plan step 17: the calling role's own documents ------------------------------------------

RECORD = "scenes/003.yaml"


# spec 001 / FR-CTX-03, FR-PERM-07 -- a role's own documents come first, verbatim, mandatory,
# and change nothing else about the assembly.
def test_role_inputs_come_first_verbatim_and_leave_the_rest_unchanged(
    fixture_store: Store,
) -> None:
    plain = assemble(fixture_store, "003")
    text = "  a record, verbatim: leading spaces and a trailing blank line kept\n\n"
    context = service.assemble_context(
        fixture_store, "003", FULL, role_inputs=[(RECORD, text), ("manuscript/003.md", "prose")]
    )
    first, second, *rest = context.entries
    assert (first.key, first.part, first.path, first.sources) == (
        RECORD,
        ContextPart.ROLE_INPUT,
        RECORD,
        [RECORD],
    )
    assert first.text == text
    assert first.mandatory
    assert first.tokens == estimate_tokens(text)
    assert second.key == "manuscript/003.md"
    assert rest == plain.entries
    assert context.removed == plain.removed
    assert context.fixed_block_tokens == plain.fixed_block_tokens
    assert context.estimate == plain.estimate + estimate_tokens(text) + estimate_tokens("prose")


# spec 001 / AC 33, FR-CTX-03 -- they count in the mandatory part: the selected entities fill
# only what is left, and a role input the cap cannot hold refuses the call.
def test_role_inputs_are_counted_in_the_mandatory_part(fixture_store: Store) -> None:
    plain = assemble(fixture_store, "003")
    mandatory = sum(entry.tokens for entry in plain.entries if entry.mandatory)
    kept_prunable = [entry for entry in plain.entries if not entry.mandatory]
    assert kept_prunable, "the fixture context has prunable entries"
    padding = "x" * (3 * kept_prunable[-1].tokens)
    squeezed = service.assemble_context(
        fixture_store, "003", FULL, cap=plain.estimate, role_inputs=[(RECORD, padding)]
    )
    assert squeezed.truncated_at == kept_prunable[-1].key
    assert squeezed.removed[0] == kept_prunable[-1].key
    with pytest.raises(ContextBudgetExceeded):
        service.assemble_context(
            fixture_store,
            "003",
            FULL,
            cap=mandatory + 10,
            role_inputs=[(RECORD, "y" * 3 * 11)],
        )


# spec 001 / FR-CTX-03 -- a document has one name.
def test_role_inputs_may_not_share_or_steal_a_key(fixture_store: Store) -> None:
    with pytest.raises(ValueError, match="one name"):
        service.assemble_context(
            fixture_store, "003", FULL, role_inputs=[(RECORD, "a"), (RECORD, "b")]
        )
    with pytest.raises(ValueError, match="reuses the key"):
        service.assemble_context(
            fixture_store, "003", FULL, role_inputs=[(paths.PROJECT, "a forged fixed block")]
        )
