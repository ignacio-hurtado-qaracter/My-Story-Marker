#!/usr/bin/env python3
"""Secrets-leak scan of the whole git history (security review, programme 004, X04).

Runs `git log -p --all` from the repository root and looks, in every *added* line, for
strings shaped like real credentials. A hit is reported as commit, file and a **masked**
prefix only: the value itself is never printed, so this script's output can be pasted into
`docs/security-report.md` safely.

A hit whose line is clearly a pattern definition, a placeholder or documentation (a regex,
`xxxx`, `example`, `TU_CLAVE_AQUI`, a `printf`-assembled test key...) is counted as
`allowlisted` and listed separately, so a reviewer can still see it.

Usage (stdlib only):

    python3 security/scan_secrets.py            # exit 1 if any non-allowlisted hit
    python3 security/scan_secrets.py --verbose  # also list the allowlisted hits
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS: dict[str, re.Pattern[str]] = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    "langfuse_secret": re.compile(r"sk-lf-[A-Za-z0-9_\-]{8,}"),
    "langfuse_public": re.compile(r"pk-lf-[A-Za-z0-9_\-]{8,}"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_\w{40,}"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "generic_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|password|passwd|token)\s*[=:]\s*"
        r"[\"']?[A-Za-z0-9_\-/+]{20,}"
    ),
}

ALLOW = re.compile(
    r"(?i)(x{4,}|example|dummy|placeholder|your[_-]|tu_clave|changeme|\btest|fake|"
    r"\[A-Za-z|\{16|\{8|\\b|re\.compile|regex|printf|\.\.\.|…|<[a-z_]+>|redacted)"
)


@dataclass(frozen=True)
class Hit:
    kind: str
    commit: str
    path: str
    masked: str
    allowlisted: bool


def mask(value: str) -> str:
    """The first 6 characters and the length; never more."""
    return f"{value[:6]}**** ({len(value)} chars)"


def scan(log: str) -> list[Hit]:
    hits: list[Hit] = []
    commit, path = "?", "?"
    for line in log.splitlines():
        if line.startswith("commit "):
            commit = line.split()[1][:10]
        elif line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for kind, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    hits.append(
                        Hit(kind, commit, path, mask(match.group(0)), bool(ALLOW.search(line)))
                    )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    log = subprocess.run(
        ["git", "log", "-p", "--all", "--no-color", "--no-ext-diff"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    ).stdout
    commits = sum(1 for line in log.splitlines() if line.startswith("commit "))
    hits = scan(log)
    real = [h for h in hits if not h.allowlisted]
    allowed = [h for h in hits if h.allowlisted]
    print(f"commits scanned: {commits}; hits: {len(real)} suspicious, {len(allowed)} allowlisted")
    for hit in real:
        print(f"  SUSPICIOUS {hit.kind:18} {hit.commit} {hit.path}  {hit.masked}")
    if args.verbose:
        for hit in allowed:
            print(f"  allowlisted {hit.kind:18} {hit.commit} {hit.path}  {hit.masked}")
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
