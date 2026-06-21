"""Structural formula strings for the δ second layer (deterministic statics).

GENESIS never lets the LLM do physics. A structural check is expressed entirely
in the EXISTING γ machinery — GROUNDED/DERIVED quantities, the safe arithmetic
evaluator (`verification/derivation.py`), the dimensional-homogeneity guard
(`verification/units.py`, C-15) and a numeric constraint (C-13). This module adds
no new gate code; it only provides the canonical formula STRINGS so the capstone
demo and the tests reference the same arithmetic — no drift between what is
demonstrated and what is verified.

Wiring (physics validators campaign, Step 7): foundational provider of δ-2
formula strings (weight, bending, peak/Kt, bolt shear per EN, per-fastener,
axial). NOT a top-level validator key in physics_validation.VALIDATORS (use γ
C-13 constraints on the DERIVED stresses instead). Referenced by name ("the
stress check (structural.py)") in docstrings of torsion.py, fracture.py,
fatigue.py, creep.py, contact.py, bolted_joint.py, plate_bending.py,
pressure_vessel.py, notch_fatigue.py, fem.py as the nominal stress primitive
that those modules complement. Seams: L3 to physics gate (via select/gate_delta
in pipeline.assess_specification when stress-using checks like "fracture" are
triggered) + direct use in demo capstone + verification (smt/cegis mirror).
Cross-checks with fem.py (exact to 1e-9). Pure strings for no-drift γ eval.
Advances Step 7 (structural/fem foundational reviewed).

Physics (researched, not invented — sources in §8 of PHASE_DELTA.md):
  * Weight of a mass under gravity: ``F = m · g`` (Newton's second law). The
    DERIVED quantity then carries dimension ``M·L·T⁻²`` = newton, checked by C-15.
    The structural check uses the DESIGN load (load × safety factor), not the raw
    load — the safety margin is applied to the demand, the standard convention.
  * Maximum bending stress in a tip-loaded cantilever of length ``L`` with a
    rectangular cross-section (breadth ``b``, depth ``h`` in the load direction):
        σ_nom = M·c / I,  with  M = F·L,  I = b·h³/12,  c = h/2
              = 6·F·L / (b·h²)
    Source: Euler-Bernoulli beam theory; rectangular-section bending,
    en.wikipedia.org/wiki/Bending ("Stress in a bent beam") and the second
    moment of area I = b·h³/12 for a rectangle. The evaluator has no power
    operator, so ``h²`` is written ``h * h``.
  * Stress concentration at the mounting hole: ``σ_peak = Kt · σ_nom``. For a
    circular hole in a plate under tension the Kirsch (1898) solution gives the
    exact, size-independent factor ``Kt = 3`` — used as a CONSERVATIVE bound (the
    finite-width / bending value is ≤ 3). Refs: E. G. Kirsch 1898; Peterson's
    Stress Concentration Factors; fracturemechanics.org/hole.html.
  * Fastener shear (the bracket-side limit, EN 1993-1-8): the per-screw shear
    demand ``F / n`` must stay below the shear resistance ``αv · f_ub · A_s``,
    with ``αv = 0.6`` for property class 8.8, ``f_ub`` the ultimate tensile
    strength and ``A_s`` the tensile stress area. Dimension ``MPa·mm² = N``.
  * Nominal axial (direct) stress: ``σ = F / A`` — force over cross-section area.
    Base for tension/compression, pressure-vessel axial, and combined-stress
    paths.

Honest boundary (the δ asymmetry, like the geometry layer): a PASS of these
constraints is NECESSARY, not sufficient. The remaining residuals are genuinely
external and are declared as narrowed gaps, not hidden — wall-substrate fastener
pull-out (depends on the wall/anchor, not the bracket), the exact FEM stress field
(vs the conservative Kt=3 bound), fatigue and dynamic/impact loads (excluded by
the declared static-load case), and print-process variability (the in-plane
strength assumes a good print at the declared orientation). A FAIL means the
modelled case already overstresses the part — definitely too weak.
"""

from __future__ import annotations

#: Standard gravity, the conventional value fixed by the 3rd CGPM (1901):
#: 9.80665 m/s². Used as a GROUNDED quantity (its number verbatim from a claim),
#: never hard-coded into a derivation as a magic literal.
STANDARD_GRAVITY = 9.80665

#: Kirsch (1898) stress concentration factor for a circular hole in a plate under
#: uniaxial tension — exactly 3, independent of hole size and material. Used as a
#: conservative bound for the mounting-hole stress raiser.
STRESS_CONCENTRATION_CIRCULAR_HOLE = 3.0

#: EN 1993-1-8 shear coefficient αv for bolt property classes 4.6 / 5.6 / 8.8.
BOLT_SHEAR_COEFFICIENT_88 = 0.6

#: Ultimate tensile strength f_ub of an ISO 898-1 property class 8.8 bolt [MPa].
BOLT_UTS_CLASS_88_MPA = 800.0

#: Tensile stress area A_s of an M4 coarse-pitch (0.70 mm) thread, ISO 898-1 [mm²].
M4_TENSILE_STRESS_AREA_MM2 = 8.78


def weight_formula(mass_id: str, gravity_id: str) -> str:
    """``F = m · g`` — the derivation string for a weight (force) quantity.

    Dimension: ``M · (L·T⁻²) = M·L·T⁻²`` (newton), verified by GATE γ C-15.
    """
    return f"{mass_id} * {gravity_id}"


def cantilever_bending_stress_formula(
    force_id: str,
    arm_id: str,
    breadth_id: str,
    depth_id: str,
) -> str:
    """``σ_nom = 6·F·L / (b·h²)`` — nominal bending stress of a tip-loaded
    cantilever with a rectangular section (breadth ``b``, depth ``h`` in the load
    direction).

    Written with ``h * h`` because the safe evaluator has no power operator.
    With force in N and lengths in mm the result is N/mm² = MPa (the consistent
    N-mm-MPa engineering unit system); dimensionally it is a pressure
    (``M·L⁻¹·T⁻²``), which GATE γ C-15 verifies against the declared unit.
    """
    return f"6 * {force_id} * {arm_id} / ({breadth_id} * {depth_id} * {depth_id})"


def peak_stress_formula(nominal_stress_id: str, kt_id: str) -> str:
    """``σ_peak = Kt · σ_nom`` — apply a stress concentration factor to the
    nominal stress. Kt is dimensionless, so σ_peak keeps the pressure dimension
    (C-15)."""
    return f"{kt_id} * {nominal_stress_id}"


def bolt_shear_capacity_formula(coeff_id: str, uts_id: str, area_id: str) -> str:
    """``F_v = αv · f_ub · A_s`` — bolt shear resistance (EN 1993-1-8).

    Dimension: ``1 · (M·L⁻¹·T⁻²) · L² = M·L·T⁻²`` (newton), so a strength in MPa
    times an area in mm² yields a force in N — verified by GATE γ C-15.
    """
    return f"{coeff_id} * {uts_id} * {area_id}"


def per_fastener_shear_formula(force_id: str, count_id: str) -> str:
    """``F / n`` — shear demand carried by each of ``n`` fasteners (force / count,
    so the dimension stays a force)."""
    return f"{force_id} / {count_id}"

def axial_stress_formula(force_id: str, area_id: str) -> str:
    """``σ = F / A`` — nominal axial stress (force over cross-section area).
    Keeps pressure dimension (verified by C-15). Common base for tension/compression checks."""
    return f"{force_id} / {area_id}"
