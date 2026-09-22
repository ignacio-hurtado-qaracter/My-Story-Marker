#!/usr/bin/env bash
# The local gate (spec 001, AC 30). One command, from `backend/`:
#
#     ./gate.sh
#
# Every stage runs even when an earlier one fails, so a single run shows everything that is
# wrong rather than the first thing. The summary lists failures *and* skips: a stage whose
# inputs do not exist yet is reported as SKIPPED by name, never passed over in silence.
#
# This is the POSIX half, and the one CI runs. `semgrep` is a real stage here, unlike in
# `gate.ps1`, because it does not run natively on Windows (plan decision P8).

set -u -o pipefail

failures=()
skips=()

stage() {
  local name="$1"
  shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then
    return 0
  fi
  local code=$?
  failures+=("$name")
  printf -- '--- %s FAILED (exit %d)\n' "$name" "$code"
  return 0
}

skip() {
  local name="$1"
  local why="$2"
  skips+=("$name  ($why)")
  printf '\n=== %s === SKIPPED: %s\n' "$name" "$why"
}

stage 'ruff'          uv run ruff check .
stage 'mypy --strict' uv run mypy .
stage 'bandit'        uv run bandit -q -c pyproject.toml -r app tools scripts
stage 'import-linter' uv run lint-imports

if command -v semgrep >/dev/null 2>&1; then
  if compgen -G 'semgrep/*.yaml' >/dev/null; then
    stage 'semgrep' semgrep --error --quiet --config semgrep/ app
  else
    skip 'semgrep' 'no rules written yet (plan step 6)'
  fi
else
  skip 'semgrep' 'semgrep not installed on this machine (P8); CI is the rule of record'
fi

if compgen -G 'schemas/*.json' >/dev/null; then
  stage 'JSON Schema freshness' uv run python scripts/export_schemas.py --check
else
  skip 'JSON Schema freshness' 'no schemas exported yet (plan step 3)'
fi

if [ -f openapi.json ]; then
  stage 'OpenAPI freshness' uv run python scripts/export_openapi.py --check
else
  skip 'OpenAPI freshness' 'openapi.json not exported yet (plan step 7)'
fi

stage 'pytest' uv run pytest

printf '\n================ gate summary ================\n'
if [ ${#skips[@]} -gt 0 ]; then
  printf 'skipped:\n'
  for s in "${skips[@]}"; do printf -- '  - %s\n' "$s"; done
fi
if [ ${#failures[@]} -eq 0 ]; then
  printf 'all stages green\n'
  exit 0
fi
printf 'failed:\n'
for f in "${failures[@]}"; do printf -- '  - %s\n' "$f"; done
exit 1
