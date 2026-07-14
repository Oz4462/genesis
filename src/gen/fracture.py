"""Linear elastic fracture mechanics — the crack-driven failure the strength checks miss.

The stress check (structural.py) compares a stress to the static strength; fatigue.py
adds cyclic endurance; buckling.py adds instability; torsion.py adds shear. None of them
sees a CRACK. A part holding a flaw of length a fails not when the stress reaches the
yield strength but when the STRESS INTENSITY K = Y*sigma*sqrt(pi*a) reaches the material's
fracture toughness K_IC — which can happen far below yield (brittle/fast fracture). And a
sub-critical crack does not sit still: under cyclic load it GROWS a little each cycle
(Paris law), so a part that is safe today fails after enough cycles. This module adds that
two-part crack axis: instantaneous fracture, and crack-growth life.

Three textbook closed forms plus a growth integral:
  • the STRESS INTENSITY K = Y*sigma*sqrt(pi*a) — Irwin's measure of the crack-tip field;
    Y is the dimensionless geometry factor (1 for a centre crack in an infinite plate,
    1.12 for an edge crack, etc.);
  • the CRITICAL CRACK SIZE a_c = (1/pi)*(K_IC/(Y*sigma))**2 — the flaw length at which
    K = K_IC at the given stress (the exact inverse of the K formula);
  • a fracture_check returning K, a_c, and the safety factor K_IC/K against fast fracture;
  • the PARIS LIFE — cycles N to grow a crack from a_i to a_f via da/dN = C*(dK)**m with
    dK = Y*delta_sigma*sqrt(pi*a), integrated in CLOSED FORM for m != 2:
    N = (a_f**(1-m/2) - a_i**(1-m/2)) / (C*(Y*delta_sigma*sqrt(pi))**m*(1-m/2)).

Verified, not asserted: K = Y*sigma*sqrt(pi*a) is pinned to the anchor 100*sqrt(pi) for
Y=1,sigma=100,a=1; a_c inverts K exactly (plug a_c back -> K == K_IC to machine precision);
the check safety factor is K_IC/K; the Paris closed form matches a direct trapezoid
integration of da/dN to ~1e-10 for m=3 (and m=4); a larger initial crack gives fewer cycles
-- all pinned in the test.

Consistent state units (stress MPa, length mm, force N): sigma and delta_sigma in MPa,
crack length a in mm, K and K_IC in MPa*sqrt(mm). (K_IC handbook values are usually quoted
in MPa*sqrt(m); 1 MPa*sqrt(m) = sqrt(1000) ~= 31.62 MPa*sqrt(mm) -- convert before use.)
Honest boundary: small-scale-yielding LINEAR ELASTIC fracture mechanics of an ideal
through-crack with a CONSTANT geometry factor Y; it does NOT cover elastic-plastic
fracture (J-integral / CTOD when the plastic zone is large), a Y that varies as the crack
grows (real handbook Y(a/W) -- this uses a fixed Y, an approximation for deep cracks),
threshold (dK_th) or fast-fracture cut-off, crack closure, mean-stress (R-ratio) or
overload-retardation effects on the Paris constants, or mixed-mode loading (Mode I only).

Source: G. R. Irwin, "Analysis of Stresses and Strains near the End of a Crack
Traversing a Plate", J. Appl. Mech. 24 (1957) -- the stress intensity factor;
P. C. Paris & F. Erdogan, "A Critical Analysis of Crack Propagation Laws",
J. Basic Eng. 85 (1963) -- the da/dN = C*(dK)**m crack-growth law.
"""

from __future__ import annotations

import math


def stress_intensity(geometry_factor_y: float, stress: float, crack_length_a: float) -> float:
    """Mode-I stress intensity K = Y*sigma*sqrt(pi*a) (MPa*sqrt(mm)).

    Y is the dimensionless geometry factor, sigma the remote stress (MPa), a the crack
    length (mm). Irwin's measure of the crack-tip field strength. Raises ValueError on a
    negative crack length (a crack has a real, non-negative size)."""
    if crack_length_a < 0.0:
        raise ValueError("crack length a must be non-negative")
    return geometry_factor_y * stress * math.sqrt(math.pi * crack_length_a)


def critical_crack_size(
    fracture_toughness_kic: float, geometry_factor_y: float, stress: float
) -> float:
    """Critical crack length a_c = (1/pi)*(K_IC/(Y*sigma))**2 (mm).

    The flaw length at which K reaches K_IC at the given stress -- the EXACT inverse of
    ``stress_intensity`` (plugging a_c back gives K == K_IC). K_IC in MPa*sqrt(mm), sigma
    in MPa. Raises ValueError on a non-positive K_IC, geometry factor, or stress (all are
    physically positive; a zero stress means no finite critical size)."""
    if fracture_toughness_kic <= 0.0:
        raise ValueError("fracture toughness K_IC must be positive")
    if geometry_factor_y <= 0.0:
        raise ValueError("geometry factor Y must be positive")
    if stress <= 0.0:
        raise ValueError("stress must be positive (a_c is unbounded at zero stress)")
    return (1.0 / math.pi) * (fracture_toughness_kic / (geometry_factor_y * stress)) ** 2


def fracture_check(
    stress: float,
    crack_length_a: float,
    fracture_toughness_kic: float,
    geometry_factor_y: float = 1.12,
) -> dict:
    """Fast-fracture check of a cracked part under a static stress.

    Computes the stress intensity K (``stress_intensity``), the critical crack size a_c
    at this stress (``critical_crack_size``), and the safety factor against fast fracture.
    Returns ``{"stress_intensity", "critical_crack_size", "safety_factor", "ok"}``:
    stress_intensity K and fracture_toughness_kic in MPa*sqrt(mm), critical_crack_size in
    mm, safety_factor = K_IC/K, ok = safety_factor >= 1 (equivalently a < a_c). The default
    geometry_factor_y = 1.12 is the edge-crack value. Deterministic. Raises ValueError on a
    non-positive stress or via the called functions on a negative crack length / non-positive
    K_IC."""
    if stress <= 0.0:
        raise ValueError("stress must be positive")
    k = stress_intensity(geometry_factor_y, stress, crack_length_a)
    a_c = critical_crack_size(fracture_toughness_kic, geometry_factor_y, stress)
    safety_factor = math.inf if k == 0.0 else fracture_toughness_kic / k
    return {
        "stress_intensity": k,
        "critical_crack_size": a_c,
        "safety_factor": safety_factor,
        "ok": safety_factor >= 1.0,
    }


def paris_life(
    paris_coeff_c: float,
    paris_exponent_m: float,
    delta_stress: float,
    a_initial: float,
    a_final: float,
    geometry_factor_y: float = 1.12,
) -> float:
    """Cycles N to grow a crack from a_initial to a_final under the Paris law.

    Integrates da/dN = C*(dK)**m with dK = Y*delta_stress*sqrt(pi*a) in CLOSED FORM
    (constant Y, m != 2):

        N = (a_f**(1-m/2) - a_i**(1-m/2)) / (C*(Y*delta_stress*sqrt(pi))**m*(1-m/2)).

    `paris_coeff_c` C and `paris_exponent_m` m are the Paris constants (units of C follow
    from m and the MPa*sqrt(mm)/mm system), `delta_stress` is the cyclic stress RANGE
    (sigma_max - sigma_min) in MPa, a_initial/a_final in mm. The m == 2 case uses the
    logarithmic closed form ln(a_f/a_i)/(C*(Y*delta_stress*sqrt(pi))**2). Raises
    ValueError on a non-positive C, delta_stress, or crack length, or if a_final <= a_initial
    (a crack only grows)."""
    if paris_coeff_c <= 0.0:
        raise ValueError("Paris coefficient C must be positive")
    if delta_stress <= 0.0:
        raise ValueError("delta_stress (the cyclic stress range) must be positive")
    if a_initial <= 0.0 or a_final <= 0.0:
        raise ValueError("crack lengths must be positive")
    if a_final <= a_initial:
        raise ValueError("a_final must be larger than a_initial (a crack only grows)")
    # m == 2: power form divides by zero; use closed logarithmic antiderivative.
    scale = geometry_factor_y * delta_stress * math.sqrt(math.pi)
    if abs(paris_exponent_m - 2.0) < 1e-15:
        return math.log(a_final / a_initial) / (paris_coeff_c * scale ** 2)
    exponent = 1.0 - paris_exponent_m / 2.0
    numerator = a_final ** exponent - a_initial ** exponent
    denominator = (
        paris_coeff_c
        * scale ** paris_exponent_m
        * exponent
    )
    return numerator / denominator
