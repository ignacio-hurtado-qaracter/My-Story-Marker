"""L04 experiment (tuning iteration 1): does Lean catch an incoherence no other validator does?

Scratch experiment, never part of the pipeline. With the `b4-temporal` brief it:

1. calls the PLANNER once (at most `--attempts` times) exactly as `plan_novel` does, applies
   the same deterministic fixes (`_repair_plan`, `normalise_events`), and **skips** the
   chronology pre-check (`chronology_problems`) and the replan, until a plan whose
   chronology Lean rejects is found;
2. exports that plan's chronology and runs `verify_chronology` (Lean 4) and B4's
   `diagnose` on it — which invariants fail, on which events;
3. stores that plan as the novel's plan (so `generate` does not re-plan) and runs the real
   pipeline once with **no repair round** (`MAX_REPAIR_ROUNDS = 0`, patched here only), so
   every validator — programmatic, `judge_chapter`, `judge_novel`, `lean_chronology` —
   judges the same text at `chapter_close` and at the first `pre_publish`;
4. writes `evals/experiments/l04-b4-bypass.json` with the plan chronology, the Lean result
   and every validator's latest verdict.

Run from `backend/` (costs about one 3-chapter novel on Haiku):

    uv run python ../evals/experiments/l04_b4_bypass.py --db /abs/path/data/l04.sqlite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIEF = REPO_ROOT / "evals" / "briefs" / "b4-temporal.json"
OUT = Path(__file__).with_name("l04-b4-bypass.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="fresh scratch HARNESS_DB")
    parser.add_argument("--attempts", type=int, default=2, help="planner calls at most")
    parser.add_argument("--novel-id", default="l04-b4-bypass")
    parser.add_argument("--no-generate", action="store_true", help="stop after step 2")
    args = parser.parse_args(argv)
    db = args.db.resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    os.environ["HARNESS_DB"] = str(db)

    from app.bible import BibleRepository
    from app.formal import verify_chronology
    from app.novel import pipeline as p
    from app.novel import context as cx
    from app.novel._bible_ext import store_plan
    from app.novel.chronology import as_chronology, normalise_events, plan_births
    from app.novel.cli import _ingest
    from app.novel.plan_check import check_plan
    from app.validators.programmatic.chronology import diagnose

    record: dict[str, Any] = {"brief": str(BRIEF.relative_to(REPO_ROOT)), "attempts": []}
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))
    with BibleRepository.open(db) as repo:
        novel_id = _ingest(repo, brief, args.novel_id)
        p.setup_validators(repo, novel_id)
        run = p._make_run(repo, novel_id, None, None, lambda line: print(line, flush=True))
        facts = run.facts()
        documents = [
            cx.brief_document(run.brief),
            cx.facts_document(facts),
            cx.forbidden_document(run.forbidden()),
            cx.names_document(run.names()),
        ]
        known = [f.key for f in facts]
        known_births = {c.name: c.birth_date for c in repo.list_characters(novel_id)}
        chosen = None
        for attempt in range(1, args.attempts + 1):
            plan = run.roles.plan(documents, chapters=3)
            plan = p._repair_plan(plan, 3, known)
            births = plan_births(plan, known_births)
            plan = normalise_events(plan, births)
            chronology = as_chronology(plan, births)
            lean = verify_chronology(chronology, f"{novel_id}-plan{attempt}")
            entry = {
                "attempt": attempt,
                "plan_check": check_plan(
                    plan,
                    chapters=3,
                    mandatory_keys=[f.key for f in facts if f.mandatory],
                    known_keys=known,
                    exact_names=run.names(),
                ),
                "lean_passed": lean.passed,
                "lean_failed_invariants": lean.failed_invariants,
                "diagnose": diagnose(chronology),
                "events": chronology["events"],
            }
            record["attempts"].append(entry)
            print(f"attempt {attempt}: lean passed={lean.passed} {lean.failed_invariants}")
            if not lean.passed:
                chosen = plan
                break
        record["lean_caught_in_plan"] = chosen is not None
        if chosen is not None and not args.no_generate:
            store_plan(repo, novel_id, chosen)
            p.MAX_REPAIR_ROUNDS = 0  # scratch only: judge the first draft, no repair round
            result = p.generate(repo, novel_id, progress=lambda line: print(line, flush=True))
            record["generation"] = {"status": result.status, "detail": result.detail[:2000]}
            latest: dict[tuple[str, str, int | None], dict[str, Any]] = {}
            for r in repo.list_validator_results(novel_id):
                latest[(r.name, r.point, r.chapter)] = {
                    "name": r.name,
                    "point": r.point,
                    "chapter": r.chapter,
                    "passed": bool(r.passed),
                    "explanation": r.explanation[:600],
                }
            record["validators"] = sorted(
                latest.values(), key=lambda v: (v["point"], v["chapter"] or 0, v["name"])
            )
            record["chapters"] = [
                {"chapter": c.chapter, "title": c.title, "summary": c.summary}
                for c in repo.list_chapters(novel_id, 1)
            ]
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
