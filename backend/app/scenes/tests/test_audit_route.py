"""IF-05, `POST /scenes/{id}/audit` -- the route over the mechanical audit (AC 15 on the wire).

The checks themselves are pinned in `app/ledger/tests/test_audit_*.py` and the write scope in
`test_audit_writes.py`. This file pins what a client of the route sees: the query defaults
(`semantic` true, `persist` false), the report's shape, the accounting of skipped checks, and
the errors at the edge.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


# spec 001 / AC 15 -- the mechanical audit of 003 over HTTP: the README's row, and its evidence.
def test_the_mechanical_audit_answers_the_readme_row(fixture_client: TestClient) -> None:
    response = fixture_client.post("/scenes/003/audit", params={"semantic": "false"})
    assert response.status_code == 200
    body = response.json()
    assert body["scene"] == "003"
    assert body["semantic"] is False
    assert [(v["invariant"], v["severity"]) for v in body["violations"]] == [
        (5, "blocking"),
        (7, "blocking"),
        (9, "reviewable"),
    ]
    lexicon = body["violations"][1]
    assert lexicon["evidence"] == {"quote": "readkey", "offset": 2403}
    assert lexicon["source"] == "mechanical"
    assert lexicon["resolution"] is None
    assert body["skipped"] == []
    assert len(body["checked"]) == 8
    assert body["persisted"] is None


# spec 001 / AC 15 -- the clean control over HTTP: nothing found, every check listed as run.
def test_the_clean_control_answers_nothing(fixture_client: TestClient) -> None:
    body = fixture_client.post("/scenes/002/audit", params={"semantic": "false"}).json()
    assert body["violations"] == []
    assert [ref["check"] for ref in body["checked"]] == [
        "FR-AUD-01",
        "FR-AUD-02",
        "FR-AUD-03",
        "FR-AUD-04",
        "FR-AUD-05",
        "FR-AUD-06",
        "FR-AUD-07",
        "FR-AUD-08",
    ]


# spec 001 / AC 15 -- `semantic` defaults to true, and the half that cannot run is skipped.
def test_semantic_defaults_to_true_and_lists_the_model_half(fixture_client: TestClient) -> None:
    body = fixture_client.post("/scenes/002/audit").json()
    assert body["semantic"] is True
    assert body["violations"] == []
    assert [(entry["check"], entry["invariant"], entry["source"]) for entry in body["skipped"]] == [
        ("FR-AUD-09", 1, "model"),
        ("FR-AUD-09", 3, "model"),
        ("FR-AUD-09", 6, "model"),
        ("FR-AUD-09", 8, "model"),
    ]


# spec 001 / AC 15 -- a scene with no draft lists its text checks as skipped, with the reason.
def test_a_scene_without_a_draft_reports_its_skipped_text_checks(
    fixture_client: TestClient,
) -> None:
    body = fixture_client.post("/scenes/006/audit", params={"semantic": "false"}).json()
    assert body["violations"] == []
    assert [entry["check"] for entry in body["skipped"]] == ["FR-AUD-05", "FR-AUD-07"]
    assert all("manuscript/006.md" in entry["reason"] for entry in body["skipped"])


# spec 001 / AC 15 -- no role is needed to read: without persist the route writes nothing.
def test_reading_needs_no_role(fixture_client: TestClient) -> None:
    response = fixture_client.post("/scenes/004/audit", params={"semantic": "false"})
    assert response.status_code == 200
    assert len(response.json()["violations"]) == 5


# spec 001 / AC 15 -- a scene with no record is a 404, a malformed id a 422 (IF-07).
def test_the_edge_errors(fixture_client: TestClient) -> None:
    missing = fixture_client.post("/scenes/999/audit")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"
    assert fixture_client.post("/scenes/abc/audit").status_code == 422
