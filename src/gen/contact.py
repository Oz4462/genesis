"""Hertzian contact stress — the local pressure where curved bodies touch (closed form).

The stress check (structural.py) sees a part's nominal section stress; the FEM layers
see global deformation. Neither sees the failure where two curved bodies TOUCH: a ball
bearing on its race, a press-fit pin, meshing gear teeth, a cam on a follower. The
contact patch is tiny, so even a modest force produces an enormous LOCAL pressure far
above the nominal stress — the seat of pitting, spalling, brinelling and subsurface
fatigue that the nominal check never reports. This module adds Hertz's 1882 closed
forms for the two geometries that cover most machine elements.

  • SPHERE-SPHERE (point contact) — a circular patch of radius a; the pressure peaks at
    the centre with p0 = 1.5·p_mean. Ball bearings, ball-and-socket, two crowned faces.
  • SPHERE-ON-FLAT — the r2 -> infinity limit of sphere-sphere (R = the ball radius).
  • CYLINDER-CYLINDER (line contact) — a strip of half-width b; the pressure peaks with
    p0 = (4/pi)·p_mean. Roller bearings, gear-tooth flanks, cam-follower lines.

Each rests on the EFFECTIVE (reduced) modulus 1/E* = (1-nu1^2)/E1 + (1-nu2^2)/E2, which
folds both bodies' elasticity into one number, and the effective radius 1/R = 1/r1 + 1/r2.

Verified, not asserted: sphere_on_flat equals sphere_sphere in the r2 -> infinity limit;
the centre/mean pressure ratios are exactly 3/2 (sphere) and 4/pi (cylinder); the line
p0 reproduces the independent identity p0 = sqrt(F'*E*/(pi*R)); a steel anchor (two
10 mm balls, F = 100 N, E = 210000 MPa, nu = 0.3) gives a = 0.1481 mm and
p0 = 2176.1 MPa — all pinned in the test.

Consistent N-mm-MPa units: forces in N (line load F' in N/mm), radii and lengths in mm,
E and pressures in MPa. Honest boundary: frictionless, non-adhesive, non-conforming
elastic contact of smooth bodies, small relative to the body radii (Hertz's
assumptions); it does NOT cover adhesion (JKR), surface roughness, tangential/traction
loading, plastic yielding once p0 exceeds ~1.6*sigma_y, or the subsurface shear that
actually nucleates rolling-contact fatigue.

Source: H. Hertz (1882), "Ueber die Beruehrung fester elastischer Koerper", J. reine
angew. Math. 92; K. L. Johnson, *Contact Mechanics* (1985), Ch. 3-4.
"""

from __future__ import annotations

import math


def effective_modulus(e1: float, nu1: float, e2: float, nu2: float) -> float:
    """Reduced (effective) contact modulus E* (MPa) from 1/E* = (1-nu1^2)/E1 +
    (1-nu2^2)/E2 — the single elastic constant Hertz contact depends on. Raises
    ValueError on a non-positive modulus."""
    if e1 <= 0.0 or e2 <= 0.0:
        raise ValueError("both moduli must be positive")
    return 1.0 / ((1.0 - nu1 ** 2) / e1 + (1.0 - nu2 ** 2) / e2)


def _effective_radius(r1: float, r2: float) -> float:
    """Combined radius R from 1/R = 1/r1 + 1/r2 (a flat is r -> infinity). Raises
    ValueError on a non-positive radius."""
    if r1 <= 0.0 or r2 <= 0.0:
        raise ValueError("both radii must be positive (use a large radius for a flat)")
    return 1.0 / (1.0 / r1 + 1.0 / r2)


def sphere_sphere_contact(
    force: float, r1: float, r2: float,
    e1: float, nu1: float, e2: float, nu2: float,
) -> dict:
    """Hertz point contact of two spheres pressed by `force` (N).

    With 1/R = 1/r1 + 1/r2 and E* the effective modulus, the circular patch has radius
    a = (3*F*R/(4*E*))^(1/3); the pressure is hemispherical, peaking at the centre with
    p0 = 3F/(2*pi*a^2) = 1.5*p_mean. Returns ``{"contact_radius", "max_pressure",
    "mean_pressure"}`` (mm, MPa, MPa). Raises ValueError on non-positive force/radius/
    modulus."""
    if force <= 0.0:
        raise ValueError("force must be positive")
    big_r = _effective_radius(r1, r2)
    e_star = effective_modulus(e1, nu1, e2, nu2)
    a = (3.0 * force * big_r / (4.0 * e_star)) ** (1.0 / 3.0)
    p0 = 3.0 * force / (2.0 * math.pi * a ** 2)
    p_mean = force / (math.pi * a ** 2)
    return {"contact_radius": a, "max_pressure": p0, "mean_pressure": p_mean}


def sphere_on_flat(
    force: float, radius: float,
    e1: float, nu1: float, e2: float, nu2: float,
) -> dict:
    """Hertz point contact of a sphere on a flat — the r2 -> infinity limit of
    `sphere_sphere_contact`, so the effective radius R is simply the sphere `radius`.
    Returns the same dict (contact radius, max and mean pressure). Raises ValueError on
    non-positive force/radius/modulus."""
    if force <= 0.0:
        raise ValueError("force must be positive")
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    e_star = effective_modulus(e1, nu1, e2, nu2)
    a = (3.0 * force * radius / (4.0 * e_star)) ** (1.0 / 3.0)
    p0 = 3.0 * force / (2.0 * math.pi * a ** 2)
    p_mean = force / (math.pi * a ** 2)
    return {"contact_radius": a, "max_pressure": p0, "mean_pressure": p_mean}


def cylinder_cylinder_contact(
    force_per_length: float, r1: float, r2: float,
    e1: float, nu1: float, e2: float, nu2: float,
) -> dict:
    """Hertz line contact of two parallel cylinders under a load per unit length
    `force_per_length` F' (N/mm).

    With 1/R = 1/r1 + 1/r2 the contact strip has half-width b = sqrt(4*F'*R/(pi*E*));
    the pressure is elliptic across the strip, peaking at p0 = 2*F'/(pi*b) = (4/pi)*
    p_mean (equivalently p0 = sqrt(F'*E*/(pi*R))). Returns ``{"half_width",
    "max_pressure"}`` (mm, MPa). A flat raceway is r2 -> infinity (pass a large radius).
    Raises ValueError on non-positive load/radius/modulus."""
    if force_per_length <= 0.0:
        raise ValueError("force per length must be positive")
    big_r = _effective_radius(r1, r2)
    e_star = effective_modulus(e1, nu1, e2, nu2)
    b = math.sqrt(4.0 * force_per_length * big_r / (math.pi * e_star))
    p0 = 2.0 * force_per_length / (math.pi * b)
    return {"half_width": b, "max_pressure": p0}


def contact_check(
    max_pressure: float | None = None,
    allowable_pressure: float | None = None,
    force: float | None = None,
    r1: float | None = None,
    r2: float | None = None,
    e1: float | None = None,
    nu1: float | None = None,
    e2: float | None = None,
    nu2: float | None = None,
) -> dict:
    """Contact-pressure design check (Hertzian).

    Supports two call styles for seam compatibility:
    - Direct: contact_check(max_pressure=..., allowable_pressure=...)
    - Recipe/geometry (from physics_selection): contact_check(force=..., r1=..., r2=..., e1=..., nu1=..., e2=..., nu2=..., allowable_pressure=...)
      Internally computes p0 via sphere_sphere_contact then compares.

    Returns ``{"max_pressure", "allowable_pressure", "safety_factor", "ok"}``.
    safety_factor = allowable / max; ok = >= 1.0. Deterministic.
    Raises on non-positive values. Backward compatible with 2-arg positional calls from tests.
    """
    if max_pressure is None and force is not None:
        # geometry path from recipe: compute p0
        if None in (force, r1, r2, e1, nu1, e2, nu2):
            raise ValueError("geometry inputs incomplete for hertz contact")
        if force <= 0.0:
            raise ValueError("force must be positive")
        p = sphere_sphere_contact(force, r1, r2, e1, nu1, e2, nu2)
        max_pressure = p["max_pressure"]
    if max_pressure is None or max_pressure <= 0.0:
        raise ValueError("max_pressure must be positive")
    if allowable_pressure is None or allowable_pressure <= 0.0:
        raise ValueError("allowable_pressure must be positive")
    safety = allowable_pressure / max_pressure
    return {
        "max_pressure": max_pressure,
        "allowable_pressure": allowable_pressure,
        "safety_factor": safety,
        "ok": safety >= 1.0,
    }
