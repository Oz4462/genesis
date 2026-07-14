#!/usr/bin/env bash
# Install CadQuery into the isolated GENESIS cad venv (never system pip / PEP 668).
# See docs/CADQUERY_VENV.md
set -euo pipefail
TARGET="${GENESIS_CAD_VENV:-/home/genesis/.venv-cad}"
echo "== CadQuery venv: $TARGET =="
if [[ ! -x "$TARGET/bin/python" ]]; then
  python3 -m venv "$TARGET"
fi
"$TARGET/bin/pip" install -U pip wheel
"$TARGET/bin/pip" install cadquery
"$TARGET/bin/python" -c "import cadquery as cq; print('cadquery', getattr(cq, '__version__', 'ok'))"
echo "Set (optional): export GENESIS_CAD_PYTHON=$TARGET/bin/python"
echo "SETUP OK"
