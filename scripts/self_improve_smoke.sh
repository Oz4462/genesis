#!/usr/bin/env bash
# Quick offline smoke for self-improve loop (no live LLM).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
echo "== pytest materials/wiki/backend/runner =="
python3 -m pytest \
  tests/test_materials.py \
  tests/test_materials_backend.py \
  tests/test_wikipedia.py \
  tests/test_english_search_boosts.py \
  tests/test_runner.py \
  -q
echo "== CLI demos =="
for m in research invent solve council structural humanoid aethon print bundle ideas dream; do
  case "$m" in
    research)
      timeout 60 python3 -m gen --mode research >/dev/null
      ;;
    humanoid|aethon)
      timeout 90 python3 -m gen --mode "$m" --demo >/dev/null
      ;;
    *)
      timeout 90 python3 -m gen --mode "$m" --demo >/dev/null 2>/dev/null \
        || timeout 90 python3 -m gen --mode "$m" >/dev/null
      ;;
  esac
  echo "  $m OK"
done
echo "SMOKE PASS"
