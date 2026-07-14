"""Dimensional analysis for γ derivations — units as an Abelian group.

The LLM never reasons about units in GENESIS; this module is the deterministic,
LLM-free arithmetic that decides whether a derivation is *dimensionally* sound.
It closes the unit-correctness hole named open in PHASE_GAMMA.md §10 and guards
against the Mars-Climate-Orbiter failure class (a value carried in the wrong
unit-dimension; pound-force·s vs newton·s, NASA 1999).

Foundations (researched, not invented):
  * Dimensional homogeneity: "only commensurable quantities (same dimension) may
    be compared, equated, added, or subtracted"; multiplication/division combine
    dimensions by adding/subtracting exponents — dimensions form an Abelian group
    under multiplication (SI / standard dimensional analysis).
  * A. Kennedy, "Types for Units-of-Measure: Theory and Practice" (CEFP 2009,
    LNCS 6299, Springer): a units-of-measure type system unifies over the
    equational theory of Abelian groups; dimensional consistency is "a first
    check on the correctness of an equation, just as the type-checker eliminates
    one possible reason for failure." This module is exactly such a check,
    applied to GENESIS derivations.

Honest boundary (documented, like dimensional analysis itself): this catches
*dimension* errors (mass + length, an area declared as a length), NOT *magnitude*
errors within one dimension (a cm→mm conversion using the wrong factor stays
dimensionally valid). Magnitude correctness is the job of the numeric recompute
(GATE γ C-6) and the verbatim value guard (C-4); dimension is an orthogonal,
independent check.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from ..core.errors import UnitError

# Seven SI base dimensions, as ASCII symbols (encoding-safe on any console):
# Length L, Mass M, Time T, Current I, Temperature Te, amount of substance N,
# luminous intensity J. A Dimension is a vector of integer exponents over these
# (plus opaque <unknown> symbols for unrecognized units).


@dataclass(frozen=True)
class Dimension:
    """A dimension as exponents over base symbols — an element of the Abelian
    group of dimensions. ``exponents`` is a frozenset of (symbol, exponent)
    pairs with no zero exponents, so equality is canonical (M·L·T⁻² has one
    representation). Unknown unit atoms become their own opaque base symbol
    (e.g. ``<widget>``) so they only ever combine with themselves — GENESIS
    never invents a compatibility it cannot justify.
    """

    exponents: frozenset[tuple[str, int]] = frozenset()

    @staticmethod
    def of(mapping: dict[str, int]) -> "Dimension":
        return Dimension(frozenset((k, v) for k, v in mapping.items() if v != 0))

    def as_dict(self) -> dict[str, int]:
        return dict(self.exponents)

    def __mul__(self, other: "Dimension") -> "Dimension":
        merged = self.as_dict()
        for k, v in other.exponents:
            merged[k] = merged.get(k, 0) + v
        return Dimension.of(merged)

    def __truediv__(self, other: "Dimension") -> "Dimension":
        merged = self.as_dict()
        for k, v in other.exponents:
            merged[k] = merged.get(k, 0) - v
        return Dimension.of(merged)

    def pow(self, n: int) -> "Dimension":
        return Dimension.of({k: v * n for k, v in self.exponents})

    def render(self) -> str:
        if not self.exponents:
            return "dimensionless"
        return "·".join(
            f"{sym}^{exp}" if exp != 1 else sym
            for sym, exp in sorted(self.exponents)
        )


DIMENSIONLESS = Dimension()


def _base(symbol: str) -> Dimension:
    return Dimension.of({symbol: 1})


# Atomic units known to GENESIS -> their dimension. Scale (cm vs m) is
# irrelevant to *dimension*; only the exponent vector matters here. Prefixed
# forms (mm, km, kN, MPa, ...) are resolved by stripping a known SI prefix when
# the remainder is a known atom — so the table stays small but covers the metric
# system. Anything unknown becomes an opaque base dimension (never guessed).
_LENGTH = _base("L")
_MASS = _base("M")
_TIME = _base("T")
_CURRENT = _base("I")
_TEMP = _base("Te")
_AMOUNT = _base("N")
_LUMINOUS = _base("J")
_FORCE = _MASS * _LENGTH / (_TIME * _TIME)            # N  = M·L·T⁻²
_PRESSURE = _FORCE / (_LENGTH * _LENGTH)              # Pa = M·L⁻¹·T⁻²
_ENERGY = _FORCE * _LENGTH                            # J  = M·L²·T⁻²
_POWER = _ENERGY / _TIME                              # W  = M·L²·T⁻³
_FREQ = DIMENSIONLESS / _TIME                         # Hz = T⁻¹
_VOLTAGE = _POWER / _CURRENT                          # V  = W/A
_RESISTANCE = _VOLTAGE / _CURRENT                     # Ω  = V/A
_CHARGE = _CURRENT * _TIME                            # Ah / C = I·T
_DOSE_EQUIVALENT = _base("Sv")                        # sievert (dose equivalent)
_DOSE_ABSORBED = _base("Gy")                          # gray (absorbed dose)

_KNOWN_UNITS: dict[str, Dimension] = {
    # dimensionless
    "1": DIMENSIONLESS, "": DIMENSIONLESS, "rad": DIMENSIONLESS,
    "deg": DIMENSIONLESS, "%": DIMENSIONLESS, "pcs": DIMENSIONLESS,
    "count": DIMENSIONLESS, "x": DIMENSIONLESS,
    # SI base (note: gram is the prefixable base for mass)
    "m": _LENGTH, "g": _MASS, "s": _TIME, "A": _CURRENT,
    "K": _TEMP, "mol": _AMOUNT, "cd": _LUMINOUS,
    # non-prefixed convenience aliases
    "metre": _LENGTH, "meter": _LENGTH,
    "min": _TIME, "h": _TIME, "hr": _TIME, "day": _TIME,
    "t": _MASS,                                        # tonne
    "L_vol": _LENGTH.pow(3),                           # explicit volume alias
    # named derived units (incl. the electrical set for the electronics domain)
    "N": _FORCE, "Pa": _PRESSURE, "bar": _PRESSURE,
    "J": _ENERGY, "W": _POWER, "Hz": _FREQ,
    "V": _VOLTAGE, "ohm": _RESISTANCE, "Ω": _RESISTANCE,
    "Ah": _CHARGE, "Wh": _ENERGY,
    # radiation dose: each its OWN base dimension, deliberately NOT J/kg — the
    # Sv↔Gy weighting factor is biology, not a unit conversion, so equating them
    # (or either with J/kg) would let a dimensional check silently launder an
    # absorbed dose into an equivalent dose. Prefixes (mSv, µSv, kGy) now resolve
    # via the standard prefix branch instead of collapsing to opaque dimensions.
    "Sv": _DOSE_EQUIVALENT, "Gy": _DOSE_ABSORBED,
    # Fracture toughness K_IC numeric values are MPa·√mm in GENESIS fracture.py.
    # Integer exponent dimensions cannot represent √L, so KIc is a dedicated opaque
    # atom (self-improve 2026-07-14): comparable only to itself — never laundered into Pa.
    "KIc": _base("<KIc>"),
}

# SI prefixes -> (kept only to RECOGNIZE a prefixed unit; scale is irrelevant to
# dimension). Includes the common engineering subset.
_PREFIXES = frozenset({
    "Y", "Z", "E", "P", "T", "G", "M", "k", "h", "da",
    "d", "c", "m", "u", "µ", "n", "p", "f", "a", "z", "y",
})

_ATOM_RE = re.compile(r"^([A-Za-zµΩ%]+|1)(\^-?\d+)?$")
_ATOM_PAT = r"(?:[A-Za-zµΩ%]+|1)(?:\^-?\d+)?"
_UNIT_RE = re.compile(rf"\s*{_ATOM_PAT}\s*(?:[*/]\s*{_ATOM_PAT}\s*)*")


def _resolve_atom(atom: str) -> Dimension:
    """One unit atom (optionally with ^exp) -> Dimension. Unknown -> opaque."""
    m = _ATOM_RE.match(atom)
    if not m:
        raise UnitError(f"unparseable unit atom {atom!r}")
    name, exp_part = m.group(1), m.group(2)
    exp = int(exp_part[1:]) if exp_part else 1
    base = _atom_dimension(name)
    return base.pow(exp)


def _atom_dimension(name: str) -> Dimension:
    # direct hit first (so "min", "mol", "m" are not mis-split as prefixes)
    if name in _KNOWN_UNITS:
        return _KNOWN_UNITS[name]
    # try a single SI prefix + known remainder (mm, km, kN, MPa, mg, ...)
    for plen in (2, 1):  # "da" is two chars
        if len(name) > plen and name[:plen] in _PREFIXES:
            remainder = name[plen:]
            if remainder in _KNOWN_UNITS:
                return _KNOWN_UNITS[remainder]
    # unknown -> its own opaque base dimension; never guessed compatible
    return _base(f"<{name}>")


def parse_unit(unit: str) -> Dimension:
    """Parse a compound unit string into a Dimension (Abelian-group element).

    Grammar: a product/quotient of atoms, e.g. ``"kg"``, ``"mm"``, ``"1"``,
    ``"m/s"``, ``"m/s^2"``, ``"kg*m/s^2"``, ``"m^3"``. Whitespace and a leading
    ``/`` are tolerated. Caret ``^`` carries the (integer) exponent. Anything
    unparseable raises ``UnitError`` (loud, never a silent dimensionless guess).
    """
    text = unit.strip()
    if text == "" or text == "1":
        return DIMENSIONLESS

    # Validate the WHOLE string against the grammar first, so malformed inputs
    # like "kg//m" fail loudly instead of being silently tolerated.
    if not _UNIT_RE.fullmatch(text):
        raise UnitError(f"unparseable unit {unit!r}")

    dim = DIMENSIONLESS
    # split into (operator, atom) where operator is implicit '*' at the start
    tokens = re.findall(r"([*/]?)\s*([^*/\s]+)", text)
    if not tokens:
        raise UnitError(f"unparseable unit {unit!r}")
    for op, atom in tokens:
        atom_dim = _resolve_atom(atom)
        if op == "/":
            dim = dim / atom_dim
        elif op in ("*", ""):  # implicit '*' (leading atom or explicit) multiplies
            dim = dim * atom_dim
    return dim


# --- unit scale (factor to the SI base, for SOUND conversions) ----------------
#
# parse_unit gives the DIMENSION; unit_scale gives the numeric factor from a unit
# to the SI base of its dimension (base = m, kg, s, A, K, mol, cd). This is what
# lets mass = volume × density convert mm³ × g/cm³ correctly instead of silently
# producing a wrong magnitude. An unknown/opaque atom yields None — GENESIS then
# refuses to claim a converted number rather than guess.

_PREFIX_FACTOR: dict[str, float] = {
    "Y": 1e24, "Z": 1e21, "E": 1e18, "P": 1e15, "T": 1e12, "G": 1e9, "M": 1e6,
    "k": 1e3, "h": 1e2, "da": 1e1,
    "d": 1e-1, "c": 1e-2, "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9,
    "p": 1e-12, "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24,
}

# Factor from each atom to the SI base of its dimension. Mass base is the
# kilogram, so the gram is 1e-3 (and the prefixed kilogram resolves to 1e3·1e-3=1).
_ATOM_SCALE: dict[str, float] = {
    "1": 1.0, "": 1.0, "rad": 1.0, "deg": 1.0, "%": 1.0,
    "pcs": 1.0, "count": 1.0, "x": 1.0,
    "m": 1.0, "g": 1e-3, "s": 1.0, "A": 1.0, "K": 1.0, "mol": 1.0, "cd": 1.0,
    "metre": 1.0, "meter": 1.0,
    "Sv": 1.0, "Gy": 1.0,  # radiation dose units (scale 1; for RADIATION domain mapping)
    # KIc = MPa·√mm numerically in fracture.py; identity scale (opaque dim, no SI base)
    "KIc": 1.0,
    "min": 60.0, "h": 3600.0, "hr": 3600.0, "day": 86400.0,
    "t": 1e3,                                   # tonne = 1000 kg
    "L_vol": 1e-3,                              # litre = 1e-3 m³
    "N": 1.0, "Pa": 1.0, "bar": 1e5, "J": 1.0, "W": 1.0, "Hz": 1.0,
    "V": 1.0, "ohm": 1.0, "Ω": 1.0,
    "Ah": 3600.0, "Wh": 3600.0,                # ampere-hour / watt-hour to SI base
}


def _atom_scale(name: str) -> float | None:
    """Factor from one atom to its SI base, or None if unknown/opaque."""
    if name in _ATOM_SCALE:
        return _ATOM_SCALE[name]
    for plen in (2, 1):
        if len(name) > plen and name[:plen] in _PREFIX_FACTOR:
            remainder = name[plen:]
            if remainder in _ATOM_SCALE:
                return _PREFIX_FACTOR[name[:plen]] * _ATOM_SCALE[remainder]
    return None


def unit_scale(unit: str) -> float | None:
    """Factor converting a value in `unit` to the SI base of its dimension.

    Compound-aware: scale("g/cm^3") = scale(g) / scale(cm)^3 = 1e-3 / (1e-2)^3 =
    1e3 (so 1.24 g/cm³ -> 1240 kg/m³). Returns None if any atom is unknown/opaque
    — the caller must then refuse to claim a converted number (GENESIS honesty).
    """
    text = unit.strip()
    if text == "" or text == "1":
        return 1.0
    if not _UNIT_RE.fullmatch(text):
        raise UnitError(f"unparseable unit {unit!r}")
    scale = 1.0
    tokens = re.findall(r"([*/]?)\s*([^*/\s]+)", text)
    for op, atom in tokens:
        m = _ATOM_RE.match(atom)
        if not m:
            raise UnitError(f"unparseable unit atom {atom!r}")
        name, exp_part = m.group(1), m.group(2)
        exp = int(exp_part[1:]) if exp_part else 1
        base = _atom_scale(name)
        if base is None:
            return None                         # unknown atom -> no sound scale
        factor = base ** exp
        scale = scale / factor if op == "/" else scale * factor
    return scale


# --- formula dimension (the homogeneity check) -------------------------------

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def formula_dimension(formula: str, input_dims: dict[str, Dimension]) -> Dimension:
    """Dimension implied by `formula` over inputs of known dimension.

    Mirrors the safe evaluator's grammar (numbers, names, + - * /, unary minus,
    parentheses) but propagates Dimensions instead of values:
      * a number is dimensionless;
      * a name takes its input's dimension;
      * ``+``/``-`` REQUIRE equal dimensions (homogeneity) — else ``UnitError``;
      * ``*``/``/`` add/subtract exponents (Abelian group).
    Raises ``UnitError`` on incommensurable add/sub or unknown name; raises
    ``UnitError`` (not a silent pass) on any syntax outside the grammar.
    """
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise UnitError(f"formula {formula!r} not parseable: {exc.msg}") from None
    return _dim_node(tree.body, formula, input_dims)


def _dim_node(node: ast.AST, formula: str, dims: dict[str, Dimension]) -> Dimension:
    if isinstance(node, ast.Constant):
        return DIMENSIONLESS  # a literal number is dimensionless
    if isinstance(node, ast.Name):
        if node.id not in dims:
            raise UnitError(f"formula {formula!r}: unknown input {node.id!r}")
        return dims[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _dim_node(node.operand, formula, dims)
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _dim_node(node.left, formula, dims)
        right = _dim_node(node.right, formula, dims)
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        # Add / Sub: homogeneity — operands must share a dimension.
        if left != right:
            raise UnitError(
                f"formula {formula!r}: cannot add/subtract {left.render()} and "
                f"{right.render()} — incommensurable"
            )
        return left
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("min", "max")
        and not node.keywords
        and node.args
    ):
        # min/max compare their arguments, so the non-literal ones must share one
        # dimension; the result carries it. A pure numeric literal argument (e.g.
        # the 2 in ``max(2, 0.1 * q_w)``) is a bound in the other arguments' unit,
        # so it is dimension-agnostic — the same rule as a literal constraint side.
        non_literal_dims = [
            _dim_node(a, formula, dims) for a in node.args if not _is_numeric_literal_node(a)
        ]
        if not non_literal_dims:
            return DIMENSIONLESS  # all arguments are literals
        first = non_literal_dims[0]
        for d in non_literal_dims[1:]:
            if d != first:
                raise UnitError(
                    f"formula {formula!r}: {node.func.id}() over incommensurable "
                    f"dimensions {first.render()} and {d.render()}"
                )
        return first
    raise UnitError(f"formula {formula!r}: disallowed syntax {type(node).__name__}")


def _is_numeric_literal_node(node: ast.AST) -> bool:
    """True for a bare numeric constant, optionally with a unary sign."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return (
        isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and isinstance(node.value, (int, float))
    )
