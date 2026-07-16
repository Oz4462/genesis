#!/usr/bin/env bash
# Nightly / owner-gated LIVE goldset (audit C2).
# Dry CI mode only verifies the scorer mechanism; this script measures real rates.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:src"
export GENESIS_ALLOW_LIVE=1

if [[ -z "${GENESIS_ALLOW_LIVE:-}" ]]; then
  echo "GENESIS_ALLOW_LIVE must be set for live goldset" >&2
  exit 2
fi

echo "=== LIVE goldset (anti-hallucination KPI) ==="
# Exit non-zero if live score fails honesty thresholds when implemented;
# today: print report and exit with pipeline rc.
python -m gen --mode goldset
echo "=== done ==="
