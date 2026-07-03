"""Thermal-expansion mismatch stress — exact closed forms and their limit cases.

The constrained value is σ = −EαΔT exactly; the bonded-bar solution satisfies
equilibrium to machine precision, vanishes for equal coefficients, and tends to the
constrained limit for a rigid partner; the bimetal curvature vanishes for equal
coefficients and reduces to 1.5·Δα·ΔT/h for equal modulus and thickness. Offline, no
LLM, pure python.

Run:  pytest tests/test_thermal_stress.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.thermal_stress import (  # noqa: E402
    bimetal_curvature,
    bonded_bars_mismatch,
    constrained_thermal_stress,
    free_thermal_strain,
    thermal_mismatch_check,
)

# steel / aluminium, MPa and 1/K
_E_ST, _A_ST = 210000.0, 12e-6
_E_AL, _A_AL = 70000.0, 23e-6


# --- constrained bar -----------------------------------------------------------

def test_constrained_bar_is_minus_e_alpha_dt():
    # heated steel held at fixed length: compression of E*alpha*dT
    assert math.isclose(constrained_thermal_stress(_E_ST, _A_ST, 100.0), -252.0)
    # cooling reverses the sign (tension)
    assert constrained_thermal_stress(_E_ST, _A_ST, -100.0) > 0.0
    assert math.isclose(free_thermal_strain(_A_ST, 100.0), 12e-4)
    with pytest.raises(ValueError):
        constrained_thermal_stress(0.0, _A_ST, 100.0)


# --- bonded parallel bars ------------------------------------------------------

def test_bonded_bars_are_in_equilibrium_and_oppose():
    r = bonded_bars_mismatch(_E_ST, 1.0, _A_ST, _E_AL, 1.0, _A_AL, 100.0)
    # heating: aluminium wants to grow more, so it is compressed and steel is tensioned
    assert r["stress1"] > 0.0 > r["stress2"]
    assert abs(r["residual_force"]) < 1e-9            # equilibrium, by construction
    assert math.isclose(r["stress1"], 57.75, rel_tol=1e-3)


def test_equal_coefficients_give_no_mismatch_stress():
    r = bonded_bars_mismatch(_E_ST, 2.0, _A_ST, _E_AL, 3.0, _A_ST, 120.0)  # same alpha
    assert abs(r["stress1"]) < 1e-9 and abs(r["stress2"]) < 1e-9


def test_rigid_partner_recovers_the_constrained_limit():
    # a vastly stiffer/larger partner forces material 1 to follow partner's expansion:
    # stress1 -> E1*(alpha2 - alpha1)*dT
    r = bonded_bars_mismatch(_E_ST, 1.0, _A_ST, _E_AL, 1e9, _A_AL, 100.0)
    assert math.isclose(r["stress1"], _E_ST * (_A_AL - _A_ST) * 100.0, rel_tol=1e-4)


def test_bonded_guards():
    with pytest.raises(ValueError):
        bonded_bars_mismatch(_E_ST, 0.0, _A_ST, _E_AL, 1.0, _A_AL, 100.0)


# --- bimetal curvature (Timoshenko) --------------------------------------------

def test_bimetal_equal_modulus_thickness_reduces_to_textbook():
    # m=n=1: kappa = 1.5 (alpha2 - alpha1) dT / h, h = h1+h2
    h1 = h2 = 0.5
    kappa = bimetal_curvature(_A_ST, _A_AL, 100.0, 70000.0, 70000.0, h1, h2)
    assert math.isclose(kappa, 1.5 * (_A_AL - _A_ST) * 100.0 / (h1 + h2), rel_tol=1e-12)


def test_bimetal_vanishes_for_equal_coefficients():
    assert math.isclose(
        bimetal_curvature(_A_ST, _A_ST, 100.0, _E_ST, _E_AL, 0.4, 0.6), 0.0, abs_tol=1e-15
    )


def test_bimetal_sign_follows_temperature():
    # heating (dT>0) and cooling (dT<0) give opposite curvature
    hot = bimetal_curvature(_A_ST, _A_AL, 100.0, _E_ST, _E_AL, 0.5, 0.5)
    cold = bimetal_curvature(_A_ST, _A_AL, -100.0, _E_ST, _E_AL, 0.5, 0.5)
    assert hot > 0.0 > cold and math.isclose(hot, -cold)
    with pytest.raises(ValueError):
        bimetal_curvature(_A_ST, _A_AL, 100.0, _E_ST, _E_AL, 0.0, 0.5)


# --- the DFM check -------------------------------------------------------------

def test_mismatch_check_flags_overstress():
    # a big temperature swing on a steel/aluminium bond
    weak = thermal_mismatch_check(_E_ST, 1.0, _A_ST, _E_AL, 1.0, _A_AL, 300.0,
                                  strength1=100.0, strength2=100.0)
    strong = thermal_mismatch_check(_E_ST, 1.0, _A_ST, _E_AL, 1.0, _A_AL, 50.0,
                                    strength1=250.0, strength2=250.0)
    assert not weak["ok"] and weak["safety_factor"] < 1.0
    assert strong["ok"] and strong["safety_factor"] > 1.0
    with pytest.raises(ValueError):
        thermal_mismatch_check(_E_ST, 1.0, _A_ST, _E_AL, 1.0, _A_AL, 50.0,
                               strength1=0.0, strength2=100.0)
