"""reality_fork — the Reality Fork Simulator (build doc 4.2, Phase 3).

Counterfactual physics sandboxes: "what if a constant were different / there were one more
spatial dimension / a symmetry were broken?". The point is SAFE exploration of wild ideas —
the engine can play out a counterfactual world WITHOUT ever presenting it as the real one.
Every GENUINE fork is labelled counterfactual; the one base case that reproduces our own world
(D=3) is honestly marked ``counterfactual=False`` rather than pretending to be a "what-if". The
discovery gate's ``bestaetigt``/``widerlegt`` is for the REAL world (fitting real data), and no
fork — counterfactual or base — ever borrows that authority. That separation is the honesty
guarantee: you can ask "what if" without lying that it is so.

Two principled, grounded forks (each internally-consistency checked):

  * SPATIAL-DIMENSION fork — Gauss's law in ``D`` spatial dimensions. A point source's field
    spreads over the surface of a (D−1)-sphere, whose area ∝ ``r^(D-1)``, so the field (and an
    inverse-square force) goes as ``r^(-(D-1))``. Our world D=3 reproduces the real ``r^-2``;
    D=4 gives ``r^-3``, D=2 gives ``r^-1``. (Ehrenfest's 1917 dimensionality argument: only
    D=3 admits stable bound orbits — surfaced as a physical NOTE, not a consistency failure.)
  * CONSTANT fork — vary a constant in a discovered power law and report the counterfactual
    scaling of the target: ``target_new/target_base = (c_new/c_base)^exponent``. (Double the
    gravitational parameter μ in Kepler's ``T ∝ μ^(-1/2)`` → the period scales by ``2^(-1/2)``.)

Internal consistency, concretely: a forked world is consistent iff it stays a well-formed,
finite, positive-magnitude power law — an integer spatial dimension ≥ 1, a positive forked
constant. A fractional/zero dimension or a non-positive constant is flagged inconsistent rather
than silently "explored". Offline, deterministic, dependency-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Our world has 3 spatial dimensions; Gauss's law then gives the inverse-square force.
REAL_SPATIAL_DIMENSION = 3


@dataclass(frozen=True)
class CounterfactualWorld:
    """A forked world. `counterfactual` is True for every genuine fork and False only for the
    base case that reproduces our own world (D=3) — neither ever carries the real-data gate's
    ``bestaetigt`` status. Carries the change, the law in that world, and whether the world is
    internally consistent (well-formed, finite, physical-sign)."""

    name: str
    kind: str  # "spatial_dimension" | "constant"
    change: dict
    forked_law: str
    internally_consistent: bool
    notes: tuple[str, ...] = field(default_factory=tuple)
    counterfactual: bool = True  # invariant: a fork is never the real world


def gauss_force_exponent(spatial_dimension: int) -> int:
    """The inverse-power exponent of a point-source force in `spatial_dimension` dimensions via
    Gauss's law: ``F ∝ r^(-(D-1))``. D=3 → −2 (our world), D=4 → −3, D=2 → −1. Raises ValueError
    on a non-integer or sub-1 dimension (no Gauss surface exists there)."""
    if not isinstance(spatial_dimension, int) or spatial_dimension < 1:
        raise ValueError("spatial dimension must be an integer >= 1")
    return -(spatial_dimension - 1)


def fork_spatial_dimension(
    new_dimension: int,
    *,
    quantity: str = "F",
    base_dimension: int = REAL_SPATIAL_DIMENSION,
) -> CounterfactualWorld:
    """Fork the number of spatial dimensions and recompute the inverse-power force law via
    Gauss's law. The base world (`base_dimension`, default 3) must reproduce ``F ∝ r^-2`` — a
    self-check. Returns a counterfactual world; an integer D≥1 is internally consistent, and
    D≥4 carries the Ehrenfest "no stable bound orbits" note (a physical caveat, not an
    inconsistency)."""
    try:
        exponent = gauss_force_exponent(new_dimension)
        consistent = True
        notes: list[str] = []
    except ValueError as exc:
        return CounterfactualWorld(
            name=f"{new_dimension}-D Raum", kind="spatial_dimension",
            change={"spatial_dimension": new_dimension}, forked_law="(nicht wohlgeformt)",
            internally_consistent=False, notes=(str(exc),))

    # self-check: the base world reproduces the real inverse-square force
    if gauss_force_exponent(base_dimension) != -2:
        notes.append(f"WARN: base dimension {base_dimension} does not give the real r^-2")
    if new_dimension == base_dimension:
        notes.append("dies ist die reale Welt (kein Counterfactual)")
    if new_dimension >= 4:
        notes.append("Ehrenfest 1917: ab D>=4 keine stabilen gebundenen Orbits — physikalischer Hinweis, keine Inkonsistenz")
    if new_dimension == 2:
        notes.append("D=2: logarithmisches Potential, F ∝ r^-1")

    return CounterfactualWorld(
        name=f"{new_dimension}-D Raum (Gauss)", kind="spatial_dimension",
        change={"spatial_dimension": new_dimension, "force_exponent": exponent},
        forked_law=f"{quantity} ∝ r^{exponent}",
        internally_consistent=consistent, notes=tuple(notes),
        counterfactual=(new_dimension != base_dimension))


def fork_constant(
    target: str,
    constant: str,
    base_value: float,
    new_value: float,
    scaling_exponent: float,
) -> CounterfactualWorld:
    """Vary a `constant` (from `base_value` to `new_value`) in a power law where the target
    scales as ``constant^scaling_exponent``, and report the counterfactual scaling of the
    target: ``target_new/target_base = (new_value/base_value)^scaling_exponent``. Internally
    consistent iff both values are positive (a power law needs positive magnitudes); a
    non-positive forked constant is flagged, not silently explored. A non-finite input
    (NaN/inf) — or an exponent/factor that turns out non-finite — is likewise flagged, since
    a consistent world is defined as a *finite* power law (module docstring); we must not
    silently emit a non-finite scale factor while claiming consistency."""
    # NaN slips past plain ``<= 0.0`` (NaN comparisons are always False), so guard finiteness
    # explicitly first — otherwise a NaN/inf magnitude would yield a non-finite scale factor
    # stamped ``internally_consistent=True``, contradicting the finite-power-law contract.
    if not (math.isfinite(base_value) and math.isfinite(new_value) and math.isfinite(scaling_exponent)):
        return CounterfactualWorld(
            name=f"{constant} -> {new_value:g}", kind="constant",
            change={"constant": constant, "base": base_value, "new": new_value},
            forked_law="(nicht-finite Magnitude)", internally_consistent=False,
            notes=("Potenzgesetz braucht finite Magnituden; NaN/inf ist inkonsistent",))
    if base_value <= 0.0 or new_value <= 0.0:
        return CounterfactualWorld(
            name=f"{constant} -> {new_value:g}", kind="constant",
            change={"constant": constant, "base": base_value, "new": new_value},
            forked_law="(nicht-positive Magnitude)", internally_consistent=False,
            notes=("Potenzgesetz braucht positive Magnituden; nicht-positiver Wert ist inkonsistent",))
    # Finite positive inputs can still overflow under exponentiation. CPython is inconsistent
    # here: ``(new/base) ** exp`` RAISES OverflowError on float power overflow, but the
    # intermediate ``new/base`` division overflows to ``inf`` instead — so we must both catch
    # the exception AND check finiteness. Either way the honest result is a flagged-inconsistent
    # world, never a crash and never a silent non-finite scale factor.
    try:
        factor = (new_value / base_value) ** scaling_exponent
        overflowed = not math.isfinite(factor)
    except OverflowError:
        overflowed = True
    if overflowed:
        return CounterfactualWorld(
            name=f"{constant} -> {new_value:g}", kind="constant",
            change={"constant": constant, "base": base_value, "new": new_value},
            forked_law="(nicht-finiter Skalenfaktor)", internally_consistent=False,
            notes=("Skalenfaktor läuft über (nicht finit); inkonsistent",))
    return CounterfactualWorld(
        name=f"{constant} -> {new_value:g}", kind="constant",
        change={"constant": constant, "base": base_value, "new": new_value,
                "target_scale_factor": factor},
        forked_law=f"{target}_neu = {factor:.6g} * {target}_real",
        internally_consistent=True,
        notes=(f"{target} skaliert mit ({constant}_neu/{constant}_real)^{scaling_exponent:g}",))


def fork_from_discovery(verdict, constant: str, new_value: float, base_value: float) -> CounterfactualWorld:
    """Fork a constant of an already-DISCOVERED law (a DiscoveryVerdict): reads the law's own
    fitted exponent for `constant` as the scaling exponent, so the counterfactual is consistent
    with the discovered relation. The fork stays counterfactual — it never re-uses the verdict's
    real-world ``bestaetigt`` status."""
    scaling = verdict.candidate.exponents.get(constant)
    if scaling is None:
        raise ValueError(f"the discovered law has no exponent for {constant!r}")
    target = verdict.candidate.expression.split("=")[0].strip()
    return fork_constant(target, constant, base_value, new_value, scaling)
