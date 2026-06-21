"""Tests für Ungleichungs-Conjectures (math-research, Stein b).

Rigorose Falsifikation für ge|gt|le|lt: ein Punkt, der die Relation rigoros verletzt,
REFUTES mit Witness; Intervall über dem Rand => inconclusive (nie falsche Refutation);
strikt refutet bei <=0, nicht-strikt nur bei strikt negativ.
"""

import pytest

from gen.identity_research import AssumptionManifest, assess_inequality


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_true_nonstrict_inequality_survives():
    art = assess_inequality("sq_nonneg", "x**2", "0", "ge", _mR())
    assert art.status == "SURVIVED_NOVEL"
    assert art.falsify.passed and art.falsify.witness is None


def test_false_inequality_refuted_with_witness():
    art = assess_inequality("ge1", "x", "1", "ge", _mR())   # x >= 1 is false for x < 1
    assert art.status == "REFUTED"
    assert art.falsify.witness is not None and art.falsify.witness["x"] < 1


def test_strict_vs_nonstrict_at_boundary():
    """The decisive case: x**2 > 0 is FALSE at x=0 (0>0), but x**2 >= 0 is TRUE."""
    strict = assess_inequality("sq_gt", "x**2", "0", "gt", _mR())
    assert strict.status == "REFUTED"
    assert strict.falsify.witness["x"] == 0.0          # boundary point refutes strict
    nonstrict = assess_inequality("sq_ge", "x**2", "0", "ge", _mR())
    assert nonstrict.status == "SURVIVED_NOVEL"        # same expr, non-strict survives


def test_le_relation_true():
    art = assess_inequality("neg_sq", "-x**2", "0", "le", _mR())   # -x^2 <= 0 always
    assert art.status == "SURVIVED_NOVEL"


def test_completing_the_square_inequality_survives():
    """x**2 + 1 >= 2*x  <=>  (x-1)**2 >= 0 — true on R."""
    art = assess_inequality("amgm", "x**2 + 1", "2*x", "ge", _mR())
    assert art.status == "SURVIVED_NOVEL"
    assert art.falsify.witness is None


def test_eq_relation_is_rejected():
    with pytest.raises(ValueError):
        assess_inequality("bad", "x", "x", "eq", _mR())  # use assess_identity for equality
