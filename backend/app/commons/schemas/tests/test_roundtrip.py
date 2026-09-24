"""AC 4, the model half — parse, serialise, parse is identity for every shared model.

Generated from each model's own JSON Schema rather than from hand-written examples. Examples
test the shapes the author thought of; the schema is the contract the store layer will
actually be handed, and generating from it is what finds the field whose serialised form does
not validate again.

Identity is checked through `model_dump(by_alias=True)`, because that is what the store layer
writes to disk. A model whose round trip only works by field name would produce YAML the next
read rejects, and `from`/`to` on ChangeEvent and Relationship are exactly that risk.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis_jsonschema import from_schema
from pydantic import BaseModel, ValidationError

from app.commons.schemas.change_event import ChangeEvent, ChangesFile
from app.commons.schemas.digest import SceneDigest
from app.commons.schemas.draft import Draft
from app.commons.schemas.knowledge import KnowledgeFile, KnowledgeState
from app.commons.schemas.lexicon import CanonicalTerm, LexiconFile
from app.commons.schemas.proposed import ProposedFact, ProposedFile
from app.commons.schemas.relationship import Relationship, RelationshipsFile
from app.commons.schemas.scene import Scene
from app.commons.schemas.setup import Setup, SetupsFile
from app.commons.schemas.thread import PlotThread, ThreadsFile
from app.commons.schemas.time import TemporalSystem
from app.commons.schemas.violation import Violation, ViolationsFile

SHARED_MODELS: list[type[BaseModel]] = [
    Scene,
    Draft,
    SceneDigest,
    KnowledgeState,
    KnowledgeFile,
    ChangeEvent,
    ChangesFile,
    Relationship,
    RelationshipsFile,
    CanonicalTerm,
    LexiconFile,
    TemporalSystem,
    Setup,
    SetupsFile,
    PlotThread,
    ThreadsFile,
    ProposedFact,
    ProposedFile,
    Violation,
    ViolationsFile,
]


# spec 001 / AC 4
@pytest.mark.parametrize("model", SHARED_MODELS, ids=lambda m: m.__name__)
def test_every_model_produces_a_json_schema(model: type[BaseModel]) -> None:
    """DR-01. A model that cannot render a schema cannot be exported or validated on read."""
    schema = model.model_json_schema()
    assert schema["title"] == model.__name__
    assert schema["type"] == "object"


# spec 001 / AC 4
@pytest.mark.parametrize("model", SHARED_MODELS, ids=lambda m: m.__name__)
def test_parse_serialise_parse_is_identity(model: type[BaseModel]) -> None:
    @given(from_schema(model.model_json_schema()))
    @settings(
        max_examples=25,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    )
    def check(instance: object) -> None:
        # Some model rules cannot be expressed in JSON Schema at all -- `Scene` requires
        # `participants` to be disjoint from `pov`, which no keyword can state -- so the
        # generator legitimately produces records the model rejects. The property under test
        # is "parse, serialise, parse is identity", which only says anything about records
        # that parse; a generated record that does not is out of its domain, not a failure.
        try:
            first = model.model_validate(instance)
        except ValidationError:
            assume(False)
            raise
        dumped = first.model_dump(mode="json", by_alias=True)
        second = model.model_validate(dumped)
        assert first == second
        assert second.model_dump(mode="json", by_alias=True) == dumped

    check()


_VIOLATION = {
    "id": "model-003-i03-000000000000",
    "scene": "003",
    "invariant": 3,
    "evidence": {"quote": "A sentence of the draft.", "offset": 12},
    "severity": "blocking",
    "resolution": None,
    "source": "model",
}
"""A DR-07 violation as a file written before `explanation` existed would hold it."""


# spec 001 / AC 4 -- DR-07 `explanation` is optional: a record without it (every file written
# before the field existed) validates with it empty, a record with it keeps it through the
# round trip the store makes, a blank one is refused, and the exported schema does not require
# it.
def test_a_violation_validates_with_and_without_its_explanation() -> None:
    without = Violation.model_validate(_VIOLATION)
    assert without.explanation is None
    assert without.model_dump(mode="json", by_alias=True)["explanation"] is None

    reason = "The record rules this out and allows only what the body can do."
    carried = Violation.model_validate({**_VIOLATION, "explanation": reason})
    assert carried.explanation == reason
    dumped = carried.model_dump(mode="json", by_alias=True)
    assert Violation.model_validate(dumped) == carried
    assert ViolationsFile.model_validate({"violations": [_VIOLATION, dumped]}).violations == [
        without,
        carried,
    ]

    with pytest.raises(ValidationError):
        Violation.model_validate({**_VIOLATION, "explanation": ""})

    schema = Violation.model_json_schema()
    assert "explanation" in schema["properties"]
    assert "explanation" not in schema["required"]
