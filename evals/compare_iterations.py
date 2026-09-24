"""Compare two eval iterations and write `evals/results/tuning.md` (spec 015, EV3).

    cd backend
    uv run python ../evals/compare_iterations.py before after \
        [--change "writer.md v3 -> v4: …"] [--db PATH] [--out ../evals/results/tuning.md]

Reads `evals/results/<label>/*.json` written by `run_evals.py` and writes, per brief, the
before/after verdict of every validator, the final status, cost and tokens, and the
Langfuse prompt versions each iteration used per role (`llm_call.prompt_version`). With
`--db` the prompt versions are re-read from the database instead of the JSON files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVALS_DIR.parent / "backend"
RESULTS_DIR = EVALS_DIR / "results"

if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run_evals import COLUMNS, brief_order, cell, final_status, injection_cell, say  # noqa: E402

_RANK = {"❌": 0, "—": 1, "⚑": 1, "✅": 2}


def load_label(label: str) -> dict[str, dict[str, Any]]:
    folder = RESULTS_DIR / label
    if not folder.is_dir():
        raise SystemExit(f"no results for label {label!r} in {folder}")
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))
    }


def prompts_from_db(db: Path, novel_id: str) -> list[dict[str, Any]]:
    from app.bible.repository import BibleRepository

    with BibleRepository.open(db) as repo:
        rows = repo.connection.execute(
            "select role, prompt_name, prompt_version, count(*) from llm_call "
            "where novel_id = ? group by role, prompt_name, prompt_version "
            "order by role, prompt_name, prompt_version",
            (novel_id,),
        ).fetchall()
    return [
        {"role": r[0], "prompt_name": r[1], "prompt_version": r[2], "calls": r[3]} for r in rows
    ]


def versions_by_role(prompts: list[dict[str, Any]]) -> dict[str, str]:
    by_role: dict[str, list[str]] = {}
    for p in prompts:
        tag = f"{p['prompt_name'] or '?'}@{p['prompt_version'] or '?'}"
        by_role.setdefault(str(p["role"]), []).append(tag)
    return {role: ", ".join(tags) for role, tags in by_role.items()}


def trend(before: str, after: str) -> str:
    if before == after:
        return "="
    return "↑" if _RANK.get(after, 1) > _RANK.get(before, 1) else "↓"


def cost_text(result: dict[str, Any] | None) -> str:
    cost = (result or {}).get("cost") or {}
    if not cost:
        return "—"
    return (
        f"{cost.get('cost_usd', 0):.4f} USD · "
        f"{cost.get('input_tokens', 0)}/{cost.get('output_tokens', 0)} tok"
    )


def render(a: str, b: str, before: dict[str, Any], after: dict[str, Any], change: str) -> str:
    lines = [
        f"# Tuning iteration — `{a}` → `{b}`",
        "",
        (
            f"Generated {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} by "
            f"`evals/compare_iterations.py` from `evals/results/{a}/` and `evals/results/{b}/`."
        ),
        "",
        f"**Change under test.** {change or '(describe the prompt change with --change)'}",
        "",
        "## Summary",
        "",
        f"| brief | final `{a}` | final `{b}` | cost `{a}` | cost `{b}` | improved | regressed |",
        "|---|---|---|---|---|---|---|",
    ]
    names = sorted(set(before) | set(after), key=lambda n: brief_order(Path(n)))
    detail: list[str] = []
    for name in names:
        rb, ra = before.get(name), after.get(name)
        cols = [*COLUMNS, "injection"]
        cells = []
        for col in cols:
            vb = (injection_cell(rb) if col == "injection" else cell(rb, col)) if rb else "—"
            va = (injection_cell(ra) if col == "injection" else cell(ra, col)) if ra else "—"
            cells.append((col, vb, va, trend(vb, va)))
        up = [c for c, _, _, t in cells if t == "↑"]
        down = [c for c, _, _, t in cells if t == "↓"]
        lines.append(
            f"| `{name}` | {final_status(rb) if rb else '—'} | {final_status(ra) if ra else '—'} "
            f"| {cost_text(rb)} | {cost_text(ra)} | {', '.join(up) or '—'} "
            f"| {', '.join(down) or '—'} |"
        )
        detail += [
            f"### `{name}`",
            "",
            f"| validator | `{a}` | `{b}` | Δ |",
            "|---|---|---|---|",
            *(f"| {c} | {vb} | {va} | {t} |" for c, vb, va, t in cells),
            "",
        ]
    lines += ["", "## Per brief and validator", "", *detail]
    lines += [
        "## Prompt versions per role",
        "",
        "Read from `llm_call.prompt_version` (the Langfuse prompt version each call used).",
        "",
        f"| brief | role | `{a}` | `{b}` |",
        "|---|---|---|---|",
    ]
    for name in names:
        pb = versions_by_role((before.get(name) or {}).get("prompts") or [])
        pa = versions_by_role((after.get(name) or {}).get("prompts") or [])
        for role in sorted(set(pb) | set(pa)):
            lines.append(f"| `{name}` | {role} | {pb.get(role, '—')} | {pa.get(role, '—')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("before", help="label of the first iteration (e.g. before)")
    parser.add_argument("after", help="label of the second iteration (e.g. after)")
    parser.add_argument("--change", default="", help="one line describing the tuning change")
    parser.add_argument("--db", type=Path, help="re-read prompt versions from this HARNESS_DB")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "tuning.md")
    args = parser.parse_args(argv)
    before, after = load_label(args.before), load_label(args.after)
    if args.db:
        for results in (before, after):
            for r in results.values():
                r["prompts"] = prompts_from_db(args.db.resolve(), r["novel_id"])
    text = render(args.before, args.after, before, after, args.change)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    say(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
