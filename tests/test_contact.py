"""Hertzian contact stress — closed forms pinned to exact limits and a steel anchor.

The sphere-on-flat case must equal the sphere-sphere case in the r2 -> infinity limit
(two independent code paths agreeing); the centre/mean pressure ratios are exactly 3/2
(sphere) and 4/pi (cylinder); the line-contact p0 must reproduce the independent
identity p0 = sqrt(F'*E*/(pi*R)). A known steel anchor (two 10 mm balls, F = 100 N)
pins the actual numbers.

Offline, no LLM, pure python (no FEM, no mesher).

Run:  pytest tests/test_contact.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.contact import (  # noqa: E402
    contact_check,
    cylinder_cylinder_contact,
    effective_modulus,
    sphere_on_flat,
    sphere_sphere_contact,
)

_E, _NU = 210000.0, 0.3            # steel: MPa, dimensionless


# --- effective modulus ----------------------------------------------------------

def test_effective_modulus_steel_steel():
    # identical bodies: 1/E* = 2*(1-nu^2)/E  ->  E* = E/(2*(1-nu^2))
    e_star = effective_modulus(_E, _NU, _E, _NU)
    assert np.isclose(e_star, _E / (2.0 * (1.0 - _NU ** 2)))
    assert np.isclose(e_star, 115384.61538461539)


def test_effective_modulus_rigid_partner_limit():
    # an infinitely stiff partner -> E* tends to the single-body plane-strain modulus
    soft = effective_modulus(_E, _NU, 1e15, _NU)
    assert np.isclose(soft, _E / (1.0 - _NU ** 2), rtol=1e-6)


# --- sphere-sphere: the steel anchor (actual verified numbers) ------------------

def test_sphere_sphere_steel_anchor():
    r = sphere_sphere_contact(100.0, 10.0, 10.0, _E, _NU, _E, _NU)
    assert np.isclose(r["contact_radius"], 0.14812480342036854)   # mm
    assert np.isclose(r["max_pressure"], 2176.1348915877165)      # MPa
    assert np.isclose(r["mean_pressure"], 1450.7565943918112)     # MPa


def test_sphere_centre_to_mean_pressure_is_three_halves():
    r = sphere_sphere_contact(250.0, 8.0, 12.0, _E, _NU, _E, _NU)
    assert np.isclose(r["max_pressure"] / r["mean_pressure"], 1.5)
    # and p0 = 3F/(2 pi a^2) consistency
    a = r["contact_radius"]
    assert np.isclose(r["max_pressure"], 3.0 * 250.0 / (2.0 * math.pi * a ** 2))


# --- sphere-on-flat is the r2 -> infinity limit of sphere-sphere ----------------

def test_sphere_on_flat_equals_sphere_sphere_limit():
    flat = sphere_on_flat(100.0, 10.0, _E, _NU, _E, _NU)
    huge = sphere_sphere_contact(100.0, 10.0, 1e12, _E, _NU, _E, _NU)
    assert np.isclose(flat["contact_radius"], huge["contact_radius"], rtol=1e-6)
    assert np.isclose(flat["max_pressure"], huge["max_pressure"], rtol=1e-6)
    assert np.isclose(flat["mean_pressure"], huge["mean_pressure"], rtol=1e-6)


def test_sphere_on_flat_uses_ball_radius_as_R():
    # sphere on flat: R = ball radius, so a = (3 F R / (4 E*))^(1/3)
    flat = sphere_on_flat(100.0, 10.0, _E, _NU, _E, _NU)
    e_star = effective_modulus(_E, _NU, _E, _NU)
    a_expected = (3.0 * 100.0 * 10.0 / (4.0 * e_star)) ** (1.0 / 3.0)
    assert np.isclose(flat["contact_radius"], a_expected)


# --- cylinder line contact ------------------------------------------------------

def test_cylinder_p0_matches_independent_identity():
    # p0 = 2F'/(pi b) must equal sqrt(F' E* / (pi R)) — two independent forms
    r = cylinder_cylinder_contact(100.0, 10.0, 10.0, _E, _NU, _E, _NU)
    e_star = effective_modulus(_E, _NU, _E, _NU)
    big_r = 5.0                                    # 1/R = 1/10 + 1/10
    p0_alt = math.sqrt(100.0 * e_star / (math.pi * big_r))
    assert np.isclose(r["max_pressure"], p0_alt)
    assert np.isclose(r["half_width"], 0.07427901022845577)
    assert np.isclose(r["max_pressure"], 857.0655026360283)


def test_cylinder_centre_to_mean_pressure_is_four_over_pi():
    r = cylinder_cylinder_contact(100.0, 10.0, 1e12, _E, _NU, _E, _NU)
    p_mean = 100.0 / (2.0 * r["half_width"])        # F'/(2b) over the strip
    assert np.isclose(r["max_pressure"] / p_mean, 4.0 / math.pi)


# --- the design check -----------------------------------------------------------

def test_contact_check_flags_overpressure():
    r = sphere_sphere_contact(100.0, 10.0, 10.0, _E, _NU, _E, _NU)
    p0 = r["max_pressure"]                           # ~2176 MPa
    safe = contact_check(p0, 3000.0)
    over = contact_check(p0, 1500.0)
    assert safe["ok"] and safe["safety_factor"] > 1.0
    assert not over["ok"] and over["safety_factor"] < 1.0
    assert np.isclose(safe["safety_factor"], 3000.0 / p0)


# --- guards & determinism ------------------------------------------------------

def test_guards_reject_nonphysical_input():
    with pytest.raises(ValueError):
        effective_modulus(-1.0, 0.3, _E, _NU)
    with pytest.raises(ValueError):
        sphere_sphere_contact(0.0, 10.0, 10.0, _E, _NU, _E, _NU)
    with pytest.raises(ValueError):
        sphere_sphere_contact(100.0, -10.0, 10.0, _E, _NU, _E, _NU)
    with pytest.raises(ValueError):
        sphere_on_flat(100.0, 0.0, _E, _NU, _E, _NU)
    with pytest.raises(ValueError):
        cylinder_cylinder_contact(-1.0, 10.0, 10.0, _E, _NU, _E, _NU)
    with pytest.raises(ValueError):
        contact_check(-1.0, 1000.0)
    with pytest.raises(ValueError):
        contact_check(1000.0, 0.0)


def test_is_deterministic():
    a = sphere_sphere_contact(100.0, 10.0, 10.0, _E, _NU, _E, _NU)
    b = sphere_sphere_contact(100.0, 10.0, 10.0, _E, _NU, _E, _NU)
    assert a == b
