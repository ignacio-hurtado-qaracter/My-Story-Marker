"""FR-AUD-07 -- invariant 9, recognisable voice. Golden on the fixture (README planted row 8)
and the edges: the POV's list only (Decision 13), typographic apostrophes, and an absent voice
profile skipped."""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import Draft, Severity, Violation
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene
from app.manuscript.service import measure_prose

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 9


def findings(store: Store) -> dict[str, list[Violation]]:
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


def write_draft(store: Store, identifier: str, body: str) -> None:
    measures = measure_prose(body)
    draft = Draft(
        scene_ref=identifier,
        words=measures.words,
        literal_tail=measures.literal_tail,
        body=body,
    )
    store.write(paths.draft(identifier), draft, role=AgentRole.WRITER)


# spec 001 / AC 15 -- README row 8: "Trust me" in Draft B, vance's list, reviewable.
def test_the_planted_line_is_found_in_draft_b(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert list(found) == ["003"]
    [finding] = found["003"]
    assert finding.severity is Severity.REVIEWABLE
    assert finding.evidence.quote == "Trust me"
    body = fixture_store.read(paths.draft("003"), Draft).body
    assert body[finding.evidence.offset :].startswith("Trust me")
    assert finding.evidence.offset == body.index("Trust me")


# spec 001 / AC 15 -- Draft A, POV ilan, contains none of ilan's never_says (the control).
def test_draft_a_is_clean_against_its_povs_list(fixture_store: Store) -> None:
    assert "002" not in findings(fixture_store)


# spec 001 / AC 15 -- Decision 13: only the POV's list; ilan's words in vance's scene pass.
def test_only_the_povs_list_is_searched(fixture_store: Store) -> None:
    write_draft(fixture_store, "004", '"Obviously," Ilan said. "It\'s fine. I remember."')
    assert "004" not in findings(fixture_store)


# spec 001 / AC 15 -- a typographic apostrophe does not hide the line; the quote keeps it.
def test_a_typographic_apostrophe_is_matched(fixture_store: Store) -> None:
    body = (
        "She did not look at him. \N{LEFT DOUBLE QUOTATION MARK}"
        "I\N{RIGHT SINGLE QUOTATION MARK}m sorry.\N{RIGHT DOUBLE QUOTATION MARK}"
    )
    write_draft(fixture_store, "004", body)
    [finding] = findings(fixture_store)["004"]
    assert finding.evidence.quote == "I\N{RIGHT SINGLE QUOTATION MARK}m sorry"
    assert body[finding.evidence.offset :].startswith(finding.evidence.quote)


# spec 001 / AC 15 -- a POV with no voice profile: the check is skipped and says so.
def test_an_absent_voice_profile_skips_the_check(fixture_store: Store) -> None:
    voice = paths.cast_file("vance", "voice")
    (fixture_store.root / voice).unlink()
    report = audit_scene(fixture_store, "003", semantic=False)
    assert [entry.check for entry in report.skipped] == ["FR-AUD-07"]
    assert voice in report.skipped[0].reason
    assert all(finding.invariant != INVARIANT for finding in report.violations)
