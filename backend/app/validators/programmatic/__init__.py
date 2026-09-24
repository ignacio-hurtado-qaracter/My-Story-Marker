"""Programmatic validators of block B4 (spec 008), registered through K3.

Call ``register_validators()`` once (the pipeline does it from ``app.novel.setup``); it is
idempotent because the registry replaces a validator of the same name at the same point.

| Name | Point(s) | Blocking | Feedback to |
|---|---|---|---|
| ``chapter_length`` | chapter_close, hook | yes | writer |
| ``exact_names`` | chapter_close, hook | yes | editor |
| ``fact_usage_recorder`` | chapter_close | no (records ``fact_usage``) | — |
| ``brief_coverage`` | pre_publish | yes | writer of the assigned chapter |
| ``schema_role_output`` | scene_accept | yes | the producing role |
| ``schema_brief`` | pre_publish | yes (skipped-pass without a schema) | interviewer |
| ``lean_chronology`` | pre_publish | yes (missing toolchain fails) | editor |
| ``prose_repetition`` | chapter_close, hook | soft (fails only when severe) | editor |
| ``calendar_consistency`` | chapter_close | yes | editor (fix or drop the weekday) |

``ctx.extra`` keys read: ``brief`` (dict), ``plan`` (dict), ``role_output`` (pydantic model
or mapping), ``role_output_model`` (pydantic class), ``feedback_role`` (str).
"""

from __future__ import annotations

from app.validators.programmatic.calendar import CalendarConsistency
from app.validators.programmatic.chronology import LeanChronology
from app.validators.programmatic.coverage import BriefCoverage, FactUsageRecorder
from app.validators.programmatic.length import ChapterLength
from app.validators.programmatic.names import ExactNames
from app.validators.programmatic.prose import ProseRepetition
from app.validators.programmatic.schema import SchemaBrief, SchemaRoleOutput
from app.validators.protocol import ValidationPoint, Validator
from app.validators.registry import register


def all_validators() -> list[Validator]:
    """Every B4 validator, one instance per point it runs at, in execution order."""
    hook = ValidationPoint.HOOK
    return [
        SchemaRoleOutput(),
        ChapterLength(),
        ExactNames(),
        ProseRepetition(),
        CalendarConsistency(),
        FactUsageRecorder(),
        SchemaBrief(),
        BriefCoverage(),
        LeanChronology(),
        ChapterLength(point=hook),
        ExactNames(point=hook),
        ProseRepetition(point=hook),
    ]


def register_validators() -> None:
    """K3 registration convention (004-contracts): register every B4 validator."""
    for validator in all_validators():
        register(validator)


__all__ = [
    "BriefCoverage",
    "CalendarConsistency",
    "ChapterLength",
    "ExactNames",
    "FactUsageRecorder",
    "LeanChronology",
    "ProseRepetition",
    "SchemaBrief",
    "SchemaRoleOutput",
    "all_validators",
    "register_validators",
]
