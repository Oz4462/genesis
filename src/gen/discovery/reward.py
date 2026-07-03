"""reward — a dimensional-consistency reward for training a discovery proposer (the unoccupied lever).

Every public symbolic-regression trainer (SR-Scientist, SymbArena, LLM-SR) rewards regression error
ONLY; AI-Feynman / SINDy use units to PRUNE the search, never to REWARD the proposer. GENESIS's
distinctive, publishable move (competitive-intel finding #1): make DIMENSIONAL CONSISTENCY a reward
term, so a proposer is trained to suggest laws that are dimensionally SOUND, not merely numerically
close. This module is that reward; the actual GRPO/PPO training loop needs a GPU and is external.

The reward is deterministic and bounded in [0, 1]: ``dimensional_consistency`` is 1.0 when the proposed
exponents form the target dimension exactly and decays with the L1 residual of the produced-minus-target
base-exponent vector; ``discovery_reward`` multiplies the (clipped) fit R² by that consistency, so a
dimensionally-IMPOSSIBLE law scores LOW even at a perfect fit — the anti-hallucination signal the gate
enforces, shaped into the proposer's reward. Reuses GENESIS's own dimensional algebra; offline.
"""

from __future__ import annotations

import math

from ..verification.units import parse_unit


def dimensional_consistency(
    target_unit: str, source_units: dict[str, str], exponents: dict[str, float]
) -> float:
    """How dimensionally consistent the power law ``∏ source^exp`` is with ``target_unit``: 1.0 when the
    produced dimension matches exactly, decaying as ``exp(−residual)`` with the L1 distance between the
    produced and target base-exponent vectors. Deterministic; unknown sources contribute nothing."""
    target = dict(parse_unit(target_unit).exponents)
    produced: dict[str, float] = {}
    for name, exp in exponents.items():
        unit = source_units.get(name)
        if unit is None:
            continue
        for base, base_exp in parse_unit(unit).exponents:
            produced[base] = produced.get(base, 0.0) + exp * base_exp
    bases = set(target) | set(produced)
    residual = sum(abs(produced.get(b, 0.0) - float(target.get(b, 0))) for b in bases)
    return math.exp(-residual)


def discovery_reward(
    *,
    r_squared: float,
    target_unit: str,
    source_units: dict[str, str],
    exponents: dict[str, float],
) -> float:
    """Bounded training reward in [0, 1]: the clipped fit R² multiplicatively gated by dimensional
    consistency. A dimensionally-impossible proposal (consistency → 0) cannot score high even at R²=1 —
    rewarding the proposer for laws that are BOTH well-fitting AND dimensionally sound, which no public
    SR trainer does."""
    fit = max(0.0, min(1.0, r_squared))
    return fit * dimensional_consistency(target_unit, source_units, exponents)
