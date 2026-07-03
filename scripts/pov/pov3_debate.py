"""PoV-3 harness — does buch-llm multi-critic debate aggregation catch more unsound
items than a single skeptic, without losing sound-recall, deterministically?

SCOPE / HONESTY (read this):
  * The AGGREGATOR is buch-llm's REAL code: `DebateOrchestrator.run_debate`
    (softmax-weighted mean + accept-decision), loaded in isolation (no LLM, no
    package import — buch-llm's 7 critics are themselves declared stubs today).
  * The CRITIC INPUTS here are SIMULATED imperfect verifiers (each catches an
    unsound item independently with a fixed detect-rate). This isolates and proves
    the *aggregation property*: independent partial detectors, combined, leak less.
  * What this does NOT prove (deferred, owner-gated): that real LLM cross-model
    critics actually disagree usefully on GENESIS specs, and the end-to-end live
    leak-rate. That needs LLM-wired critics + a live Ollama run.

Deterministic: seeded RNG, scores precomputed. Writes runs/pov/pov3/report.json.
Exit 0 iff the aggregation property holds (debate leak-rate < single-critic leak-rate
AND sound-recall preserved AND identical across two runs).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_SCRIPT = Path(__file__).resolve()
_GENESIS_REPO = _SCRIPT.parents[2]
_DESKTOP = _GENESIS_REPO.parents[2]
_MAD_PATH = (
    _DESKTOP / "alle apps" / "buch llm" / "src" / "buch_llm" / "orchestrator" / "multi_agent_debate.py"
)
if not _MAD_PATH.exists():
    raise SystemExit(f"buch-llm debate module missing: {_MAD_PATH}")

# Load the single module file in isolation (its top-level imports are stdlib only;
# the one relative import is lazy and never reached without bandit_state).
_spec = importlib.util.spec_from_file_location("mad_isolated", _MAD_PATH)
_mad = importlib.util.module_from_spec(_spec)
sys.modules["mad_isolated"] = _mad
_spec.loader.exec_module(_mad)
DebateOrchestrator = _mad.DebateOrchestrator
CriticReport = _mad.CriticReport

N_CRITICS = 7
ACCEPT_THRESHOLD = 0.7
DETECT_RATE = 0.4          # a single critic catches an unsound item 40% of the time
SOUND_MEAN, UNSOUND_LOW, MISS_HIGH = 0.85, 0.30, 0.80
SD = 0.05


class _FixedCritic:
    """A critic whose verdict for the current item is fixed (injected score)."""

    def __init__(self, name: str, score: float) -> None:
        self.name = name
        self._score = float(min(0.999, max(0.001, score)))

    def __call__(self, chapter_text, richtlinien, history=None) -> "CriticReport":
        return CriticReport(name=self.name, score=self._score)


def _item_scores(rng: np.random.Generator, sound: bool) -> list[float]:
    out: list[float] = []
    for _ in range(N_CRITICS):
        if sound:
            out.append(float(rng.normal(SOUND_MEAN, SD)))
        else:
            if rng.random() < DETECT_RATE:
                out.append(float(rng.normal(UNSOUND_LOW, SD)))   # caught
            else:
                out.append(float(rng.normal(MISS_HIGH, SD)))     # missed
    return out


def _evaluate(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n_each = 300
    single_leak = single_sound_accept = 0
    debate_leak = debate_sound_accept = 0

    for sound in (False, True):
        for _ in range(n_each):
            scores = _item_scores(rng, sound)
            # Single-skeptic baseline = critic[0] accepts iff its score >= threshold.
            single_accept = scores[0] >= ACCEPT_THRESHOLD
            # Debate = buch-llm's REAL aggregator over all N critics.
            critics = [_FixedCritic(f"c{i}", s) for i, s in enumerate(scores)]
            orch = DebateOrchestrator(critics, accept_threshold=ACCEPT_THRESHOLD)
            debate_accept = orch.run_debate("item", {}).accept_decision

            if sound:
                single_sound_accept += int(single_accept)
                debate_sound_accept += int(debate_accept)
            else:
                single_leak += int(single_accept)      # unsound accepted = leak
                debate_leak += int(debate_accept)

    return {
        "n_per_class": n_each,
        "single_leak_rate": single_leak / n_each,
        "debate_leak_rate": debate_leak / n_each,
        "single_sound_recall": single_sound_accept / n_each,
        "debate_sound_recall": debate_sound_accept / n_each,
    }


def main() -> int:
    a = _evaluate(13)
    b = _evaluate(13)  # determinism check: identical seed -> identical result
    deterministic = a == b

    leak_improved = a["debate_leak_rate"] < a["single_leak_rate"]
    recall_preserved = a["debate_sound_recall"] >= a["single_sound_recall"] - 1e-9
    gate = leak_improved and recall_preserved and deterministic

    report = {
        "pov": "PoV-3 buch-llm multi-critic debate aggregation",
        "run_id": "pov3",
        "scope": "real aggregator + simulated imperfect verifiers; LLM-critics+live deferred",
        "params": {
            "n_critics": N_CRITICS,
            "accept_threshold": ACCEPT_THRESHOLD,
            "single_critic_detect_rate": DETECT_RATE,
        },
        "metrics": a,
        "deterministic": deterministic,
        "gate_pass": gate,
    }
    out = _GENESIS_REPO / "runs" / "pov" / "pov3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== PoV-3: buch-llm multi-critic debate ===")
    print(
        f"leak-rate (unsound accepted): single={a['single_leak_rate']:.3f} -> "
        f"debate={a['debate_leak_rate']:.3f}  (lower is better)"
    )
    print(
        f"sound-recall               : single={a['single_sound_recall']:.3f} -> "
        f"debate={a['debate_sound_recall']:.3f}"
    )
    print(f"deterministic={deterministic}  -> GATE: {'PASS' if gate else 'FAIL'}")
    print(f"(report: {out / 'report.json'})")
    return 0 if gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
