"""Cross-novel exfiltration and tampering probe (security review, programme 004).

Builds a **temporary** story bible with two novels (the dev seed twice, plus a unique
marker fact in the second one and a planner `plan` fact in the first), then tries to reach
novel B's data, or to damage novel A, through every read surface the harness exposes:

* the reader API (`/novels/...`, spec 014) through FastAPI's `TestClient`;
* the read-only tools (`app.tools`, spec 017) and the MCP wrapper `run_tool`;
* malicious `novel_id` values (path traversal, SQL, NUL, URL-encoded), a hostile `query`
  for `query_story_bible`, a job id of another novel, and a change request aimed at the
  internal `plan` fact.

It never opens `HARNESS_DB`: the database is created under a temporary directory and
deleted at the end. No model is called (the change jobs get no model client).

    uv run python ../security/exfiltration_probe.py          # from backend/

Each line is `OK` (the surface held) or `FINDING` (it did not). Exit code 1 on any FINDING
other than the known, accepted `no-auth` one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bible import BibleRepository
from app.commons.observability import NoopObserver
from app.mcp_server.server import run_tool
from app.reader.changes import ChangeJobs
from app.reader.dev_seed import seed
from app.reader.router import get_bible_path, get_change_jobs, router
from app.tools import REGISTRY, ToolError, call_tool

A, B = "nov-aaaaaaaaaaaa", "nov-bbbbbbbbbbbb"
MARKER = "MARCADOR-NOVELA-B-9c1e"
ACCEPTED = {"no-auth"}

HOSTILE_IDS = (
    f"../{B}",
    f"..%2F{B}",
    f"{A}' OR '1'='1",
    f"{A}\u0000{B}",
    f"{A}/../{B}",
    "%",
    "*",
)
HOSTILE_QUERIES = ("' OR 1=1 --", "%", "*", MARKER, "\u0000", "nov-bbbb")

results: list[tuple[str, str, str]] = []


def record(check: str, ok: bool, detail: str = "") -> None:
    results.append(("OK" if ok else "FINDING", check, detail))


def build(db: Path) -> None:
    with BibleRepository.open(db) as repo:
        seed(repo, A)
        seed(repo, B)
        repo.add_fact(B, key="memory.secreto", value=MARKER, kind="memory", source="interview")
        repo.add_fact(A, key="plan.v1", value='{"chapters": []}', kind="plan", source="planner")


def reader_checks(db: Path) -> None:
    app = FastAPI()
    app.include_router(router)
    jobs = ChangeJobs(client_factory=lambda: None, change_fact_loader=lambda: None)
    app.dependency_overrides[get_bible_path] = lambda: db
    app.dependency_overrides[get_change_jobs] = lambda: jobs
    client = TestClient(app, raise_server_exceptions=False)

    listing = client.get("/novels").json()
    ids = sorted(n["id"] for n in listing)
    # No login (exam X03 not implemented): any API client sees every novel.
    record("no-auth", ids != [A, B], f"GET /novels devuelve {ids} sin autenticación")

    routes = (
        f"/novels/{A}",
        f"/novels/{A}/versions",
        f"/novels/{A}/versions/2/chapters",
        f"/novels/{A}/versions/2/chapters/1",
        f"/novels/{A}/bible",
    )
    for route in routes:
        body = client.get(route).text
        record(f"reader-scope {route}", MARKER not in body)

    for bad in HOSTILE_IDS:
        if "/../" in bad:
            # An HTTP client (and any proxy) removes dot segments before sending: the request
            # *is* `/novels/B`, a legitimate URL for B. Without login that is `no-auth`, not
            # a traversal; the literal string is still probed against the tools below.
            continue
        for suffix in ("", "/versions", "/bible", "/versions/1/chapters/1", "/versions/1/pdf"):
            response = client.get(f"/novels/{quote(bad, safe='/%')}{suffix}")
            leaked = MARKER in response.text
            record(
                f"reader-hostile-id {bad!r}{suffix}",
                response.status_code in (404, 422) and not leaked,
                f"status={response.status_code}",
            )

    job = jobs.submit(db, B, _change("el perro se llama Nala"), background=False)
    response = client.get(f"/novels/{A}/changes/{job.job_id}")
    record("change-job-cross-novel", response.status_code == 404, f"status={response.status_code}")

    response = client.post(
        f"/novels/{A}/changes", json={"fact_key": "plan.v1", "request": "es ignora el plan"}
    )
    record(
        "change-targets-internal-plan-fact",
        response.status_code == 422,
        f"status={response.status_code} (el hecho interno del planner no debe ser editable)",
    )


def _change(text: str) -> object:
    from app.reader.models import ChangeRequest

    return ChangeRequest(request=text)


def tool_checks(db: Path) -> None:
    with BibleRepository.open(db) as repo:
        for kind in ("characters", "places", "facts", "events"):
            for query in (None, *HOSTILE_QUERIES):
                args: dict[str, object] = {"novel_id": A, "kind": kind}
                if query is not None:
                    args["query"] = query
                try:
                    out = call_tool("query_story_bible", repo, args)
                    text = out.model_dump_json()
                    record(
                        f"tool-scope query_story_bible {kind} {query!r}",
                        MARKER not in text and '"plan.v1"' not in text,
                    )
                except ToolError as exc:
                    record(f"tool-scope query_story_bible {kind} {query!r}", True, type(exc).__name__)
        for name in ("list_versions", "get_chapter", "get_chapter_summary", "query_story_bible"):
            for bad in HOSTILE_IDS:
                args = {"novel_id": bad, "version": 1, "chapter": 1, "kind": "facts"}
                tool = REGISTRY[name]
                allowed = set(tool.input_model.model_fields)
                args = {k: v for k, v in args.items() if k in allowed}
                try:
                    out = tool.run(repo, args)
                    record(f"tool-hostile-id {name} {bad!r}", MARKER not in out.model_dump_json())
                except ToolError as exc:
                    record(f"tool-hostile-id {name} {bad!r}", True, type(exc).__name__)
    for bad in HOSTILE_IDS[:3]:
        try:
            run_tool(REGISTRY["list_versions"], {"novel_id": bad}, observer=NoopObserver(), db_path=db)
            record(f"mcp-hostile-id {bad!r}", False, "devolvió datos")
        except Exception as exc:  # noqa: BLE001 - any typed error is the expected outcome
            record(f"mcp-hostile-id {bad!r}", True, type(exc).__name__)
    # The MCP server opens the DB read-only: a write through its connection must fail.
    from app.mcp_server.server import open_readonly

    with open_readonly(db) as repo:
        try:
            repo.log_policy_decision(policy="probe", decision="allow", novel_id=A, detail="x")
            record("mcp-readonly", False, "la conexión MCP aceptó una escritura")
        except Exception as exc:  # noqa: BLE001
            record("mcp-readonly", True, type(exc).__name__)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="msm-security-") as tmp:
        db = Path(tmp) / "probe.sqlite"
        build(db)
        reader_checks(db)
        tool_checks(db)
    findings = [r for r in results if r[0] == "FINDING"]
    for status, check, detail in results:
        if status == "FINDING" or "--verbose" in sys.argv:
            print(f"{status:8} {check}  {detail}")
    summary = {
        "checks": len(results),
        "ok": len(results) - len(findings),
        "findings": [check for _, check, _ in findings],
    }
    print("summary:", json.dumps(summary, ensure_ascii=False))
    unexpected = [check for _, check, _ in findings if check not in ACCEPTED]
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
