"""Fatigue — cyclic-load failure below the static strength (closed form, no FEM).

The stress check (structural.py) compares a peak stress to the static strength; it
cannot see that a part cycled enough times fails at a stress FAR below that strength.
A shaft, a spring, a vibrating bracket: each can pass every static check and still
crack by fatigue. This module adds the standard high-cycle-fatigue checks — the third
mechanical lifetime axis alongside stress (static) and resonance (modal).

Three pieces, each a textbook closed form:
  • the ENDURANCE LIMIT S_e — the stress amplitude a steel survives indefinitely,
    ≈0.5·UTS (capped), optionally reduced by Marin surface/size/reliability factors;
  • the BASQUIN S-N law σ_a = σ'_f·(2N)^b — finite life at a given amplitude;
  • MEAN-STRESS corrections (Goodman, Soderberg, Gerber) — a real load has a mean
    stress σ_m as well as an amplitude σ_a, and a tensile mean cuts the allowable
    amplitude. Goodman (line to UTS) is the standard conservative choice; Soderberg
    (line to yield) is stricter; Gerber (parabola) is least conservative.

Plus Miner's rule for cumulative damage under a spectrum of amplitudes.

Verified, not asserted: the Goodman/Soderberg/Gerber lines reduce to their exact
endpoints (pure alternating → fail at S_e; pure mean → fail at UTS/S_y), Soderberg ≤
Goodman ≤ Gerber in allowable load, Basquin inverts exactly (σ→N→σ), and Miner sums
to 1 at failure — all pinned in the test.

Consistent units: stresses in MPa (as structural.py). Honest boundary: high-cycle
(stress-based) fatigue of nominally elastic material; it does NOT cover low-cycle
plastic fatigue (Coffin-Manson), crack growth (Paris law), or environmental effects —
and the mean-stress lines assume a TENSILE mean (a compressive mean is non-damaging
and is conservatively ignored, not credited).
"""

from __future__ import annotations

import math


def endurance_limit(uts: float, *, marin_factor: float = 1.0, cap: float = 700.0) -> float:
    """Corrected endurance limit S_e (MPa) for steel: S_e' = min(0.5·UTS, cap), times a
    combined Marin `marin_factor` (the product of surface/size/load/reliability factors,
    each ≤1). The 0.5·UTS rule and the ~700 MPa plateau hold for steels to ~1400 MPa
    UTS (Shigley). Raises ValueError on a non-positive UTS."""
    if uts <= 0.0:
        raise ValueError("UTS must be positive")
    base = min(0.5 * uts, cap)
    return marin_factor * base


def basquin_life(stress_amplitude: float, fatigue_strength_coeff: float,
                 fatigue_strength_exponent: float) -> float:
    """Cycles to failure N_f from Basquin's law σ_a = σ'_f·(2N)^b, inverted:
    N_f = ½·(σ_a/σ'_f)^(1/b). `fatigue_strength_exponent` b is negative. MPa in."""
    if stress_amplitude <= 0.0:
        raise ValueError("stress amplitude must be positive")
    if fatigue_strength_exponent >= 0.0:
        raise ValueError("the Basquin exponent b must be negative")
    return 0.5 * (stress_amplitude / fatigue_strength_coeff) ** (1.0 / fatigue_strength_exponent)


def basquin_stress(cycles: float, fatigue_strength_coeff: float,
                   fatigue_strength_exponent: float) -> float:
    """Stress amplitude σ_a = σ'_f·(2N)^b that fails at `cycles` (the Basquin S-N
    curve evaluated forward). The exact inverse of `basquin_life`."""
    if cycles <= 0.0:
        raise ValueError("cycles must be positive")
    return fatigue_strength_coeff * (2.0 * cycles) ** fatigue_strength_exponent


def goodman_safety_factor(stress_amplitude: float, mean_stress: float,
                          uts: float, endurance: float) -> float:
    """Fatigue safety factor by the modified Goodman line: 1/n = σ_a/S_e + σ_m/UTS.
    n ≥ 1 means infinite life. A compressive (negative) mean is conservatively treated
    as zero (no credit). Raises ValueError on non-positive UTS or S_e."""
    if uts <= 0.0 or endurance <= 0.0:
        raise ValueError("UTS and endurance limit must be positive")
    if stress_amplitude < 0.0:
        raise ValueError("stress amplitude must be non-negative (negative = upstream sign error, not infinite life)")
    sm = max(mean_stress, 0.0)
    demand = stress_amplitude / endurance + sm / uts
    return math.inf if demand <= 0.0 else 1.0 / demand


def soderberg_safety_factor(stress_amplitude: float, mean_stress: float,
                            yield_strength: float, endurance: float) -> float:
    """Fatigue safety factor by the Soderberg line: 1/n = σ_a/S_e + σ_m/S_y. Uses the
    yield strength (not UTS), so it is stricter than Goodman. Compressive mean → 0."""
    if yield_strength <= 0.0 or endurance <= 0.0:
        raise ValueError("yield strength and endurance limit must be positive")
    if stress_amplitude < 0.0:
        raise ValueError("stress amplitude must be non-negative (negative = upstream sign error, not infinite life)")
    sm = max(mean_stress, 0.0)
    demand = stress_amplitude / endurance + sm / yield_strength
    return math.inf if demand <= 0.0 else 1.0 / demand


def gerber_safety_factor(stress_amplitude: float, mean_stress: float,
                         uts: float, endurance: float) -> float:
    """Fatigue safety factor by the Gerber parabola: n·(σ_a/S_e) + (n·σ_m/UTS)² = 1,
    solved for n. Least conservative of the three (a parabola above the Goodman line).
    Compressive mean → 0 (reduces to n = S_e/σ_a)."""
    if uts <= 0.0 or endurance <= 0.0:
        raise ValueError("UTS and endurance limit must be positive")
    if stress_amplitude < 0.0:
        raise ValueError("stress amplitude must be non-negative (negative = upstream sign error, not infinite life)")
    if stress_amplitude == 0.0:
        return math.inf
    a = stress_amplitude / endurance
    b = max(mean_stress, 0.0) / uts
    if b == 0.0:
        return 1.0 / a
    # b²·n² + a·n − 1 = 0 → positive root
    return (-a + math.sqrt(a * a + 4.0 * b * b)) / (2.0 * b * b)


def goodman_check(stress_amplitude: float, mean_stress: float, uts: float,
                  endurance: float) -> dict:
    """Goodman fatigue check. Returns ``{"goodman_value", "safety_factor", "ok",
    "infinite_life"}``: goodman_value = σ_a/S_e + σ_m/UTS (≤1 ⇒ safe), safety_factor =
    1/goodman_value, ok = safety_factor ≥ 1; infinite_life mirrors ok (the load sits on
    or below the endurance line). Deterministic."""
    n = goodman_safety_factor(stress_amplitude, mean_stress, uts, endurance)
    value = math.inf if n == 0 else 1.0 / n
    return {
        "goodman_value": value,
        "safety_factor": n,
        "ok": n >= 1.0,
        "infinite_life": n >= 1.0,
    }


def miner_damage(blocks: list[tuple[float, float]]) -> dict:
    """Palmgren-Miner cumulative damage D = Σ nᵢ/Nᵢ over load blocks `(applied_cycles,
    cycles_to_failure)`. Returns ``{"damage", "ok", "remaining_life_fraction"}``: the
    part is predicted to fail when D reaches 1, so ok = D < 1 and the remaining fraction
    is 1−D (clamped at 0). Raises ValueError if any block has non-positive life."""
    damage = 0.0
    for applied, life in blocks:
        if life <= 0.0:
            raise ValueError("cycles_to_failure must be positive")
        damage += applied / life
    return {
        "damage": damage,
        "ok": damage < 1.0,
        "remaining_life_fraction": max(0.0, 1.0 - damage),
    }
