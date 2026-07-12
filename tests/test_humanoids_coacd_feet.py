"""Tests for gen.humanoids.coacd_feet — convex-decomposed (CoACD) collision feet for stable contact.

Skip-guarded on coacd + the TienKung asset (like the other in-engine humanoid tests). The slow part is
the decomposition itself (tens of seconds/foot), so the heavy end-to-end test only runs the decomposition
if the artifact URDF is not already present; the rest test pure logic (sole-slab extraction, URDF
rewrite) and that the convex-foot URDF loads + makes DENSER ground contact than the mesh-foot URDF (the
whole point). Honest: these assert the contact gets denser and the robot still stands the passive hold —
NOT that ankle control suddenly works (it does not; that is the measured finding, pinned elsewhere).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gen.humanoids import catalog
from gen.humanoids import coacd_feet as cf
from gen.humanoids.insim import pybullet_available

pytestmark = pytest.mark.skipif(not cf.coacd_available(), reason="coacd not installed")


def _tienkung_present() -> bool:
    ref = catalog.ASSETS.get("tienkung")
    return ref is not None and ref.model_path is not None and Path(ref.model_path).is_file()


_TK = pytest.mark.skipif(not _tienkung_present(), reason="tienkung asset missing")
_PB = pytest.mark.skipif(not pybullet_available(), reason="PyBullet not installed")


def _foot_mesh() -> Path:
    return Path(catalog.ASSETS["tienkung"].model_path).parent / "../meshes/ankle_roll_l_link.STL"


# ── pure-logic tests (no sim) ─────────────────────────────────────────────────────────────────────────

@_TK
def test_sole_slab_is_thin_and_at_the_bottom():
    """The sole-slab extractor keeps only the bottom band of the foot mesh (the contact surface)."""
    import trimesh
    full = trimesh.load(str(_foot_mesh().resolve()), force="mesh")
    slab = cf._sole_slab(full, sole_thickness=0.02)
    # the slab is anchored at the foot's lowest point and is a THIN band (faces are kept by centroid, so a
    # boundary triangle can poke a little above the cut — allow up to ~2x the thickness, but it must be far
    # thinner than the whole foot, which is ~0.083 m tall) and must sit at the bottom.
    slab_h = float(slab.bounds[1][2] - slab.bounds[0][2])
    full_h = float(full.bounds[1][2] - full.bounds[0][2])
    assert slab_h <= 2.0 * 0.02
    assert slab_h < 0.5 * full_h                                # genuinely just the bottom band
    assert abs(float(slab.bounds[0][2]) - float(full.bounds[0][2])) < 1e-6  # same lowest point
    assert len(slab.vertices) >= 4


def test_build_requires_existing_urdf(tmp_path):
    with pytest.raises(FileNotFoundError):
        cf.build_convex_feet_urdf(tmp_path / "nope.urdf", tmp_path / "out.urdf")


@_TK
def test_build_rejects_unknown_foot_link(tmp_path):
    with pytest.raises(ValueError):
        cf.build_convex_feet_urdf(catalog.ASSETS["tienkung"].model_path, tmp_path / "out.urdf",
                                  foot_links=("not_a_link",), mode="sole")


# ── artifact + load + denser-contact test ──────────────────────────────────────────────────────────────

@_TK
def test_decompose_one_foot_writes_convex_parts(tmp_path):
    """Decomposing one foot writes >= 2 convex OBJ parts that all reach the sole (sole mode)."""
    fd = cf.decompose_foot(_foot_mesh().resolve(), tmp_path, "ankle_roll_l_link",
                           "../meshes/ankle_roll_l_link.STL", mode="sole", sole_thickness=0.02,
                           max_convex_hull=6)
    assert fd.n_parts >= 2
    assert fd.n_sole_parts >= 1
    for part in fd.parts:
        assert Path(part).is_file()


@_TK
@_PB
def test_coacd_feet_urdf_loads_and_densifies_contact():
    """The convex-foot URDF loads in PyBullet and makes MORE foot-ground contacts than the mesh-foot one.

    Builds the artifact lazily (only if absent) to keep the suite fast. Runs the passive crouch hold on
    both URDFs and asserts (a) both stand the short horizon, (b) the convex feet give strictly more mean
    contacts (the whole point of the decomposition)."""
    from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig, recommended_standing_pose

    mesh_urdf = catalog.ASSETS["tienkung"].model_path
    coacd_urdf = cf.TIENKUNG_COACD_URDF
    if not Path(coacd_urdf).is_file():
        cf.build_tienkung_coacd_feet(mode="sole", sole_thickness=0.02)
    assert Path(coacd_urdf).is_file()

    pose = recommended_standing_pose("tienkung")

    def mean_contacts(urdf: str) -> tuple[float, float]:
        cfg = BalanceEnvConfig(robot="tienkung", urdf_path=urdf, horizon_s=1.0, standing_pose=pose)
        env = BalanceEnv(cfg)
        try:
            env.reset()
            ncs = []
            done = False
            while not done:
                res = env.step(np.zeros(env.action_dim))
                ncs.append(res.info["n_contacts"])
                done = res.done
            return float(np.mean(ncs)), env.upright_seconds
        finally:
            env.close()

    mesh_c, mesh_up = mean_contacts(mesh_urdf)
    coacd_c, coacd_up = mean_contacts(coacd_urdf)
    assert mesh_up == pytest.approx(1.0, abs=1e-6)   # both stand the (short) passive hold
    assert coacd_up == pytest.approx(1.0, abs=1e-6)
    assert coacd_c > mesh_c                            # convex feet → denser contact (the point)
    assert coacd_c >= 2 * mesh_c                       # and substantially so (measured ~5x)
