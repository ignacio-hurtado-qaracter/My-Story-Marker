"""Quick API-hardening pass over the FastAPI app (security review, programme 004).

Against a **temporary** story bible seeded with the dev novel (never `HARNESS_DB`), it
checks: CORS (a cross-origin preflight must not be granted), CSRF-style "simple" requests
(a `text/plain` POST must not be parsed as JSON), what error bodies reveal (404/422/500),
what `/health` reveals, and the PDF route with a hostile id.

    uv run python ../security/api_hardening_probe.py      # from backend/

The app's lifespan (store-root and embedder checks) is not entered: `TestClient` is used
without a `with` block, so no store tree is needed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.bible import BibleRepository
from app.main import create_app
from app.reader.dev_seed import NOVEL_ID, seed
from app.reader.router import get_bible_path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="msm-security-") as tmp:
        db = Path(tmp) / "api.sqlite"
        with BibleRepository.open(db) as repo:
            seed(repo)
        app = create_app()
        app.dependency_overrides[get_bible_path] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        out: dict[str, object] = {}

        pre = client.options(
            f"/novels/{NOVEL_ID}/changes",
            headers={"origin": "https://evil.example", "access-control-request-method": "POST"},
        )
        out["cors_preflight"] = {
            "status": pre.status_code,
            "allow_origin": pre.headers.get("access-control-allow-origin"),
        }
        simple = client.post(
            f"/novels/{NOVEL_ID}/changes",
            content=json.dumps({"request": "el perro se llama X", "fact_key": "nope"}),
            headers={"content-type": "text/plain", "origin": "https://evil.example"},
        )
        out["text_plain_post"] = {"status": simple.status_code, "body": simple.text[:160]}
        missing = client.get("/novels/nov-does-not-exist")
        out["404_body"] = missing.text[:200]
        bad_version = client.get(f"/novels/{NOVEL_ID}/versions/99999999999/chapters")
        out["422_huge_version"] = bad_version.status_code
        pdf = client.get("/novels/..%2F..%2Fetc%2Fpasswd/versions/1/pdf")
        out["pdf_hostile_id"] = pdf.status_code
        health = client.get("/health")
        out["health"] = {"status": health.status_code, "body": health.text[:300]}
        dup = client.post(
            "/interview/briefs",
            json={"brief": {"recipient": {"name": "x"}}, "novel_id": NOVEL_ID},
        )
        out["ingest_over_existing_novel"] = {"status": dup.status_code, "body": dup.text[:160]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
