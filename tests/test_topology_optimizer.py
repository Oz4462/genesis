"""Tests for the SIMP topology optimizer (topology_optimizer.py).

Pins the honesty contract and the classic-benchmark behaviour on the cantilever:
material concentrates along the load paths (flange/strut pattern), the measured
compliance gain is real under TWO independent evaluations (SIMP model start→final
AND fresh re-solve of the thresholded binary design vs the Voigt uniform
baseline), the volume constraint is never violated, the sensitivity filter
measurably reduces checkerboarding, budget 0 is honestly "nicht_optimiert", and
invalid inputs fail loud (fem3d's shared step-7d guards). Offline, deterministic.

Acceptance floors are set BELOW values measured at design time on this exact
mesh (24x8x1, vf=0.4): improvement_factor 2.89, binary-vs-Voigt 1.11, outer-row
density 0.95 vs middle 0.19, checkerboard 0.150 (filter) vs 0.316 (none) — the
factors are measurements, not guesses.
"""

import numpy as np
import pytest

from gen.fem3d import structured_box_mesh
from gen.topology_optimizer import (
    DEFAULT_FILTER_RADIUS_CELLS,
    VOLUME_CONSTRAINT_TOL,
    TopologyProposal,
    cantilever_tip_load_bcs,
    checkerboard_index,
    simp_optimize,
    threshold_resolve,
)

# the canonical cantilever benchmark: coarse (fast) but fine enough for the pattern
LX, LY, LZ = 60.0, 20.0, 2.5
NX, NY, NZ = 24, 8, 1
E, NU, F, VF = 2000.0, 0.35, 50.0, 0.4


def _bcs():
    nodes, _ = structured_box_mesh(LX, LY, LZ, NX, NY, NZ)
    return cantilever_tip_load_bcs(nodes, LX, F)


@pytest.fixture(scope="module")
def proposal() -> TopologyProposal:
    fixed, loads = _bcs()
    return simp_optimize(
        lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
        volume_fraction=VF, fixed_dofs=fixed, loads=loads, max_iterations=60,
    )


# --- acceptance: the classic benchmark behaves like the classic benchmark ------------------------

def test_material_concentrates_along_the_load_paths(proposal):
    # Cantilever, tip load: bending is carried by the outer fibres near the
    # support — the optimizer must put material there (flanges), not midplane.
    d = proposal.densities[:, :, 0]
    half = NX // 2
    outer = float(np.concatenate([d[:half, 0], d[:half, -1]]).mean())
    middle = float(d[:half, NY // 2 - 1 : NY // 2 + 1].mean())
    assert outer > 0.8            # measured 0.95: near-solid flanges
    assert outer > 2.0 * middle   # measured 0.95 vs 0.19: clear flange/web split


def test_compliance_gain_is_measured_within_the_simp_model(proposal):
    # First proof: uniform start vs final field, both under the SAME SIMP
    # interpolation and volume — measured 2.89x at design time.
    assert proposal.converged
    assert proposal.compliance < proposal.compliance_start
    assert proposal.improvement_factor > 2.0
    assert proposal.improvement_factor == pytest.approx(
        proposal.compliance_start / proposal.compliance
    )


def test_threshold_resolve_confirms_the_gain_independently(proposal):
    # Second proof: the field thresholded to a BINARY equal-volume design and
    # re-solved fresh (no rho^p interpolation) must beat the uniform baseline
    # even under the baseline's most favourable (Voigt, rho*E0) evaluation —
    # measured 1.11x at design time.
    fixed, loads = _bcs()
    check = threshold_resolve(
        densities=proposal.densities, lx=LX, ly=LY, lz=LZ, e_modulus=E, nu=NU,
        volume_fraction=VF, fixed_dofs=fixed, loads=loads,
    )
    assert check.passed
    assert check.compliance_binary < check.compliance_uniform
    assert check.improvement_factor > 1.05
    assert check.kept_fraction == pytest.approx(VF, abs=1.0 / (NX * NY * NZ))


def test_verdict_is_an_unverified_proposal_naming_the_delta_path(proposal):
    # Honesty contract: a density field is a PROPOSAL, never a certified part.
    assert proposal.verdict == "vorschlag_unverifiziert"
    assert "threshold_resolve" in proposal.delta_path
    assert "printability" in proposal.delta_path


def test_volume_constraint_is_never_violated(proposal):
    # Audit trail: after EVERY OC update the mean density sits on the target.
    assert proposal.volume_history                    # non-empty: iterations ran
    for vol in proposal.volume_history:
        assert abs(vol - VF) <= VOLUME_CONSTRAINT_TOL
    assert proposal.achieved_volume_fraction == pytest.approx(VF, abs=VOLUME_CONSTRAINT_TOL)
    assert float(proposal.densities.min()) >= 0.0
    assert float(proposal.densities.max()) <= 1.0


# --- filter: checkerboarding measurably reduced ---------------------------------------------------

def test_sensitivity_filter_reduces_checkerboarding():
    # radius 1.0 keeps only the self-weight (filter effectively off); the
    # default 1.5 couples face neighbours. Measured 0.150 vs 0.316 at design time.
    nodes, _ = structured_box_mesh(40.0, 15.0, 2.5, 16, 6, 1)
    fixed, loads = cantilever_tip_load_bcs(nodes, 40.0, F)
    common = dict(
        lx=40.0, ly=15.0, lz=2.5, nx=16, ny=6, nz=1, e_modulus=E, nu=NU,
        volume_fraction=VF, fixed_dofs=fixed, loads=loads, max_iterations=30,
    )
    with_filter = simp_optimize(**common, filter_radius_cells=DEFAULT_FILTER_RADIUS_CELLS)
    without = simp_optimize(**common, filter_radius_cells=1.0)
    assert checkerboard_index(with_filter.densities) < 0.8 * checkerboard_index(without.densities)


def test_checkerboard_index_rejects_bad_fields():
    with pytest.raises(ValueError):
        checkerboard_index(np.ones((4, 4)))           # not 3-D
    with pytest.raises(ValueError):
        checkerboard_index(np.full((2, 2, 1), np.nan))


# --- determinism ----------------------------------------------------------------------------------

def test_is_deterministic_bitwise():
    nodes, _ = structured_box_mesh(30.0, 10.0, 2.5, 12, 4, 1)
    fixed, loads = cantilever_tip_load_bcs(nodes, 30.0, F)
    kw = dict(
        lx=30.0, ly=10.0, lz=2.5, nx=12, ny=4, nz=1, e_modulus=E, nu=NU,
        volume_fraction=VF, fixed_dofs=fixed, loads=loads, max_iterations=15,
    )
    a, b = simp_optimize(**kw), simp_optimize(**kw)
    assert np.array_equal(a.densities, b.densities)
    assert a.compliance == b.compliance
    assert a.compliance_history == b.compliance_history


# --- negative tests (fail loud, honest zero-budget) ------------------------------------------------

def test_zero_iterations_is_honestly_not_optimized():
    fixed, loads = _bcs()
    p = simp_optimize(
        lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
        volume_fraction=VF, fixed_dofs=fixed, loads=loads, max_iterations=0,
    )
    assert p.verdict == "nicht_optimiert"
    assert not p.converged
    assert p.iterations == 0
    assert p.improvement_factor == 1.0                # nothing ran, nothing claimed
    assert np.all(p.densities == VF)                  # field is the uniform start


def test_nan_load_raises_value_error():
    # inherited from fem3d's shared step-7d guard: NaN never propagates silently
    fixed, loads = _bcs()
    loads[next(iter(loads))] = float("nan")
    with pytest.raises(ValueError):
        simp_optimize(
            lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
            volume_fraction=VF, fixed_dofs=fixed, loads=loads,
        )


def test_invalid_volume_fraction_raises():
    fixed, loads = _bcs()
    for bad in (0.0, 1.0, -0.2, float("nan")):
        with pytest.raises(ValueError):
            simp_optimize(
                lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
                volume_fraction=bad, fixed_dofs=fixed, loads=loads,
            )


def test_nonzero_prescribed_displacement_raises():
    # compliance minimisation is defined for homogeneous Dirichlet only — a
    # silent reinterpretation of the objective would be a lie, so: fail loud.
    fixed, loads = _bcs()
    fixed[next(iter(fixed))] = 0.5
    with pytest.raises(ValueError):
        simp_optimize(
            lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
            volume_fraction=VF, fixed_dofs=fixed, loads=loads, max_iterations=1,
        )


def test_empty_loads_raise():
    fixed, _ = _bcs()
    with pytest.raises(ValueError):
        simp_optimize(
            lx=LX, ly=LY, lz=LZ, nx=NX, ny=NY, nz=NZ, e_modulus=E, nu=NU,
            volume_fraction=VF, fixed_dofs=fixed, loads={},
        )


def test_threshold_resolve_rejects_bad_inputs(proposal):
    fixed, loads = _bcs()
    with pytest.raises(ValueError):
        threshold_resolve(
            densities=proposal.densities[:, :, 0],    # not 3-D
            lx=LX, ly=LY, lz=LZ, e_modulus=E, nu=NU,
            volume_fraction=VF, fixed_dofs=fixed, loads=loads,
        )
    with pytest.raises(ValueError):
        threshold_resolve(
            densities=proposal.densities, lx=LX, ly=LY, lz=LZ, e_modulus=E, nu=NU,
            volume_fraction=float("nan"), fixed_dofs=fixed, loads=loads,
        )
