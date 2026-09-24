"""Exam compliance checker: evaluates exam/requirements.toml against the repository.

Standard library only, so it runs with any Python 3.11+ and needs no virtualenv:

    python exam/check.py            writes exam/compliance.md and prints the summary
    python exam/check.py --strict   same, and exits 1 if a required item is not met
    python exam/check.py --stdout   prints the report instead of writing it

The checks are heuristics over file presence and content. A pass says an artefact
exists, not that it is good; items marked manual are listed so they are not forgotten.
The report is deterministic (no timestamps, no commit ids), so it only changes in git
when the repository's compliance changes.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "exam" / "requirements.toml"
REPORT = ROOT / "exam" / "compliance.md"

# Never searched: derived, vendored or self-referential content.
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
EXCLUDED_PREFIXES = ("exam/", "backend/tests/fixtures/")

PASS, PARTIAL, MISSING, MANUAL, REVIEW = "✅", "🟡", "❌", "📝", "📝✅"


@dataclass
class Result:
    ok: bool
    detail: str


@dataclass
class Item:
    id: str
    block: str
    text: str
    checks: list[dict[str, object]]
    manual: bool = False
    optional: bool = False
    any: bool = False
    results: list[Result] = field(default_factory=list)

    @property
    def status(self) -> str:
        passed = sum(r.ok for r in self.results)
        if self.manual and not self.results:
            return MANUAL
        if passed == len(self.results) or (self.any and passed):
            return REVIEW if self.manual else PASS
        return PARTIAL if passed else MISSING

    @property
    def met(self) -> bool:
        return self.status in {PASS, REVIEW}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _included(path: Path) -> bool:
    rel = _rel(path)
    return (
        path.is_file()
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        and not rel.startswith(EXCLUDED_PREFIXES)
    )


def _expand(patterns: list[str]) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if _included(path):
                found[_rel(path)] = path
    return [found[k] for k in sorted(found)]


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def check_exists(paths: list[str]) -> Result:
    hits = [p for p in paths if (ROOT / p).exists()]
    return Result(bool(hits), f"exists: {hits[0]}" if hits else f"missing: {' | '.join(paths)}")


def check_glob(patterns: list[str], minimum: int) -> Result:
    hits = _expand(patterns)
    ok = len(hits) >= minimum
    return Result(ok, f"{len(hits)} file(s) for {' | '.join(patterns)} (need {minimum})")


def check_grep(regex: str, files: list[str], minimum: int) -> Result:
    pattern = re.compile(regex)
    count, where = 0, []
    for path in _expand(files):
        text = _read(path)
        if text is None:
            continue
        n = len(pattern.findall(text))
        if n:
            count += n
            where.append(_rel(path))
    ok = count >= minimum
    if ok:
        return Result(True, f"/{regex}/ in {where[0]}" + (f" (+{len(where) - 1})" if len(where) > 1 else ""))
    return Result(False, f"/{regex}/ found {count}x in {' | '.join(files)} (need {minimum})")


def check_no_match(regex: str) -> Result:
    pattern = re.compile(regex)
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8").split("\0")
    offenders = []
    for rel in filter(None, listed):
        path = ROOT / rel
        if not path.exists() or not _included(path):
            continue
        text = _read(path)
        if text is not None and pattern.search(text):
            offenders.append(rel)
    # Offending file names are reported; matched values never are.
    return Result(not offenders, "no match in tracked files" if not offenders else f"matches in {', '.join(offenders)}")


def run(check: dict[str, object]) -> Result:
    kind = check["kind"]
    minimum = int(check.get("min", 1))  # type: ignore[arg-type]
    if kind == "exists":
        return check_exists(list(check["paths"]))  # type: ignore[arg-type]
    if kind == "glob":
        return check_glob(list(check["patterns"]), minimum)  # type: ignore[arg-type]
    if kind == "grep":
        return check_grep(str(check["regex"]), list(check["files"]), minimum)  # type: ignore[arg-type]
    if kind == "no_match":
        return check_no_match(str(check["regex"]))
    raise ValueError(f"unknown check kind: {kind!r}")


def load() -> list[Item]:
    data = tomllib.loads(REQUIREMENTS.read_text(encoding="utf-8"))
    items = [
        Item(
            id=raw["id"],
            block=raw["block"],
            text=raw["text"],
            checks=raw.get("checks", []),
            manual=raw.get("manual", False),
            optional=raw.get("optional", False),
            any=raw.get("any", False),
        )
        for raw in data["item"]
    ]
    ids = [i.id for i in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate item ids: {sorted(duplicates)}")
    return items


def render(items: list[Item]) -> str:
    blocks: dict[str, list[Item]] = {}
    for item in items:
        blocks.setdefault(item.block, []).append(item)

    required = [i for i in items if not i.optional and not (i.manual and not i.checks)]
    met = sum(i.met for i in required)

    out = [
        "# Cumplimiento del examen",
        "",
        "Generado por `python exam/check.py` a partir de `exam/requirements.toml`. No se edita a mano.",
        "",
        "Las comprobaciones son heurísticas: ✅ dice que el artefacto existe, no que sea bueno.",
        "",
        f"**Obligatorios comprobables cumplidos: {met} de {len(required)}.**",
        "",
        "Leyenda: ✅ cumple · 🟡 parcial · ❌ falta · 📝 manual · 📝✅ existe, revisar a mano",
        "",
        "## Resumen por bloque",
        "",
        "| Bloque | ✅ | 🟡 | ❌ | 📝 |",
        "|---|---|---|---|---|",
    ]
    for block, group in blocks.items():
        counts = {s: sum(i.status == s for i in group) for s in (PASS, PARTIAL, MISSING)}
        manual = sum(i.status in {MANUAL, REVIEW} for i in group)
        out.append(f"| {block} | {counts[PASS]} | {counts[PARTIAL]} | {counts[MISSING]} | {manual} |")

    for block, group in blocks.items():
        out += ["", f"## {block}", "", "| Id | Estado | Requisito | Evidencia |", "|---|---|---|---|"]
        for item in group:
            tag = " *(opcional)*" if item.optional else ""
            evidence = "<br>".join(("✓ " if r.ok else "✗ ") + r.detail.replace("|", "\\|") for r in item.results)
            out.append(f"| {item.id} | {item.status} | {item.text}{tag} | {evidence or '—'} |")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="exit 1 if a required item is not met")
    parser.add_argument("--stdout", action="store_true", help="print the report instead of writing it")
    args = parser.parse_args()

    items = load()
    for item in items:
        item.results = [run(c) for c in item.checks]

    report = render(items)
    if args.stdout:
        sys.stdout.write(report)
    else:
        REPORT.write_text(report, encoding="utf-8", newline="\n")
        summary = [line for line in report.splitlines() if line.startswith("**Obligatorios")]
        print(summary[0].strip("*") if summary else "report written")
        print(f"report: {_rel(REPORT)}")

    unmet = [i.id for i in items if not i.optional and not i.manual and not i.met]
    if args.strict and unmet:
        print(f"strict: {len(unmet)} required item(s) not met: {', '.join(unmet)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
