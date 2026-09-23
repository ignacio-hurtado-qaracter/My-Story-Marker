#!/usr/bin/env bash
# The local gate (spec 001, AC 30). One command, from `backend/`:
#
#     ./gate.sh
#
# Every stage runs even when an earlier one fails, so a single run shows everything that is
# wrong rather than the first thing. The summary lists failures *and* skips: a stage whose
# inputs do not exist yet is reported as SKIPPED by name, never passed over in silence.
#
# This is the POSIX half, and the one CI runs. `semgrep` runs through `uvx`, pinned to the
# same version as `gate.ps1` (plan decision P8, amended by correction C10): `--test` holds each
# rule to its annotated fixture under `semgrep/tests/`, then a scan of `app/` must be clean.

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

SEMGREP_VERSION='1.177.0'

# One rule file at a time, failing unless semgrep says its tests passed: a config that
# fails to load is reported but does not change semgrep's exit code, so the stage would
# otherwise pass having tested less than it claims (and on Windows the parallel form races
# on semgrep's own settings file). Same logic as gate.ps1.
semgrep_rule_test() {
  local output
  output=$(uvx --python 3.12 "semgrep==${SEMGREP_VERSION}" --test --metrics=off \
    --disable-version-check --config "$1" "$2" 2>&1)
  printf '%s\n' "$output"
  grep -q 'All tests passed' <<<"$output" && ! grep -q 'produced errors' <<<"$output"
}

if compgen -G 'semgrep/*.yaml' >/dev/null; then
  for rule_file in semgrep/*.yaml; do
    rule_name=$(basename "$rule_file" .yaml)
    stage "semgrep --test ${rule_name}" semgrep_rule_test "$rule_file" "semgrep/tests/${rule_name}.py"
  done
  stage 'semgrep' uvx --python 3.12 "semgrep==${SEMGREP_VERSION}" scan --error --quiet --metrics=off --disable-version-check --config semgrep/ app
else
  skip 'semgrep' 'no rules written yet (plan step 6)'
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
