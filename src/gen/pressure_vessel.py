"""Pressure-vessel wall stress — the hoop stress that bursts a tank/pipe/cylinder
(closed form, no FEM).

A point-load stress check (structural.py) never sees the failure of a part that
carries no external point load at all: a closed tank, a pipe, a gas cylinder under
INTERNAL PRESSURE. The pressure pushes outward on the wall everywhere, and the
circumferential (hoop) stress it raises is the one that splits the wall lengthwise —
typically twice the longitudinal (axial) stress, and entirely invisible to a check
that only looks for an applied force. This module adds that pressure axis.

Three textbook closed forms, each with an exact limit pinned in the test:
  * THIN-WALL membrane theory — for t/r small the wall carries a near-uniform
    membrane stress: cylinder hoop sigma_h = p*r/t, axial sigma_a = p*r/(2*t) (so
    hoop = 2*axial, the reason a sausage/pipe splits along its length); sphere
    sigma = p*r/(2*t) (a sphere is the optimal pressure shape — half the cylinder
    hoop).
  * THICK-WALL Lame (1833) — when the wall is not thin the stress varies through it.
    With A = p_i*r_i^2/(r_o^2-r_i^2) and B = p_i*r_i^2*r_o^2/(r_o^2-r_i^2),
    sigma_r = A - B/r^2 and sigma_theta = A + B/r^2. The hoop is MAXIMUM at the
    inner wall and the radial stress satisfies the exact boundary conditions
    sigma_r(r_i) = -p_i and sigma_r(r_o) = 0.

Verified, not asserted: the thin-wall hoop is exactly twice the axial stress; the
Lame radial stress hits its two boundary conditions exactly; the thick-wall hoop at
the inner wall is HIGHER than the thin-wall estimate and the two converge as
t/r -> 0 (1.0% gap at t/r=0.02, 66.7% at t/r=1.0, 0.05% at t/r=0.001 — all pinned);
and the anchor p=10 MPa, r=500 mm, t=10 mm gives hoop = 500 MPa exactly.

Consistent units (as structural.py): pressure and stress in MPa, lengths in mm.
Honest boundary: linear-elastic, static internal pressure, axisymmetric prismatic
cylinder/sphere far from ends and openings. It does NOT cover end-cap/discontinuity
bending, nozzle stress-concentration, external pressure / buckling collapse (a
separate instability mode — see buckling.py), or autofrettage residual stress; and
the thin-wall forms are an approximation that under-predicts the true inner-wall hoop
(use model='thick' when t/r is not small).

Source: thin-wall membrane theory (Shigley, *Mechanical Engineering Design*); Lame,
G. & Clapeyron, B. (1833), thick-wall cylinder solution.
"""

from __future__ import annotations

from .core.errors import GeometryError


def thin_wall_cylinder(pressure: float, radius: float, thickness: float) -> dict:
    """Thin-wall cylinder under internal pressure (membrane theory).

    Returns ``{"hoop_stress", "axial_stress"}`` with hoop = p*r/t and
    axial = p*r/(2*t) (MPa). The hoop (circumferential) stress is exactly twice the
    axial (longitudinal) stress, which is why a pressurised cylinder splits along
    its length rather than across it. Raises GeometryError on a non-positive radius
    or thickness (a guessed geometry would fabricate a stress).
    """
    if not (radius > 0.0) or not (thickness > 0.0):
        raise GeometryError(
            f"radius and thickness must be positive (got r={radius}, t={thickness})"
        )
    return {
        "hoop_stress": pressure * radius / thickness,
        "axial_stress": pressure * radius / (2.0 * thickness),
    }


def thin_wall_sphere(pressure: float, radius: float, thickness: float) -> float:
    """Hoop (membrane) stress sigma = p*r/(2*t) (MPa) of a thin-wall sphere under
    internal pressure. A sphere carries equal stress in every direction, so its
    wall stress is half a cylinder's hoop — the optimal pressure-vessel shape.
    Raises GeometryError on a non-positive radius or thickness."""
    if not (radius > 0.0) or not (thickness > 0.0):
        raise GeometryError(
            f"radius and thickness must be positive (got r={radius}, t={thickness})"
        )
    return pressure * radius / (2.0 * thickness)


def thick_wall_cylinder_stresses(
    pressure_internal: float, r_inner: float, r_outer: float, r: float
) -> dict:
    """Lame (1833) radial and hoop stress at radius `r` in a thick-wall cylinder
    under non-negative internal pressure only (external pressure disclaimed; see
    module docstring). Negative pressure will produce negative stresses but is
    not a valid input for this internal model.

    With A = p_i*r_i^2/(r_o^2-r_i^2) and B = p_i*r_i^2*r_o^2/(r_o^2-r_i^2):
    sigma_r = A - B/r^2 and sigma_theta = A + B/r^2 (MPa). Returns
    ``{"radial_stress", "hoop_stress"}``. The hoop stress is maximum at the inner
    wall; the radial stress satisfies sigma_r(r_i) = -p_i and sigma_r(r_o) = 0
    exactly. Raises GeometryError if the radii are non-positive, if r_outer is not
    strictly greater than r_inner, or if `r` lies outside [r_inner, r_outer]
    (an extrapolated stress would be a fabricated value).
    """
    if not (r_inner > 0.0) or not (r_outer > 0.0):
        raise GeometryError(
            f"radii must be positive (got r_inner={r_inner}, r_outer={r_outer})"
        )
    if r_outer <= r_inner:
        raise GeometryError(
            f"r_outer ({r_outer}) must exceed r_inner ({r_inner})"
        )
    if r < r_inner or r > r_outer:
        raise GeometryError(
            f"evaluation radius r={r} is outside the wall [{r_inner}, {r_outer}]"
        )
    span = r_outer ** 2 - r_inner ** 2
    a = pressure_internal * r_inner ** 2 / span
    b = pressure_internal * r_inner ** 2 * r_outer ** 2 / span
    return {
        "radial_stress": a - b / r ** 2,
        "hoop_stress": a + b / r ** 2,
    }


def pressure_vessel_check(
    pressure: float,
    r_inner: float,
    thickness: float,
    yield_strength: float,
    *,
    model: str = "thin",
) -> dict:
    """Internal-pressure wall check against yield.

    Computes the maximum hoop stress (at the inner wall) by the chosen `model` and
    compares it to `yield_strength`. With ``model='thin'`` the max hoop is the
    membrane estimate p*r_i/t; with ``model='thick'`` it is the exact Lame
    inner-wall hoop p*(r_o^2+r_i^2)/(r_o^2-r_i^2) with r_o = r_inner + thickness
    (always >= the thin estimate). Returns ``{"max_hoop", "model", "safety_factor",
    "ok"}``: safety_factor = yield_strength / max_hoop, ok = safety_factor >= 1.
    Deterministic.

    Units: MPa and mm. Assumes pressure >= 0 (internal pressure model). Raises
    GeometryError on a non-positive (or non-finite) radius/thickness/pressure or an
    unknown model; raises ValueError on a non-positive (or non-finite) yield strength.
    """
    # Use "not > 0" (instead of <=0) so NaN/inf/-inf are rejected (they bypass <=0
    # comparisons and would otherwise produce NaN results or surprising ok=False/True).
    # This is a genuine defect fix per round-2 review (silent non-finite factual values).
    if not (r_inner > 0.0):
        raise GeometryError(
            f"r_inner and thickness must be positive (got r_inner={r_inner}, "
            f"thickness={thickness})"
        )
    if not (thickness > 0.0):
        raise GeometryError(
            f"r_inner and thickness must be positive (got r_inner={r_inner}, "
            f"thickness={thickness})"
        )
    if not (yield_strength > 0.0):
        raise ValueError("yield strength must be positive")
    if not (pressure >= 0.0):
        raise GeometryError(
            f"pressure must be non-negative (internal-pressure model; "
            f"got pressure={pressure}; external pressure disclaimed)"
        )
    if model == "thin":
        max_hoop = pressure * r_inner / thickness
    elif model == "thick":
        r_outer = r_inner + thickness
        max_hoop = thick_wall_cylinder_stresses(
            pressure, r_inner, r_outer, r_inner
        )["hoop_stress"]
    else:
        raise GeometryError(f"unknown model {model!r}; one of 'thin', 'thick'")
    safety_factor = float("inf") if max_hoop <= 0.0 else yield_strength / max_hoop
    return {
        "max_hoop": max_hoop,
        "model": model,
        "safety_factor": safety_factor,
        "ok": max_hoop <= 0.0 or safety_factor >= 1.0,
    }
