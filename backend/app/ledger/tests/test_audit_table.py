"""AC 15 as one table: the fixture README's "Expected mechanical audit output, scene by scene".

The per-invariant files (`test_audit_01.py` ... `test_audit_10.py`) pin each check and its
edges. This file pins the whole answer key at once, so a check that fired on a scene the
README keeps clean -- most importantly 002, the clean control, and 006, the tempting scene the
live run writes -- fails here even if its own golden test was written too narrowly. It also
pins the accounting that makes an empty answer mean something: `checked`, `skipped`, and the
FR-AUD-09 entries for the model-backed half.
"""

from __future__ import annotations

import re

import pytest

from app.commons.errors import InvalidRecord, NotFound
from app.commons.permissions import AgentRole
from app.commons.schemas import Draft, Scene, Severity, ViolationSource
from app.commons.stores import Store, paths
from app.ledger.audit import MECHANICAL_CHECKS, audit_scene

SCENES = ("001", "002", "003", "004", "005", "006")

B = Severity.BLOCKING
R = Severity.REVIEWABLE

EXPECTED: dict[str, list[tuple[int, Severity]]] = {
    "001": [(5, B)],
    "002": [],
    "003": [(5, B), (7, B), (9, R)],
    "004": [(1, B), (2, R), (4, B), (5, B), (10, R)],
    "005": [(2, R), (4, B), (5, B), (8, R), (10, R)],
    "006": [],
}
"""README, "Expected mechanical audit output, scene by scene", transcribed cell by cell."""

ALL_MECHANICAL = [check.check for check in MECHANICAL_CHECKS]
ID_GRAMMAR = re.compile(r"^mech-\d{3}-i\d{2}-[0-9a-f]{12}$")


# spec 001 / AC 15 -- the whole answer key, scene by scene, severity by severity.
def test_every_scene_matches_the_readme_table(fixture_store: Store) -> None:
    actual = {
        scene: sorted(
            (finding.invariant, finding.severity)
            for finding in audit_scene(fixture_store, scene, semantic=False).violations
        )
        for scene in SCENES
    }
    assert actual == EXPECTED


# spec 001 / AC 15 -- the clean control and the tempting scene produce nothing at all.
@pytest.mark.parametrize("scene", ["002", "006"])
def test_the_clean_scenes_report_nothing(fixture_store: Store, scene: str) -> None:
    report = audit_scene(fixture_store, scene, semantic=False)
    assert report.violations == []


# spec 001 / AC 15 -- 002 is clean *and every check ran on it*: silence earned, not assumed.
def test_the_clean_control_ran_every_mechanical_check(fixture_store: Store) -> None:
    report = audit_scene(fixture_store, "002", semantic=False)
    assert [ref.check for ref in report.checked] == ALL_MECHANICAL
    assert report.skipped == []


# spec 001 / AC 15 -- every finding is mechanical, unresolved, and carries its evidence.
def test_every_finding_is_a_mechanical_unresolved_report(fixture_store: Store) -> None:
    for scene in SCENES:
        for finding in audit_scene(fixture_store, scene, semantic=False).violations:
            assert finding.source is ViolationSource.MECHANICAL
            assert finding.resolution is None
            assert finding.scene == scene
            assert finding.evidence.quote


# spec 001 / AC 15 -- a scene without a draft skips the two text checks and says so.
@pytest.mark.parametrize("scene", ["001", "004", "005", "006"])
def test_a_scene_with_no_draft_lists_the_text_checks_as_skipped(
    fixture_store: Store, scene: str
) -> None:
    report = audit_scene(fixture_store, scene, semantic=False)
    skipped = {entry.check: entry for entry in report.skipped}
    assert set(skipped) == {"FR-AUD-05", "FR-AUD-07"}
    for entry in skipped.values():
        assert entry.source is ViolationSource.MECHANICAL
        assert paths.draft(scene) in entry.reason
    ran = [ref.check for ref in report.checked]
    assert ran == [check for check in ALL_MECHANICAL if check not in skipped]


# spec 001 / AC 15 -- FR-AUD-09: requesting the semantic half, which cannot run yet, lists it.
def test_the_semantic_half_is_listed_as_skipped_when_requested(fixture_store: Store) -> None:
    report = audit_scene(fixture_store, "003", semantic=True)
    semantic = [entry for entry in report.skipped if entry.source is ViolationSource.MODEL]
    assert [(entry.check, entry.invariant) for entry in semantic] == [
        ("FR-AUD-09", 1),
        ("FR-AUD-09", 3),
        ("FR-AUD-09", 6),
        ("FR-AUD-09", 8),
    ]
    assert all("plan step 17" in entry.reason for entry in semantic)
    assert report.semantic is True


# spec 001 / AC 15 -- asked for the mechanical half only, nothing is listed for the other.
def test_the_mechanical_only_audit_lists_no_semantic_skips(fixture_store: Store) -> None:
    report = audit_scene(fixture_store, "003", semantic=False)
    assert report.skipped == []
    assert report.semantic is False


# spec 001 / AC 15, AC 16 -- the same finding has the same id on every run, and ids are unique.
def test_violation_ids_are_deterministic_and_unique(fixture_store: Store) -> None:
    for scene in SCENES:
        first = [v.id for v in audit_scene(fixture_store, scene, semantic=False).violations]
        second = [v.id for v in audit_scene(fixture_store, scene, semantic=False).violations]
        assert first == second
        assert len(set(first)) == len(first)
        assert all(ID_GRAMMAR.fullmatch(identifier) for identifier in first)


# spec 001 / AC 15 -- DR-07 evidence: draft spans point at the draft; record evidence cannot.
def test_draft_evidence_is_a_span_and_record_evidence_names_its_record(
    fixture_store: Store,
) -> None:
    body = fixture_store.read(paths.draft("003"), Draft).body
    report = audit_scene(fixture_store, "003", semantic=False)
    text_checks = {7, 9}
    for finding in report.violations:
        quote, offset = finding.evidence.quote, finding.evidence.offset
        if finding.invariant in text_checks:
            assert body[offset : offset + len(quote)] == quote
        else:
            assert offset == 0
            assert quote.startswith(("scenes/", "cast/", "ledger/", "canon/"))
            assert body[offset : offset + len(quote)] != quote


# spec 001 / AC 15 -- an audit of a scene with no record has no answer, not an empty one.
def test_auditing_a_scene_with_no_record_is_not_found(fixture_store: Store) -> None:
    with pytest.raises(NotFound):
        audit_scene(fixture_store, "999", semantic=False)


# spec 001 / AC 15 -- a draft that names another scene stops the audit: its evidence would be
# filed under the wrong scene (DR-08), and an audit that narrowed itself would read as clean.
def test_a_draft_naming_another_scene_is_refused(fixture_store: Store) -> None:
    draft = fixture_store.read(paths.draft("003"), Draft)
    fixture_store.write(
        paths.draft("004"), draft.model_copy(update={"scene_ref": "003"}), role=AgentRole.WRITER
    )
    with pytest.raises(InvalidRecord) as refused:
        audit_scene(fixture_store, "004", semantic=False)
    assert refused.value.context["file"] == paths.draft("004")


# spec 001 / AC 15 -- a scene file whose record names another id stops the audit of every
# scene: the book-wide checks (4, 5, 10) would otherwise run over a misfiled record.
def test_a_scene_record_filed_under_another_id_is_refused(fixture_store: Store) -> None:
    record = fixture_store.read(paths.scene("006"), Scene)
    fixture_store.write(
        paths.scene("007"), record.model_copy(update={"id": "006"}), role=AgentRole.ARCHITECT
    )
    with pytest.raises(InvalidRecord) as refused:
        audit_scene(fixture_store, "002", semantic=False)
    assert refused.value.context["file"] == paths.scene("007")
