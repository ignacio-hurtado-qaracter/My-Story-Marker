"""Shared helpers for the presentation build (deck and annexes).

Reads live numbers from the repository so the deck and the annexes can be rebuilt after
every run: eval tables, TLC output, costs, counterexamples, and the Mermaid diagrams of
docs/process/diagramas.md rendered to PNG with @mermaid-js/mermaid-cli.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRES = HERE.parent
ROOT = PRES.parent
IMG = HERE / "img"


def chrome_path() -> str | None:
    """A Chromium binary for mermaid-cli and for printing the annexes to PDF."""
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")),
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
        shutil.which("google-chrome") or "",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --------------------------------------------------------------------------- Mermaid

def mermaid_blocks(rel: str) -> list[str]:
    return re.findall(r"```mermaid\n(.*?)```", read(rel), flags=re.S)


# name -> (source file, block index)
DIAGRAMS: dict[str, tuple[str, int]] = {
    "arquitectura": ("docs/process/diagramas.md", 0),
    "tla-estados": ("docs/process/diagramas.md", 1),
    "esquema-sqlite": ("docs/process/diagramas.md", 2),
    "validadores": ("docs/process/diagramas.md", 3),
    "arquitectura-resumen": ("README.md", 0),
    "oleadas": ("docs/process/spec-inicial.md", 0),
    "subagentes": ("docs/process/subagentes-comandos-skills.md", 0),
    "tla-readme": ("formal/tla/README.md", 0),
}

def _sanitise(src: str) -> str:
    """Work around a Mermaid parse quirk: in stateDiagram a ';' inside a transition label
    ends the statement and creates stray states (diagramas.md, TLA+ block)."""
    if src.lstrip().startswith("stateDiagram"):
        src = "\n".join(
            (ln.split(" : ", 1)[0] + " : " + ln.split(" : ", 1)[1].replace(";", ","))
            if " : " in ln else ln
            for ln in src.splitlines()
        )
    return src


MERMAID_CONFIG = {
    "theme": "base",
    "themeVariables": {
        "primaryColor": "#FBE9DF",
        "primaryBorderColor": "#C2551F",
        "primaryTextColor": "#1F2933",
        "lineColor": "#52606D",
        "secondaryColor": "#E6EEF2",
        "tertiaryColor": "#F7F7F5",
        "fontFamily": "Arial, sans-serif",
        "fontSize": "16px",
    },
}


def render_mermaid(name: str, force: bool = False) -> Path | None:
    """Render one named diagram to img/<name>.png, cached by the hash of its source.

    Without npx the committed PNG is used as is.
    """
    out = IMG / f"{name}.png"
    src_file, idx = DIAGRAMS[name]
    blocks = mermaid_blocks(src_file)
    if idx >= len(blocks):
        return out if out.exists() else None
    src = blocks[idx]
    src = _sanitise(src)
    width = "4800"
    digest = hashlib.sha256((src + width).encode()).hexdigest()[:12]
    stamp = IMG / f"{name}.sha"
    if out.exists() and not force and stamp.exists() and stamp.read_text().strip() == digest:
        return out
    npx = shutil.which("npx")
    if not npx:
        return out if out.exists() else None
    IMG.mkdir(parents=True, exist_ok=True)
    work = HERE / ".mmd"
    work.mkdir(exist_ok=True)
    (work / f"{name}.mmd").write_text(src, encoding="utf-8")
    (work / "config.json").write_text(json.dumps(MERMAID_CONFIG))
    pp: dict[str, object] = {"args": ["--no-sandbox"]}
    chrome = chrome_path()
    if chrome:
        pp["executablePath"] = chrome
    (work / "puppeteer.json").write_text(json.dumps(pp))
    cmd = [
        npx, "-y", "@mermaid-js/mermaid-cli",
        "-i", str(work / f"{name}.mmd"), "-o", str(out),
        "-c", str(work / "config.json"), "-p", str(work / "puppeteer.json"),
        "--size", width, "-b", "white",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        stamp.write_text(digest)
        print(f"  mermaid {name} -> {out.relative_to(ROOT)}")
    except (subprocess.SubprocessError, OSError) as exc:  # keep the committed PNG
        print(f"  ! mermaid {name}: {exc}")
    return out if out.exists() else None


def render_all(force: bool = False) -> dict[str, Path | None]:
    return {n: render_mermaid(n, force) for n in DIAGRAMS}


# --------------------------------------------------------------------------- Markdown tables

def md_tables(text: str) -> list[list[list[str]]]:
    """Every pipe table in a markdown text, as rows of cells (header first, no separator)."""
    tables: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = s.replace("**", "").replace("`", "")
    return re.sub(r"(?<!\w)\*(\S[^*]*?)\*(?!\w)", r"\1", s)


# --------------------------------------------------------------------------- live data

@dataclass
class TLC:
    ok: bool = False
    generated: str = "?"
    distinct: str = "?"
    depth: str = "?"
    duration: str = "?"
    version: str = ""


def _es(n: str) -> str:
    return f"{int(n):,}".replace(",", ".")


def tlc() -> TLC:
    t = read("formal/tla/tlc-output.txt")
    r = TLC(ok="No error has been found" in t)
    m = re.search(r"^(\d+) states generated, (\d+) distinct states found", t, re.M)
    if m:
        r.generated, r.distinct = _es(m.group(1)), _es(m.group(2))
    m = re.search(r"depth of the complete state graph search is (\d+)", t)
    if m:
        r.depth = m.group(1)
    m = re.search(r"Finished in (\S+)", t)
    if m:
        r.duration = m.group(1)
    m = re.search(r"TLC2 Version (\S+)", t)
    if m:
        r.version = m.group(1)
    return r


def tla_config() -> dict[str, str]:
    return dict(re.findall(r"^\s+(\w+) = (\S+)", read("formal/tla/GiftNovelHarness.cfg"), re.M))


def counterexamples() -> list[list[str]]:
    tabs = md_tables(read("formal/tla/COUNTEREXAMPLES.md"))
    return tabs[0] if tabs else []


@dataclass
class EvalRun:
    brief: str
    label: str
    outcome: str
    cost: float | None
    latency_s: float | None
    calls: int | None
    chapters: int | None
    by_chapter: list[dict] = field(default_factory=list)
    final: dict | None = None


def eval_runs() -> list[EvalRun]:
    runs: list[EvalRun] = []
    for f in sorted(glob.glob(str(ROOT / "evals/results/*/*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        c = d.get("cost") or {}
        runs.append(EvalRun(
            brief=d.get("brief", Path(f).stem), label=d.get("label", Path(f).parent.name),
            outcome=d.get("outcome", "?"), cost=c.get("cost_usd"), latency_s=c.get("latency_s"),
            calls=c.get("calls"), chapters=d.get("chapters_requested"),
            by_chapter=c.get("by_chapter") or [], final=d.get("final"),
        ))
    return runs


def eval_labels() -> list[str]:
    return sorted({Path(p).parent.name for p in glob.glob(str(ROOT / "evals/results/*/*.json"))})


def results_table() -> list[list[str]]:
    tabs = md_tables(read("evals/results.md"))
    return tabs[0] if tabs else []


def results_label() -> str:
    m = re.search(r"# Eval results — `([^`]+)`", read("evals/results.md"))
    return m.group(1) if m else "?"


def tuning_md() -> str:
    return read("evals/results/tuning.md")


def lean_real_case() -> str:
    return read("docs/process/lean-caso-real.md")


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "?"
