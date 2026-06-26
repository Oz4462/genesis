#!/usr/bin/env python3
"""check_build.py — fail-fast import-health guard for the ``gen`` package.

This catches the exact failure the 2026-06-26 island-triage caused: moving a module to
``src/gen/_experimental/`` without updating its re-export made ``import gen.cli`` (and the whole
package) fail. Run this AFTER any move / triage / refactor — and wire it as a CI gate before the
crew/grok loops are ever turned back on. Exit 0 = healthy; non-zero = a dangling import (the broken
chain is printed). The "proper" way to triage an island: move the file, then drop or guard its
re-export (``try/except ImportError``), then run this — green before you continue.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ENTRY = [
    "gen", "gen.cli", "gen.tools", "gen.runner", "gen.inventor",
    "gen.inventor.domains.thermal", "gen.discovery", "gen.pipelines", "gen.ledger",
    "gen.finalizer", "gen.physics_selection", "gen.web.app",
]


def main() -> int:
    broken: list[tuple[str, str]] = []
    optional: list[tuple[str, str]] = []
    for m in ENTRY:
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as e:
            missing = e.name or ""
            # A missing INTERNAL module (gen.*) is a real dangling-import break (the grok-triage failure
            # class). A missing THIRD-PARTY module is just an optional extra (e.g. fastapi for [web]).
            if missing == "gen" or missing.startswith("gen."):
                broken.append((m, f"ModuleNotFoundError: {e}"))
            else:
                optional.append((m, missing))
        except Exception as e:  # noqa: BLE001 — any other import error is a real break
            broken.append((m, f"{type(e).__name__}: {e}"))
    if optional:
        print("· optional (extra not installed, not a break): "
              + ", ".join(f"{m} (needs {dep})" for m, dep in optional))
    if broken:
        print("✗ BUILD BROKEN — internal dangling imports:")
        for m, err in broken:
            print(f"   {m}: {err}")
        return 1
    print(f"✓ build healthy — {len(ENTRY) - len(optional)} core entry packages import cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
