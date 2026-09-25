"""The AST mirror of the semgrep boundary rules (plan decision P8, amended by correction C10).

The rules of record for AC 3, AC 13 and AC 17 are the YAML files under `backend/semgrep/`.
They run in the local gate (`semgrep` 1.177 installs and runs natively on Windows through
`uvx`) and in CI; this module implements the same rules with the standard library `ast`
module so they also run inside `pytest`, with no download, on every platform.

**Both must pass, and a disagreement between them is a bug in this mirror.** The two are held
to one set of annotated fixtures, `semgrep/tests/<rule file>.py`: `semgrep --test` checks the
YAML against them and `tests/test_boundaries_mirror.py` checks this module against the same
lines. Where the two could still differ (a nested function inside `promote`, say), this one
is written to be the stricter.

The rules:

1. **forbidden-store-write** (AC 3) - no file primitive outside `app/commons/stores/`.
   FR-STORE-02. An import contract can see that a module imported `pathlib`; it cannot see
   what path the module then opened, which is why this check exists at all.
2. **canon-write-outside-promote** (AC 13) - nothing under `ledger/` or `agents/` writes
   canon except `promote` and `rule`. `promote` is the only write path into canon during
   drafting, and it only adds; `rule`, carrying a human, is the one that can overwrite. Outside
   those two functions a store write must name its path as a literal, an UPPER_CASE constant
   or a direct `paths.<helper>(...)` call, none of them canon or cast, and the canon and cast
   services' write functions may not be called.
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
import re
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
touch `.index/` is allowed to touch anything. The narrower guarantee comes from elsewhere:
`import-linter` keeps the two `commons` owners out of the features, and the one that reads
the tree to build rows (`commons/db/rebuild.py`) reads it through `Store`, whose path helpers
it imports for exactly that; the two `agents` owners hold no `Store` at all."""

TEMPORARY_FILE_WRITERS = ("app/commons/llm/claude_code_client.py",)
"""The one module outside the store layer that writes a file which is neither a store path nor
under `.index/`: the model client writes the role's system prompt into a fresh temporary
directory, because the Claude Code CLI takes it through `--system-prompt-file` (spec FR-LLM-05,
plan step 15). A temporary file is not a store path, like `.index/`.

Exempted by file, not by package, and mirrored in `semgrep/forbidden-store-write.yaml`: the
rest of `commons/llm/` -- the fake, the protocol, the estimator -- stays under the rule. The
same limit as `INDEX_WRITERS` applies (the rule sees primitives, not paths); the narrower
guarantee is that `commons.llm` may not import `commons.stores` (the internal layers contract),
so it has no way to build a store path."""

STORE_FAMILIES = ("canon", "cast", "structure", "scenes", "manuscript", "ledger")

MUTATING_METHODS = frozenset(
    {
        "open",
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

PROMOTE_FUNCTIONS = frozenset({"promote", "rule"})
"""AC 13. The only functions under `ledger/` that may reach canon, and `rule` only ever runs
with `actor: human` behind it (FR-OPS-07). `reconcile` is not among them: it reads and never
writes (FR-OPS-08), so it needs no exemption and gets none."""

CANON_RULE_SCOPE = ("app/ledger", "app/agents")
CANON_RULE_EXEMPT = ("app/agents/records.py", "app/agents/lock.py")
"""The `.index/` owners hold no `Store` and write no store file; their file writes are rule 1's
business, and the semgrep rule excludes them by the same names."""

STORE_WRITES = frozenset({"write", "write_text"})

CANON_PATH_NAMES = frozenset(
    {
        "canon_entity",
        "canon_dir",
        "cast_file",
        "cast_dir",
        "CANON",
        "CAST",
        "PROJECT",
        "STYLE",
        "LEXICON",
        "TIME",
        "RELATIONSHIPS",
    }
)
"""The `app.commons.stores.paths` helpers and constants that name a canon or cast path."""

CANON_SERVICES = ("app.canon.service", "app.cast.service")
SERVICE_WRITE = re.compile(r"(?:replace|save)_\w*")
"""The owning features' write functions (`replace_entity`, `save_dossier`, ...)."""

CONSTANT = re.compile(r"[A-Z][A-Z0-9_]*")
PATH_HELPER = re.compile(r"[a-z_]+")


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


GIFT_NOVEL_FILE_ACCESS = (
    "app/export/cli.py",
    "app/export/pdf.py",
    "app/formal/lean_runner.py",
    "app/judge/compare.py",
    "app/novel/cli.py",
    "app/novel/setup.py",
    "app/reader/changes.py",
    "app/reader/dev_seed.py",
    "app/reader/router.py",
    "app/tools/download.py",
    "app/validators/programmatic/schema.py",
)
"""Programme 004, approved by the user on 2026-09-25 (option 1 of the boundaries decision).

The gift-novel pipeline keeps its records in the authoritative database (plan 004, V4), not in
the Figure 3 stores. These files touch files that are not store paths: the generated Lean story
and per-novel Lean copies (specs 012, 007), exported PDFs (spec 014), the human-review report
(spec 011), the brief JSON Schema (spec 008), CLI brief input, the dev seed and the
authoritative database opened by the reader and the tools (`BibleRepository.open`). Exempted
by file, not by package, and mirrored in `semgrep/forbidden-store-write.yaml`; any other file
in these packages stays under the rule."""


def check_forbidden_store_write(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 1, AC 3."""
    if (
        relative.startswith(STORE_LAYER)
        or relative.startswith(INDEX_WRITERS)
        or relative in TEMPORARY_FILE_WRITERS
        or relative in GIFT_NOVEL_FILE_ACCESS
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


def _path_argument(call: ast.Call) -> ast.expr | None:
    """The path a store write is aimed at: its first positional argument or `path=`."""
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "path":
            return keyword.value
    return None


def _is_paths_module(node: ast.expr) -> bool:
    return (isinstance(node, ast.Name) and node.id == "paths") or (
        isinstance(node, ast.Attribute) and node.attr == "paths"
    )


def _names_canon(path: ast.expr) -> bool:
    """A literal `canon/...` or `cast/...`, or any mention of a canon or cast path helper."""
    literal = _string_of(path)
    if literal is not None and literal.split("/")[0] in {"canon", "cast"}:
        return True
    return any(
        isinstance(node, ast.Attribute)
        and node.attr in CANON_PATH_NAMES
        and _is_paths_module(node.value)
        for node in ast.walk(path)
    )


def _is_dotted_constant(node: ast.expr) -> bool:
    """`PROPOSED_PATH` or `repository.PROPOSED_PATH`: an UPPER_CASE name, however qualified."""
    if isinstance(node, ast.Name):
        return CONSTANT.fullmatch(node.id) is not None
    if isinstance(node, ast.Attribute) and CONSTANT.fullmatch(node.attr):
        value = node.value
        while isinstance(value, ast.Attribute):
            value = value.value
        return isinstance(value, ast.Name)
    return False


def _has_a_checkable_shape(path: ast.expr) -> bool:
    """A literal, a constant or a direct `paths.<helper>(...)` call: a path whose target can
    be read off the source. Anything else -- a variable, an attribute of an object, an
    f-string -- cannot be shown not to be canon."""
    if _string_of(path) is not None or _is_dotted_constant(path):
        return True
    return (
        isinstance(path, ast.Call)
        and isinstance(path.func, ast.Attribute)
        and isinstance(path.func.value, ast.Name)
        and path.func.value.id == "paths"
        and PATH_HELPER.fullmatch(path.func.attr) is not None
    )


def _service_writers(tree: ast.Module) -> tuple[set[str], set[str]]:
    """How this module can reach the canon and cast services' write functions: the local
    names bound to either service module, and the write functions imported by name."""
    modules: set[str] = set()
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in CANON_SERVICES:
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if f"{node.module}.{alias.name}" in CANON_SERVICES:
                    modules.add(alias.asname or alias.name)
                elif node.module in CANON_SERVICES and SERVICE_WRITE.fullmatch(alias.name):
                    functions.add(alias.asname or alias.name)
    return modules, functions


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


def _calls_a_service_writer(call: ast.Call, modules: set[str], functions: set[str]) -> bool:
    target = call.func
    if isinstance(target, ast.Name):
        return target.id in functions
    if isinstance(target, ast.Attribute) and SERVICE_WRITE.fullmatch(target.attr):
        return _dotted(target.value) in modules
    return False


def check_canon_write_outside_promote(relative: str, tree: ast.Module) -> list[Finding]:
    """Rule 2, AC 13.

    Outside `promote` and `rule`, in a module under `ledger/` or `agents/`, refuses three
    shapes: a store write whose path names canon or cast; a store write whose path cannot be
    shown not to (see `_has_a_checkable_shape`); and a call to the canon or cast service's
    write functions. The second is what makes the rule bite: `promote` itself writes canon
    through a variable (`target.path`), so a rule that only recognised canon spellings would
    miss the very shape a quiet second promotion path would take.
    """
    if not relative.startswith(CANON_RULE_SCOPE) or relative in CANON_RULE_EXEMPT:
        return []
    if _is_test(relative):
        return []

    owners = _enclosing_functions(tree)
    modules, functions = _service_writers(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        enclosing = owners.get(node.lineno, "<module>")
        if enclosing in PROMOTE_FUNCTIONS:
            continue
        reason: str | None = None
        target = node.func
        if isinstance(target, ast.Attribute) and target.attr in STORE_WRITES:
            path = _path_argument(node)
            if path is not None and _names_canon(path):
                reason = f"store write to canon or cast ({ast.unparse(path)})"
            elif path is not None and not _has_a_checkable_shape(path):
                reason = (
                    f"store write to {ast.unparse(path)}, which cannot be shown not to be "
                    "canon; pass a literal, an UPPER_CASE constant or a paths helper call"
                )
        elif _calls_a_service_writer(node, modules, functions):
            reason = f"call to the canon or cast service's {ast.unparse(target)}()"
        if reason is not None:
            findings.append(
                Finding(
                    "canon-write-outside-promote",
                    relative,
                    node.lineno,
                    f"{reason} in {enclosing}(); canon is written only by promote(), which "
                    "only adds, and rule(), which a human calls",
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
