"""Characterization: fem3d_quadratic T10 10-node tet is a genuine linear-strain element, not a stub.

The module supplies a quadratic 10-node tetrahedron (T10) whose shape functions are
quadratic, producing LINEAR strain variation inside the element (vs constant-strain T4).
This characterization proves the element-level math is real computation on a SINGLE
hand-built T10 with explicit corner + edge-midpoint coordinates — no gmsh required for
the core claims.

Exercised (gmsh-FREE):
- _shape_grads, _b_matrix: strain-displacement at natural Gauss points
- t10_stiffness: 30x30 integrated via 4-pt Gauss + shared D matrix
- t10_nodal_stresses: stress sampled at the 10 nodal locations (corners+edges)
- t10_mass, _t10_mass_reference: exact analytic consistent mass (no quadrature)

A facade/stub would return fixed numbers independent of coords/E/nu/rho or would fail the
exact patch recovery for arbitrary constant strain.

gmsh is used ONLY for optional cross-checks (box_mesh_t10/_t10_from_gmsh) and is guarded
by pytest.importorskip — the main test body is pure numpy + explicit coords.

Offline, numpy + hypothesis. Deterministic.

Run:  pytest tests/test_fem3d_quadratic_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.fem3d import _elasticity_matrix  # noqa: E402  (pre-existing; shared)
from gen.fem3d_quadratic import (  # noqa: E402
    _EDGES,
    _GAUSS,
    _NODE_NAT,
    _b_matrix,
    _shape_grads,
    _t10_mass_reference,
    box_mesh_t10,
    t10_mass,
    t10_nodal_stresses,
    t10_stiffness,
)

E = 210000.0
NU = 0.3
RHO = 7850.0


def _explicit_single_t10() -> np.ndarray:
    """Hand-built T10 element with explicit corner coords + explicit edge midpoints.

    Corners: [ (2,0,0), (0,3,0), (0,0,4), (0,0,0) ]
    Mids computed as arithmetic means (the definition of straight-edge T10).
    Local ordering matches the module: 4 corners, then _EDGES order.
    """
    corners = np.array([
        [2.0, 0.0, 0.0],
        [0.0, 3.0, 0.0],
        [0.0, 0.0, 4.0],
        [0.0, 0.0, 0.0],
    ], dtype=float)
    mids = np.array(
        [(corners[a] + corners[b]) / 2.0 for a, b in _EDGES], dtype=float
    )
    return np.vstack([corners, mids])


def _tet_volume(corners4: np.ndarray) -> float:
    """Signed volume / abs from 4x4 det (standard tet volume formula)."""
    m = np.ones((4, 4))
    m[:, 1:] = corners4
    return abs(np.linalg.det(m)) / 6.0


# --- element fundamentals (gmsh-free) -----------------------------------------

def test_shape_grads_returns_10x3_at_natural_points():
    g = _shape_grads(0.25, 0.25, 0.25)
    assert g.shape == (10, 3)
    # not all zero (real derivatives)
    assert np.any(np.abs(g) > 1e-12)


def test_b_matrix_and_patch_test_recover_exact_constant_strain():
    """Linear displacement field (constant strain) must recover EXACTLY via B@u.

    This is the linear patch test. A stub or wrong B would not match arbitrary
    imposed strain to 1e-12. Uses explicit hand-built coords.
    """
    coords = _explicit_single_t10()
    # arbitrary constant strain via grad G; strain = sym(G)
    g = np.array([
        [0.010, 0.002, -0.001],
        [0.000, -0.003, 0.004],
        [0.005, 0.000, 0.006],
    ])
    u = (coords @ g.T).ravel()
    exx, eyy, ezz = g[0, 0], g[1, 1], g[2, 2]
    exy = g[0, 1] + g[1, 0]
    eyz = g[1, 2] + g[2, 1]
    ezx = g[2, 0] + g[0, 2]
    expected = np.array([exx, eyy, ezz, exy, eyz, ezx])

    for gp in _GAUSS:
        b, detj = _b_matrix(coords, gp)
        recovered = b @ u
        assert np.allclose(recovered, expected, atol=1e-12)
        assert detj > 0.0


def test_t10_nodal_stresses_uniform_and_exact_for_constant_strain():
    """For constant strain, stress sampled at all 10 nodes (via t10_nodal_stresses)
    must be identical and equal to D @ epsilon. Proves nodal recovery path is live.
    """
    coords = _explicit_single_t10()
    g = np.array([
        [0.010, 0.002, -0.001],
        [0.000, -0.003, 0.004],
        [0.005, 0.000, 0.006],
    ])
    u = (coords @ g.T).ravel()
    nodes = coords
    tets = np.array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]], dtype=int)
    d = _elasticity_matrix(E, NU)
    expected_strain = np.array([
        g[0, 0], g[1, 1], g[2, 2],
        g[0, 1] + g[1, 0], g[1, 2] + g[2, 1], g[2, 0] + g[0, 2],
    ])
    expected_stress = d @ expected_strain

    sn = t10_nodal_stresses(nodes, tets, u, E, NU)
    assert sn.shape == (1, 10, 6)
    for i in range(10):
        assert np.allclose(sn[0, i], expected_stress, atol=1e-10)


def test_t10_stiffness_symmetric_scales_with_E_and_with_geometry():
    """Stiffness is assembled from real B/D integration: symmetric, linear in E,
    and for affine scaling s of geometry, scales ~s (B~1/s, detJ~s^3 => net s).
    Changing E or size must change the matrix — input is consumed.
    """
    coords = _explicit_single_t10()
    ke = t10_stiffness(coords, E, NU)
    assert ke.shape == (30, 30)
    assert np.allclose(ke, ke.T, atol=1e-9)

    # E scaling
    ke2 = t10_stiffness(coords, 2 * E, NU)
    assert np.allclose(ke2, 2 * ke, rtol=1e-9)

    # geometry scaling (linear dims *2 -> vol*8, B/2, integral factor 2)
    coords2 = coords * 2.0
    ke_big = t10_stiffness(coords2, E, NU)
    assert np.allclose(ke_big, 2 * ke, rtol=1e-9)

    # prove sensitivity: different nu produces different ke (not constant)
    ke_nu = t10_stiffness(coords, E, 0.25)
    assert not np.allclose(ke, ke_nu, rtol=1e-3)


def test_t10_mass_and_reference_exact_sum_and_rhoV():
    """_t10_mass_reference is the exact barycentric integral (sums to 1).
    t10_mass = rho*V * kron(C, I3) and totals rho*V per axis on real vol.
    """
    cref = _t10_mass_reference()
    assert cref.shape == (10, 10)
    assert np.isclose(cref.sum(), 1.0, rtol=1e-12)

    coords = _explicit_single_t10()
    vol = _tet_volume(coords[:4])
    m = t10_mass(coords, RHO)
    assert m.shape == (30, 30)
    assert np.allclose(m, m.T, atol=1e-9)

    total_x = m[0::3, 0::3].sum()
    assert np.isclose(total_x, RHO * vol, rtol=1e-12)

    # density scaling
    m2 = t10_mass(coords, 2 * RHO)
    assert np.allclose(m2, 2 * m, rtol=1e-9)


# --- property-based: invariants must hold for many inputs ----------------------

@settings(max_examples=25, deadline=None)
@given(
    exx=st.floats(-0.02, 0.02),
    eyy=st.floats(-0.02, 0.02),
    ezz=st.floats(-0.02, 0.02),
    gxy=st.floats(-0.01, 0.01),
    gyz=st.floats(-0.01, 0.01),
    gzx=st.floats(-0.01, 0.01),
)
def test_property_patch_recovers_arbitrary_constant_strain(exx, eyy, ezz, gxy, gyz, gzx):
    """For ANY small constant strain (6 components), the B operator on linear u-field
    recovers it to machine precision at all Gauss points. This is the defining
    property of a complete linear-strain element.
    """
    coords = _explicit_single_t10()
    # construct compatible grad G such that sym parts match the strain voigt
    # simple: put shears on off-diag /2
    g = np.array([
        [exx, gxy / 2, gzx / 2],
        [gxy / 2, eyy, gyz / 2],
        [gzx / 2, gyz / 2, ezz],
    ])
    u = (coords @ g.T).ravel()
    expected = np.array([exx, eyy, ezz, gxy, gyz, gzx])
    for gp in _GAUSS:
        b, _ = _b_matrix(coords, gp)
        assert np.allclose(b @ u, expected, atol=1e-11)


@settings(max_examples=15, deadline=None)
@given(scale=st.floats(0.1, 4.0))
def test_property_stiffness_linear_in_E(scale):
    """K(E) must be exactly scale * K(1) — linear elasticity, no higher powers."""
    coords = _explicit_single_t10()
    k1 = t10_stiffness(coords, E, NU)
    ks = t10_stiffness(coords, scale * E, NU)
    assert np.allclose(ks, scale * k1, rtol=1e-9, atol=1e-9)


# --- negative / fail-loud (documented or natural numeric loud failure) --------

def test_degenerate_zero_volume_raises_loud_on_singular_jacobian():
    """A flat (zero-volume) tet has singular J; the code must fail loudly (LinAlgError)
    instead of producing a silent NaN/zero stiffness or wrong mass. This is L4 edge.
    """
    # degenerate: all points in one plane (c3 coincides with c0 -> vol=0)
    corners = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0],  # collapses volume
    ], dtype=float)
    mids = np.array(
        [(corners[a] + corners[b]) / 2.0 for a, b in _EDGES], dtype=float
    )
    coords = np.vstack([corners, mids])
    with pytest.raises(np.linalg.LinAlgError):
        _b_matrix(coords, _GAUSS[0])
    with pytest.raises(np.linalg.LinAlgError):
        t10_stiffness(coords, E, NU)


def test_box_mesh_cross_check_path_is_guarded_and_optional():
    """Any use of box_mesh_t10 / gmsh path must be import-skipped so test stays
    green without gmsh. This exercises the 'guard ONLY cross-check' rule.
    The call here is a minimal existence probe (not a numeric claim).
    """
    pytest.importorskip("gmsh", reason="gmsh optional; only for cross-checks")
    # cheap probe: small box produces nodes+tets (actual numeric cross in legacy)
    nodes, tets = box_mesh_t10(2.0, 2.0, 2.0, 2.0)
    assert nodes.shape[1] == 3
    assert tets.shape[1] == 10
    assert len(tets) >= 1


def test_geometry_error_on_absent_gmsh_is_loud_and_documented():
    """_require_gmsh (reached via box_mesh_t10) raises the documented GeometryError
    when the gmsh import fails. This exercises the real except branch (patch.dict
    forces ImportError on the runtime `import gmsh` inside _require_gmsh).
    """
    from unittest import mock
    with mock.patch.dict("sys.modules", {"gmsh": None}):
        with pytest.raises(GeometryError) as excinfo:
            box_mesh_t10(1.0, 1.0, 1.0, 0.5)
        msg = str(excinfo.value).lower()
        assert "gmsh" in msg or "optional" in msg
