"""PoV-1 harness — does trust-core's verification math replace + extend GENESIS's?

Read-only against GENESIS production code. Proves three things with numbers:

  A. EQUIVALENCE  — GENESIS `gen.calibration.conformal_quantile` and trust-core
     `trust_core.conformal.split.split_conformal_threshold` are the SAME estimator
     (same finite-sample formula k=ceil((n+1)(1-alpha))). Verified over many
     deterministic randomized cases. Boundary convention differs only in how the
     "calibration set too small" case is reported (GENESIS -> None, trust-core -> +inf);
     that is treated as equivalent.

  B. NEW CAPABILITY — trust-core CCDD streaming drift detection flags a real
     distribution shift and stays quiet on a no-shift stream. GENESIS has NO drift
     detector today, so this is a net-new guarantee.

  C. REPLACEABLE LOC — how much split-conformal code GENESIS could delete by
     depending on trust-core, plus how much CCDD code GENESIS would otherwise have
     to author itself to gain drift detection.

Deterministic: fixed seeds, no wall-clock in any decision. Writes a JSON report to
runs/pov/pov1/report.json and prints a human summary. Exit 0 iff all gates PASS.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

# --- locate the two source trees (this repo + the sibling trust-core repo) ----
_SCRIPT = Path(__file__).resolve()
_GENESIS_REPO = _SCRIPT.parents[2]              # ...\Genesis\genesis\genesis
_GENESIS_SRC = _GENESIS_REPO / "src"
_DESKTOP = _GENESIS_REPO.parents[2]             # ...\Desktop
_TRUSTCORE_SRC = _DESKTOP / "alle apps" / "trust-core" / "src"

for p in (_GENESIS_SRC, _TRUSTCORE_SRC):
    if not p.exists():
        raise SystemExit(f"required source tree missing: {p}")
    sys.path.insert(0, str(p))

from gen.calibration import conformal_quantile  # noqa: E402  (GENESIS)
from trust_core.conformal.split import split_conformal_threshold  # noqa: E402
from trust_core.conformal.ccdd import calibrate, StreamingDetector  # noqa: E402


# --- A. equivalence ----------------------------------------------------------
def prove_equivalence() -> dict:
    rng = np.random.default_rng(20260613)
    cases = 0
    mismatches: list[dict] = []
    boundary_agreements = 0
    for _ in range(5000):
        n = int(rng.integers(1, 60))
        scores = rng.normal(size=n).tolist()
        alpha = float(rng.uniform(0.01, 0.5))
        g = conformal_quantile(scores, alpha)           # None when k>n
        t = split_conformal_threshold(scores, alpha)    # +inf when k>n
        cases += 1
        if g is None:
            # GENESIS abstains exactly when trust-core returns +inf (k>n).
            if t == math.inf:
                boundary_agreements += 1
            else:
                mismatches.append({"n": n, "alpha": alpha, "genesis": None, "trustcore": t})
        else:
            if not (t != math.inf and abs(g - t) <= 1e-12):
                mismatches.append({"n": n, "alpha": alpha, "genesis": g, "trustcore": t})
    return {
        "cases": cases,
        "exact_value_matches": cases - boundary_agreements - len(mismatches),
        "boundary_agreements": boundary_agreements,
        "mismatches": len(mismatches),
        "examples": mismatches[:5],
        "pass": len(mismatches) == 0,
    }


# --- B. CCDD drift detection (capability GENESIS lacks) ----------------------
def prove_drift() -> dict:
    rng = np.random.default_rng(424242)
    d, n_cal, window = 8, 400, 100
    baseline = rng.normal(0.0, 1.0, size=(n_cal, d))
    model = calibrate(baseline)

    def run_stream(shift: float) -> dict:
        det = StreamingDetector(model, window_size=window, alpha_inner=0.05, alpha_outer=0.01)
        alerted = False
        first_alert_at = None
        for i in range(300):
            emb = rng.normal(shift, 1.0, size=d)
            det.observe(f"x{i}", emb)
            if det.check_alert() is not None:
                alerted = True
                if first_alert_at is None:
                    first_alert_at = i
        return {"alerted": alerted, "first_alert_at": first_alert_at}

    no_shift = run_stream(0.0)     # H0: same distribution -> expect quiet
    shifted = run_stream(1.5)      # real shift -> expect alert
    passed = (not no_shift["alerted"]) and shifted["alerted"]
    return {
        "no_shift": no_shift,
        "shifted": shifted,
        "genesis_has_drift_detection": False,
        "pass": passed,
    }


# --- C. replaceable / saved LOC ----------------------------------------------
def _loc(path: Path) -> int:
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def count_loc() -> dict:
    cal = (_GENESIS_SRC / "gen" / "calibration.py").read_text(encoding="utf-8").splitlines()
    # split-conformal block in GENESIS that trust-core would supply (replaceable).
    repl = [ln for ln in cal if ln.strip()]
    start = next(i for i, ln in enumerate(cal) if "def conformal_quantile" in ln)
    replaceable = sum(1 for ln in cal[start:] if ln.strip())
    ccdd_dir = _TRUSTCORE_SRC / "trust_core" / "conformal" / "ccdd"
    ccdd_loc = sum(_loc(p) for p in ccdd_dir.glob("*.py"))
    return {
        "genesis_calibration_total_loc": len(repl),
        "genesis_split_conformal_replaceable_loc": replaceable,
        "trustcore_ccdd_loc_genesis_would_otherwise_author": ccdd_loc,
        # informational: net effect confirmed in Phase 1 once the adapter exists.
        "note": "drift detection alone = "
        f"{ccdd_loc} tested LOC GENESIS gets for free; "
        f"{replaceable} GENESIS LOC become a thin adapter.",
    }


def main() -> int:
    equiv = prove_equivalence()
    drift = prove_drift()
    loc = count_loc()
    gate_pass = equiv["pass"] and drift["pass"]
    report = {
        "pov": "PoV-1 trust-core",
        "run_id": "pov1",
        "deterministic_seeds": [20260613, 424242],
        "equivalence": equiv,
        "drift": drift,
        "loc": loc,
        "gate_pass": gate_pass,
    }
    out_dir = _GENESIS_REPO / "runs" / "pov" / "pov1"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== PoV-1: trust-core ===")
    print(
        f"A. equivalence  : {equiv['exact_value_matches']} exact + "
        f"{equiv['boundary_agreements']} boundary, {equiv['mismatches']} mismatch "
        f"over {equiv['cases']} cases -> {'PASS' if equiv['pass'] else 'FAIL'}"
    )
    print(
        f"B. CCDD drift   : no-shift alerted={drift['no_shift']['alerted']}, "
        f"shift alerted={drift['shifted']['alerted']} "
        f"(first@{drift['shifted']['first_alert_at']}) -> {'PASS' if drift['pass'] else 'FAIL'}"
    )
    print(
        f"C. LOC          : {loc['genesis_split_conformal_replaceable_loc']} GENESIS LOC "
        f"-> adapter; +{loc['trustcore_ccdd_loc_genesis_would_otherwise_author']} CCDD LOC for free"
    )
    print(f"GATE: {'PASS' if gate_pass else 'FAIL'}  (report: {out_dir / 'report.json'})")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
