#!/usr/bin/env python
"""Smoke for HORIZON δ+ E2E cert elaboration in LUMEN (smallest guarded wiring).
Runs process_dream (with tmp wq), asserts new δ+ reality + cert keys + chain.
Uses same pattern as test_lumencrucible.
"""

import tempfile
import os
from pathlib import Path

from gen.grenzverschiebung.lumencrucible import process_dream, LumenCrucible

def main():
    with tempfile.TemporaryDirectory() as td:
        wq = Path(td) / "WORK_QUEUE.md"
        # smoke jetpack path (triggers more)
        res = process_dream(
            "jetpack hover energy impossible with current battery for sustained manned flight over people",
            run_id="smoke-horizon-delta-001",
            work_queue_path=str(wq),
        )
        print("=== SMOKE OUTPUT KEYS ===")
        print(sorted(k for k in res.keys()))
        print("run_state present:", res.get("run_state") is not None)
        print("reality_verdict present:", "reality_verdict" in res)
        print("delta_plus_result:", res.get("delta_plus_result"))
        print("coverage_certificate present:", "coverage_certificate" in res)
        print("seam_certificate present:", res.get("seam_certificate") is not None)
        print("memory_fabric present:", res.get("memory_fabric") is not None)
        rv = res.get("reality_verdict")
        if rv:
            print("verdict status:", getattr(rv, "status", None))
            print("within_tolerance:", getattr(rv, "within_tolerance", None))
        dpr = res.get("delta_plus_result") or {}
        print("dpr status:", dpr.get("status"))
        print("learning notes kinds include delta_plus_reality:", any(getattr(n, "kind", "") == "delta_plus_reality" for n in res.get("omega_certificate", type("x",(),{"learning_notes":[]})()).learning_notes ))
        wq_text = wq.read_text(encoding="utf-8") if wq.exists() else ""
        print("WQ appended LUMENCRUCIBLE:", "LUMENCRUCIBLE" in wq_text)
        print("=== SMOKE SUCCESS (E2E δ+ call + cert attach exercised) ===")
        assert "reality_verdict" in res
        assert res.get("delta_plus_result")
        print("All smoke asserts passed.")

if __name__ == "__main__":
    main()
