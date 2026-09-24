#!/usr/bin/env bash
# Run TLC on the gift-novel harness model (spec 013, AC 3).
#
# Usage: formal/tla/run-tlc.sh [Module] [extra TLC args...]
#   Module defaults to GiftNovelHarness (reads Module.tla and Module.cfg).
#
# Downloads a pinned tla2tools.jar into formal/tla/tools/ (git-ignored) if it is missing,
# checks its SHA-256, runs TLC and tees the output to formal/tla/tlc-output.txt.
# Needs Java 11+ on PATH. Development-time only; never run per generation.
set -euo pipefail

TLA_VERSION="1.8.0"
TLA_URL="https://github.com/tlaplus/tlaplus/releases/download/v${TLA_VERSION}/tla2tools.jar"
TLA_SHA256="32d64fbbc464559fc7192341b27b885fa4eb6b92d1648d2b49fb9cdcb7aacf81"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR="${HERE}/tools/tla2tools.jar"
MODULE="${1:-GiftNovelHarness}"
shift || true

if [[ ! -f "${JAR}" ]]; then
  mkdir -p "${HERE}/tools"
  echo "Downloading tla2tools.jar v${TLA_VERSION} ..." >&2
  curl -fsSL -o "${JAR}.part" "${TLA_URL}"
  mv "${JAR}.part" "${JAR}"
fi

actual="$(sha256sum "${JAR}" | cut -d' ' -f1)"
if [[ "${actual}" != "${TLA_SHA256}" ]]; then
  echo "tla2tools.jar checksum mismatch: ${actual} (expected ${TLA_SHA256})" >&2
  exit 1
fi

cd "${HERE}"
# -deadlock is not passed: the model has explicit terminal stuttering, so a real deadlock
# is reported as an error.
java -XX:+UseParallelGC -cp "${JAR}" tlc2.TLC \
  -workers auto -cleanup -metadir "${HERE}/states" \
  -config "${MODULE}.cfg" "${MODULE}.tla" "$@" 2>&1 \
  | grep --line-buffered -v '^Picked up JAVA_TOOL_OPTIONS' \
  | tee "${HERE}/tlc-output.txt"
exit "${PIPESTATUS[0]}"
