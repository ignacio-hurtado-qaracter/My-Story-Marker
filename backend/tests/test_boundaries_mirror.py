"""AC 3, AC 13 and AC 17 — the boundary rules, run through the AST mirror.

The rules of record are the YAML files under `backend/semgrep/`. They run in the local gate
and in CI (`semgrep --test` against the annotated fixtures, then a scan of `app/`); the
mirror in `tools/check_boundaries.py` implements the same rules with the standard library and
runs here, inside `pytest`, with no download (plan decision P8, amended by correction C10).

Three halves, and all are necessary:

* **The tree is clean.** A rule that never fires proves nothing about the tree.
* **The mirror flags exactly the lines semgrep must flag.** Each rule file has one annotated
  fixture, `semgrep/tests/<rule file>.py`, in semgrep's own test format: the line after a
  "ruleid" annotation must be reported and the line after an "ok" annotation must not.
  `semgrep --test` holds the YAML to those lines; this file holds the mirror to the same
  lines, so a disagreement between the two fails one side or the other instead of hiding.
* **The silent lines stay silent.** A rule that flags the *correct* way of writing a store
  file teaches people to suppress it, which is worse than a rule that misses.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.check_boundaries import check_source, check_tree

BACKEND = Path(__file__).resolve().parent.parent
RULES = BACKEND / "semgrep"
FIXTURES = RULES / "tests"
STORE_FIXTURE = FIXTURES / "forbidden-store-write.py"

SCOPE = re.compile(r"# mirror-scope: (\S+)")
ANNOTATION = re.compile(r"#\s*(ruleid|ok):\s*([\w-]+)")
RULE_ID = re.compile(r"^\s*-\s*id:\s*([\w-]+)\s*$", re.MULTILINE)


def rule_files() -> list[Path]:
    return sorted(RULES.glob("*.yaml"))


def annotated_lines(source: str) -> tuple[str, dict[str, set[int]], dict[str, set[int]]]:
    """The scope a fixture declares, and per rule the lines that must and must not fire.

    An annotation applies to the line after it, as in semgrep's test format.
    """
    lines = source.splitlines()
    scope = SCOPE.match(lines[0])
    assert scope, "a rule fixture starts with '# mirror-scope: <app path>'"
    expected: dict[str, set[int]] = {}
    silent: dict[str, set[int]] = {}
    for number, line in enumerate(lines, start=1):
        found = ANNOTATION.search(line)
        if found is None:
            continue
        kind, rule = found.groups()
        (expected if kind == "ruleid" else silent).setdefault(rule, set()).add(number + 1)
    return scope.group(1), expected, silent


# spec 001 / AC 3, AC 13, AC 17
def test_the_tree_is_clean() -> None:
    findings = check_tree(BACKEND)
    assert not findings, "boundary violations:\n" + "\n".join(str(f) for f in findings)


# spec 001 / AC 3, AC 13, AC 17 — every rule file has its fixture, and every rule it defines is
# exercised there in both directions.
@pytest.mark.parametrize("rules", rule_files(), ids=lambda path: path.stem)
def test_every_rule_has_annotated_cases_both_ways(rules: Path) -> None:
    fixture = FIXTURES / f"{rules.stem}.py"
    assert fixture.is_file(), f"{rules.name} has no fixture at {fixture}"
    _, expected, silent = annotated_lines(fixture.read_text(encoding="utf-8"))
    for rule in RULE_ID.findall(rules.read_text(encoding="utf-8")):
        assert expected.get(rule), f"{rule} has no line that must fire"
        assert silent.get(rule), f"{rule} has no line that must stay silent"


# spec 001 / AC 3, AC 13, AC 17 — the mirror reports exactly the annotated lines: every line
# semgrep must flag, and none it must not.
@pytest.mark.parametrize("rules", rule_files(), ids=lambda path: path.stem)
def test_the_mirror_flags_exactly_the_annotated_lines(rules: Path) -> None:
    fixture = FIXTURES / f"{rules.stem}.py"
    scope, expected, silent = annotated_lines(fixture.read_text(encoding="utf-8"))
    findings = check_source(scope, fixture.read_text(encoding="utf-8"))
    for rule in RULE_ID.findall(rules.read_text(encoding="utf-8")):
        flagged = {finding.line for finding in findings if finding.rule == rule}
        assert flagged == expected.get(rule, set()), (
            f"{rule}: mirror flagged {sorted(flagged)}, annotations expect "
            f"{sorted(expected.get(rule, set()))}"
        )
        assert not flagged & silent.get(rule, set())


# spec 001 / AC 3 — the store layer itself is exempt, or it could not do its job.
def test_the_store_layer_is_exempt() -> None:
    source = STORE_FIXTURE.read_text(encoding="utf-8")
    findings = check_source("app/commons/stores/writer.py", source)
    assert not [f for f in findings if f.rule == "forbidden-store-write"]


# spec 001 / AC 13 — outside `ledger/` and `agents/` the canon rule does not apply: the canon
# and cast features write their own records through their own routes.
def test_the_canon_rule_is_scoped_to_ledger_and_agents() -> None:
    source = (FIXTURES / "canon-write-outside-promote.py").read_text(encoding="utf-8")
    findings = check_source("app/canon/service.py", source)
    assert not [f for f in findings if f.rule == "canon-write-outside-promote"]


# spec 001 / AC 13 — promote and rule are the two functions that may reach canon.
def test_promote_and_rule_may_write_canon() -> None:
    source = (
        "def promote(store, record, role, target):\n"
        "    store.write(target.path, record, role=role)\n"
        "\n"
        "def rule(store, record, role):\n"
        "    store.write('canon/axioms/fold-drive.md', record, role=role)\n"
    )
    assert not check_source("app/ledger/promote.py", source)


# spec 001 / AC 13 — and nothing else is, not even a helper promote might call.
def test_any_other_function_may_not() -> None:
    source = (
        "def _apply(store, record, role, target):\n"
        "    store.write(target.path, record, role=role)\n"
    )
    findings = check_source("app/ledger/promote.py", source)
    assert [f for f in findings if f.rule == "canon-write-outside-promote"]


# spec 001 / AC 13 — `reconcile` reads; it gets no exemption to write.
def test_reconcile_is_not_exempt() -> None:
    source = (
        "def reconcile(store, record, role):\n"
        "    store.write('canon/axioms/fold-drive.md', record, role=role)\n"
    )
    findings = check_source("app/agents/turn.py", source)
    assert [f for f in findings if f.rule == "canon-write-outside-promote"]


# spec 001 / AC 3 — the discriminator that keeps `str.replace` out of the findings. The
# semgrep rule uses the same arity test, and a disagreement between the two is a bug in the
# mirror rather than a finding.
def test_string_replace_is_not_a_file_primitive() -> None:
    source = "def normalise(path: str) -> str:\n    return path.replace('\\\\', '/')\n"
    assert not check_source("app/canon/service.py", source)


# spec 001 / AC 3 — but `Path.replace(target)` still is.
def test_path_replace_is_a_file_primitive() -> None:
    source = "def move(temporary, target):\n    temporary.replace(target)\n"
    assert check_source("app/canon/service.py", source)


# spec 001 / AC 3 — the `.index/` exemption is by module, and coarse. It is worth pinning
# that it does not leak: a feature is still caught, and so is a commons module that owns no
# `.index/` path.
@pytest.mark.parametrize(
    "scope",
    ["app/canon/repository.py", "app/commons/permissions/table.py", "app/commons/llm/client.py"],
)
def test_the_index_exemption_does_not_leak(scope: str) -> None:
    source = STORE_FIXTURE.read_text(encoding="utf-8")
    assert [f for f in check_source(scope, source) if f.rule == "forbidden-store-write"]


# spec 001 / AC 3 — and that it does cover the four modules that own `.index/`.
@pytest.mark.parametrize(
    "scope",
    [
        "app/agents/records.py",
        "app/agents/lock.py",
        "app/commons/db/rebuild.py",
        "app/commons/embeddings/fastembed_impl.py",
    ],
)
def test_the_index_owners_are_exempt(scope: str) -> None:
    source = STORE_FIXTURE.read_text(encoding="utf-8")
    assert not [f for f in check_source(scope, source) if f.rule == "forbidden-store-write"]


# spec 001 / AC 3, FR-STORE-05 — the mirror implements the rule of record's SECOND rule too.
# It did not, for a while: an adversarial review planted `f"cast/{character}/..."` in a
# feature repository and the local gate stayed green while the semgrep rule would have
# fired. A mirror weaker than the rule it mirrors is worse than no mirror, because it is
# trusted.
@pytest.mark.parametrize(
    "source",
    [
        'def p(c: str) -> str:\n    return f"cast/{c}/voice.md"\n',
        'def p(c: str) -> str:\n    return "cast/%s/voice.md" % c\n',
        'def p(c: str) -> str:\n    return "manuscript/" + c + ".md"\n',
        'def p(s: str) -> str:\n    return f"scenes/{s}.yaml"\n',
    ],
    ids=["fstring", "percent", "concat", "scenes"],
)
def test_a_store_path_built_by_hand_is_caught(source: str) -> None:
    findings = check_source("app/cast/repository.py", source)
    assert [f for f in findings if f.rule == "store-path-built-by-hand"], source


# spec 001 / AC 3 — but the store layer and the permission layer build and match those paths
# for a living, so neither is a finding there.
@pytest.mark.parametrize(
    "scope", ["app/commons/stores/paths.py", "app/commons/permissions/table.py"]
)
def test_the_path_builders_are_exempt(scope: str) -> None:
    source = 'def p(c: str) -> str:\n    return f"cast/{c}/voice.md"\n'
    assert not [f for f in check_source(scope, source) if f.rule == "store-path-built-by-hand"]


# spec 001 / AC 3 — and a string that merely mentions a family is not a path.
@pytest.mark.parametrize(
    "source",
    [
        'MESSAGE = f"canon has {n} entries"\n',
        'def p(x: str) -> str:\n    return f"notes/{x}.md"\n',
    ],
    ids=["prose", "not-a-store-family"],
)
def test_no_false_positive_on_ordinary_strings(source: str) -> None:
    assert not [
        f for f in check_source("app/cast/repository.py", source)
        if f.rule == "store-path-built-by-hand"
    ]
