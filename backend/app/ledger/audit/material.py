"""Everything the mechanical audit reads, loaded once per scene and handed to every check.

These are the files FR-AUD names for the mechanical checks. They are wider than the auditor's
`In` column of Figure 3 in three places -- `ledger/setups.yaml` (FR-AUD-02),
`ledger/threads.yaml` (FR-AUD-08) and the POV's `cast/{id}/voice.md` (FR-AUD-07) -- because
that column bounds what the *model* receives (FR-AGENT-09) and these reads are the backend's
own code, not a context; the gap is recorded in spec 001's open questions.

Each check below is a pure function of an `AuditMaterial` and none of them touches the store.
That is also what lets the checks be tested against a record built in memory as easily as
against the fixture.

Three rules govern the loading.

* **Scene records are the authority on both axes.** `story_time` and `discourse_order` are
  read from every `scenes/NNN.yaml`; `ledger/timeline.yaml` is a derived projection
  (`app.ledger.models.TimelineFile`) and is deliberately not consulted, so a stale projection
  cannot make a check pass.
* **Invalid is not absent.** A file that exists and fails validation raises `InvalidRecord`
  naming file and field (FR-STORE-06) and the whole audit stops with it: an audit that
  skipped a broken lexicon would report a clean scene over a check it never ran. A file that
  is *absent* is `None` here, and the check that needs it reports itself skipped.
* **Reads go through `Store` and the ledger's own repository only.** Other features' files
  are read through `Store` with their models (`commons.schemas`, and `VoiceProfile` from
  `app.cast.models`); `scenes` sits above `ledger` in the layer contract (NFR-04), so its
  service is not importable from here and its records are read directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel

from app.cast.models import VoiceProfile
from app.commons.errors import InvalidRecord, NotFound
from app.commons.schemas import (
    Draft,
    KnowledgeFile,
    LexiconFile,
    Scene,
    SetupsFile,
    TemporalSystem,
    ThreadsFile,
)
from app.commons.stores import Store, paths
from app.ledger import repository

YAML_SUFFIX: Final[str] = ".yaml"


@dataclass(frozen=True, slots=True)
class AuditMaterial:
    """The audited scene, the book's other scene records, and the records the checks read.

    Optional fields are `None` exactly when the file is absent from the tree; the check that
    needs one returns `Skip` naming the file. `knowledge` has an entry for every character
    whose `cast/{id}/knowledge.yaml` exists: a character with no knowledge file holds no
    knowledge states, which is a population of zero rather than a missing input.
    """

    scene: Scene
    scenes: Mapping[str, Scene]
    draft: Draft | None
    lexicon: LexiconFile | None
    time: TemporalSystem | None
    setups: SetupsFile | None
    threads: ThreadsFile | None
    knowledge: Mapping[str, KnowledgeFile]
    voice: VoiceProfile | None

    @property
    def is_last_scene(self) -> bool:
        """Whether the audited scene is the last the reader meets (FR-AUD-02's escalation).

        "Last" is by `discourse_order`, as the fixture README reads FR-AUD-02: the book ends
        where the reader stops, not where the story clock stops.
        """
        last = max(record.discourse_order for record in self.scenes.values())
        return self.scene.discourse_order == last


def _optional[RecordT: BaseModel](
    store: Store, relative: str, model: type[RecordT]
) -> RecordT | None:
    """The record, or `None` when the file is absent. A present but invalid file still raises
    `InvalidRecord` from the store layer (FR-STORE-06)."""
    return store.read(relative, model) if store.exists(relative) else None


def _read_scenes(store: Store) -> dict[str, Scene]:
    """Every scene record, keyed by id.

    A file under `scenes/` whose name is not a scene id, or whose record names another scene,
    stops the audit rather than being skipped. Invariants 4, 5 and 10 are questions about the
    whole book; answering them over the scenes that happened to parse would be answering a
    different question and reporting it as this one.
    """
    records: dict[str, Scene] = {}
    for relative in store.list_files(paths.SCENES, YAML_SUFFIX):
        name = relative.rsplit("/", 1)[-1].removesuffix(YAML_SUFFIX)
        try:
            identifier = paths.scene_id(name)
        except ValueError as error:
            message = f"{relative} cannot be addressed as a scene record: {error}"
            raise InvalidRecord(message, file=relative) from error
        record = store.read(paths.scene(identifier), Scene)
        if record.id != identifier:
            message = (
                f"{relative} is scene {identifier!r} but the record names {record.id!r}; the "
                "audit would attribute its findings to the wrong scene (DR-08)"
            )
            raise InvalidRecord(message, file=relative, field="id")
        records[identifier] = record
    return records


def _read_knowledge(store: Store) -> dict[str, KnowledgeFile]:
    """Every character's knowledge file, keyed by the directory's character id."""
    files: dict[str, KnowledgeFile] = {}
    for character in store.list_subdirectories(paths.CAST):
        try:
            relative = paths.cast_file(character, "knowledge")
        except ValueError as error:
            message = f"a directory under {paths.CAST} is not a character id: {error}"
            raise InvalidRecord(message, file=paths.CAST) from error
        record = _optional(store, relative, KnowledgeFile)
        if record is not None:
            files[character] = record
    return files


def load_material(store: Store, scene_id: str) -> AuditMaterial:
    """Read everything the eight mechanical checks need for `scene_id`.

    `NotFound` when the scene has no record: an audit of a scene that does not exist has no
    answer, and an empty report would read as a clean one.
    """
    identifier = paths.scene_id(scene_id)
    scenes = _read_scenes(store)
    scene = scenes.get(identifier)
    if scene is None:
        message = f"no scene record with id {identifier!r}"
        raise NotFound(message, kind="scene", identifier=identifier)

    draft_path = paths.draft(identifier)
    draft = _optional(store, draft_path, Draft)
    if draft is not None and draft.scene_ref != identifier:
        message = (
            f"{draft_path} is the draft of scene {identifier!r} but names {draft.scene_ref!r}; "
            "its evidence would be attributed to the wrong scene (DR-08)"
        )
        raise InvalidRecord(message, file=draft_path, field="scene_ref")

    setups_path = repository.SETUPS_PATH
    threads_path = repository.THREADS_PATH
    return AuditMaterial(
        scene=scene,
        scenes=scenes,
        draft=draft,
        lexicon=_optional(store, paths.LEXICON, LexiconFile),
        time=_optional(store, paths.TIME, TemporalSystem),
        setups=repository.read_setups(store) if store.exists(setups_path) else None,
        threads=repository.read_threads(store) if store.exists(threads_path) else None,
        knowledge=_read_knowledge(store),
        voice=_optional(store, paths.cast_file(scene.pov, "voice"), VoiceProfile),
    )


__all__ = ["AuditMaterial", "load_material"]
