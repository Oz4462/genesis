"""Structural formula strings for the δ second layer (deterministic statics).

GENESIS never lets the LLM do physics. A structural check is expressed entirely
in the EXISTING γ machinery — GROUNDED/DERIVED quantities, the safe arithmetic
evaluator (`verification/derivation.py`), the dimensional-homogeneity guard
(`verification/units.py`, C-15) and a numeric constraint (C-13). This module adds
no new gate code; it only provides the canonical formula STRINGS so the capstone
demo and the tests reference the same arithmetic — no drift between what is
demonstrated and what is verified.

Physics (researched, not invented):
  * Weight of a mass under gravity: ``F = m · g`` (Newton's second law). The
    DERIVED quantity then carries dimension ``M·L·T⁻²`` = newton, checked by C-15.
  * Maximum bending stress in a tip-loaded cantilever of length ``L`` with a
    rectangular cross-section (breadth ``b``, depth ``h`` in the load direction):
        σ_max = M·c / I,  with  M = F·L,  I = b·h³/12,  c = h/2
              = 6·F·L / (b·h²)
    Source: Euler-Bernoulli beam theory; rectangular-section bending,
    en.wikipedia.org/wiki/Bending ("Stress in a bent beam") and the second
    moment of area I = b·h³/12 for a rectangle. The evaluator has no power
    operator, so ``h²`` is written ``h * h``.

Honest boundary (the δ asymmetry, like the geometry layer): a PASS of the stress
constraint is NECESSARY, not sufficient. This is an idealized single-load
Euler-Bernoulli model — it ignores stress concentration at the clearance hole,
screw pull-out, fastener shear, dynamic/impact loads, fatigue, and anisotropy of
a 3D-printed part (layer adhesion). It proves the simple bending case does not
overstress the section; it does not certify the part. A FAIL means the simple
case already overstresses it — definitely too weak.
"""

from __future__ import annotations

#: Standard gravity, the conventional value fixed by the 3rd CGPM (1901):
#: 9.80665 m/s². Used as a GROUNDED quantity (its number verbatim from a claim),
#: never hard-coded into a derivation as a magic literal.
STANDARD_GRAVITY = 9.80665


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
    """``σ = 6·F·L / (b·h²)`` — peak bending stress of a tip-loaded cantilever
    with a rectangular section (breadth ``b``, depth ``h`` in the load direction).

    Written with ``h * h`` because the safe evaluator has no power operator.
    With force in N and lengths in mm the result is N/mm² = MPa (the consistent
    N-mm-MPa engineering unit system); dimensionally it is a pressure
    (``M·L⁻¹·T⁻²``), which GATE γ C-15 verifies against the declared unit.
    """
    return f"6 * {force_id} * {arm_id} / ({breadth_id} * {depth_id} * {depth_id})"
