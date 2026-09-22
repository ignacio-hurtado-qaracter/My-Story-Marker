"""AC 3, AC 13 and AC 17 — the boundary rules, run locally through the AST mirror.

The rules of record are the YAML files under `backend/semgrep/`, which run in CI on Linux.
`semgrep` does not run natively on Windows (plan decision P8), so `tools/check_boundaries.py`
mirrors the same three rules with the standard library and runs here on every platform.

Two halves, and both are necessary:

* **The tree is clean.** A rule that never fires proves nothing about the tree.
* **The rules fire on the planted fixtures, and stay silent on the planted negatives.** A
  rule narrowed until it matches nothing would pass the first half forever. The negatives
  matter as much: a rule that flags the *correct* way of writing a store file teaches people
  to suppress it, which is worse than a rule that misses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_boundaries import check_source, check_tree

BACKEND = Path(__file__).resolve().parent.parent
FIXTURES = BACKEND / "semgrep" / "tests"

# Each planted fixture is evaluated under a path that puts it inside the rule's scope: the
# rules are scoped by directory, so the same source is a finding under `app/ledger/` and not
# under `app/commons/stores/`.
POSITIVES = [
    ("writes_store_directly.py", "app/canon/service.py", "forbidden-store-write"),
    ("writes_canon_from_ledger.py", "app/ledger/service.py", "canon-write-outside-promote"),
    ("hand_written_toolset.py", "app/agents/roles.py", "hand-written-toolset"),
]

NEGATIVE_SCOPES = [
    "app/canon/service.py",
    "app/ledger/service.py",
    "app/agents/roles.py",
    "app/scenes/repository.py",
]


# spec 001 / AC 3, AC 13, AC 17
def test_the_tree_is_clean() -> None:
    findings = check_tree(BACKEND)
    assert not findings, "boundary violations:\n" + "\n".join(str(f) for f in findings)


# spec 001 / AC 3, AC 13, AC 17 — a rule that never fires proves nothing.
@pytest.mark.parametrize(("name", "scope", "rule"), POSITIVES, ids=[p[2] for p in POSITIVES])
def test_each_rule_fires_on_its_planted_fixture(name: str, scope: str, rule: str) -> None:
    source = (FIXTURES / "positive" / name).read_text(encoding="utf-8")
    findings = check_source(scope, source)
    triggered = [finding for finding in findings if finding.rule == rule]
    assert triggered, f"{rule} did not fire on {name}"


# spec 001 / AC 3 — every planted call in the store fixture is caught, not just the first.
def test_the_store_fixture_is_caught_call_by_call() -> None:
    source = (FIXTURES / "positive" / "writes_store_directly.py").read_text(encoding="utf-8")
    findings = check_source("app/canon/service.py", source)
    assert len(findings) >= 6, f"expected every planted primitive to be caught, got {findings}"


# spec 001 / AC 3, AC 13, AC 17 — and silence where the code is right.
@pytest.mark.parametrize("scope", NEGATIVE_SCOPES, ids=str)
def test_no_rule_fires_on_the_planted_negatives(scope: str) -> None:
    source = (FIXTURES / "negative" / "uses_the_store_layer.py").read_text(encoding="utf-8")
    findings = check_source(scope, source)
    assert not findings, f"false positives under {scope}: {[str(f) for f in findings]}"


# spec 001 / AC 3 — the store layer itself is exempt, or it could not do its job.
def test_the_store_layer_is_exempt() -> None:
    source = (FIXTURES / "positive" / "writes_store_directly.py").read_text(encoding="utf-8")
    assert not check_source("app/commons/stores/writer.py", source)


# spec 001 / AC 3 — `.index/` is not a store, so the orchestrator's own records are exempt
# by name (Decision R2-1, FR-TURN-06).
@pytest.mark.parametrize("scope", ["app/agents/records.py", "app/agents/lock.py"])
def test_the_index_writers_are_exempt(scope: str) -> None:
    source = (FIXTURES / "positive" / "writes_store_directly.py").read_text(encoding="utf-8")
    assert not [f for f in check_source(scope, source) if f.rule == "forbidden-store-write"]


# spec 001 / AC 13 — promote and rule are the two functions that may reach canon.
def test_promote_and_rule_may_write_canon() -> None:
    source = (
        "def promote(store, record, role):\n"
        "    store.write('canon/axioms/fold-drive.md', record, role=role)\n"
        "\n"
        "def rule(store, record, role):\n"
        "    store.write('canon/axioms/fold-drive.md', record, role=role)\n"
    )
    assert not check_source("app/ledger/promote.py", source)


# spec 001 / AC 13 — and nothing else is.
def test_any_other_function_may_not() -> None:
    source = (
        "def merge_quietly(store, record, role):\n"
        "    store.write('canon/axioms/fold-drive.md', record, role=role)\n"
    )
    findings = check_source("app/ledger/service.py", source)
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
