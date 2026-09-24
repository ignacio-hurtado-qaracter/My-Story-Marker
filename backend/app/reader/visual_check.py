"""Exam § 5a: the visual check of the web reader, as a `pre_publish` validator (spec 014).

`visual_check` runs `frontend/e2e/visual-check.spec.ts` (Playwright, chromium) against a
running reader: the cover shows the title and the dedication, the index lists the chapters,
a chapter renders its text, the character sheet links to at least one chapter. Screenshots
go to `frontend/screenshots/visual-check/`.

It runs only when `VISUAL_CHECK=1` **and** the reader answers at `BASE_URL` (default
`http://127.0.0.1:5173`, the Vite dev server that proxies `/api` to the backend). Otherwise
it passes with the explanation "skipped: ..." and no score, so an offline pipeline run is
never blocked by a browser it does not have. A failing check names the step that failed and
is returned to the writer (`feedback_role`), like any other pre-publish failure.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - runs the repository's own Playwright spec, fixed argv
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.error import URLError

from app.commons.config import REPO_ROOT
from app.validators import ValidationContext, ValidationPoint, ValidationResult, register

NAME: Final[str] = "visual_check"
FRONTEND_DIR: Final[Path] = REPO_ROOT / "frontend"
SPEC: Final[str] = "e2e/visual-check.spec.ts"
CONFIG: Final[str] = "e2e/visual-check.config.ts"
SCREENSHOTS: Final[Path] = FRONTEND_DIR / "screenshots" / "visual-check"
DEFAULT_BASE_URL: Final[str] = "http://127.0.0.1:5173"
TIMEOUT_S: Final[int] = 240


def _reachable(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    try:
        with urllib.request.urlopen(url, timeout=5):  # nosec B310 - scheme checked above
            return True
    except (URLError, OSError, ValueError):
        return False


def _tail(text: str, lines: int = 25) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


@dataclass(frozen=True, slots=True)
class VisualCheck:
    """K3 validator. `run` never raises: a missing tool is a skip, a failed page a fail."""

    name: str = NAME
    point: ValidationPoint = ValidationPoint.PRE_PUBLISH

    def run(self, ctx: ValidationContext) -> ValidationResult:
        if os.environ.get("VISUAL_CHECK") != "1":
            return ValidationResult(
                name=self.name, passed=True, score=None,
                explanation="skipped: VISUAL_CHECK not enabled",
            )
        base_url = os.environ.get("BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        npx = shutil.which("npx")
        if npx is None or not (FRONTEND_DIR / SPEC).is_file():
            return ValidationResult(
                name=self.name, passed=True, score=None,
                explanation="skipped: npx or the Playwright spec is not available",
            )
        if not (_reachable(base_url) and _reachable(f"{base_url}/api/novels")):
            return ValidationResult(
                name=self.name, passed=True, score=None,
                explanation=f"skipped: the reader is not reachable at {base_url}",
            )
        env = {**os.environ, "BASE_URL": base_url, "NOVEL_ID": ctx.novel_id}
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        try:
            done = subprocess.run(  # nosec B603 - fixed argv, no shell
                [npx, "playwright", "test", "--config", CONFIG, "--reporter=line"],
                cwd=FRONTEND_DIR,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                name=self.name, passed=False, score=0.0,
                explanation=(
                    f"the visual check did not finish in {TIMEOUT_S}s; feedback_role: writer"
                ),
            )
        shots = sorted(str(p.relative_to(REPO_ROOT)) for p in SCREENSHOTS.glob("*.png"))
        output = _tail(done.stdout + "\n" + done.stderr)
        passed = done.returncode == 0
        return ValidationResult(
            name=self.name,
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence=[*shots, output],
            explanation=(
                "cover, index, chapter and character sheet render"
                if passed
                else "the reader failed the visual check (see evidence); feedback_role: writer"
            ),
        )


def register_validators() -> None:
    """K3 registration convention (contract page): idempotent, by name."""
    register(VisualCheck())


__all__ = ["NAME", "VisualCheck", "register_validators"]
