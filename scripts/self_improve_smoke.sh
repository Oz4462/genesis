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
  tests/test_physics_selection.py \
  tests/test_physics_validation.py \
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
echo "$out" | grep -qE "by=inventor.score_(proxy|recomputable)" || { echo "thermal invent missing γ+ score front"; echo "$out"; exit 1; }
echo "$out" | grep -q "plate_k=401" || { echo "thermal invent expected copper plate_k=401"; echo "$out"; exit 1; }
echo "  invent-thermal OK"
# Material-aware plate k (Al brief → registry aluminum k=205)
out_al=$(timeout 60 python3 -m gen --mode invent --demo "Kühlung Aluminium 1kW" 2>&1) || true
echo "$out_al" | grep -qE "Geerdet:[[:space:]]+[1-9]" || { echo "Al thermal invent expected >=1 grounded"; echo "$out_al"; exit 1; }
echo "$out_al" | grep -q "plate_k=205" || { echo "Al thermal invent expected plate_k=205"; echo "$out_al"; exit 1; }
echo "  invent-thermal-al OK"
# Cad-venv print path (skip if cad python missing — honest optional)
if [[ -x "${GENESIS_CAD_PYTHON:-/home/genesis/.venv-cad/bin/python}" ]]; then
  echo "== print via cad-venv =="
  pout=$(timeout 120 python3 -m gen --mode print --demo 2>&1) || true
  echo "$pout" | grep -qE "Status:[[:space:]]+(print_ready|needs_attention)" \
    || { echo "print demo expected print_ready/needs_attention when cad venv present"; echo "$pout"; exit 1; }
  echo "  print-cad OK"
else
  echo "== print via cad-venv SKIP (no GENESIS_CAD_PYTHON / .venv-cad) =="
fi
echo "SMOKE PASS"
