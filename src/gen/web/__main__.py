r"""Run the GENESIS web UI locally (Zukunftstechnik leap demo UI with 3D/AR/provenance).

**PowerShell (empfohlen - exakt so kopieren):**
  cd "C:\Users\Ozan\Desktop\Genesis\genesis\genesis"
  $env:PYTHONPATH = "src"
  python -m gen.web --port 8080

**Noch besser (einmalig):**
  cd "C:\Users\Ozan\Desktop\Genesis\genesis\genesis"
  pip install -e ".[web]"
  python -m gen.web --port 8080

Danach im Browser: http://127.0.0.1:8080
Die Seite enthält den 3D-Explorer (Three.js + WebXR + Live-Sliders für Bio/DRC + Provenance + 2036-Export).

Binds to 127.0.0.1 only — the UI and the engine stay on this machine.
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path


def _ensure_importable():
    """Stellt sicher, dass das 'gen'-Package gefunden wird, auch wenn PYTHONPATH nicht gesetzt ist.
    Funktioniert bei src-Layout, wenn man aus dem Projekt-Root startet oder das Skript direkt aufruft.
    """
    here = Path(__file__).resolve()
    # hier: .../src/gen/web/__main__.py  → parents[3] = .../src
    src_dir = here.parents[3]
    if src_dir.is_dir() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


def main() -> int:
    _ensure_importable()

    import uvicorn
    from .app import create_app

    parser = argparse.ArgumentParser(prog="gen.web", description="GENESIS local web UI (8080 for leap demos)")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
