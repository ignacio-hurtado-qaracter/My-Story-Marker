"""Figure 3's write table, as data, and the single check that reads it.

This is the load-bearing wall of the whole design. `architecture.md` says so plainly: the
permission asymmetry *is* the anti-drift mechanism, and everything else is support for it.
Two properties are worth stating because the code below exists to guarantee them:

* **`canon/` has exactly two inbound write edges**, the world builder during planning and the
  canoniser during drafting. The writer -- the agent that generates the most tokens and
  therefore has the most opportunities to be wrong -- has none. It proposes into `ledger/`
  and cannot commit.
* **The auditor writes only `ledger/violations.yaml`.** Its output is a report. An auditor
  that could act on its own findings would trim exactly the living details that made a scene
  work, because those are the ones that deviate from the plan.

FR-PERM-05: the table is a module constant. There is no configuration key and no code path
that widens it at runtime, and `may_write` is the only check (FR-PERM-03).
"""

from __future__ import annotations

import re
from typing import Final

from app.commons.permissions.roles import AgentRole

SCENE_FILE = "[0-9][0-9][0-9]"
"""`NNN` as Figure 3 writes it. Spelled as a glob so the table stays readable as a
transcription of the table in the document."""

WRITE_TABLE: Final[dict[AgentRole, tuple[str, ...]]] = {
    AgentRole.ARCHITECT: (
        "structure/**",
        "scenes/**",
    ),
    AgentRole.WORLD_BUILDER: ("canon/**",),
    AgentRole.WRITER: (
        f"manuscript/{SCENE_FILE}.md",
        f"manuscript/digests/{SCENE_FILE}.md",
        "ledger/proposed.yaml",
    ),
    AgentRole.STYLE_EDITOR: (f"manuscript/{SCENE_FILE}.md",),
    AgentRole.AUDITOR: ("ledger/violations.yaml",),
    AgentRole.CANONISER: (
        "canon/**",
        "cast/**",
        "ledger/proposed.yaml",
    ),
    # Spec 005. The gift-novel roles write the authoritative database only (plan 004, V4);
    # they have no file-store write, so no row of Figure 3 is widened (spec 004, D7).
    AgentRole.INTERVIEWER: (),
    AgentRole.PLANNER: (),
    AgentRole.EDITOR: (),
    AgentRole.JUDGE: (),
}
"""FR-PERM-02, transcribed from Figure 3's table and nothing else.

Note what is absent, since absence is the whole point: the writer has no `canon/` entry, the
style editor has no `ledger/` entry (a voice decision does not become a rule), the auditor
has no `manuscript/` entry, and the canoniser has nothing under `manuscript/`.
"""

STORE_FAMILIES: Final[tuple[str, ...]] = (
    "canon",
    "cast",
    "structure",
    "scenes",
    "manuscript",
    "ledger",
)
"""The six top-level directories of the storage layout. `.index/` is deliberately not here:
it is not a store, is not governed by Figure 3, and no agent reads it (Decision R2-1)."""


def compile_store_glob(pattern: str) -> re.Pattern[str]:
    """Translate a store glob to a regex.

    Three meanings, and the difference between the first two is load-bearing: `**` crosses
    directory separators, `*` does not. Without that distinction `manuscript/*.md` would also
    match `manuscript/digests/001.md`, and the style editor -- which may write a draft but
    not a digest -- would silently gain a permission Figure 3 does not give it.
    """
    out: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        elif char == "[":
            close = pattern.find("]", index)
            if close == -1:
                out.append(re.escape(char))
                index += 1
            else:
                out.append(pattern[index : close + 1])
                index = close + 1
        else:
            out.append(re.escape(char))
            index += 1
    out.append("$")
    return re.compile("".join(out))


_COMPILED: Final[dict[AgentRole, tuple[re.Pattern[str], ...]]] = {
    role: tuple(compile_store_glob(pattern) for pattern in patterns)
    for role, patterns in WRITE_TABLE.items()
}


def normalise(path: str) -> str:
    """A store-relative POSIX path, or `ValueError`.

    Rejects anything that could leave the root before the pattern match sees it, so a
    traversal cannot be smuggled past the table by a pattern that happens to be permissive
    (FR-STORE-05).
    """
    candidate = path.replace("\\", "/").strip()
    if not candidate:
        message = "empty store path"
        raise ValueError(message)
    if candidate.startswith("/") or ":" in candidate:
        message = f"store paths are relative to the root: {path!r}"
        raise ValueError(message)
    parts = [part for part in candidate.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        message = f"store path escapes the root: {path!r}"
        raise ValueError(message)
    return "/".join(parts)


def may_write(role: AgentRole, path: str) -> bool:
    """FR-PERM-03. The single check, and the store layer is its only production caller.

    A path outside every store family is never writable by any role: `.index/` is not a store
    and does not become one by being asked about here.
    """
    try:
        target = normalise(path)
    except ValueError:
        return False
    if target.split("/")[0] not in STORE_FAMILIES:
        return False
    return any(pattern.match(target) for pattern in _COMPILED[role])


def writable_patterns(role: AgentRole) -> tuple[str, ...]:
    """FR-PERM-04, FR-PERM-06. What `/permissions` exports and what the tool sets are built
    from, so the two cannot be written down twice and drift."""
    return WRITE_TABLE[role]


__all__ = [
    "SCENE_FILE",
    "STORE_FAMILIES",
    "WRITE_TABLE",
    "compile_store_glob",
    "may_write",
    "normalise",
    "writable_patterns",
]
