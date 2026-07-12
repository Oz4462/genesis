"""Multi-robot stand/balance coverage in BalanceEnv (GOAL: env covers more than one real robot).

Pins the HONEST upright-seconds of each broadened robot in the same stand/balance env, so the env's
multi-robot claim is evidence-backed, not aspirational:

  * Berkeley Humanoid Lite — stands the full horizon (positive control; already covered, re-pinned here
    in the multi-robot context).
  * AGILOped (nimbro_new, repaired inertials, parallel-linkage shadow tree stripped) — DOES NOT stand:
    the nimbro_new lineage is mounted with splayed legs and a 44deg-rolled ankle_link whose sole is not
    flat, so it topples under gravity (measured). This is asserted as the honest current state (a known
    model-geometry blocker, not a harness bug — Berkeley/TienKung stand in the identical env), so a future
    fix that makes it stand will flip this test and be noticed.

Skip-guarded on PyBullet + each asset. AGILOped uses the parallel-stripped URDF if present (built by the
broadening work); if only the original repaired URDF exists the AGILOped test is skipped (its parallel
shadow tree makes the raw model even less stand-ready).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gen.humanoids import catalog
from gen.humanoids.insim import pybullet_available

pytestmark = pytest.mark.skipif(not pybullet_available(), reason="PyBullet not installed")

from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig  # noqa: E402
from gen.humanoids.balance_controller import BalanceController, run_controller  # noqa: E402

_AGILOPED_NOPAR = ("/home/genesis/humanoid_assets/agiloped/nimbro_op_model/robots/"
                   "nimbro_new_repaired_noparallel.urdf")


class _Zero(BalanceController):
    def act(self, obs, env):
        return np.zeros(env.action_dim)


def _present(robot: str) -> bool:
    ref = catalog.ASSETS.get(robot)
    return ref is not None and ref.model_path is not None and Path(ref.model_path).is_file()


@pytest.mark.skipif(not _present("berkeley_lite"), reason="berkeley_lite asset missing")
def test_berkeley_stands_full_horizon():
    """Berkeley holds the full 5 s in the multi-robot env (the positive control for broadening)."""
    r = run_controller("berkeley_lite", _Zero(), seconds=5.0)
    assert r.held_full_horizon is True
    assert r.upright_seconds == pytest.approx(5.0, abs=1e-6)
    assert r.max_lean_deg < 10.0


@pytest.mark.skipif(not Path(_AGILOPED_NOPAR).is_file(), reason="AGILOped parallel-stripped URDF missing")
def test_agiloped_noparallel_loads_with_clean_mass_but_does_not_stand():
    """AGILOped (parallel-stripped, inertials repaired) loads cleanly but topples — honest current state.

    The parallel shadow tree removed → 20 movable DOF, ~10.43 kg (the real declared inertial sum). It
    still does NOT stand: splayed legs + a 44deg-rolled ankle_link sole make flat foot contact impossible
    in the neutral pose, so it falls within ~1.5 s. Asserted as a measured blocker (Berkeley/TienKung
    stand in the SAME env, so this is the model, not the harness). A future pose/geometry fix flips this."""
    ankles = ("left_ankle_pitch", "left_ankle_roll", "right_ankle_pitch", "right_ankle_roll")
    cfg = BalanceEnvConfig(robot="agiloped", urdf_path=_AGILOPED_NOPAR, horizon_s=5.0,
                           standing_pose={}, controlled_joints=ankles)
    env = BalanceEnv(cfg)
    try:
        env.reset()
        # clean mass: floating-base total ~10.43 kg (parallel shadow removed)
        p, c, bid = env._p, env._client, env._bid
        total = p.getDynamicsInfo(bid, -1, physicsClientId=c)[0] + sum(
            p.getDynamicsInfo(bid, j, physicsClientId=c)[0] for j in range(p.getNumJoints(bid, physicsClientId=c)))
        assert 9.5 < total < 11.5
        done = False
        while not done:
            done = env.step(np.zeros(env.action_dim)).done
        # honest blocker: it falls (does not hold the horizon)
        assert env.upright_seconds < 4.0
        assert env.max_lean_deg >= env.cfg.fall_tilt_deg - 1e-6
    finally:
        env.close()
