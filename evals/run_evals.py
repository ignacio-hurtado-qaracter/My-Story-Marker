"""Run the eval briefs through the harness and tabulate the validators (spec 015, EV1-EV2).

    cd backend
    uv run python ../evals/run_evals.py [--only b2-infantil,b3-injection] [--chapters N]
                                        [--db PATH] [--label before|after] [--jobs 3]
                                        [--timeout SECONDS] [--collect-only]

For each brief in `evals/briefs/`:

1. validate it with `app.interview.brief.validate_brief` (the interviewer's rules);
2. if it is valid, run the generation CLI as a subprocess
   (`python -m app.novel.cli generate --brief P --novel-id eval-<label>-<brief>`) with
   `HARNESS_DB` pointing at `--db`, under a per-brief timeout;
3. read back, through `BibleRepository`, the validator results (latest row per validator,
   chapter and scene), the policy decisions, the cost summary, the prompt versions and the
   status of the latest version.

It writes `evals/results/<label>/<brief>.json`, `evals/results/<label>/table.md` and the
index `evals/results.md` (the table of the last label run). The harness only reads the
database; every write is the pipeline's. A validator with no row is shown as `—`; a
pipeline that is not installed yet is recorded as `pipeline_unavailable`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os

# Runs our own CLI with a fixed argument list and no shell.
import subprocess  # nosec B404
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
BRIEFS_DIR = EVALS_DIR / "briefs"
RESULTS_DIR = EVALS_DIR / "results"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MAX_JOBS = 3
DEFAULT_TIMEOUT_S = 45 * 60
INJECTION_POLICY = "free_text_injection"

# Table column -> validator names that may carry it (the first one with rows wins).
COLUMNS: dict[str, tuple[str, ...]] = {
    "brief_schema": ("brief_schema", "schema_brief"),
    "forbidden_words_scene": ("forbidden_words_scene",),
    "forbidden_words_chapter": ("forbidden_words_chapter",),
    "chapter_length": ("chapter_length",),
    "exact_names": ("exact_names",),
    "brief_coverage": ("brief_coverage",),
    "prose_repetition": ("prose_repetition",),
    "judge_chapter": ("judge_chapter",),
    "judge_novel": ("judge_novel",),
    "lean_chronology": ("lean_chronology",),
    "visual_check": ("visual_check",),
}

# What each brief is designed to show (evals/README.md explains why).
EXPECTED: dict[str, str] = {
    "ejemplo": "published; every validator ✅",
    "b2-infantil": "published; child-safe tone, 3 chapters",
    "b3-injection": "injection flagged; forbidden terms absent; story unchanged",
    "b4-temporal": "lean_chronology or judge_novel catch the planted incoherences",
    "b5-contradiction": "rejected by brief validation (age x genre/tone, missing length)",
}

PASS, FAIL, NONE, FLAG = "✅", "❌", "—", "⚑"


@dataclass(frozen=True)
class Options:
    label: str
    db: Path
    chapters: int | None
    timeout_s: int
    collect_only: bool


def say(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def novel_id_for(label: str, brief: str) -> str:
    return f"eval-{label}-{brief}"


def load_brief(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def validate(data: dict[str, Any]) -> dict[str, Any]:
    from app.interview.brief import validate_brief

    return validate_brief(data).model_dump()


def prescan(data: dict[str, Any]) -> list[str]:
    """Deterministic injection markers of the brief's free text (no model call)."""
    text = data.get("free_text") or ""
    if not text.strip():
        return []
    from app.interview.extract import prescan_injection

    return list(prescan_injection(text).markers)


def pipeline_available() -> bool:
    try:
        return importlib.util.find_spec("app.novel.cli") is not None
    except ModuleNotFoundError:
        return False


def generate_cmd(brief_path: Path, novel_id: str, chapters: int | None) -> list[str]:
    """The one place that knows the pipeline CLI's flags (plan 015, risks)."""
    cmd = [
        sys.executable,
        "-m",
        "app.novel.cli",
        "generate",
        "--brief",
        str(brief_path),
        "--novel-id",
        novel_id,
    ]
    if chapters is not None:
        cmd += ["--chapters", str(chapters)]
    return cmd


def run_generation(brief_path: Path, novel_id: str, opts: Options, log: Path) -> dict[str, Any]:
    env = {**os.environ, "HARNESS_DB": str(opts.db)}
    cmd = generate_cmd(brief_path, novel_id, opts.chapters)
    started = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as out:
        out.write("$ " + " ".join(cmd) + "\n")
        out.flush()
        try:
            proc = subprocess.run(  # nosec B603
                cmd,
                cwd=BACKEND_DIR,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=opts.timeout_s,
                check=False,
            )
            code: int | None = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            code, timed_out = None, True
    return {
        "command": cmd,
        "exit_code": code,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 1),
        "log": str(log.relative_to(REPO_ROOT)),
    }


def _latest_by_unit(rows: list[Any]) -> dict[str, list[Any]]:
    """name -> latest row per (chapter, scene): retries are superseded by the last run."""
    latest: dict[tuple[str, int | None, int | None], Any] = {}
    for row in sorted(rows, key=lambda r: r.id):
        latest[(row.name, row.chapter, row.scene)] = row
    grouped: dict[str, list[Any]] = {}
    for (name, _, _), row in latest.items():
        grouped.setdefault(name, []).append(row)
    return grouped


def collect(novel_id: str, db: Path) -> dict[str, Any]:
    """Read everything the table needs. Never writes."""
    if not db.exists():
        return {"db_found": False}
    from app.bible.repository import BibleRepository

    with BibleRepository.open(db) as repo:
        version = repo.latest_version(novel_id)
        rows = repo.list_validator_results(novel_id)
        if version is not None:
            # Rows of older versions are history; rows with no version (brief_schema) stay.
            rows = [r for r in rows if r.version in (None, version.version)]
        grouped = _latest_by_unit(rows)
        validators: dict[str, Any] = {}
        for name, latest in grouped.items():
            all_rows = [r for r in rows if r.name == name]
            validators[name] = {
                "passed": all(r.passed for r in latest),
                "units": len(latest),
                "failed_units": [
                    {"chapter": r.chapter, "scene": r.scene, "explanation": r.explanation}
                    for r in latest
                    if not r.passed
                ],
                "rows_total": len(all_rows),
                "rows_failed": sum(1 for r in all_rows if not r.passed),
                "min_score": min((r.score for r in latest if r.score is not None), default=None),
            }
        decisions = repo.list_policy_decisions(novel_id)
        policy: dict[str, dict[str, int]] = {}
        for d in decisions:
            policy.setdefault(d.policy, {}).setdefault(d.decision, 0)
            policy[d.policy][d.decision] += 1
        injection = [
            {"decision": d.decision, "detail": d.detail}
            for d in decisions
            if d.policy == INJECTION_POLICY
        ]
        cost = repo.cost_summary(novel_id).model_dump(mode="json")
        prompts = [
            {"role": r[0], "prompt_name": r[1], "prompt_version": r[2], "calls": r[3]}
            for r in repo.connection.execute(
                "select role, prompt_name, prompt_version, count(*) from llm_call "
                "where novel_id = ? group by role, prompt_name, prompt_version "
                "order by role, prompt_name, prompt_version",
                (novel_id,),
            ).fetchall()
        ]
        final: dict[str, Any] | None = None
        if version is not None:
            chapters = repo.list_chapters(novel_id, version.version)
            final = {
                "version": version.version,
                "status": version.status,
                "repair_rounds": version.repair_rounds,
                "note": version.note,
                "chapters": len(chapters),
                "words": [c.word_count for c in chapters],
            }
    return {
        "db_found": True,
        "validators": validators,
        "policy": policy,
        "injection_decisions": injection,
        "cost": cost,
        "prompts": prompts,
        "final": final,
    }


def evaluate(brief_path: Path, opts: Options) -> dict[str, Any]:
    name = brief_path.stem
    novel_id = novel_id_for(opts.label, name)
    data = load_brief(brief_path)
    report = validate(data)
    result: dict[str, Any] = {
        "brief": name,
        "label": opts.label,
        "novel_id": novel_id,
        "expected": EXPECTED.get(name, ""),
        "chapters_requested": opts.chapters or (data.get("length") or {}).get("chapters"),
        "validation": report,
        "injection_prescan": prescan(data),
        "has_free_text": bool((data.get("free_text") or "").strip()),
        "forbidden_terms": data.get("forbidden_terms", []),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "generation": None,
    }
    if not report["valid"]:
        result["outcome"] = "rejected_by_validation"
    elif opts.collect_only:
        result["outcome"] = "collected"
    elif not pipeline_available():
        result["outcome"] = "pipeline_unavailable"
    else:
        log = RESULTS_DIR / opts.label / "logs" / f"{name}.log"
        gen = run_generation(brief_path, novel_id, opts, log)
        result["generation"] = gen
        if gen["timed_out"]:
            result["outcome"] = "timeout"
        else:
            result["outcome"] = "ok" if gen["exit_code"] == 0 else "pipeline_error"
    result.update(collect(novel_id, opts.db) if report["valid"] else {"db_found": None})
    return result


# ---------------------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------------------


def cell(result: dict[str, Any], column: str) -> str:
    validators: dict[str, Any] = result.get("validators") or {}
    for name in COLUMNS[column]:
        if name in validators:
            return PASS if validators[name]["passed"] else FAIL
    if column == "brief_schema":
        return PASS if result["validation"]["valid"] else FAIL
    return NONE


def injection_cell(result: dict[str, Any]) -> str:
    if not result["has_free_text"]:
        return NONE
    stored = [d["decision"] for d in result.get("injection_decisions") or []]
    if any(d in ("flag", "reject") for d in stored) or result["injection_prescan"]:
        return FLAG
    return PASS


def final_status(result: dict[str, Any]) -> str:
    final = result.get("final")
    if final:
        return f"{final['status']} v{final['version']}"
    return str(result["outcome"])


def render_table(results: list[dict[str, Any]], label: str) -> str:
    columns = [*COLUMNS, "injection"]
    head = ["brief", *columns, "final", "cost USD", "tokens in/out"]
    lines = [
        f"# Eval results — `{label}`",
        "",
        (
            f"Generated {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} by "
            "`evals/run_evals.py`. ✅ passed (latest run of every chapter/scene) · ❌ failed · "
            "— no result recorded · ⚑ injection flagged (treated as data only)."
        ),
        "",
        "| " + " | ".join(head) + " |",
        "|" + "|".join("---" for _ in head) + "|",
    ]
    for r in results:
        cost = r.get("cost") or {}
        row = [
            f"`{r['brief']}`",
            *(cell(r, c) for c in COLUMNS),
            injection_cell(r),
            final_status(r),
            f"{cost.get('cost_usd', 0):.4f}" if cost else NONE,
            f"{cost.get('input_tokens', 0)}/{cost.get('output_tokens', 0)}" if cost else NONE,
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Expected per brief", ""]
    for r in results:
        lines.append(f"- `{r['brief']}` — {r['expected']} → outcome `{r['outcome']}`.")
    failures = [
        (r["brief"], name, u)
        for r in results
        for name, v in (r.get("validators") or {}).items()
        for u in v["failed_units"]
    ]
    if failures:
        lines += ["", "## Failures (latest run)", ""]
        for brief, name, unit in failures:
            where = f"ch {unit['chapter']}" + (f" sc {unit['scene']}" if unit["scene"] else "")
            text = " ".join(str(unit["explanation"]).split())[:200]
            lines.append(f"- `{brief}` · `{name}` · {where}: {text}")
    rejected = [r for r in results if not r["validation"]["valid"]]
    if rejected:
        lines += ["", "## Rejected by brief validation", ""]
        for r in rejected:
            v = r["validation"]
            reasons = v["missing"] + v["contradictions"] + v["errors"]
            lines.append(f"- `{r['brief']}`: " + "; ".join(reasons))
    return "\n".join(lines) + "\n"


def brief_order(path: Path) -> tuple[int, str]:
    """The example first, then b2..b5."""
    return (0 if path.stem == "ejemplo" else 1, path.stem)


def select_briefs(only: str | None) -> list[Path]:
    paths = sorted(BRIEFS_DIR.glob("*.json"), key=brief_order)
    if not only:
        return paths
    wanted = [w.strip() for w in only.split(",") if w.strip()]

    def matches(path: Path, word: str) -> bool:
        return path.stem == word or path.stem.startswith(word + "-")

    chosen = [p for p in paths if any(matches(p, w) for w in wanted)]
    unknown = [w for w in wanted if not any(matches(p, w) for p in paths)]
    if unknown:
        raise SystemExit(f"unknown brief(s): {', '.join(unknown)}")
    return chosen


def default_db() -> Path:
    try:
        from app.commons.config import get_settings

        return Path(get_settings().harness_db_path)
    except Exception:  # settings are optional for --help and validate-only runs
        return REPO_ROOT / "data" / "harness.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", help="comma-separated brief names or prefixes (b2,b3)")
    parser.add_argument("--chapters", type=int, help="override length.chapters for every run")
    parser.add_argument("--db", type=Path, help="HARNESS_DB for the runs (default: settings)")
    parser.add_argument("--label", default="before", help="iteration label (before|after|…)")
    parser.add_argument("--jobs", type=int, default=MAX_JOBS, help=f"parallel runs, ≤{MAX_JOBS}")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="seconds per brief")
    parser.add_argument(
        "--collect-only", action="store_true", help="do not generate; re-read the database"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.label.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("--label must be alphanumeric (dashes and underscores allowed)")
    opts = Options(
        label=args.label,
        db=(args.db or default_db()).resolve(),
        chapters=args.chapters,
        timeout_s=args.timeout,
        collect_only=args.collect_only,
    )
    briefs = select_briefs(args.only)
    out_dir = RESULTS_DIR / opts.label
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = max(1, min(args.jobs, MAX_JOBS))
    say(f"[evals] label={opts.label} db={opts.db} briefs={[p.stem for p in briefs]} jobs={jobs}")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda p: evaluate(p, opts), briefs))
    for r in results:
        path = out_dir / f"{r['brief']}.json"
        path.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        say(f"[evals] {r['brief']}: {r['outcome']} -> {path.relative_to(REPO_ROOT)}")
    # The table covers every brief of the label on disk, not only the ones run now.
    all_results = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(out_dir.glob("*.json"), key=brief_order)
    ]
    table = render_table(all_results, opts.label)
    (out_dir / "table.md").write_text(table, encoding="utf-8")
    (EVALS_DIR / "results.md").write_text(table, encoding="utf-8")
    say(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
