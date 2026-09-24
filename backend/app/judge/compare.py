"""Human review vs LLM judge (spec 011, AC 3).

Reads a filled `review-template.yaml` and the judge's `validator_result` rows for the same
novel and version (through `BibleRepository`, K1), and writes a Markdown comparison per
chapter and criterion with the difference (human - LLM) and the mean absolute error.

    cd backend && uv run python ../evals/human-review/compare.py REVIEW.yaml [--db PATH]
    cd backend && uv run python -m app.judge.compare REVIEW.yaml [--db PATH]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import yaml

from app.bible import BibleRepository
from app.judge.rubric import CHAPTER_CRITERIA, NOVEL_CRITERIA, evaluate
from app.judge.validators import EVIDENCE_LINE

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR: Final[Path] = REPO_ROOT / "evals" / "human-review"
NOVEL: Final[str] = "novela"
"""The `unit` of the whole-novel row."""


@dataclass(frozen=True, slots=True)
class Row:
    unit: str
    criterion: str
    human: int | None
    llm: int | None

    @property
    def diff(self) -> int | None:
        if self.human is None or self.llm is None:
            return None
        return self.human - self.llm


def _scores_from_yaml(block: Mapping[str, object], keys: Sequence[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for key in keys:
        entry = block.get(key)
        if isinstance(entry, Mapping):
            value = entry.get("score")
            if isinstance(value, int) and 1 <= value <= 5:
                scores[key] = value
    return scores


def load_review(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        message = f"{path}: a review is a YAML mapping"
        raise ValueError(message)
    return cast("dict[str, object]", data)


def human_scores(review: Mapping[str, object]) -> dict[str, dict[str, int]]:
    """unit ("1", "2", …, "novela") -> criterion -> score."""
    out: dict[str, dict[str, int]] = {}
    chapter_keys = [c.key for c in CHAPTER_CRITERIA]
    chapters = review.get("chapters")
    if isinstance(chapters, list):
        for entry in chapters:
            if isinstance(entry, Mapping) and isinstance(entry.get("chapter"), int):
                out[str(entry["chapter"])] = _scores_from_yaml(entry, chapter_keys)
    novel = review.get("novel")
    if isinstance(novel, Mapping):
        out[NOVEL] = _scores_from_yaml(novel, [c.key for c in NOVEL_CRITERIA])
    return out


def _parse_evidence(evidence: Sequence[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for line in evidence:
        match = EVIDENCE_LINE.match(line)
        if match is not None:
            scores[match["key"]] = int(match["score"])
    return scores


def llm_scores(repo: BibleRepository, novel_id: str, version: int) -> dict[str, dict[str, int]]:
    """The latest judge result per chapter, and for the novel, as unit -> criterion -> score."""
    out: dict[str, dict[str, int]] = {}
    for name, point in (("judge_chapter", "chapter_close"), ("judge_novel", "pre_publish")):
        rows = repo.list_validator_results(novel_id, version=version, name=name, point=point)
        for row in sorted(rows, key=lambda r: r.id):  # later rows overwrite earlier retries
            parsed = _parse_evidence(row.evidence)
            if not parsed:
                continue
            unit = NOVEL if name == "judge_novel" else str(row.chapter)
            out[unit] = parsed
    return out


def build_rows(
    human: Mapping[str, Mapping[str, int]], llm: Mapping[str, Mapping[str, int]]
) -> list[Row]:
    def order(unit: str) -> tuple[int, int]:
        return (1, 0) if unit == NOVEL else (0, int(unit))

    rows: list[Row] = []
    units = {u for u in set(human) | set(llm) if human.get(u) or llm.get(u)}
    for unit in sorted(units, key=order):
        criteria = NOVEL_CRITERIA if unit == NOVEL else CHAPTER_CRITERIA
        for criterion in criteria:
            rows.append(
                Row(
                    unit=unit,
                    criterion=criterion.key,
                    human=human.get(unit, {}).get(criterion.key),
                    llm=llm.get(unit, {}).get(criterion.key),
                )
            )
    return rows


def mae_by_criterion(rows: Sequence[Row]) -> dict[str, tuple[float | None, int]]:
    """criterion -> (mean absolute error, number of paired scores)."""
    out: dict[str, tuple[float | None, int]] = {}
    for criterion in NOVEL_CRITERIA:
        diffs = [abs(r.diff) for r in rows if r.criterion == criterion.key and r.diff is not None]
        out[criterion.key] = (sum(diffs) / len(diffs) if diffs else None, len(diffs))
    return out


def _fmt(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+d}" if isinstance(value, int) else f"{value:.2f}"


def _verdict(scores: Mapping[str, int]) -> str:
    if not scores:
        return "—"
    return "aprueba" if evaluate(scores).passed else "suspende"


def render(
    novel_id: str,
    version: int,
    rows: Sequence[Row],
    human: Mapping[str, Mapping[str, int]],
    llm: Mapping[str, Mapping[str, int]],
) -> str:
    lines = [
        f"# Revisión humana vs juez LLM — `{novel_id}` v{version}",
        "",
        "Generado por `app.judge.compare` (spec 011). Diferencia = humano - LLM.",
        "",
        "## Error absoluto medio por criterio",
        "",
        "| Criterio | MAE | Pares |",
        "|---|---|---|",
    ]
    for key, (mae, count) in mae_by_criterion(rows).items():
        lines.append(f"| {key} | {_fmt(mae)} | {count} |")
    paired = [abs(r.diff) for r in rows if r.diff is not None]
    overall = sum(paired) / len(paired) if paired else None
    lines += [f"| **total** | **{_fmt(overall)}** | {len(paired)} |", ""]
    lines += [
        "## Veredicto (regla D11) por unidad",
        "",
        "| Unidad | Humano | LLM | ¿Coinciden? |",
        "|---|---|---|---|",
    ]
    for unit in dict.fromkeys(r.unit for r in rows):
        h, m = _verdict(human.get(unit, {})), _verdict(llm.get(unit, {}))
        agree = "—" if "—" in (h, m) else ("sí" if h == m else "**no**")
        label = unit if unit == NOVEL else f"cap. {unit}"
        lines.append(f"| {label} | {h} | {m} | {agree} |")
    lines += [
        "",
        "## Detalle",
        "",
        "| Unidad | Criterio | Humano | LLM | Diferencia |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        label = r.unit if r.unit == NOVEL else f"cap. {r.unit}"
        human_cell = "—" if r.human is None else str(r.human)
        llm_cell = "—" if r.llm is None else str(r.llm)
        lines.append(f"| {label} | {r.criterion} | {human_cell} | {llm_cell} | {_fmt(r.diff)} |")
    lines.append("")
    return "\n".join(lines)


def compare(
    review_path: Path,
    repo: BibleRepository,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    novel_id: str | None = None,
    version: int | None = None,
) -> tuple[Path, str]:
    """Write `comparison-<novel>.md` into `out_dir`; return its path and text."""
    review = load_review(review_path)
    novel = novel_id or str(review.get("novel_id") or "")
    if not novel:
        message = "the review names no novel_id (or pass --novel-id)"
        raise ValueError(message)
    raw_version = version if version is not None else review.get("version", 1)
    ver = raw_version if isinstance(raw_version, int) else 1
    human = human_scores(review)
    llm = llm_scores(repo, novel, ver)
    text = render(novel, ver, build_rows(human, llm), human, llm)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"comparison-{novel}.md"
    target.write_text(text, encoding="utf-8")
    return target, text


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare a human review with the LLM judge.")
    parser.add_argument("review", type=Path, help="filled review YAML")
    parser.add_argument("--db", type=Path, default=None, help="HARNESS_DB (default: settings)")
    parser.add_argument("--novel-id", default=None)
    parser.add_argument("--version", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    with BibleRepository.open(args.db) as repo:
        target, text = compare(
            args.review,
            repo,
            out_dir=args.out_dir,
            novel_id=args.novel_id,
            version=args.version,
        )
    sys.stdout.write(text)
    sys.stdout.write(f"\nwritten: {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
