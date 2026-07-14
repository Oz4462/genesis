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
  tests/test_the_well_probe.py \
  tests/test_runner.py \
  tests/test_inventor_score.py \
  tests/test_inventor_loop.py \
  tests/test_inventor_domains.py \
  -q
echo "== CLI demos =="
for m in research invent solve council structural humanoid aethon print bundle ideas dream well-probe; do
  case "$m" in
    research)
      timeout 60 python3 -m gen --mode research >/dev/null
      ;;
    well-probe)
      timeout 30 python3 -m gen --mode well-probe --demo >/dev/null
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
# Thermal invent path (overtemperature recipe + γ+ score) — must not regress to vacuous δ
echo "== invent thermal =="
out=$(timeout 60 python3 -m gen --mode invent --demo "Kühlung für 1kW Chip" 2>&1) || true
echo "$out" | grep -q "physik-verifiziert (δ-Physik-Gate)" || { echo "thermal invent missing gate line"; exit 1; }
echo "$out" | grep -qE "Geerdet:[[:space:]]+[1-9]" || { echo "thermal invent expected >=1 grounded"; echo "$out"; exit 1; }
echo "$out" | grep -q "by=inventor.score_proxy" || { echo "thermal invent missing γ+ score_proxy"; echo "$out"; exit 1; }
echo "  invent-thermal OK"
echo "SMOKE PASS"
