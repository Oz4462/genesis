"""Live end-to-end smoke — REAL models, REAL search, REAL fetch, REAL cross-model.

Not a test (no asserts on content): it runs the actual Phase α pipeline against a
local Ollama (generator + verifier of different families) and the keyless
Wikipedia backend, then prints the report and the full agent log so the real
behaviour — verified findings AND honest gaps — is visible. The system is allowed
to abstain; abstention is a valid GENESIS output, not a failure.

Usage:  py -3 scripts/live_smoke.py "your question" [generator] [verifier]
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console is cp1252; report has 'α'

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.cli import build_live, format_report  # noqa: E402
from gen.config import Config, config_hash  # noqa: E402
from gen.runner import load_checkpoint, run  # noqa: E402


def _capped_config(generator: str, verifier: str) -> Config:
    # Same models the deps run on (keeps the skeptic's cross-model audit and
    # config_hash consistent), but cap refine rounds to keep the smoke bounded.
    models = {"generator": generator, "verifier": verifier}
    return Config.from_dict(
        {
            "phase_alpha": {"models": models, "max_refine_rounds": 1},
            "phase_beta": {"models": models, "max_refine_rounds": 1},
        }
    )


async def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "What is a geometric modeling kernel in CAD software?"
    )
    generator = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:14b"
    verifier = sys.argv[3] if len(sys.argv) > 3 else "gemma4:latest"

    deps, _ = build_live(generator, verifier)
    cfg = _capped_config(generator, verifier)
    ckpt_dir = str(Path(__file__).resolve().parents[1] / "runs")

    print(f"QUESTION: {question}")
    print(f"generator={generator}  verifier={verifier}  config_hash={config_hash(cfg)[:12]}")
    print("running live pipeline (real models, this takes minutes)...\n", flush=True)

    t0 = time.time()
    report = await run(question, deps, config=cfg, run_id="live-smoke", checkpoint_dir=ckpt_dir)
    dt = time.time() - t0

    print(format_report(report))
    print(f"\nelapsed: {dt:.0f}s")
    print(f"verified findings: {len(report.statement_to_claim)}  "
          f"gaps: {len(report.gaps)}  sources used: {len(report.sources_used)}")

    # The checkpoint carries the full audit trail (per-agent log + every claim with
    # its status/provenance) — this is the real proof of what each agent did.
    ckpt = load_checkpoint(str(Path(ckpt_dir) / "live-smoke" / "checkpoint.json"))
    print("\n===== FULL AGENT LOG (audit trail) =====")
    for line in ckpt["log"]:
        print("  " + line)
    print("\n===== EVERY CLAIM (status + provenance) =====")
    for c in ckpt["claims"]:
        print(f"  [{c['status']}] conf={c['confidence']:.2f} :: {c['text'][:90]}")
        print(f"       sources={c['sources']}  verification={c['verification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
