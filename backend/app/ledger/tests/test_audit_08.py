"""FR-AUD-06 -- invariant 8, no inert scenes, record half. Golden on the fixture (README
planted row 7) and the edges: empty and blank values, and a signed value passing."""

from __future__ import annotations

import pytest

from app.commons.permissions import AgentRole
from app.commons.schemas import Scene, Severity, Violation
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 8


def findings(store: Store) -> dict[str, list[Violation]]:
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


def with_value_change(store: Store, identifier: str, value: str) -> None:
    relative = paths.scene(identifier)
    record = store.read(relative, Scene).model_copy(update={"value_change": value})
    store.write(relative, record, role=AgentRole.ARCHITECT)


# spec 001 / AC 15 -- README row 7: 005's value_change is non-empty and unsigned, reviewable.
def test_the_unsigned_value_change_is_reviewable_at_005(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert list(found) == ["005"]
    [finding] = found["005"]
    assert finding.severity is Severity.REVIEWABLE
    assert finding.evidence.quote == f"{paths.scene('005')} value_change: authority over the vault"
    assert finding.evidence.offset == 0


# spec 001 / AC 15 -- an empty or blank value is reported too, with a readable quote.
@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_value_change_is_reported(fixture_store: Store, value: str) -> None:
    with_value_change(fixture_store, "002", value)
    [finding] = findings(fixture_store)["002"]
    assert finding.severity is Severity.REVIEWABLE
    assert finding.evidence.quote == f"{paths.scene('002')} value_change: (empty)"


# spec 001 / AC 15 -- once the sign is written, the scene is no longer reported.
@pytest.mark.parametrize("sign", ["(+)", "(-)"])
def test_a_signed_value_change_passes(fixture_store: Store, sign: str) -> None:
    with_value_change(fixture_store, "005", f"authority over the vault: held -> lost {sign}")
    assert findings(fixture_store) == {}
