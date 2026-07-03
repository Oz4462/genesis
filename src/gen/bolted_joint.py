"""Bolted-joint preload — the load-sharing failure a nominal stress check misses.

The stress check (structural.py) and the bolt-shear check size a fastener against
the EXTERNAL load alone. Neither sees what a torqued bolt actually does: the wrench
PRELOADS the bolt in tension and clamps the joined members in compression. Under that
preload an external tensile load P does NOT just add to the bolt — it is SHARED
between bolt and members in proportion to their stiffnesses, so the bolt sees only a
FRACTION C of P added on top of its full preload, while the clamp force in the members
drops. Two distinct things can then go wrong that a nominal P/A_t stress completely
misses: the preloaded bolt can be far closer to yield than the external load suggests
(F_i + C*P >> P), and the joint can SEPARATE — the members lose all clamp force and
the bolt suddenly carries the entire load with no help. This module adds that axis.

Five textbook closed forms (Shigley / VDI 2230), each a sound algebraic relation:
  • PRELOAD from torque, F_i = T/(K*d), the nut-factor (torque-tension) estimate
    (K ~= 0.2 as-received steel) — T in N*mm, d in mm give F_i in N;
  • the JOINT STIFFNESS FACTOR C = k_b/(k_b + k_m), the fraction of the external load
    the BOLT carries (the members carry 1-C); C is in [0, 1] by construction;
  • the BOLT LOAD F_bolt = F_i + C*P (preload plus the bolt's share of P);
  • the SEPARATION LOAD P_sep = F_i/(1 - C), the external load at which the member
    clamp force F_m = F_i - (1-C)*P just reaches zero and the joint opens;
  • a DFM-style bolted_joint_check returning the bolt stress, separation margin,
    yield safety, and an ok bool (safe only if it neither separates NOR yields).

Verified, not asserted: C in [0, 1] always (stiff bolt vs soft member -> C near 1,
soft bolt -> C near 0); the anchor F_i = T/(K*d) with T=10000 N*mm, d=10 mm, K=0.2
gives 5000 N; with k_b = k_m -> C = 0.5 and F_i = 5000 -> P_sep = 10000 N; the member
force is exactly zero at P = P_sep; and the true preloaded bolt stress (F_i + C*P)/A_t
is far above the naive nominal P/A_t (which omits the preload) — all pinned in the test.

Consistent N-mm-MPa units (as structural.py): torque T in N*mm, diameters/areas in mm
and mm**2, forces in N, stresses (proof strength, bolt stress) in MPa. Honest boundary:
static, linear-elastic load sharing of a CONCENTRICALLY loaded, already-preloaded
joint by the standard spring model. It does NOT cover the torque-tension scatter (the
nut factor K varies ~+-25% with lubrication/surface, so F_i is an estimate, not a
measured preload), eccentric/prying loads, gasket creep or embedding relaxation that
sheds preload over time, fatigue of the bolt (use fatigue.py on the alternating part
C*P/2), or thread-stripping / member-bearing — and the member stiffness k_m itself
(Rotscher/VDI frustum) is taken as a given input here, not derived.

Source: J. E. Shigley & R. G. Budynas, *Mechanical Engineering Design* (bolted-joint
preload, the load factor C = k_b/(k_b+k_m), bolt load F_b = F_i + C*P and separation
load P_0 = F_i/(1-C)); VDI 2230 (systematic calculation of high-duty bolted joints);
the torque-tension relation T = K*F_i*d (nut factor K).
"""

from __future__ import annotations

import math


def preload_from_torque(
    torque: float, nominal_diameter: float, k_factor: float = 0.2
) -> float:
    """Bolt preload F_i = torque/(k_factor*nominal_diameter) (N) from the applied
    tightening torque.

    The torque-tension (nut-factor) relation T = K*F_i*d inverted. `torque` in N*mm,
    `nominal_diameter` in mm, dimensionless `k_factor` K (~0.2 for as-received steel)
    give F_i in N. K lumps thread + under-head friction; it is an estimate, not a
    measured preload. Raises ValueError on a non-positive diameter or k_factor (a real
    bolt has a positive size and the friction model needs a positive factor)."""
    if nominal_diameter <= 0.0:
        raise ValueError("nominal diameter must be positive")
    if k_factor <= 0.0:
        raise ValueError("k_factor (nut factor) must be positive")
    return torque / (k_factor * nominal_diameter)


def joint_stiffness_factor(bolt_stiffness_kb: float, member_stiffness_km: float) -> float:
    """Joint stiffness factor C = k_b/(k_b + k_m), the fraction of the external load
    carried by the BOLT (the members carry 1 - C).

    C lies in [0, 1] by construction: a bolt much stiffer than its members (k_b >> k_m)
    -> C near 1 (the bolt takes almost all of the added load); a soft bolt in stiff
    members -> C near 0. `bolt_stiffness_kb`, `member_stiffness_km` in N/mm (any
    consistent stiffness unit — only their ratio matters). Raises ValueError on a
    non-positive stiffness (a real spring has positive stiffness)."""
    if bolt_stiffness_kb <= 0.0 or member_stiffness_km <= 0.0:
        raise ValueError("bolt and member stiffness must be positive")
    return bolt_stiffness_kb / (bolt_stiffness_kb + member_stiffness_km)


def bolt_load(preload_Fi: float, external_load_P: float, stiffness_factor_C: float) -> float:
    """Total bolt load F_bolt = F_i + C*P (N) under preload plus an external tensile
    load.

    Only the fraction C of the external load P adds to the bolt; the rest unloads the
    member clamp force. At P = 0 the bolt load is exactly the preload F_i. `preload_Fi`
    and `external_load_P` in N, `stiffness_factor_C` from ``joint_stiffness_factor``.
    Raises ValueError if C is outside [0, 1] (not a valid load-sharing fraction)."""
    if not 0.0 <= stiffness_factor_C <= 1.0:
        raise ValueError("stiffness factor C must lie in [0, 1]")
    return preload_Fi + stiffness_factor_C * external_load_P


def separation_load(preload_Fi: float, stiffness_factor_C: float) -> float:
    """External tensile load P_sep = F_i/(1 - C) (N) at which the joint just separates.

    The member clamp force is F_m = F_i - (1 - C)*P; it reaches zero — the members lose
    all contact pressure and the bolt then carries the entire load — exactly at
    P = F_i/(1 - C). A rigid-bolt limit (C -> 1) pushes P_sep to infinity (the model's
    members never separate). `preload_Fi` in N, `stiffness_factor_C` in [0, 1).
    Raises ValueError on C outside [0, 1) (C = 1 gives no finite separation load)."""
    if not 0.0 <= stiffness_factor_C < 1.0:
        raise ValueError("stiffness factor C must lie in [0, 1) for a finite separation load")
    return preload_Fi / (1.0 - stiffness_factor_C)


def bolted_joint_check(
    torque: float,
    nominal_diameter: float,
    tensile_stress_area: float,
    external_load_P: float,
    bolt_stiffness_kb: float,
    member_stiffness_km: float,
    proof_strength: float,
    *,
    k_factor: float = 0.2,
) -> dict:
    """Preloaded bolted-joint load-sharing check (the axis a nominal P/A_t stress
    misses).

    Computes the preload (``preload_from_torque``), the load factor C
    (``joint_stiffness_factor``), the true bolt load F_i + C*P (``bolt_load``) and its
    stress over the tensile stress area, and the separation load (``separation_load``).
    Returns ``{"preload", "stiffness_factor_C", "bolt_load", "bolt_stress",
    "separation_load", "separation_margin", "yield_safety", "ok"}``: bolt_stress =
    bolt_load/tensile_stress_area (MPa), separation_margin = separation_load/external_load_P
    (>1 ⇒ does not separate), yield_safety = proof_strength/bolt_stress (>1 ⇒ does not
    yield), and ok is True only if it BOTH does not separate (P < P_sep) AND does not
    yield (bolt_stress <= proof_strength) — a joint can be safe on one and fail the
    other. Deterministic.

    Forces in N, torque in N*mm, diameter/area in mm and mm**2, proof_strength and
    bolt_stress in MPa. Raises ValueError on a non-positive tensile_stress_area,
    external_load_P, or proof_strength (or via the called functions on a non-positive
    diameter/stiffness/k_factor)."""
    if tensile_stress_area <= 0.0:
        raise ValueError("tensile stress area must be positive")
    if external_load_P <= 0.0:
        raise ValueError("external load P must be positive")
    if proof_strength <= 0.0:
        raise ValueError("proof strength must be positive")
    preload = preload_from_torque(torque, nominal_diameter, k_factor)
    c = joint_stiffness_factor(bolt_stiffness_kb, member_stiffness_km)
    f_bolt = bolt_load(preload, external_load_P, c)
    bolt_stress = f_bolt / tensile_stress_area
    p_sep = separation_load(preload, c)
    no_separation = external_load_P < p_sep
    no_yield = bolt_stress <= proof_strength
    return {
        "preload": preload,
        "stiffness_factor_C": c,
        "bolt_load": f_bolt,
        "bolt_stress": bolt_stress,
        "separation_load": p_sep,
        "separation_margin": p_sep / external_load_P,
        "yield_safety": math.inf if bolt_stress == 0.0 else proof_strength / bolt_stress,
        "ok": no_separation and no_yield,
    }
