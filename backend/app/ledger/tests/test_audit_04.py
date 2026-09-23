"""FR-AUD-03 -- invariant 4, spatial uniqueness. Golden on the fixture (README planted row 3)
and the edges: the same place is not a breach, and each double-booked character is one."""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import Scene, Severity, Violation
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 4


def findings(store: Store) -> dict[str, list[Violation]]:
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


def rewrite_scene(store: Store, identifier: str, **changes: object) -> None:
    relative = paths.scene(identifier)
    record = store.read(relative, Scene)
    store.write(
        relative,
        Scene.model_validate({**record.model_dump(), **changes}),
        role=AgentRole.ARCHITECT,
    )


# spec 001 / AC 15 -- README row 3: vance at 004 (vault) and 005 (gallery) at hour 318,
# blocking, reported against both members of the pair with the same evidence.
def test_the_planted_pair_is_blocking_on_both_scenes(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert {scene: [v.severity for v in hits] for scene, hits in found.items()} == {
        "004": [Severity.BLOCKING],
        "005": [Severity.BLOCKING],
    }
    quote = found["004"][0].evidence.quote
    assert quote == found["005"][0].evidence.quote
    assert quote.startswith(f"{paths.scene('004')} and {paths.scene('005')}: vance")
    assert found["004"][0].id != found["005"][0].id


# spec 001 / AC 15 -- the only story-time tie is the only finding (README rows 3 and 5).
def test_the_same_hour_in_the_same_place_is_not_a_breach(fixture_store: Store) -> None:
    rewrite_scene(fixture_store, "005", location="pump_vault")
    assert findings(fixture_store) == {}


# spec 001 / AC 15 -- one breach per character: ilan double-booked too is a second finding.
def test_each_double_booked_character_is_its_own_finding(fixture_store: Store) -> None:
    rewrite_scene(fixture_store, "005", participants=["vance", "ilan"])
    found = findings(fixture_store)
    for scene in ("004", "005"):
        people = sorted(v.evidence.quote.split(": ")[1].split(" ")[0] for v in found[scene])
        assert people == ["ilan", "vance"]
        assert all(v.severity is Severity.BLOCKING for v in found[scene])
