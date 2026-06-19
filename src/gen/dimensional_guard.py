"""dimensional_guard — automatic detection of DIMENSIONAL formula errors by scale invariance.

The complement to the canonical-formula library. ``mechanics_formulas`` kills wrong DIMENSIONLESS
coefficients (m·L²/3 vs m·L²/12 — same units, a units check is blind); this module kills DIMENSIONAL
errors (a wrong power, an added incommensurable term, a rogue dimensional constant) with a single
general property, no per-formula anchor needed:

  A closed-form check returns a DIMENSIONLESS verdict (``safety_factor`` is a ratio of two
  same-dimension quantities). If the formula is dimensionally homogeneous, that number is INVARIANT
  under a coherent change of base units. So: re-express every input in a consistently rescaled unit
  system (multiply each value by ∏ scaleₖ^exponentₖ over its dimension) and the safety_factor must
  not move. If it moves, a term is dimensionally inconsistent — caught without knowing the "right"
  answer, for any present or future validator.

The dimension of each input is read from its UNIT STRING via ``verification.units.parse_unit`` — the
same units the physics-selection recipes already carry — so the test reuses existing metadata.

HONEST SCOPE: valid only for checks HOMOGENEOUS IN THEIR DECLARED INPUTS. A validator that bakes in a
DIMENSIONAL constant it does not take as an argument (e.g. g = 9.81 m/s² hard-coded) is not
input-homogeneous — rescaling the inputs but not the hidden constant breaks invariance even when the
formula is correct. Such checks are excluded (and should instead take the constant as an argument, or
be pinned by an anchor). Purely dimensionless checks (all inputs ``1``) are invariant trivially and
gain nothing here.

Deterministic, offline, stdlib + the in-repo units module only.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from .verification.units import parse_unit

#: Distinct, deterministic scale factors per SI base symbol (small primes, all ≠ 1 so any
#: non-homogeneous term shows up). Unknown/opaque base symbols default to 1.0 (no rescale).
_BASE_SCALES: dict[str, float] = {
    "L": 2.0, "M": 3.0, "T": 5.0, "I": 7.0, "Te": 11.0, "N": 13.0, "J": 17.0,
}


class DimensionalInconsistencyError(AssertionError):
    """Raised when a check's dimensionless result is NOT invariant under a coherent unit rescaling —
    evidence the underlying formula mixes dimensions."""


def _input_scale(unit: str, scales: dict[str, float]) -> float:
    """The factor an input's NUMERIC VALUE picks up when the base units are rescaled by ``scales``:
    ∏ scaleₖ^exponentₖ over the input's dimension (parsed from its unit string)."""
    factor = 1.0
    for sym, exp in parse_unit(unit).as_dict().items():
        factor *= scales.get(sym, 1.0) ** exp
    return factor


def scale_invariance_report(
    fn: Callable[..., dict],
    inputs: dict[str, tuple[float, str]],
    *,
    result_key: str = "safety_factor",
    scales: dict[str, float] | None = None,
    rel_tol: float = 1e-9,
) -> dict:
    """Run ``fn`` at the given inputs and at a coherently rescaled copy, and compare ``result_key``.

    ``inputs`` maps each argument name to ``(value, unit_string)``. Returns ``{"invariant", "base",
    "rescaled", "rel_change"}``: ``invariant`` is True when the dimensionless result is unchanged
    (within ``rel_tol``) under the rescaling — i.e. the formula is dimensionally homogeneous in its
    inputs. A non-finite or zero base result compares by exact equality. Deterministic."""
    scales = scales or _BASE_SCALES
    base_kwargs = {k: v for k, (v, _u) in inputs.items()}
    rescaled_kwargs = {k: v * _input_scale(u, scales) for k, (v, u) in inputs.items()}
    base = fn(**base_kwargs)[result_key]
    rescaled = fn(**rescaled_kwargs)[result_key]
    if not math.isfinite(base) or base == 0.0:
        invariant = base == rescaled
        rel_change = 0.0 if invariant else float("inf")
    else:
        rel_change = abs(rescaled - base) / abs(base)
        invariant = rel_change <= rel_tol
    return {"invariant": invariant, "base": base, "rescaled": rescaled, "rel_change": rel_change}


def assert_scale_invariant(
    fn: Callable[..., dict],
    inputs: dict[str, tuple[float, str]],
    *,
    result_key: str = "safety_factor",
    rel_tol: float = 1e-9,
) -> dict:
    """Assert ``fn``'s ``result_key`` is invariant under a coherent unit rescaling, raising
    ``DimensionalInconsistencyError`` (with the offending numbers) if not. Returns the report."""
    rep = scale_invariance_report(fn, inputs, result_key=result_key, rel_tol=rel_tol)
    if not rep["invariant"]:
        raise DimensionalInconsistencyError(
            f"{getattr(fn, '__name__', fn)}: {result_key} changed under unit rescaling "
            f"({rep['base']!r} -> {rep['rescaled']!r}, rel_change={rep['rel_change']:.3e}) — "
            "a dimensionally inconsistent term")
    return rep
