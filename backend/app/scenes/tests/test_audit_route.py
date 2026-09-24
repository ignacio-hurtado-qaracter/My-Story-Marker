"""IF-05, `POST /scenes/{id}/audit` -- the route over the audit (AC 15 on the wire).

The checks themselves are pinned in `app/ledger/tests/test_audit_*.py` and the write scope in
`test_audit_writes.py`. This file pins what a client of the route sees: the query defaults
(`semantic` true, `persist` false), the report's shape, the accounting of skipped checks, and
the errors at the edge.

Since plan step 17 the full audit (`semantic`, the default) runs the auditor role after the
mechanical checks (FR-AGENT-07), wired in by the app factory (`commons.deps.SemanticAuditor`).
The root `fixture_client` serves it with a fake model client that fails every unscripted call,
so by default the semantic halves come back in `skipped` with the failure as the reason
(FR-AUD-09); the tests that need the model to answer script their own fake.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.commons.deps import get_model_client, get_semantic_auditor
from app.commons.llm import ApiError, FakeModelClient, Reply
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    Evidence,
    SemanticAuditOutput,
    SemanticViolation,
    Severity,
    ViolationsFile,
)
from app.commons.stores import Store, paths
from app.manuscript import service as manuscript_service

SEMANTIC: list[tuple[str | int, ...]] = [
    ("FR-AUD-09", 1, "model"),
    ("FR-AUD-09", 3, "model"),
    ("FR-AUD-09", 6, "model"),
    ("FR-AUD-09", 8, "model"),
]
"""FR-AUD-09's four semantic halves, as the report lists them when they did not run."""


def served(client: TestClient) -> FastAPI:
    app = client.app
    assert isinstance(app, FastAPI)
    return app


Row = dict[str, str | int]


def model_skips(body: dict[str, list[Row]]) -> list[Row]:
    return [entry for entry in body["skipped"] if entry["source"] == "model"]


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
    served(fixture_client).dependency_overrides[get_semantic_auditor] = lambda: None
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


# spec 001 / AC 15 -- with no auditor wired, the reason says so.
def test_with_no_auditor_wired_the_semantic_half_is_skipped_as_before(
    fixture_client: TestClient,
) -> None:
    served(fixture_client).dependency_overrides[get_semantic_auditor] = lambda: None
    body = fixture_client.post("/scenes/003/audit").json()
    assert all("none is wired" in str(entry["reason"]) for entry in model_skips(body))


# spec 001 / AC 15 (skipped list), FR-AUD-09 -- the full audit route with a failing model: the
# mechanical findings are reported and the four semantic halves are listed as skipped.
def test_the_full_audit_with_a_failing_model_lists_the_semantic_halves(
    fixture_client: TestClient,
) -> None:
    fake = FakeModelClient({AgentRole.AUDITOR: [ApiError(status=500)]})
    served(fixture_client).dependency_overrides[get_model_client] = lambda: fake
    response = fixture_client.post("/scenes/003/audit")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["semantic"] is True
    assert [(v["invariant"], v["source"]) for v in body["violations"]] == [
        (5, "mechanical"),
        (7, "mechanical"),
        (9, "mechanical"),
    ]
    skipped = model_skips(body)
    assert [(e["check"], e["invariant"], e["source"]) for e in skipped] == SEMANTIC
    assert all("model step failed" in str(entry["reason"]) for entry in skipped)
    assert [ref["check"] for ref in body["checked"]].count("FR-AUD-09") == 0
    [call] = fake.calls
    assert call.role is AgentRole.AUDITOR


# spec 001 / AC 15 -- the default fake fails every unscripted call the same way: no test
# reaches the CLI through the route.
def test_the_default_fake_model_fails_unscripted_calls(fixture_client: TestClient) -> None:
    body = fixture_client.post("/scenes/003/audit").json()
    skipped = model_skips(body)
    assert [(e["check"], e["invariant"], e["source"]) for e in skipped] == SEMANTIC
    assert all("unscripted" in str(entry["reason"]) for entry in skipped)


# spec 001 / IF-05 -- `semantic=false` calls no model at all.
def test_the_mechanical_audit_calls_no_model(fixture_client: TestClient) -> None:
    fake = FakeModelClient()
    served(fixture_client).dependency_overrides[get_model_client] = lambda: fake
    assert fixture_client.post("/scenes/003/audit", params={"semantic": "false"}).status_code == 200
    assert fake.calls == []


# spec 001 / FR-AGENT-07, AC 16 -- a settled model step joins the report and, persisted under
# the auditor, the violations file, beside the mechanical findings.
def test_the_full_audit_reports_and_persists_the_model_findings(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    body_text = manuscript_service.read_draft(fixture_store, "003").body
    quote = body_text[300:340]
    finding = SemanticViolation(
        invariant=6,
        evidence=Evidence(quote=quote, offset=300),
        severity=Severity.BLOCKING,
        explanation="The prose sees in the dark the axiom keeps dark.",
    )
    fake = FakeModelClient([Reply.of(SemanticAuditOutput(violations=[finding]))])
    served(fixture_client).dependency_overrides[get_model_client] = lambda: fake
    response = fixture_client.post(
        "/scenes/003/audit",
        params={"persist": "true"},
        headers={"X-Agent-Role": "auditor"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    model = [v for v in body["violations"] if v["source"] == "model"]
    assert [(v["invariant"], v["evidence"], v["severity"]) for v in model] == [
        (6, {"quote": quote, "offset": 300}, "blocking")
    ]
    assert model[0]["id"].startswith("model-003-i06-")
    semantic_checks = [ref["invariant"] for ref in body["checked"] if ref["check"] == "FR-AUD-09"]
    assert semantic_checks == [1, 3, 6, 8]
    assert body["persisted"]["role"] == "auditor"
    on_disk = fixture_store.read(paths.VIOLATIONS, ViolationsFile).violations
    assert model[0]["id"] in {v.id for v in on_disk}
    assert "vi_002" in {v.id for v in on_disk}
    [call] = fake.calls
    assert call.role is AgentRole.AUDITOR
    assert any(document.path == "computed/mechanical-findings" for document in call.documents)
