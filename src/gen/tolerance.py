"""Tolerance / fit reference data and worst-case stack-up formulas (δ-layer).

A real assembly is not its nominal dimensions — it is a distribution of them.
GENESIS answers the deterministic half of that question without any new gate
code: a worst-case tolerance stack-up is expressed in the EXISTING γ machinery —
the tolerances are GROUNDED/DERIVED quantities, the worst-case clearance is a
DERIVED quantity (the gate recomputes it, C-6, and dimension-checks it, C-15),
and "is it still assemblable?" is a numeric constraint (C-13). This module only
supplies (a) the standard general-tolerance table and (b) the formula strings,
so the demo and the tests reference the same arithmetic — no drift.

Worst-case (deterministic, 100 %-assemblability) vs statistical (Monte-Carlo,
predicts yield): we implement the worst-case method — it is the one that follows
with certainty and never claims a probability it cannot prove (the same honest
asymmetry as the geometry layer). For a clearance fit (hole over shaft):

    min clearance = hole_min - shaft_max = (hole_nom - t_hole) - (shaft_nom + t_shaft)

If the minimum clearance is >= 0 the parts always assemble; if it can go negative
the fit can interfere — a definite defect.

Sources (verified 2026-06-11):
  * ISO 2768-1 general tolerances for linear dimensions, class m (medium): the
    encoded subset 0.5..120 mm (±0.1 / ±0.1 / ±0.2 / ±0.3). Outside this verified
    range the lookup RAISES rather than guess a standard value it has not checked.
    Refs: ISO 2768-1; amesweb.info ISO-2768 linear table; Xometry ISO 2768/286.
  * Worst-case vs statistical (Monte-Carlo) stack-up: standard tolerance-analysis
    methods (worst-case sums tolerances at their extremes for 100 % assemblability).
"""

from __future__ import annotations

from .core.errors import ToleranceError

# ISO 2768-1 class m (medium) permissible deviations for linear dimensions [mm].
# Each row is (low_exclusive_except_first, high_inclusive, plus_minus). Only the
# ranges verified this session are encoded; a nominal outside them raises.
_ISO2768_M_LINEAR: tuple[tuple[float, float, float], ...] = (
    (0.5, 3.0, 0.1),    # 0.5 <= n <= 3
    (3.0, 6.0, 0.1),    # 3   <  n <= 6
    (6.0, 30.0, 0.2),   # 6   <  n <= 30
    (30.0, 120.0, 0.3),  # 30 <  n <= 120
)


def iso2768_medium_linear_tolerance(nominal_mm: float) -> float:
    """Symmetric general tolerance ±value [mm] for a linear nominal under
    ISO 2768-1 class m (medium).

    Verified subset 0.5..120 mm. A nominal outside it raises ``ToleranceError``
    rather than extrapolate a standard value GENESIS has not checked.
    """
    n = abs(float(nominal_mm))
    for i, (lo, hi, tol) in enumerate(_ISO2768_M_LINEAR):
        if (n >= lo if i == 0 else n > lo) and n <= hi:
            return tol
    raise ToleranceError(
        f"nominal {nominal_mm} mm is outside the verified ISO 2768-1 m range "
        "(0.5..120 mm) — extend the verified table, do not guess."
    )


def worst_case_min_clearance_formula(
    hole_id: str,
    hole_tol_id: str,
    shaft_id: str,
    shaft_tol_id: str,
) -> str:
    """``(hole_nom - t_hole) - (shaft_nom + t_shaft)`` — worst-case minimum
    clearance of a hole/shaft fit. All four are lengths, so the result is a
    length (GATE γ C-15); a constraint ``>= 0`` proves worst-case assemblability
    (C-13)."""
    return f"({hole_id} - {hole_tol_id}) - ({shaft_id} + {shaft_tol_id})"
