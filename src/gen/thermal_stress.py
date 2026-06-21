"""Thermal-expansion mismatch stress — the heat-and-structure coupling (closed form).

The conduction layer (thermal.py) finds the temperature; the stress layer finds the
load stress. Between them sits a failure neither sees alone: a temperature change makes
materials want to change size, and when that is CONSTRAINED — a part clamped between
rigid supports, or two bonded materials with different expansion coefficients — it
builds stress with no external load at all. A brass insert in a PLA bracket, a metal
trace on a polymer board, any heated press-fit: each can crack purely from a
temperature swing. This module adds the three standard closed forms.

  • CONSTRAINED bar — a member held at fixed length and heated by ΔT carries
    σ = −E·α·ΔT (compression when heated, tension when cooled), independent of length.
  • BONDED parallel bars — two materials forced to a common length share an internal
    force: compatibility (equal strain) + equilibrium (no net force) give each stress
    exactly. Reduces to zero when the coefficients match and to the fully-constrained
    value when one partner is rigid.
  • BIMETAL curvature — two bonded layers of different α bend on heating; Timoshenko's
    1925 closed form gives the curvature.

Verified, not asserted: the constrained value is the exact σ = −EαΔT; the bonded-bar
solution satisfies equilibrium to machine precision, vanishes for equal coefficients,
and tends to the constrained limit for a rigid partner; the bimetal curvature vanishes
for equal coefficients and reduces to the textbook 1.5·Δα·ΔT/h for equal modulus and
thickness — all pinned in the test.

Consistent units: E in MPa, α in 1/K, ΔT in K, areas in mm², thicknesses in mm →
stress in MPa, curvature in 1/mm. Honest boundary: linear elastic, uniform ΔT, 1-D
(bars) or Timoshenko beam (bimetal) — no through-thickness gradient, no yielding, no
viscoelastic relaxation (which would relieve the stress over time in a polymer).

Auto-selected via physics_selection RECIPE for thermal mismatch when "thermal.delta_t" present; used in gate_delta_physics for high-temp constrained stress checks.
"""

from __future__ import annotations


def free_thermal_strain(cte: float, delta_t: float) -> float:
    """Unconstrained thermal strain ε = α·ΔT (dimensionless) — how much the material
    WANTS to grow; constraint of this strain is what builds the stress."""
    return cte * delta_t


def constrained_thermal_stress(e_modulus: float, cte: float, delta_t: float) -> float:
    """Stress in a fully constrained bar heated by ΔT: σ = −E·α·ΔT (MPa). Negative
    (compression) for heating, positive (tension) for cooling — independent of length.
    Raises ValueError on a non-positive modulus."""
    if e_modulus <= 0.0:
        raise ValueError("modulus must be positive")
    return -e_modulus * cte * delta_t


def bonded_bars_mismatch(
    e1: float, area1: float, cte1: float,
    e2: float, area2: float, cte2: float,
    delta_t: float,
) -> dict:
    """Two materials bonded in parallel and forced to a COMMON length, heated by ΔT
    with no external load.

    Compatibility ε = α₁ΔT + σ₁/E₁ = α₂ΔT + σ₂/E₂ and equilibrium A₁σ₁ + A₂σ₂ = 0 give
    the common strain ε = (A₁E₁α₁ + A₂E₂α₂)·ΔT/(A₁E₁ + A₂E₂) and σᵢ = Eᵢ(ε − αᵢΔT).
    Returns ``{"stress1", "stress2", "common_strain", "residual_force"}`` (residual_force
    = A₁σ₁ + A₂σ₂, ~0 by construction — an equilibrium self-check). Deterministic.
    Raises ValueError on non-positive modulus or area."""
    if min(e1, e2, area1, area2) <= 0.0:
        raise ValueError("moduli and areas must be positive")
    k1, k2 = area1 * e1, area2 * e2
    common_strain = (k1 * cte1 + k2 * cte2) * delta_t / (k1 + k2)
    stress1 = e1 * (common_strain - cte1 * delta_t)
    stress2 = e2 * (common_strain - cte2 * delta_t)
    return {
        "stress1": stress1,
        "stress2": stress2,
        "common_strain": common_strain,
        "residual_force": area1 * stress1 + area2 * stress2,
    }


def bimetal_curvature(
    cte1: float, cte2: float, delta_t: float,
    e1: float, e2: float, h1: float, h2: float,
) -> float:
    """Curvature κ = 1/ρ (1/mm) of a bonded bimetallic strip heated by ΔT — Timoshenko
    (1925). Layer 1 (α₁, E₁, thickness h₁) and layer 2 (α₂, E₂, h₂); a positive result
    (α₂ > α₁) bends the strip toward layer 1.

        κ = 6(α₂−α₁)ΔT(1+m)² / [h(3(1+m)² + (1+mn)(m² + 1/(mn)))],
        m = h₁/h₂,  n = E₁/E₂,  h = h₁+h₂.

    Reduces to 1.5(α₂−α₁)ΔT/h for equal modulus and thickness, and to 0 when the
    coefficients match. Raises ValueError on non-positive modulus or thickness."""
    if min(e1, e2, h1, h2) <= 0.0:
        raise ValueError("moduli and thicknesses must be positive")
    m = h1 / h2
    n = e1 / e2
    h = h1 + h2
    denom = h * (3.0 * (1.0 + m) ** 2 + (1.0 + m * n) * (m * m + 1.0 / (m * n)))
    return 6.0 * (cte2 - cte1) * delta_t * (1.0 + m) ** 2 / denom


def thermal_mismatch_check(
    e1: float, area1: float, cte1: float,
    e2: float, area2: float, cte2: float,
    delta_t: float,
    *,
    strength1: float,
    strength2: float,
) -> dict:
    """Thermal-mismatch DFM check on a bonded pair: the larger |mismatch stress| against
    each material's strength.

    Returns ``{"stress1", "stress2", "safety_factor", "governing", "ok"}``: safety_factor
    is the smaller of strengthᵢ/|σᵢ|, governing names the limiting material, ok = both
    stresses stay within their strengths. Deterministic. Raises ValueError on a
    non-positive strength."""
    if strength1 <= 0.0 or strength2 <= 0.0:
        raise ValueError("strengths must be positive")
    res = bonded_bars_mismatch(e1, area1, cte1, e2, area2, cte2, delta_t)
    s1, s2 = abs(res["stress1"]), abs(res["stress2"])
    n1 = strength1 / s1 if s1 > 0.0 else float("inf")
    n2 = strength2 / s2 if s2 > 0.0 else float("inf")
    governing = "material1" if n1 <= n2 else "material2"
    return {
        "stress1": res["stress1"],
        "stress2": res["stress2"],
        "safety_factor": min(n1, n2),
        "governing": governing,
        "ok": min(n1, n2) >= 1.0,
    }
