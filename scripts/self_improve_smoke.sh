#!/usr/bin/env bash
# Quick offline smoke for self-improve loop (no live LLM).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
echo "== pytest materials/wiki/backend =="
python3 -m pytest tests/test_materials.py tests/test_materials_backend.py tests/test_wikipedia.py tests/test_english_search_boosts.py -q
echo "== CLI demos =="
for m in research invent council structural humanoid; do
  if [[ "$m" == research ]]; then
    timeout 60 python3 -m gen --mode research >/dev/null
  elif [[ "$m" == humanoid ]]; then
    timeout 90 python3 -m gen --mode humanoid --demo >/dev/null
  else
    timeout 60 python3 -m gen --mode "$m" --demo >/dev/null 2>/dev/null || timeout 60 python3 -m gen --mode "$m" >/dev/null
  fi
  echo "  $m OK"
done
echo "SMOKE PASS"
