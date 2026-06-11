"""Tests for dimensional analysis — units as an Abelian group (no LLM, no net).

These pin the deterministic core of GATE γ's dimensional homogeneity check:
add/subtract require equal dimensions, multiply/divide combine exponents, known
metric units (incl. prefixes) resolve to real dimensions, unknown units become
opaque (never silently compatible), and a correct unit conversion stays
dimensionally valid while a real dimension error is caught.

Foundations: standard dimensional homogeneity + Kennedy, "Types for
Units-of-Measure: Theory and Practice" (CEFP 2009). Motivating failure: the
Mars Climate Orbiter (pound-force·s vs newton·s, NASA 1999).

Run:  pytest tests/test_units.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import UnitError  # noqa: E402
from gen.verification.units import (  # noqa: E402
    DIMENSIONLESS,
    Dimension,
    formula_dimension,
    parse_unit,
)


# --- parsing: known units, prefixes, compounds, dimensionless -----------------

def test_dimensionless_forms():
    assert parse_unit("1") == DIMENSIONLESS
    assert parse_unit("") == DIMENSIONLESS
    assert parse_unit("  1 ") == DIMENSIONLESS


def test_base_units_resolve():
    assert parse_unit("m") == Dimension.of({"L": 1})
    assert parse_unit("s") == Dimension.of({"T": 1})


def test_prefixed_units_share_their_base_dimension():
    # mm, cm, km are all length; kg, mg are all mass — prefix is irrelevant to dimension
    length = Dimension.of({"L": 1})
    mass = Dimension.of({"M": 1})
    assert parse_unit("mm") == length
    assert parse_unit("cm") == length
    assert parse_unit("km") == length
    assert parse_unit("kg") == mass
    assert parse_unit("mg") == mass


def test_direct_atom_wins_over_prefix_split():
    # "min" is minute (time), not milli-"in"; "mol" is amount, not milli-"ol"
    assert parse_unit("min") == Dimension.of({"T": 1})
    assert parse_unit("mol") == Dimension.of({"N": 1})


def test_named_derived_units():
    force = Dimension.of({"M": 1, "L": 1, "T": -2})
    assert parse_unit("N") == force
    assert parse_unit("kN") == force                      # prefixed derived unit
    # pressure = force/area
    assert parse_unit("Pa") == Dimension.of({"M": 1, "L": -1, "T": -2})


def test_compound_units():
    assert parse_unit("m/s") == Dimension.of({"L": 1, "T": -1})
    assert parse_unit("m/s^2") == Dimension.of({"L": 1, "T": -2})
    assert parse_unit("kg*m/s^2") == Dimension.of({"M": 1, "L": 1, "T": -2})
    assert parse_unit("m^3") == Dimension.of({"L": 3})


def test_unknown_unit_is_opaque_not_guessed():
    widget = parse_unit("widget")
    assert widget == parse_unit("widget")                 # stable
    assert widget != parse_unit("kg")                     # never compatible with a known dim
    assert widget != DIMENSIONLESS                        # not silently dimensionless


def test_unparseable_unit_raises():
    with pytest.raises(UnitError):
        parse_unit("kg//m")


# --- Abelian-group algebra ----------------------------------------------------

def test_mul_div_combine_exponents():
    L = Dimension.of({"L": 1})
    T = Dimension.of({"T": 1})
    assert (L / T) == Dimension.of({"L": 1, "T": -1})
    assert (L * L) == Dimension.of({"L": 2})
    assert (L / L) == DIMENSIONLESS                       # inverse cancels


# --- formula homogeneity (the heart of the check) -----------------------------

def test_multiply_combines_dimensions():
    dims = {"q_load": parse_unit("kg"), "q_sf": parse_unit("1")}
    assert formula_dimension("q_load * q_sf", dims) == parse_unit("kg")


def test_divide_by_scalar_keeps_dimension():
    dims = {"q_d": parse_unit("mm")}
    assert formula_dimension("q_d / 2", dims) == parse_unit("mm")


def test_area_is_length_squared():
    dims = {"q_w": parse_unit("mm"), "q_h": parse_unit("mm")}
    assert formula_dimension("q_w * q_h", dims) == parse_unit("mm^2")


def test_add_incommensurable_raises():
    # the Mars-Orbiter class: adding mass to length is dimensional nonsense
    dims = {"q_load": parse_unit("kg"), "q_len": parse_unit("mm")}
    with pytest.raises(UnitError):
        formula_dimension("q_load + q_len", dims)


def test_add_commensurable_ok_even_across_prefixes():
    # cm + mm are both length -> homogeneous (magnitude is a separate concern)
    dims = {"a": parse_unit("cm"), "b": parse_unit("mm")}
    assert formula_dimension("a + b", dims) == parse_unit("m")  # all length


def test_unit_conversion_is_dimensionally_consistent():
    # GENESIS rule: 50 mm from a "5 cm" source is DERIVED via q_cm * 10.
    # Dimensionally: length * dimensionless = length == mm. Consistent.
    dims = {"q_cm": parse_unit("cm")}
    assert formula_dimension("q_cm * 10", dims) == parse_unit("mm")


def test_unknown_formula_input_raises():
    with pytest.raises(UnitError):
        formula_dimension("ghost * 2", {"a": parse_unit("m")})


def test_formula_outside_grammar_raises():
    with pytest.raises(UnitError):
        formula_dimension("a ** 2", {"a": parse_unit("m")})
