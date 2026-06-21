"""Torsion — the shear failure of a twisted circular shaft (closed form, no FEM).

The stress check (structural.py) and the bending/axial layers compare a normal
stress to the static strength; buckling.py adds instability, fatigue.py adds cyclic
life. None of them sees a shaft loaded in TORSION: a torque twists the shaft and
raises a SHEAR stress that is largest at the outer surface, where the material can
shear off below any bending/axial margin. A drive shaft, an axle, a torsion bar, a
fastened lug under a wrenching moment: each can pass every bending/axial check and
still fail by torsional shear. This module adds that fourth axis.

Four textbook closed forms for a circular cross-section (the only section whose
torsion stays plane and admits an exact elementary solution):
  • the POLAR SECOND MOMENT OF AREA J — J = pi*d**4/32 for a solid shaft,
    J = pi*(D**4 - d**4)/32 for a hollow shaft (the section property torsion uses,
    the rotational analogue of the bending I);
  • the TORSIONAL SHEAR STRESS tau = T*r/J at radius r (linear from zero on the
    axis to a maximum at the surface);
  • the surface stress of a solid shaft tau_max = 16*T/(pi*d**3), which is exactly
    T*(d/2)/J with J = pi*d**4/32 — an algebraic identity, not an approximation;
  • the ANGLE OF TWIST phi = T*L/(G*J) [radians], linear in length and in 1/G.

Plus a DFM-style shaft_torsion_check returning the surface stress, the twist angle,
a safety factor against the shear strength, and an ok bool.

Verified, not asserted: the surface stress equals 16*T/(pi*d**3) AND equals T*(d/2)/J
to machine precision (the identity), the hollow J reduces to the solid J when the
inner diameter is zero, the twist scales linearly with L and with 1/G, and the
concrete anchor T=100000 N*mm on d=20 mm gives tau=63.66 MPa — all pinned in the test.

Consistent N-mm-MPa units (as structural.py / fem.py): T in N*mm, lengths in mm,
G in MPa (N/mm**2), stresses in MPa, twist in rad. Honest boundary: linear-elastic
St-Venant torsion of a PRISMATIC CIRCULAR shaft (solid or hollow). It does NOT cover
non-circular sections (which warp out of plane and need the membrane analogy /
torsion constant, not J), stress concentrations at shoulders/keyways/holes (apply a
K_t separately), plastic torsion, or combined bending+torsion (use a von-Mises /
maximum-shear failure criterion on the combined stress state for that).

Source: torsion of circular shafts, standard Mechanics of Materials
(R. C. Hibbeler, *Mechanics of Materials*, 10th ed., 2017, ch. 5; Timoshenko &
Gere, *Mechanics of Materials*) — the elementary tau = T*rho/J and phi = T*L/(G*J).
"""

from __future__ import annotations

import math


def polar_moment_solid(diameter: float) -> float:
    """Polar second moment of area J = pi*d**4/32 (mm**4) of a solid circular shaft.

    The rotational stiffness/strength property of the section. Raises ValueError on a
    non-positive diameter (a shaft has a real, positive size)."""
    if diameter <= 0.0:
        raise ValueError("diameter must be positive")
    return math.pi * diameter ** 4 / 32.0


def polar_moment_hollow(outer_diameter: float, inner_diameter: float) -> float:
    """Polar second moment J = pi*(D**4 - d**4)/32 (mm**4) of a hollow circular shaft.

    Reduces exactly to the solid value when ``inner_diameter`` is zero. Raises
    ValueError on a non-positive outer diameter, a negative inner diameter, or an
    inner diameter not smaller than the outer (no material left to carry the torque)."""
    if outer_diameter <= 0.0:
        raise ValueError("outer diameter must be positive")
    if inner_diameter < 0.0:
        raise ValueError("inner diameter must be non-negative")
    if inner_diameter >= outer_diameter:
        raise ValueError("inner diameter must be smaller than the outer diameter")
    return math.pi * (outer_diameter ** 4 - inner_diameter ** 4) / 32.0


def torsional_shear_stress(torque: float, radius: float, polar_moment: float) -> float:
    """Torsional shear stress tau = T*r/J (MPa) at radius r from the axis.

    Linear in the radius: zero on the centroidal axis, maximum at the outer surface.
    `polar_moment` is J from ``polar_moment_solid``/``polar_moment_hollow``. Raises
    ValueError on a non-positive J or a negative radius."""
    if polar_moment <= 0.0:
        raise ValueError("polar moment J must be positive")
    if radius < 0.0:
        raise ValueError("radius must be non-negative")
    return torque * radius / polar_moment


def max_shaft_shear_stress(torque: float, diameter: float) -> float:
    """Surface shear stress tau_max = 16*T/(pi*d**3) (MPa) of a SOLID circular shaft.

    This is algebraically identical to ``torsional_shear_stress(T, d/2,
    polar_moment_solid(d))`` (substitute J = pi*d**4/32) — a closed form, not an
    approximation. Raises ValueError on a non-positive diameter."""
    if diameter <= 0.0:
        raise ValueError("diameter must be positive")
    return 16.0 * torque / (math.pi * diameter ** 3)


def angle_of_twist(
    torque: float, length: float, shear_modulus_g: float, polar_moment: float
) -> float:
    """Total angle of twist phi = T*L/(G*J) (radians) of a prismatic circular shaft.

    Linear in the length L and in 1/G (a softer material twists proportionally more).
    `shear_modulus_g` G and the implied stresses are in MPa; the result is
    dimensionless (radians). Raises ValueError on a non-positive G or J."""
    if shear_modulus_g <= 0.0:
        raise ValueError("shear modulus G must be positive")
    if polar_moment <= 0.0:
        raise ValueError("polar moment J must be positive")
    return torque * length / (shear_modulus_g * polar_moment)


def shaft_torsion_check(
    torque: float,
    diameter: float,
    length: float,
    shear_modulus_g: float,
    shear_strength: float,
) -> dict:
    """Torsional shear check of a SOLID circular shaft.

    Computes the surface shear stress (``max_shaft_shear_stress``) and the angle of
    twist (``angle_of_twist`` with J = pi*d**4/32). Returns ``{"max_shear",
    "twist_angle", "polar_moment", "safety_factor", "ok"}``: max_shear and shear_strength
    in MPa, twist_angle in rad, safety_factor = shear_strength / max_shear,
    ok = safety_factor >= 1. Deterministic. Raises ValueError on a non-positive
    shear_strength (or via the called functions on a non-positive diameter/G)."""
    if shear_strength <= 0.0:
        raise ValueError("shear strength must be positive")
    j = polar_moment_solid(diameter)
    max_shear = max_shaft_shear_stress(torque, diameter)
    twist = angle_of_twist(torque, length, shear_modulus_g, j)
    safety_factor = math.inf if max_shear == 0.0 else shear_strength / max_shear
    return {
        "max_shear": max_shear,
        "twist_angle": twist,
        "polar_moment": j,
        "safety_factor": safety_factor,
        "ok": safety_factor >= 1.0,
    }
