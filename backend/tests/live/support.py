"""What the two live tests share: the environment they run in and where their evidence goes.

Spec 001, plan step 20 (AC 26 and AC 27). Both are **D** -- demonstrated runs, not assertions
a model can be trusted to meet every time. The plan's risk register says what a miss is:
"record the miss in `last_run.md`; the criterion is D and the miss is the finding." So each
test writes what happened to `last_run.md` *before* it asserts, and the report is the evidence
the PR cites whether the assertions held or not.

NFR-10 keeps prose out of logs outside the store tree. The report therefore carries the
findings' evidence quotes -- the sentence a finding is about, which is what a reviewer needs to
judge it -- and the path of the run's private store copy, where the draft itself stays.

A live run takes minutes, most of them inside `claude -p`. `Progress` prints one line per step
as the step ends -- its status, how long it took and what runs next -- so that a user running
`pytest tests/live --live -s` watches the run move instead of waiting on silence.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import pytest

from app.commons.config import Settings, get_settings
from app.commons.embeddings import FastEmbedEmbedder
from app.commons.llm import ClaudeCodeModelClient
from app.commons.stores import Store

LIVE_DIR = Path(__file__).resolve().parent
BACKEND = LIVE_DIR.parent.parent
LAST_RUN = LIVE_DIR / "last_run.md"
REAL_MODEL_CACHE = Path(os.environ.get("EMBED_CACHE_DIR") or BACKEND / ".index" / "models")
"""AC 26 asks for the real embedder. Its model is cached where it survives the run, as the
`model`-marked embedder tests cache it, so it is downloaded at most once."""


@dataclass(frozen=True)
class LiveEnv:
    """A private fixture copy served by the production dependencies: `claude -p` under the
    user's Claude Code login (no API key, FR-LLM-01) and the real `fastembed` model."""

    root: Path
    store: Store
    settings: Settings
    client: ClaudeCodeModelClient
    embedder: FastEmbedEmbedder


def live_env(fixture_root: Path, monkeypatch: pytest.MonkeyPatch) -> LiveEnv:
    """The production client and embedder over the fixture copy `fixture_root` already made."""
    monkeypatch.setenv("EMBED_CACHE_DIR", str(REAL_MODEL_CACHE))
    monkeypatch.setenv("EMBED_OFFLINE", "0")
    get_settings.cache_clear()
    settings = get_settings()
    store = Store(root=fixture_root, index_dir=fixture_root.parent / ".index")
    return LiveEnv(
        root=fixture_root,
        store=store,
        settings=settings,
        client=ClaudeCodeModelClient(settings),
        embedder=FastEmbedEmbedder(settings),
    )


def append_section(title: str, lines: list[str]) -> None:
    """Append one run's section to `last_run.md`, newest last, stamped in UTC."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    existing = (
        LAST_RUN.read_text(encoding="utf-8")
        if LAST_RUN.is_file()
        else "# Live runs (spec 001, AC 26 and AC 27)\n\nWritten by `tests/live/`; newest last.\n"
    )
    block = "\n".join([f"## {title} -- {stamp}", "", *lines, ""])
    LAST_RUN.write_text(existing.rstrip("\n") + "\n\n" + block, encoding="utf-8")


def mark(ok: bool) -> str:
    """How a check reads in the report."""
    return "yes" if ok else "**NO**"


class Progress:
    """One printed line per step of a live run (plan step 20, AC 26 and AC 27): which step, how
    it ended, its elapsed seconds and the run's, and what runs next. Flushed at once, so it
    shows as it happens under `-s`; pytest captures it otherwise, and nothing depends on it."""

    def __init__(self, label: str) -> None:
        self._label = label
        self._started = monotonic()
        self._last = self._started

    def start(self, what: str, first: str) -> None:
        """The run's opening line: what it does and the step it runs first."""
        self._emit(f"{what}; next: {first}")

    def step(self, name: str, status: str, next_step: str | None = None) -> None:
        """A step has ended with `status`; `next_step` is what runs now, if anything."""
        now = monotonic()
        tail = f"; next: {next_step}" if next_step else ""
        self._emit(
            f"{name}: {status} ({now - self._last:.1f}s, total {now - self._started:.1f}s){tail}"
        )
        self._last = now

    def _emit(self, line: str) -> None:
        sys.stdout.write(f"[live {self._label}] {line}\n")
        sys.stdout.flush()
