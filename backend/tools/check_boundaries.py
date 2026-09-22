"""The local mirror of the semgrep boundary rules (plan decision P8).

`semgrep` does not run natively on Windows, and the developer is on Windows. The rules of
record for AC 3, AC 13 and AC 17 are the YAML files under `backend/semgrep/` and they run in
CI on Linux; this module implements the same three rules with the standard library `ast`
module so they also run inside `pytest` on every platform.

**Both must pass, and a disagreement between them is a bug in this mirror.** The point of a
mirror is that the local gate is not blind, not that it replaces the rule. Where the two
could differ, this one is written to be the stricter.

The three rules:

1. **forbidden-store-write** (AC 3) - no file primitive outside `app/commons/stores/`.
   FR-STORE-02. An import contract can see that a module imported `pathlib`; it cannot see
   what path the module then opened, which is why this check exists at all.
2. **canon-write-outside-promote** (AC 13) - nothing under `ledger/` or `agents/` writes
   canon except `promote` and `rule`. `promote` is the only write path into canon during
   drafting, and a collision is escalated to a human rather than resolved silently.
3. **store-path-built-by-hand** (AC 3, FR-STORE-05) - no feature builds a store path by
   interpolation or concatenation. Paths derive from identifiers inside the store layer, so an
   id that would escape the root, or that fails its grammar, is rejected before it can become
   a path. A module that writes `f"cast/{character}/voice.md"` has taken that check out of the
   loop even though it never opens the file itself.
4. **hand-written-toolset** (AC 17) - no literal list of store paths in `agents/`. FR-PERM-06
   derives each role's tools from the write table by code, so the two cannot diverge; a
   hand-written list is precisely that divergence waiting to happen.

Run it directly for a report, or let `tests/test_boundaries_mirror.py` run it:

    uv run python tools/check_boundaries.py
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

APP = "app"

STORE_LAYER = ("app/commons/stores",)
"""The only place a file primitive may be applied to a store path (FR-STORE-02)."""

INDEX_WRITERS = (
    "app/agents/records.py",
    "app/agents/lock.py",
    "app/commons/db/",
    "app/commons/embeddings/",
)
"""The modules that own paths under `.index/`, which is **not** a store: it is not governed by
Figure 3 and no agent reads it (Decision R2-1).

`agents/records.py` and `agents/lock.py` hold the turn records and the turn lock;
`commons/db/` owns `index.sqlite`; `commons/embeddings/` owns the model cache
(`EMBED_CACHE_DIR`, FR-EMB-03).

The exemption is coarse, and that is a real limit rather than an oversight: this rule matches
file primitives by name and cannot see which path they are applied to, so a module allowed to
touch `.index/` is allowed to touch anything. The narrower guarantee comes from elsewhere --
`import-linter` keeps these modules out of the features, and none of them imports
`commons.stores.paths`, so they have no way to build a store path in the first place."""

STORE_FAMILIES = ("canon", "cast", "structure", "scenes", "manuscript", "ledger")

MUTATING_METHODS = frozenset(
    {
        "write_text",
        "write_bytes",
        "unlink",
        "mkdir",
        "rmdir",
        "touch",
        "read_text",
        "read_bytes",
    }
)

SINGLE_ARGUMENT_METHODS = frozenset({"rename", "replace"})
"""`Path.replace(target)` takes one argument; `str.replace(old, new)` takes two. Matching on
the name alone would flag every `path.replace("\\", "/")` in the codebase, so the arity is
what tells the two apart. The semgrep rule uses the same discriminator (`$P.replace($X)`),
because a mirror that disagrees with the rule of record is worse than no mirror."""

MUTATING_FUNCTIONS = frozenset(
    {
        ("os", "remove"),
        ("os", "unlink"),
        ("os", "rename"),
        ("os", "replace"),
        ("os", "makedirs"),
        ("os", "rmdir"),
        ("shutil", "copy"),
        ("shutil", "copy2"),
        ("shutil", "copyfile"),
        ("shutil", "copytree"),
        ("shutil", "move"),
        ("shutil", "rmtree"),
    }
)

PROMOTE_FUNCTIONS = frozenset({"promote", "rule", "reconcile"})
"""AC 13. The only functions under `ledger/` that may reach canon, and `rule` only ever runs
with `actor: human` behind it (FR-OPS-07)."""


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def _posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test(relative: str) -> bool:
    return "/tests/" in relative or relative.endswith("conftest.py")


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Line number -> name of the innermost function containing it."""
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            for line in range(node.lineno, end + 1):
                owner[line] = node.name
    return owner


def check_forbidden_store_write(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 1, AC 3."""
    if (
        relative.startswith(STORE_LAYER)
        or relative.startswith(INDEX_WRITERS)
        or _is_test(relative)
    ):
        return []

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name) and target.id == "open":
            findings.append(
                Finding(
                    "forbidden-store-write",
                    relative,
                    node.lineno,
                    "open() outside the store layer; use Store.read / Store.write",
                )
            )
        elif isinstance(target, ast.Attribute):
            single_argument = len(node.args) == 1 and not node.keywords
            is_primitive = target.attr in MUTATING_METHODS or (
                target.attr in SINGLE_ARGUMENT_METHODS and single_argument
            )
            if is_primitive:
                findings.append(
                    Finding(
                        "forbidden-store-write",
                        relative,
                        node.lineno,
                        f"{target.attr}() outside the store layer; use Store.read / Store.write",
                    )
                )
            elif isinstance(target.value, ast.Name):
                pair = (target.value.id, target.attr)
                if pair in MUTATING_FUNCTIONS:
                    findings.append(
                        Finding(
                            "forbidden-store-write",
                            relative,
                            node.lineno,
                            f"{pair[0]}.{pair[1]}() outside the store layer",
                        )
                    )
    return findings


def check_canon_write_outside_promote(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 2, AC 13.

    Looks for a call to a store write whose path argument mentions `canon/` or `cast/` from a
    module under `ledger/` or `agents/`, outside `promote`, `rule` and `reconcile`.
    """
    if not relative.startswith(("app/ledger", "app/agents")):
        return []
    if _is_test(relative):
        return []

    owners = _enclosing_functions(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if not (isinstance(target, ast.Attribute) and target.attr in {"write", "write_text"}):
            continue
        enclosing = owners.get(node.lineno, "<module>")
        if enclosing in PROMOTE_FUNCTIONS:
            continue
        for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
            literal = _string_of(argument)
            if literal and literal.startswith(("canon/", "cast/")):
                findings.append(
                    Finding(
                        "canon-write-outside-promote",
                        relative,
                        node.lineno,
                        f"write to {literal!r} in {enclosing}(); canon is written only by "
                        "promote() and rule(), and a collision is escalated to a human",
                    )
                )
    return findings


def check_store_path_built_by_hand(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 3, AC 3 and FR-STORE-05.

    Catches a store path assembled in a feature rather than derived in
    `commons/stores/paths.py`: an f-string or a concatenation or a `%` format whose literal
    head names a store family. The store layer and the permission layer are exempt, because
    building and matching those paths is exactly their job.

    This rule was missing from the mirror while the semgrep rule of record had it, which an
    adversarial review found by planting `f"cast/{character}/..."` in a feature repository and
    watching the local gate stay green. A mirror that is weaker than the rule it mirrors is
    worse than no mirror, because it is trusted.
    """
    if relative.startswith((*STORE_LAYER, "app/commons/permissions/")) or _is_test(relative):
        return []

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.expr):
            continue
        head = _literal_head(node)
        if head is None:
            continue
        first = head.split("/")[0]
        if first in STORE_FAMILIES and "/" in head:
            findings.append(
                Finding(
                    "store-path-built-by-hand",
                    relative,
                    node.lineno,
                    f"store path built from {head!r}; derive it in "
                    "app.commons.stores.paths, which rejects an identifier that would "
                    "escape the root or fail its grammar (FR-STORE-05)",
                )
            )
    return findings


def _literal_head(node: ast.expr) -> str | None:
    """The constant prefix of an interpolated or concatenated string, if it has one."""
    if isinstance(node, ast.JoinedStr):
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                return part.value
            return None
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        return _string_of(node.left)
    return None


def check_hand_written_toolset(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 3, AC 17.

    A list or tuple literal under `agents/` holding two or more store paths is a tool set
    someone wrote by hand. FR-PERM-06 derives them from the write table by code so the two
    cannot diverge.
    """
    if not relative.startswith("app/agents") or _is_test(relative):
        return []

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List | ast.Tuple | ast.Set):
            continue
        literals = [value for value in (_string_of(item) for item in node.elts) if value]
        store_paths = [
            value for value in literals if value.split("/")[0] in STORE_FAMILIES and "/" in value
        ]
        if len(store_paths) >= 2:
            findings.append(
                Finding(
                    "hand-written-toolset",
                    relative,
                    node.lineno,
                    f"literal list of store paths {store_paths}; derive the tool set from "
                    "the write table with toolset_for(role) (FR-PERM-06)",
                )
            )
    return findings


def _string_of(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def check_tree(root: Path) -> list[Finding]:
    """Run all three rules over `root/app`, sorted by path then line."""
    findings: list[Finding] = []
    for path in sorted((root / APP).rglob("*.py")):
        relative = _posix(path, root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:  # pragma: no cover - a file that will not parse
            findings.append(Finding("parse-error", relative, error.lineno or 0, str(error)))
            continue
        findings.extend(check_forbidden_store_write(relative, tree))
        findings.extend(check_canon_write_outside_promote(relative, tree))
        findings.extend(check_store_path_built_by_hand(relative, tree))
        findings.extend(check_hand_written_toolset(relative, tree))
    return sorted(findings, key=lambda finding: (finding.path, finding.line, finding.rule))


def check_source(relative: str, source: str) -> list[Finding]:
    """One file's worth, for the rule fixtures under `semgrep/tests/`."""
    tree = ast.parse(source, filename=relative)
    return [
        *check_forbidden_store_write(relative, tree),
        *check_canon_write_outside_promote(relative, tree),
        *check_store_path_built_by_hand(relative, tree),
        *check_hand_written_toolset(relative, tree),
    ]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    findings = check_tree(root)
    if not findings:
        print("boundaries: clean")
        return 0
    print(f"boundaries: {len(findings)} finding(s)")
    for finding in findings:
        print(f"  {finding}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
