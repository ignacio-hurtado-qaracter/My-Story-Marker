"""Run the Lean 4 chronology check. Spec 012 (B8), AC 3 and AC 4 — L03.

``verify_chronology`` exports the chronology (``lean_export``), writes it to
``formal/lean/Chronology/Generated/Story.lean``, runs ``lake build`` on that module and
reports which invariants failed. It never raises for a failing story, a malformed
chronology, a timeout or a missing toolchain: each is a ``LeanResult`` with
``passed=False`` and an explanation in ``output``, because the caller is a publication
gate and a gate that crashes is a gate that is skipped.

The pre-publish validator (blocks B3/B4) calls it; on ``passed=False`` the version is not
published and ``failed_invariants`` plus ``output`` go back to the editor as feedback. The
result is sent to Langfuse (block B6) as the score ``lean_chronology`` (1 or 0).
"""

from __future__ import annotations

import os
import re
import shutil

# Runs the pinned `lake` binary, resolved to an absolute path, with fixed arguments.
import subprocess  # nosec B404
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.formal.lean_export import INVARIANTS, ChronologyError, export_lean

__all__ = [
    "DEFAULT_LEAN_DIR",
    "GENERATED_MODULE",
    "LeanResult",
    "find_lake",
    "verify_chronology",
]

#: ``formal/lean`` at the repository root (this file is ``backend/app/formal/…``).
DEFAULT_LEAN_DIR = Path(__file__).resolve().parents[3] / "formal" / "lean"
#: The module name is fixed: nothing from the chronology decides where the file goes.
GENERATED_MODULE = "Chronology.Generated.Story"
_GENERATED_PATH = Path("Chronology") / "Generated" / "Story.lean"
_ERROR_LINE = re.compile(r"Story\.lean:(\d+):\d+:\s*error|error:\s*\S*Story\.lean:(\d+):\d+")
_THEOREM = re.compile(r"^theorem story_(\w+)\b")

# One generated file per Lean project: two concurrent runs in this process would
# overwrite each other's story. Runs from separate processes need separate `lean_dir`s.
_BUILD_LOCK = threading.Lock()


@dataclass(frozen=True)
class LeanResult:
    """Outcome of one Lean check of a chronology."""

    passed: bool
    failed_invariants: list[str] = field(default_factory=list)
    output: str = ""
    lean_file: str = ""


def find_lake() -> Path | None:
    """Return the ``lake`` executable from ``PATH`` or ``~/.elan/bin``, or ``None``."""
    on_path = shutil.which("lake")
    if on_path:
        return Path(on_path)
    elan = Path.home() / ".elan" / "bin" / "lake"
    if elan.is_file() and os.access(elan, os.X_OK):
        return elan
    return None


def _theorem_lines(source: str) -> list[tuple[int, str]]:
    """``(line, invariant)`` for every per-invariant theorem of the generated file."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        match = _THEOREM.match(line)
        if match and match.group(1) in INVARIANTS:
            found.append((number, match.group(1)))
    return found


def failed_invariants(output: str, source: str) -> list[str]:
    """Name the invariants whose theorem Lean reported an error on.

    Two independent signals, so a change in Lean's message format degrades to one: the
    error's line number mapped to the theorem on that line, and the Bool check that
    ``decide`` names in its message (``agesCoherentB story = true … is false``).
    """
    theorems = _theorem_lines(source)
    failed: set[str] = set()
    for match in _ERROR_LINE.finditer(output):
        line = int(match.group(1) or match.group(2))
        for start, name in theorems:
            if start == line:
                failed.add(name)
    for name, check in INVARIANTS.items():
        if re.search(rf"\b{check} story = true\s+is false", output):
            failed.add(name)
    return [name for name in INVARIANTS if name in failed]


def verify_chronology(
    chronology: Mapping[str, object],
    novel_id: str,
    lean_dir: Path | None = None,
    timeout: float = 300,
) -> LeanResult:
    """Check ``chronology`` against the Lean invariants with ``lake build``."""
    project = (lean_dir or DEFAULT_LEAN_DIR).resolve()
    lean_file = project / _GENERATED_PATH

    try:
        source = export_lean(chronology, novel_id)
    except ChronologyError as exc:
        return LeanResult(False, [], f"chronology export failed: {exc}", "")

    lake = find_lake()
    if lake is None:
        return LeanResult(
            False,
            [],
            "Lean toolchain missing: `lake` is not on PATH nor in ~/.elan/bin. Install elan "
            "and the toolchain pinned in formal/lean/lean-toolchain (see formal/lean/README.md)."
            " The chronology was not verified.",
            "",
        )
    if not (project / "lakefile.toml").is_file():
        return LeanResult(False, [], f"no Lake project at {project}", "")

    with _BUILD_LOCK:
        lean_file.parent.mkdir(parents=True, exist_ok=True)
        lean_file.write_text(source, encoding="utf-8")
        try:
            completed = subprocess.run(  # nosec B603
                [str(lake), "build", GENERATED_MODULE],
                cwd=project,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return LeanResult(False, [], f"lake build timed out after {timeout} s", str(lean_file))
        except OSError as exc:
            return LeanResult(False, [], f"could not run lake: {exc}", str(lean_file))

    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode == 0:
        return LeanResult(True, [], output, str(lean_file))
    return LeanResult(False, failed_invariants(output, source), output, str(lean_file))
