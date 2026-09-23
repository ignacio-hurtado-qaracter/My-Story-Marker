"""Shared store records: the models used by two or more features (DR-01).

What is **not** here is as deliberate as what is. Records owned by a single feature live in
that feature's `models.py` -- `Axiom` and `Project` in `app/canon/`, `Character` and
`VoiceProfile` in `app/cast/`, the structure containers in `app/scenes/` -- because
`commons/` must not know a feature's name (NFR-04) and speculative sharing is how a commons
turns into a dumping ground.

The store layer never looks a model up here either. `read_record` takes the model as a
parameter, so `commons/stores/` can validate an axiom without knowing what an axiom is.
"""

from __future__ import annotations

from app.commons.schemas.change_event import ChangeEvent, ChangesFile
from app.commons.schemas.common import (
    ENTITY_ID_PATTERN,
    SCENE_ID_PATTERN,
    SCHEMA_VERSION,
    Certainty,
    DigestLevel,
    EntityId,
    Evidence,
    FactStatus,
    HarnessModel,
    Invariant,
    Order,
    Outcome,
    Ruling,
    RulingKind,
    SceneId,
    SetupResolution,
    Severity,
    StoreDocument,
    StoryHours,
    StrictInteger,
    ThreadState,
    Valence,
    Via,
    ViolationResolution,
    ViolationSource,
    Words,
)
from app.commons.schemas.digest import SceneDigest
from app.commons.schemas.draft import Draft
from app.commons.schemas.knowledge import KnowledgeFile, KnowledgeState
from app.commons.schemas.lexicon import CanonicalTerm, LexiconFile
from app.commons.schemas.proposed import ProposedFact, ProposedFile
from app.commons.schemas.relationship import DatedValence, Relationship, RelationshipsFile
from app.commons.schemas.role_outputs import (
    DigestOutput,
    ExtractOutput,
    PolishOutput,
    ProposedFactDraft,
    ReviseOutput,
    SemanticAuditOutput,
    SemanticViolation,
    WriterOutput,
)
from app.commons.schemas.scene import Scene
from app.commons.schemas.setup import Setup, SetupsFile
from app.commons.schemas.thread import PlotThread, ThreadsFile
from app.commons.schemas.time import Calendar, TemporalSystem
from app.commons.schemas.turn import (
    AuditIteration,
    DigestMeasure,
    DraftMeasure,
    EscalationCategory,
    FactRecord,
    ModelCallRecord,
    RevisionScopeRecord,
    SelectedEntity,
    SkippedRecord,
    StepRecord,
    StepStatus,
    TurnEscalation,
    TurnOutcome,
    TurnRecord,
    TurnStep,
    WriteRecord,
)
from app.commons.schemas.violation import Violation, ViolationsFile

__all__ = [
    "ENTITY_ID_PATTERN",
    "SCENE_ID_PATTERN",
    "SCHEMA_VERSION",
    "AuditIteration",
    "Calendar",
    "CanonicalTerm",
    "Certainty",
    "ChangeEvent",
    "ChangesFile",
    "DatedValence",
    "DigestLevel",
    "DigestMeasure",
    "DigestOutput",
    "Draft",
    "DraftMeasure",
    "EntityId",
    "EscalationCategory",
    "Evidence",
    "ExtractOutput",
    "FactRecord",
    "FactStatus",
    "HarnessModel",
    "Invariant",
    "KnowledgeFile",
    "KnowledgeState",
    "LexiconFile",
    "ModelCallRecord",
    "Order",
    "Outcome",
    "PlotThread",
    "PolishOutput",
    "ProposedFact",
    "ProposedFactDraft",
    "ProposedFile",
    "Relationship",
    "RelationshipsFile",
    "ReviseOutput",
    "RevisionScopeRecord",
    "Ruling",
    "RulingKind",
    "Scene",
    "SceneDigest",
    "SceneId",
    "SelectedEntity",
    "SemanticAuditOutput",
    "SemanticViolation",
    "Setup",
    "SetupResolution",
    "SetupsFile",
    "Severity",
    "SkippedRecord",
    "StepRecord",
    "StepStatus",
    "StoreDocument",
    "StoryHours",
    "StrictInteger",
    "TemporalSystem",
    "ThreadState",
    "ThreadsFile",
    "TurnEscalation",
    "TurnOutcome",
    "TurnRecord",
    "TurnStep",
    "Valence",
    "Via",
    "Violation",
    "ViolationResolution",
    "ViolationSource",
    "ViolationsFile",
    "Words",
    "WriteRecord",
    "WriterOutput",
]
