"""mechanics_formulas — the canonical, single-source-of-truth rigid-body formulas.

WHY this module exists: the same elementary formula, inlined as a magic expression in several
places, drifts. Two real cross-model review findings were the SAME mistake — a uniform rod's moment
of inertia taken about the WRONG axis: ``m·L²/3`` (about the end) written where ``m·L²/12`` (about the
centre of mass) was meant, and vice-versa. Both are dimensionally identical (a dimensionless
coefficient differs), so a units check cannot catch them; only a single, named, anchor-tested
definition can. Every caller that needs a rod inertia now calls the function whose NAME states the
axis, so the axis can no longer be confused, and the coefficient lives in exactly one tested place.

Closed-form, deterministic, stdlib only. Each function raises ValueError on non-physical input
(negative mass/length) and is pinned to its textbook value in tests/test_mechanics_formulas.py.

Sources: any classical-mechanics text (e.g. Goldstein; Hibbeler, *Engineering Mechanics: Dynamics*).
The uniform thin rod of mass m and length L, about a transverse axis: I_centre = m·L²/12,
I_end = m·L²/3; the two are linked by the parallel-axis theorem with d = L/2:
I_end = I_centre + m·(L/2)² = m·L²/12 + m·L²/4 = m·L²/3.
"""

from __future__ import annotations


def rod_inertia_about_center(mass: float, length: float) -> float:
    """Moment of inertia of a UNIFORM THIN ROD about a transverse axis through its CENTRE OF MASS:
    I = m·L²/12.

    This is the value a URDF/SDF ``<inertial>`` tensor needs, because that tensor is expressed about
    the link's COM. A physics engine then re-applies the parallel-axis shift to the joint itself.
    Raises ValueError on negative mass or length."""
    if mass < 0.0 or length < 0.0:
        raise ValueError("mass and length must be non-negative")
    return mass * length * length / 12.0


def rod_inertia_about_end(mass: float, length: float) -> float:
    """Moment of inertia of a UNIFORM THIN ROD about a transverse axis through ONE END: I = m·L²/3.

    This is the value a pendulum/swing SCREEN needs when the rod rotates about its proximal joint
    (e.g. a leg swinging about the hip). It already includes the parallel-axis shift from the COM.
    Raises ValueError on negative mass or length."""
    if mass < 0.0 or length < 0.0:
        raise ValueError("mass and length must be non-negative")
    return mass * length * length / 3.0


def parallel_axis_inertia(inertia_com: float, mass: float, distance: float) -> float:
    """Parallel-axis (Steiner) theorem: the inertia about an axis parallel to one through the COM,
    offset by ``distance`` d, is I = I_com + m·d².

    The bridge between the two rod formulas above: ``rod_inertia_about_end(m, L)`` equals
    ``parallel_axis_inertia(rod_inertia_about_center(m, L), m, L/2)``. Raises ValueError on negative
    inertia or mass (distance may be any sign; only d² enters)."""
    if inertia_com < 0.0 or mass < 0.0:
        raise ValueError("inertia_com and mass must be non-negative")
    return inertia_com + mass * distance * distance


def point_mass_inertia(mass: float, radius: float) -> float:
    """Moment of inertia of a POINT MASS at orbital radius r about the axis: I = m·r². Raises
    ValueError on negative mass or radius."""
    if mass < 0.0 or radius < 0.0:
        raise ValueError("mass and radius must be non-negative")
    return mass * radius * radius


def solid_cylinder_inertia_axial(mass: float, radius: float) -> float:
    """Moment of inertia of a SOLID CYLINDER about its own symmetry (spin) axis: I = ½·m·r². Raises
    ValueError on negative mass or radius."""
    if mass < 0.0 or radius < 0.0:
        raise ValueError("mass and radius must be non-negative")
    return 0.5 * mass * radius * radius
