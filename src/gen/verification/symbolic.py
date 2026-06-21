"""Independent SymPy cross-check for the discovery gate — a SECOND, disjoint dimensional engine.

GENESIS already decides dimensional consistency two ways: ``verification/units.py`` (an integer
Abelian-group ``Dimension``) and the discovery engine's own least-squares exponent solve. This module
adds a THIRD, fully independent check built on ``sympy.physics.units`` — SymPy ships its OWN
definitions of the derived dimensions (``pressure = mass·length⁻¹·time⁻²`` etc.) and its OWN reduction
(``get_dimensional_dependencies``), so an agreement here is a genuine cross-engine corroboration, not a
restatement. Two independent implementations confirming the same base-dimension vector is exactly the
anti-hallucination posture GENESIS sells (CLAUDE.md §3 cross-model, generalised to cross-engine).

What it adds over the existing checks:
  * EXACT rational exponents. ``units.py``'s ``Dimension`` carries integer base exponents only; a
    power law like ``a^(3/2)·mu^(-1/2)`` is verified here with ``sympy.Rational`` powers, so the
    half-integer dimensional algebra is checked symbolically, not just by a float lstsq residual.
  * EXACT constant recovery. ``recover_exact_constant`` uses ``nsimplify`` to report that the fitted
    Kepler constant ``6.2831…`` is ``2·π`` — informational provenance, NEVER overwriting the numeric
    ``coefficient``/``r_squared``/``rmse`` (those stay the measured truth).

Honest boundaries (researched, not invented — same discipline as ``units.py``):
  * This catches DIMENSION errors, never MAGNITUDE errors within a dimension (a wrong unit factor).
  * An unknown/opaque unit atom yields ``available=False`` — an honest "cannot corroborate", never a
    guessed pass or fail. GENESIS never invents a compatibility it cannot justify.
  * ``nsimplify`` is used WITHOUT ``rational``/``force`` coercion and only accepted when it re-evaluates
    to the input within tolerance AND is structurally simple (involves π or a small-denominator
    rational); otherwise the constant stays numeric. A pretty closed form that hides a fitted
    coefficient's uncertainty would itself be a hallucination.

Offline, deterministic, no network. SymPy is already a GENESIS dependency.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from fractions import Fraction

from sympy import Integer, Rational, count_ops, nsimplify, pi
from sympy.physics.units.definitions.dimension_definitions import (
    amount_of_substance,
    charge,
    current,
    energy,
    force,
    frequency,
    impedance,
    length,
    luminous_intensity,
    mass,
    power,
    pressure,
    temperature,
    time,
    voltage,
)
from sympy.physics.units.systems.si import dimsys_SI

from ..core.errors import UnitError
from .units import parse_unit

#: Largest denominator when coercing a fitted float exponent to an exact rational for the symbolic
#: power (mirrors discovery.engine.EXPONENT_MAX_DENOMINATOR so the two engines agree on 1.4999→3/2).
EXPONENT_MAX_DENOMINATOR = 24

_DIMLESS = Integer(1)

# GENESIS unit atom -> SymPy dimension. SymPy's derived dimensions carry their OWN definitions, so
# this table only NAMES atoms; the reduction to base exponents is SymPy's, independent of units.py.
# (Scale/prefix is irrelevant to DIMENSION; "g" and "kg" are both `mass`.)
_ATOM_DIM = {
    "1": _DIMLESS, "": _DIMLESS, "rad": _DIMLESS, "deg": _DIMLESS, "%": _DIMLESS,
    "pcs": _DIMLESS, "count": _DIMLESS, "x": _DIMLESS,
    "m": length, "metre": length, "meter": length,
    "g": mass, "t": mass,
    "s": time, "min": time, "h": time, "hr": time, "day": time,
    "A": current, "K": temperature, "mol": amount_of_substance, "cd": luminous_intensity,
    "N": force, "Pa": pressure, "bar": pressure, "J": energy, "Wh": energy,
    "W": power, "Hz": frequency, "V": voltage, "ohm": impedance, "Ω": impedance,
    "Ah": charge, "L_vol": length ** 3,
}

# SI prefixes — recognised only so a prefixed atom (mm, kN, MPa) resolves; scale is dropped.
_PREFIXES = frozenset({
    "Y", "Z", "E", "P", "T", "G", "M", "k", "h", "da",
    "d", "c", "m", "u", "µ", "n", "p", "f", "a", "z", "y",
})

# Translation from units.py base symbols to the SymPy dimension names, for the parsing cross-check.
_UNITS_TO_SYMPY = {
    "L": "length", "M": "mass", "T": "time", "I": "current",
    "Te": "temperature", "N": "amount_of_substance", "J": "luminous_intensity",
}

_TOKEN = re.compile(r"\s*([*/])?\s*([A-Za-zµΩ%]+|1)(?:\^(-?\d+))?")


def _atom_dim(name: str):
    """One GENESIS unit atom -> a SymPy dimension, or None if unknown/opaque (never guessed)."""
    if name in _ATOM_DIM:
        return _ATOM_DIM[name]
    for plen in (2, 1):  # "da" is two chars
        if len(name) > plen and name[:plen] in _PREFIXES and name[plen:] in _ATOM_DIM:
            return _ATOM_DIM[name[plen:]]
    return None


def _parse_to_sympy(unit: str):
    """Parse a compound unit string into a SymPy dimension expression, or None if any atom is
    opaque or the string is malformed. Independent of units.py's parser (its own atom table)."""
    text = unit.strip()
    if text in ("", "1"):
        return _DIMLESS
    expr = _DIMLESS
    pos = 0
    for m in _TOKEN.finditer(text):
        if m.start() != pos:            # a gap -> the string is not a clean product/quotient of atoms
            return None
        pos = m.end()
        op, name, exp = m.group(1), m.group(2), m.group(3)
        dim = _atom_dim(name)
        if dim is None:
            return None
        term = dim ** (int(exp) if exp else 1)
        expr = expr / term if op == "/" else expr * term
    if pos != len(text):
        return None
    return expr


def _base_exponents(expr) -> dict[str, Fraction]:
    """Reduce a SymPy dimension expression to ``{base_dimension_name: exponent}`` (SymPy's engine)."""
    deps = dimsys_SI.get_dimensional_dependencies(expr)
    out: dict[str, Fraction] = {}
    for d, v in deps.items():
        r = Rational(v)                       # coerce int OR SymPy number -> exact Rational
        out[str(d.name)] = Fraction(int(r.p), int(r.q))
    return out


def sympy_base_exponents(unit: str) -> dict[str, Fraction] | None:
    """Base-dimension exponents of a unit string via SymPy, or None if it cannot be reduced.

    None means "opaque to SymPy" — an honest abstention, never a dimensionless guess.
    """
    expr = _parse_to_sympy(unit)
    return None if expr is None else _base_exponents(expr)


@dataclass(frozen=True)
class SymbolicDimensionCheck:
    """Result of the independent SymPy cross-check of one power-law candidate.

    ``available`` is False when any unit was opaque to SymPy (cannot corroborate — honest abstention);
    ``agrees`` is only meaningful when ``available``. ``target``/``candidate`` are the two base-exponent
    vectors so a disagreement is fully explained.
    """

    available: bool
    agrees: bool
    target: dict[str, Fraction] = field(default_factory=dict)
    candidate: dict[str, Fraction] = field(default_factory=dict)
    detail: str = ""


def cross_check_power_law(
    target_unit: str,
    source_units: dict[str, str],
    exponents: dict[str, float],
) -> SymbolicDimensionCheck:
    """Independently verify ``target = C · ∏ source_i^exp_i`` is dimensionally consistent, via SymPy.

    ``source_units`` maps each source name to its unit string; ``exponents`` maps the same names to the
    fitted exponents (coerced to exact rationals with denominator ≤ EXPONENT_MAX_DENOMINATOR). Returns
    a structured verdict; on any opaque/missing unit it returns ``available=False`` rather than guess.
    """
    target = sympy_base_exponents(target_unit)
    if target is None:
        return SymbolicDimensionCheck(False, False, detail=f"target unit {target_unit!r} opaque to SymPy")
    expr = _DIMLESS
    for name, exp in exponents.items():
        unit = source_units.get(name)
        if unit is None:
            return SymbolicDimensionCheck(False, False, target=target, detail=f"no unit for source {name!r}")
        dim = _parse_to_sympy(unit)
        if dim is None:
            return SymbolicDimensionCheck(False, False, target=target, detail=f"source unit {unit!r} opaque")
        rational = Rational(Fraction(exp).limit_denominator(EXPONENT_MAX_DENOMINATOR))
        expr = expr * dim ** rational
    candidate = _base_exponents(expr)
    agrees = candidate == target
    return SymbolicDimensionCheck(
        available=True,
        agrees=agrees,
        target=target,
        candidate=candidate,
        detail="" if agrees else f"SymPy: candidate {candidate} != target {target}",
    )


def cross_engine_dimension_agrees(unit: str) -> bool | None:
    """Do SymPy and ``units.py`` independently reduce ``unit`` to the SAME base dimensions?

    Returns None when either engine cannot reduce it (opaque atom) — then there is nothing to cross-
    check, which is reported honestly rather than as agreement.
    """
    s = sympy_base_exponents(unit)
    if s is None:
        return None
    try:
        genesis = parse_unit(unit).as_dict()  # {genesis_symbol: int}
    except UnitError:
        return None
    translated: dict[str, Fraction] = {}
    for symbol, exp in genesis.items():
        if symbol not in _UNITS_TO_SYMPY:     # an opaque <widget> base — cannot cross-check
            return None
        translated[_UNITS_TO_SYMPY[symbol]] = Fraction(exp)
    return translated == s


def recover_exact_constant(value: float, *, tol: float = 1e-9) -> str | None:
    """Report a fitted dimensionless constant's exact closed form (e.g. 6.2831… -> '2*pi'), or None.

    Conservative by construction: a closed form is returned ONLY when it re-evaluates to ``value``
    within ``tol`` AND is structurally SIMPLE — a small ``c·π^k`` form (``count_ops ≤ 2``), or a rational
    with denominator ≤ 64. Otherwise the constant stays numeric (an empirical constant like R = 8.314…
    is left as-is). The ``count_ops`` bound is the load-bearing guard: ``nsimplify`` will otherwise
    return a contrived π-laden expression that matches by coincidence (e.g. for R) — a deceptively
    "exact" hallucination. This is provenance, never a replacement for the measured coefficient.
    """
    if value is None or not math.isfinite(value) or value == 0.0:
        return None
    scale = max(1.0, abs(value))
    try:
        expr = nsimplify(value, [pi], tolerance=tol)
    except Exception:  # noqa: BLE001 — nsimplify can raise on pathological inputs; stay numeric then
        expr = None
    if (
        expr is not None
        and expr.has(pi)
        and count_ops(expr) <= 2                 # reject contrived π-laden coincidences (e.g. for R)
        and abs(float(expr) - value) <= scale * tol
    ):
        return str(expr)
    fr = Fraction(value).limit_denominator(64)
    if 1 < fr.denominator <= 64 and abs(float(fr) - value) <= scale * tol:
        return f"{fr.numerator}/{fr.denominator}"
    return None
