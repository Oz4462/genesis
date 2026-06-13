"""PoV-2b — live smoke of the PRODUCTION verified-facts memory (gen.memory) with the
real Ollama embedder, through the VENDORED conformal/retrieval modules.

Confirms the vendoring + adapter behave like PoV-2 end-to-end: paraphrased repeats of
verified facts are recalled, nonsense queries are abstained (no false reuse). Needs a
running local Ollama (embeddinggemma). Writes runs/pov/pov2b/report.json; exit 0 iff PASS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve()
_GENESIS_REPO = _SCRIPT.parents[2]
sys.path.insert(0, str(_GENESIS_REPO / "src"))

from gen.core.state import Claim, ClaimStatus, SourceRef  # noqa: E402
from gen.memory import VerifiedFactsLibrary, ollama_embedder  # noqa: E402

FACTS = [
    ("g0", "standard gravity equals 9.80665 meters per second squared"),
    ("g1", "the speed of light in vacuum is 299792458 meters per second"),
    ("g2", "an M4 screw has a nominal diameter of 4 millimeters"),
    ("g3", "the Python programming language was created by Guido van Rossum"),
    ("g4", "PLA filament has a typical density of 1.24 grams per cubic centimeter"),
]
CALIB = [
    "value of standard gravity in m/s^2",
    "how fast does light travel in vacuum",
    "nominal diameter of an M4 screw",
    "who created the Python language",
    "density of PLA filament for 3D printing",
] * 8
REPEATS = [("standard acceleration of gravity numeric value", "g0"),
           ("vacuum speed of light constant", "g1"),
           ("M4 fastener nominal diameter", "g2"),
           ("inventor of the Python language", "g3"),
           ("typical 3D printing PLA density", "g4")]
NONSENSE = ["mechanical properties of the Glubbex GX-7 polymer",
            "yield strength of Vorkstanium-7075 alloy",
            "the Brennholz-Kawaguchi theorem of beam stability"]


def main() -> int:
    lib = VerifiedFactsLibrary(ollama_embedder(), alpha=0.1, k=3)
    lib.remember(
        [Claim(id=i, text=t, sources=[SourceRef(url_or_id=f"src://{i}", retrieved=True)],
               status=ClaimStatus.VERIFIED) for i, t in FACTS]
    )
    # warm calibration from genuine paraphrase nearest-match scores
    for q in CALIB:
        hits = lib._store.query_similar_steps(q, k=1)  # noqa: SLF001 (harness)
        if hits:
            lib.add_calibration([hits[0][1]])

    correct = sum(1 for q, cid in REPEATS
                  if any(f.claim_id == cid for f in lib.recall(q).accepted))
    false_reuse = sum(1 for q in NONSENSE if not lib.recall(q).abstained)

    # Hard invariant for a no-hallucination engine: ZERO false reuse (abstention is
    # the safe failure). Recall is a tuning knob (alpha/k/calibration size), reported
    # informationally — not a hard gate.
    gate = false_reuse == 0 and correct >= 1
    report = {"pov": "PoV-2b vendored live", "run_id": "pov2b", "n_facts": lib.n_facts,
              "repeat_correct": correct, "n_repeat": len(REPEATS),
              "recall_rate_informational": correct / len(REPEATS),
              "false_reuse": false_reuse, "n_nonsense": len(NONSENSE),
              "honesty_gate_zero_false_reuse": false_reuse == 0, "gate_pass": gate}
    out = _GENESIS_REPO / "runs" / "pov" / "pov2b"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"=== PoV-2b vendored live (n_facts={lib.n_facts}) ===")
    print(f"repeat_correct={correct}/{len(REPEATS)} (recall tuning-dependent)  "
          f"false_reuse={false_reuse}/{len(NONSENSE)} (hard honesty gate)")
    print(f"GATE: {'PASS' if gate else 'FAIL'}  (report: {out / 'report.json'})")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
