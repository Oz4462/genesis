"""Notch fatigue — a geometric stress raiser cuts the fatigue strength (closed form).

The static stress-concentration factor K_t (a hole, fillet, groove, keyway) multiplies
the local PEAK stress; structural.py and torsion.py apply it to a static check. But
under CYCLIC load the fatigue strength is NOT cut by the full K_t: real materials show
NOTCH SENSITIVITY q in [0, 1] — a small plastic zone and the steep stress gradient at a
sharp notch let the material "average out" some of the peak, so the effective fatigue
factor K_f is between 1 and K_t. A shaft fillet, a bolt thread root, a plate hole under
reversed loading: each fails by fatigue at a stress the bare K_t would over-predict (too
conservative) and the no-concentration check would under-predict (unsafe). This module
adds that bridge from the static K_t to the fatigue limit — the piece that connects
stress-concentration geometry to high-cycle life.

Three textbook closed forms:
  * Peterson NOTCH SENSITIVITY q = 1 / (1 + a/r) — a is a material constant (mm), r the
    notch-root radius (mm); q rises toward 1 as the notch gets blunt (large r) and falls
    toward 0 as it gets sharp (small r);
  * the FATIGUE NOTCH FACTOR K_f = 1 + q*(K_t - 1) — the fraction q of the static
    concentration excess (K_t - 1) that the fatigue strength actually feels;
  * the NOTCH-REDUCED ENDURANCE LIMIT Se_notched = Se / K_f — the smooth-specimen
    endurance limit divided by K_f (K_f acts as a strength-reduction factor).

Plus a DFM-style notch_fatigue_check returning K_f, q, the reduced endurance limit, a
safety factor against the local effective stress, and an ok bool.

Verified, not asserted: q -> 1 (so K_f -> K_t) for a blunt notch (a/r -> 0), q -> 0 (so
K_f -> 1) for a sharp tiny notch (a/r -> inf), 1 < K_f < K_t for any finite r, and the
concrete anchor K_t=3, r=1 mm, a=0.25 mm -> q=0.8, K_f=2.6, Se_notched=Se/2.6 — all
pinned in the test.

Consistent units (as fatigue.py / structural.py): stresses (Se, nominal) in MPa,
lengths (notch radius, Peterson constant a) in mm; q, K_t, K_f dimensionless. Honest
boundary: empirical Peterson notch sensitivity for high-cycle (stress-based) fatigue of
metals; q is an EMPIRICAL fit, not a first-principles result, and the material constant
a depends on the steel/alloy and its strength (e.g. a ~ 0.01..0.02 mm for steels) and
must be supplied — this module does not invent a from the UTS. It assumes K_t is already
known for the geometry (from a chart / FEA / a peterson-Kt formula), a single notch in
the high-cycle regime, and a tensile reversed load; it does not cover low-cycle plastic
notches, crack initiation/growth (fracture mechanics), or multiaxial notch states.

Source: Peterson notch-sensitivity q = 1/(1 + a/r); K_f = 1 + q*(K_t - 1) (Neuber /
Peterson). R. E. Peterson, *Stress Concentration Factors*, Wiley 1974; J. E. Shigley &
R. G. Budynas, *Shigley's Mechanical Engineering Design*, 10th ed., ch. 6 (fatigue).
"""

from __future__ import annotations

import math


def notch_sensitivity(notch_radius: float, peterson_constant_a: float) -> float:
    """Peterson notch sensitivity q = 1 / (1 + a/r), dimensionless in [0, 1].

    `notch_radius` r and `peterson_constant_a` a are both in mm. q -> 1 as the notch
    gets blunt (r >> a, the fatigue strength feels the full K_t) and q -> 0 as it gets
    sharp (r << a, the notch barely matters to fatigue). Raises ValueError on a
    non-positive radius or a negative material constant (a is a real, non-negative
    length the material supplies; r is a real positive geometry)."""
    if notch_radius <= 0.0:
        raise ValueError("notch radius must be positive")
    if peterson_constant_a < 0.0:
        raise ValueError("Peterson constant a must be non-negative")
    return 1.0 / (1.0 + peterson_constant_a / notch_radius)


def fatigue_notch_factor(
    kt: float, notch_radius: float, peterson_constant_a: float
) -> float:
    """Fatigue notch factor K_f = 1 + q*(K_t - 1), with q from `notch_sensitivity`.

    K_f is the fraction q of the static concentration excess (K_t - 1) that the fatigue
    strength actually feels: K_f = K_t when q = 1 (blunt notch) and K_f = 1 when q = 0
    (sharp tiny notch), and strictly between for finite r. `kt` is the (>= 1) static
    stress-concentration factor. Raises ValueError on K_t < 1 (a stress raiser cannot
    relieve stress) or via `notch_sensitivity` on a bad radius/constant."""
    if kt < 1.0:
        raise ValueError("stress-concentration factor K_t must be >= 1")
    q = notch_sensitivity(notch_radius, peterson_constant_a)
    return 1.0 + q * (kt - 1.0)


def notch_endurance_limit(smooth_endurance_se: float, kf: float) -> float:
    """Notch-reduced endurance limit Se_notched = Se / K_f (MPa).

    The smooth-specimen endurance limit `smooth_endurance_se` (MPa) divided by the
    fatigue notch factor K_f >= 1 (K_f acts as a strength-reduction factor on the
    notched part). Raises ValueError on a non-positive Se or a K_f < 1."""
    if smooth_endurance_se <= 0.0:
        raise ValueError("smooth endurance limit Se must be positive")
    if kf < 1.0:
        raise ValueError("fatigue notch factor K_f must be >= 1")
    return smooth_endurance_se / kf


def notch_fatigue_check(
    nominal_alternating_stress: float,
    kt: float,
    notch_radius: float,
    peterson_constant_a: float,
    smooth_endurance_se: float,
) -> dict:
    """Notch high-cycle-fatigue check against the smooth endurance limit.

    Computes q (Peterson), K_f = 1 + q*(K_t - 1), the local effective alternating stress
    K_f * nominal, and the reduced endurance limit Se / K_f. Returns ``{"kf", "q",
    "se_notched", "local_effective_stress", "safety_factor", "ok"}``: stresses in MPa,
    safety_factor = Se / (K_f * nominal) (equivalently Se_notched / nominal),
    ok = safety_factor >= 1 (infinite life). Deterministic. Raises ValueError on a
    non-positive nominal stress (or via the called functions on a bad K_t / radius /
    constant / Se)."""
    if nominal_alternating_stress <= 0.0:
        raise ValueError("nominal alternating stress must be positive")
    q = notch_sensitivity(notch_radius, peterson_constant_a)
    kf = fatigue_notch_factor(kt, notch_radius, peterson_constant_a)
    se_notched = notch_endurance_limit(smooth_endurance_se, kf)
    local_effective = kf * nominal_alternating_stress
    safety_factor = math.inf if local_effective == 0.0 else smooth_endurance_se / local_effective
    return {
        "kf": kf,
        "q": q,
        "se_notched": se_notched,
        "local_effective_stress": local_effective,
        "safety_factor": safety_factor,
        "ok": safety_factor >= 1.0,
    }
