"""Run the GENESIS web UI locally:  python -m gen.web  [--port 8077]

Binds to 127.0.0.1 only — the UI and the engine stay on this machine.
"""

from __future__ import annotations

import argparse


def main() -> int:
    import uvicorn

    from .app import create_app

    parser = argparse.ArgumentParser(prog="gen.web", description="GENESIS local web UI")
    parser.add_argument("--port", type=int, default=8077)
    args = parser.parse_args()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
