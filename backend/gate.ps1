# The local gate (spec 001, AC 30). One command, from `backend/`:
#
#     .\gate.ps1
#
# Every stage runs even when an earlier one fails, so a single run shows everything that is
# wrong rather than the first thing. The summary at the end lists failures *and* skips: a
# stage whose inputs do not exist yet is reported as SKIPPED by name, never passed over in
# silence, because a green gate that quietly checked less is worse than a red one.
#
# `semgrep` runs here through `uvx`, pinned, so the rules of record for AC 3, 13 and 17 run
# locally as well as in CI (plan decision P8, amended by correction C10: semgrep 1.177 runs
# natively on Windows). Two stages: `--test` holds each rule to its annotated fixture under
# `semgrep/tests/`, then a scan of `app/` must be clean. The AST mirror in
# `tools/check_boundaries.py` still runs inside pytest against the same fixtures.

$ErrorActionPreference = 'Continue'

$failures = New-Object System.Collections.ArrayList
$skips    = New-Object System.Collections.ArrayList

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][scriptblock] $Body
    )
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $Body
    if ($LASTEXITCODE -ne 0) {
        [void]$failures.Add($Name)
        Write-Host "--- $Name FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
    }
}

function Skip-Stage {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][string] $Why
    )
    [void]$skips.Add("$Name  ($Why)")
    Write-Host ""
    Write-Host "=== $Name === SKIPPED: $Why" -ForegroundColor Yellow
}

Invoke-Stage 'ruff'         { uv run ruff check . }
Invoke-Stage 'mypy --strict' { uv run mypy . }
Invoke-Stage 'bandit'       { uv run bandit -q -c pyproject.toml -r app tools scripts }
Invoke-Stage 'import-linter' { uv run lint-imports }

$SemgrepVersion = '1.177.0'
$env:PYTHONUTF8 = '1'
Invoke-Stage 'semgrep rule tests' {
    uvx --python 3.12 "semgrep==$SemgrepVersion" --test --metrics=off --disable-version-check --config semgrep/ semgrep/tests/
}
Invoke-Stage 'semgrep' {
    uvx --python 3.12 "semgrep==$SemgrepVersion" scan --error --quiet --metrics=off --disable-version-check --config semgrep/ app
}

if (Test-Path 'schemas') {
    $schemaFiles = Get-ChildItem 'schemas' -Filter '*.json' -ErrorAction SilentlyContinue
} else {
    $schemaFiles = @()
}
if ($schemaFiles.Count -gt 0) {
    Invoke-Stage 'JSON Schema freshness' { uv run python scripts/export_schemas.py --check }
} else {
    Skip-Stage 'JSON Schema freshness' 'no schemas exported yet (plan step 3)'
}

if (Test-Path 'openapi.json') {
    Invoke-Stage 'OpenAPI freshness' { uv run python scripts/export_openapi.py --check }
} else {
    Skip-Stage 'OpenAPI freshness' 'openapi.json not exported yet (plan step 7)'
}

Invoke-Stage 'pytest' { uv run pytest }

Write-Host ""
Write-Host "================ gate summary ================"
if ($skips.Count -gt 0) {
    Write-Host "skipped:" -ForegroundColor Yellow
    foreach ($s in $skips) { Write-Host "  - $s" -ForegroundColor Yellow }
}
if ($failures.Count -eq 0) {
    Write-Host "all stages green" -ForegroundColor Green
    exit 0
}
Write-Host "failed:" -ForegroundColor Red
foreach ($f in $failures) { Write-Host "  - $f" -ForegroundColor Red }
exit 1
