"""AC 16 -- the audit writes only `ledger/violations.yaml`, only under the auditor role; any
other role is a 403 and a byte-identical tree.

Measured the way AC 2's integration half is measured: a hash of every path and every byte
under the store root, before and after. A system that wrote and rolled back would pass a test
that only looked at the final file; it would still have had the wrong bytes on disk. Per-file
hashes are kept as well, so "only violations.yaml changed" is a set equality rather than an
inference.

The second half pins the merge rules (`app.ledger.audit.persist`): resolved findings survive,
re-running does not duplicate, a finding that is gone is dropped only if its check ran, and
nothing the model-backed auditor wrote is touched.
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Evidence,
    Scene,
    Severity,
    Violation,
    ViolationResolution,
    ViolationsFile,
    ViolationSource,
)
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene, merge

AUDITOR = {"X-Agent-Role": "auditor"}
NOT_AUDITORS = [role for role in AgentRole if role is not AgentRole.AUDITOR]


def file_hashes(store: Store) -> dict[str, str]:
    """Every file under the store root, by store-relative path."""
    root = store.root
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def tree_hash(store: Store) -> str:
    """One hash over every path and every byte under the store root (as AC 2 measures it)."""
    root = store.root
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}


def violations(store: Store) -> list[Violation]:
    return store.read(paths.VIOLATIONS, ViolationsFile).violations


# --- write scope ----------------------------------------------------------------------


# spec 001 / AC 16 -- without persist nothing is written, even under the auditor.
def test_an_audit_without_persist_writes_nothing(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    before = tree_hash(fixture_store)
    for scene in ("001", "002", "003", "004", "005", "006"):
        response = fixture_client.post(f"/scenes/{scene}/audit", headers=AUDITOR)
        assert response.status_code == 200
        assert response.json()["persisted"] is None
    assert tree_hash(fixture_store) == before
    assert fixture_store.provenance() == []


# spec 001 / AC 16 -- persist under the auditor changes ledger/violations.yaml and nothing else.
def test_persist_under_the_auditor_changes_only_the_violations_file(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    before = file_hashes(fixture_store)
    response = fixture_client.post("/scenes/004/audit", params={"persist": "true"}, headers=AUDITOR)
    assert response.status_code == 200
    assert changed(before, file_hashes(fixture_store)) == {paths.VIOLATIONS}

    persisted = response.json()["persisted"]
    assert persisted["path"] == paths.VIOLATIONS
    assert persisted["role"] == "auditor"
    [line] = fixture_store.provenance()
    assert line.path == paths.VIOLATIONS
    assert line.role is AgentRole.AUDITOR


# spec 001 / AC 16 -- every other role is refused with 403, and the tree is byte-identical.
@pytest.mark.parametrize("role", NOT_AUDITORS, ids=lambda role: role.value)
def test_persist_under_any_other_role_is_403_and_changes_no_byte(
    fixture_client: TestClient, fixture_store: Store, role: AgentRole
) -> None:
    before = tree_hash(fixture_store)
    response = fixture_client.post(
        "/scenes/004/audit",
        params={"persist": "true"},
        headers={"X-Agent-Role": role.value},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "permission_denied"
    assert body["role"] == role.value
    assert body["path"] == paths.VIOLATIONS
    assert tree_hash(fixture_store) == before
    assert fixture_store.provenance() == []


# spec 001 / AC 16 -- a refused role is refused even when the merge would change nothing: the
# write is always attempted, so Figure 3 decides and a no-op cannot pass for permission.
@pytest.mark.parametrize("role", NOT_AUDITORS, ids=lambda role: role.value)
def test_a_no_op_persist_is_still_refused_to_other_roles(
    fixture_client: TestClient, fixture_store: Store, role: AgentRole
) -> None:
    before = tree_hash(fixture_store)
    response = fixture_client.post(
        "/scenes/002/audit",
        params={"persist": "true"},
        headers={"X-Agent-Role": role.value},
    )
    assert response.status_code == 403
    assert tree_hash(fixture_store) == before


# spec 001 / AC 16 -- persist without a role is a 400 before anything runs (IF-02).
def test_persist_without_a_role_is_400_and_changes_no_byte(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    before = tree_hash(fixture_store)
    response = fixture_client.post("/scenes/004/audit", params={"persist": "true"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_role"
    assert tree_hash(fixture_store) == before


# --- merge rules ----------------------------------------------------------------------


# spec 001 / AC 16 -- re-running does not duplicate: the second persist writes the same bytes.
def test_persisting_the_same_audit_twice_is_idempotent(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    fixture_client.post("/scenes/004/audit", params={"persist": "true"}, headers=AUDITOR)
    first = (fixture_store.root / paths.VIOLATIONS).read_bytes()
    fixture_client.post("/scenes/004/audit", params={"persist": "true"}, headers=AUDITOR)
    assert (fixture_store.root / paths.VIOLATIONS).read_bytes() == first
    ids = [finding.id for finding in violations(fixture_store)]
    assert len(ids) == len(set(ids))
    assert len([v for v in violations(fixture_store) if v.scene == "004"]) == 5


# spec 001 / AC 16 -- the fixture's prior report vi_002 is recognised, not duplicated, and the
# resolved vi_001 (model, scene 002) survives untouched.
def test_prior_reports_are_recognised_and_kept(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    original = {v.id: v for v in violations(fixture_store)}
    fixture_client.post("/scenes/003/audit", params={"persist": "true"}, headers=AUDITOR)
    merged = violations(fixture_store)
    assert merged[0] == original["vi_001"]
    assert merged[1] == original["vi_002"]
    lexicon = [v for v in merged if v.scene == "003" and v.invariant == 7]
    assert [v.id for v in lexicon] == ["vi_002"]
    assert sorted(v.invariant for v in merged if v.scene == "003") == [5, 7, 9]


# spec 001 / AC 16 -- a finding a human resolved survives re-audit, resolved, and is not
# raised again beside itself.
def test_a_resolved_finding_survives_and_is_not_raised_again(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    fixture_client.post("/scenes/003/audit", params={"persist": "true"}, headers=AUDITOR)
    current = violations(fixture_store)
    voice = next(v for v in current if v.scene == "003" and v.invariant == 9)
    settled = [
        v.model_copy(update={"resolution": ViolationResolution.ACCEPT_WITH_REASON})
        if v.id == voice.id
        else v
        for v in current
    ]
    ruling = fixture_client.put(
        "/ledger/violations",
        json=ViolationsFile(violations=settled).model_dump(mode="json"),
        headers={**AUDITOR, "X-Actor": "human"},
    )
    assert ruling.status_code == 200

    fixture_client.post("/scenes/003/audit", params={"persist": "true"}, headers=AUDITOR)
    again = [v for v in violations(fixture_store) if v.scene == "003" and v.invariant == 9]
    assert [(v.id, v.resolution) for v in again] == [
        (voice.id, ViolationResolution.ACCEPT_WITH_REASON)
    ]


# spec 001 / AC 16 -- a finding the scene no longer produces is dropped on the next persist.
def test_a_fixed_finding_is_dropped(fixture_client: TestClient, fixture_store: Store) -> None:
    fixture_client.post("/scenes/005/audit", params={"persist": "true"}, headers=AUDITOR)
    assert any(v.scene == "005" and v.invariant == 8 for v in violations(fixture_store))

    relative = paths.scene("005")
    fixed = fixture_store.read(relative, Scene).model_copy(
        update={"value_change": "authority over the vault: held -> slipping (-)"}
    )
    fixture_store.write(relative, fixed, role=AgentRole.ARCHITECT)

    fixture_client.post("/scenes/005/audit", params={"persist": "true"}, headers=AUDITOR)
    remaining = sorted(v.invariant for v in violations(fixture_store) if v.scene == "005")
    assert remaining == [2, 4, 5, 10]


# spec 001 / AC 16 -- a check that did not run vouches for nothing: its findings are kept.
def test_a_skipped_check_does_not_drop_its_findings(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    (fixture_store.root / paths.LEXICON).unlink()
    response = fixture_client.post("/scenes/003/audit", params={"persist": "true"}, headers=AUDITOR)
    assert "FR-AUD-05" in [entry["check"] for entry in response.json()["skipped"]]
    assert any(v.id == "vi_002" for v in violations(fixture_store))


# spec 001 / AC 16 -- persisting a scene leaves every other scene's findings and every
# model-sourced finding exactly as they were, in place.
def test_merge_touches_only_this_scenes_mechanical_findings(fixture_store: Store) -> None:
    def foreign(identifier: str, scene: str, source: ViolationSource) -> Violation:
        return Violation(
            id=identifier,
            scene=scene,
            invariant=6,
            evidence=Evidence(quote="The ring caught the lamp.", offset=12),
            severity=Severity.BLOCKING,
            resolution=None,
            source=source,
        )

    existing = ViolationsFile(
        violations=[
            foreign("vi_model_004", "004", ViolationSource.MODEL),
            foreign("vi_mech_001", "001", ViolationSource.MECHANICAL),
        ]
    )
    report = audit_scene(fixture_store, "004", semantic=False)
    merged = merge(existing, report)
    assert merged.violations[:2] == existing.violations
    assert merged.violations[2:] == report.violations


# spec 001 / AC 16 -- the severity of a reproduced finding follows the fresh audit (FR-AUD-02
# escalates when its scene becomes the last), and its id and position do not move.
def test_a_reproduced_finding_takes_the_fresh_severity(fixture_store: Store) -> None:
    report = audit_scene(fixture_store, "005", semantic=False)
    debt = next(v for v in report.violations if v.invariant == 2)
    stale = debt.model_copy(update={"id": "vi_hand_made", "severity": Severity.BLOCKING})
    merged = merge(ViolationsFile(violations=[stale]), report)
    assert merged.violations[0].id == "vi_hand_made"
    assert merged.violations[0].severity is Severity.REVIEWABLE
    assert [v.id for v in merged.violations].count(debt.id) == 0


# spec 001 / AC 16 -- merge rule 1: a resolved finding is kept exactly as the human left it,
# whether or not the fresh audit still reproduces it, and its severity is not overwritten.
def test_a_resolved_finding_is_kept_as_it_is_even_when_not_reproduced(
    fixture_store: Store,
) -> None:
    report = audit_scene(fixture_store, "005", semantic=False)
    inert = next(v for v in report.violations if v.invariant == 8)
    gone = inert.model_copy(
        update={
            "id": "vi_old_wording",
            "evidence": Evidence(quote=f"{paths.scene('005')} value_change: authority", offset=0),
            "resolution": ViolationResolution.FIX_PROSE,
        }
    )
    reproduced = inert.model_copy(
        update={
            "id": "vi_accepted",
            "severity": Severity.BLOCKING,
            "resolution": ViolationResolution.ACCEPT_WITH_REASON,
        }
    )
    merged = merge(ViolationsFile(violations=[gone, reproduced]), report)
    assert merged.violations[:2] == [gone, reproduced]
    assert [v.id for v in merged.violations].count(inert.id) == 0


# spec 001 / AC 16 -- the 403 does not depend on the state of the file: a forbidden role asking
# to persist over a broken `ledger/violations.yaml` is refused as forbidden, not as invalid.
@pytest.mark.parametrize("role", NOT_AUDITORS, ids=lambda role: role.value)
def test_a_forbidden_role_is_refused_before_a_broken_file_is_read(
    fixture_client: TestClient, fixture_store: Store, role: AgentRole
) -> None:
    (fixture_store.root / paths.VIOLATIONS).write_text("violations: [{id: 7}]\n", encoding="utf-8")
    before = tree_hash(fixture_store)
    response = fixture_client.post(
        "/scenes/004/audit",
        params={"persist": "true", "semantic": "false"},
        headers={"X-Agent-Role": role.value},
    )
    assert response.status_code == 403
    assert tree_hash(fixture_store) == before
