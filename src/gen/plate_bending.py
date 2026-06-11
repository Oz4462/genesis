"""Plate bending — the out-of-plane deflection failure of a flat panel under pressure
(Kirchhoff thin-plate theory, closed form, no FEM).

The beam/bar layers (structural.py, fem.py) carry load along ONE dimension; the
pressure-vessel layer carries a membrane stress in a curved shell. None of them sees
the failure of a flat 2-D plate: a panel, an instrument cover, a window pane, a PCB,
a tank head — clamped or simply supported around its rim and pushed on by a uniform
pressure. The plate has no axis to carry the load along; it must BEND in two
directions at once, deflecting at its centre and raising a bending stress that can
crack a brittle window or yield a thin cover long before any 1-D check would flag it.
This module adds that two-dimensional bending axis.

Closed-form Kirchhoff solutions for a CIRCULAR plate of radius R and thickness t under
uniform pressure q (the circular case is the one with an exact elementary solution; a
rectangular plate needs the tabulated coefficient of its aspect ratio):
  * the FLEXURAL RIGIDITY D = E*t**3/(12*(1-nu**2)) — the plate's bending stiffness,
    the 2-D analogue of the beam's E*I, cubic in the thickness;
  * CLAMPED edge (built-in rim, zero slope and deflection at r=R): the deflection is
    largest at the centre, w_max = q*R**4/(64*D), and the bending stress is largest at
    the EDGE, sigma_max = 3*q*R**2/(4*t**2) (the clamped rim is where the plate fights
    the load hardest);
  * SIMPLY SUPPORTED edge (rim free to rotate, held only against deflection): a softer
    boundary, so it deflects MORE — w_max = (5+nu)*q*R**4/(64*(1+nu)*D) at the centre —
    and now the bending stress is largest at the CENTRE,
    sigma_max = 3*(3+nu)*q*R**2/(8*t**2).

Plus a DFM-style plate_bending_check returning the centre deflection, the maximum
bending stress, a safety factor against an allowable stress, and an ok bool.

Verified, not asserted: a simply-supported plate deflects MORE than a clamped one of
the same geometry (w_ss/w_clamped = (5+nu)/(1+nu) = 4.077 at nu=0.3 — a softer rim);
D scales exactly as t**3 (doubling t stiffens 8x); the deflection scales as R**4
(doubling R deflects 16x) and as 1/t**3 (doubling t deflects 1/8x); and the concrete
steel anchor q=0.1 MPa, R=100 mm, t=5 mm, E=210000, nu=0.3 gives, clamped,
w_max = 0.065 mm and sigma_max = 30.0 MPa — all pinned in the test.

Consistent N-mm-MPa units (as structural.py / pressure_vessel.py): pressure q and
stress in MPa (N/mm**2), lengths R and t in mm, E in MPa; the deflection w is in mm.
Honest boundary: linear-elastic SMALL-deflection (Kirchhoff) bending of a thin, flat,
isotropic CIRCULAR plate under UNIFORM pressure, with an idealised clamped or
simply-supported rim. It does NOT cover large deflections (when w approaches t the
plate stiffens via membrane action and these forms OVER-predict the deflection),
rectangular/other shapes (use the tabulated Roark coefficient for the aspect ratio),
point/patch loads, in-plane (membrane) preload, orthotropic laminates, or stress
concentrations at holes/fixings (apply a K_t separately).

Source: Timoshenko, S. & Woinowsky-Krieger, S. (1959), *Theory of Plates and Shells*,
2nd ed., ch. 3 (symmetrical bending of circular plates); Young, W. C. & Budynas, R. G.,
*Roark's Formulas for Stress and Strain* (flat circular plate, uniform load, cases for
clamped and simply-supported edges).
"""

from __future__ import annotations

import math


def flexural_rigidity(e_modulus: float, thickness: float, nu: float) -> float:
    """Flexural (bending) rigidity D = E*t**3/(12*(1-nu**2)) (N*mm) of a thin plate.

    The 2-D analogue of the beam's E*I — the plate's resistance to bending, cubic in
    the thickness. `e_modulus` E in MPa, `thickness` t in mm, `nu` the Poisson ratio.
    Raises ValueError on a non-positive E or thickness, or a Poisson ratio outside
    the physical open interval (-1, 0.5) (which would make 1-nu**2 non-positive or
    the material thermodynamically impossible)."""
    if e_modulus <= 0.0:
        raise ValueError("elastic modulus must be positive")
    if thickness <= 0.0:
        raise ValueError("thickness must be positive")
    if not -1.0 < nu < 0.5:
        raise ValueError("Poisson ratio must lie in (-1, 0.5)")
    return e_modulus * thickness ** 3 / (12.0 * (1.0 - nu ** 2))


def circular_plate_clamped(
    pressure_q: float, radius_R: float, thickness_t: float, e_modulus: float, nu: float
) -> dict:
    """Circular plate with a CLAMPED edge under uniform pressure (Kirchhoff theory).

    Built-in rim (zero deflection and zero slope at r=R). Returns
    ``{"max_deflection", "max_stress"}``: the deflection is largest at the CENTRE,
    w_max = q*R**4/(64*D), and the bending stress is largest at the EDGE,
    sigma = 3*q*R**2/(4*t**2) (MPa) — the clamped rim is where the plate works
    hardest. `pressure_q` and stresses in MPa, lengths in mm; w in mm. Raises
    ValueError on a non-positive radius or thickness (via ``flexural_rigidity`` for
    a bad E/nu)."""
    if radius_R <= 0.0:
        raise ValueError("radius must be positive")
    if thickness_t <= 0.0:
        raise ValueError("thickness must be positive")
    d = flexural_rigidity(e_modulus, thickness_t, nu)
    return {
        "max_deflection": pressure_q * radius_R ** 4 / (64.0 * d),
        "max_stress": 3.0 * pressure_q * radius_R ** 2 / (4.0 * thickness_t ** 2),
    }


def circular_plate_simply_supported(
    pressure_q: float, radius_R: float, thickness_t: float, e_modulus: float, nu: float
) -> dict:
    """Circular plate with a SIMPLY SUPPORTED edge under uniform pressure (Kirchhoff).

    The rim is held against deflection but free to rotate — a softer boundary than
    clamped, so it deflects MORE. Returns ``{"max_deflection", "max_stress"}``: the
    deflection is largest at the CENTRE, w_max = (5+nu)*q*R**4/(64*(1+nu)*D), and now
    the bending stress is also largest at the CENTRE,
    sigma = 3*(3+nu)*q*R**2/(8*t**2) (MPa). `pressure_q` and stresses in MPa, lengths
    in mm; w in mm. Raises ValueError on a non-positive radius or thickness (via
    ``flexural_rigidity`` for a bad E/nu)."""
    if radius_R <= 0.0:
        raise ValueError("radius must be positive")
    if thickness_t <= 0.0:
        raise ValueError("thickness must be positive")
    d = flexural_rigidity(e_modulus, thickness_t, nu)
    return {
        "max_deflection": (5.0 + nu) * pressure_q * radius_R ** 4
        / (64.0 * (1.0 + nu) * d),
        "max_stress": 3.0 * (3.0 + nu) * pressure_q * radius_R ** 2
        / (8.0 * thickness_t ** 2),
    }


def plate_bending_check(
    pressure_q: float,
    radius_R: float,
    thickness_t: float,
    e_modulus: float,
    nu: float,
    allowable_stress: float,
    *,
    edge: str = "clamped",
) -> dict:
    """Bending check of a uniformly loaded circular plate against an allowable stress.

    Computes the centre deflection and the maximum bending stress for the chosen
    `edge` ('clamped' or 'simply_supported') and compares the stress to
    `allowable_stress`. Returns ``{"max_deflection", "max_stress", "safety_factor",
    "ok"}``: max_stress and allowable_stress in MPa, max_deflection in mm,
    safety_factor = allowable_stress / max_stress, ok = safety_factor >= 1.
    Deterministic.

    Units: MPa and mm. Raises ValueError on a non-positive allowable stress or an
    unknown `edge` (a guessed boundary would fabricate the governing stress); raises
    ValueError via the called functions on a non-positive radius/thickness or a bad
    E/nu."""
    if allowable_stress <= 0.0:
        raise ValueError("allowable stress must be positive")
    if edge == "clamped":
        result = circular_plate_clamped(
            pressure_q, radius_R, thickness_t, e_modulus, nu
        )
    elif edge == "simply_supported":
        result = circular_plate_simply_supported(
            pressure_q, radius_R, thickness_t, e_modulus, nu
        )
    else:
        raise ValueError(
            f"unknown edge {edge!r}; one of 'clamped', 'simply_supported'"
        )
    max_stress = result["max_stress"]
    safety_factor = math.inf if max_stress <= 0.0 else allowable_stress / max_stress
    return {
        "max_deflection": result["max_deflection"],
        "max_stress": max_stress,
        "safety_factor": safety_factor,
        "ok": max_stress <= 0.0 or safety_factor >= 1.0,
    }
