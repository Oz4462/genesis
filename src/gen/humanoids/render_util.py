"""render_util — headless PNG renders of a humanoid in a PyBullet DIRECT client (visual verification).

The project rule is to VISUALLY verify a standing robot (alignment / overlap / cut-off / floor
penetration), not just trust numbers. The env runs headless (DIRECT), so this captures an offscreen RGB
image via PyBullet's TINY (CPU) renderer and writes a PNG with Pillow. It is a pure helper — it takes an
already-built :class:`gen.humanoids.balance_env.BalanceEnv` (which owns the client + robot) and shoots a
camera at the robot's current state. No new sim, no side effects on the env beyond reading state.

Optional dependency on Pillow (PNG write); raises fail-loud if it is missing rather than silently
skipping the visual check.
"""

from __future__ import annotations

from pathlib import Path


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def render_env_png(env, out_png: str | Path, *, width: int = 640, height: int = 480,
                   distance: float = 2.2, yaw: float = 50.0, pitch: float = -15.0,
                   target_z: float = 0.6) -> str:
    """Render the current state of ``env``'s robot to ``out_png`` (PNG). Returns the absolute path.

    Aims the camera at ``(robot_x, robot_y, target_z)`` from ``distance`` m at the given yaw/pitch. Uses
    the env's existing DIRECT client + body, so call it after :meth:`BalanceEnv.reset`/``step`` to capture
    that pose. Raises if Pillow is unavailable (fail-loud — the visual check is mandatory, not optional)."""
    if not pillow_available():
        raise RuntimeError("Pillow is not installed — cannot write a render PNG for visual verification")
    import numpy as np
    from PIL import Image

    p, c, bid = env._p, env._client, env._bid
    bp = p.getBasePositionAndOrientation(bid, physicsClientId=c)[0]
    view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=[bp[0], bp[1], target_z], distance=distance,
        yaw=yaw, pitch=pitch, roll=0, upAxisIndex=2)
    proj = p.computeProjectionMatrixFOV(fov=55.0, aspect=width / height, nearVal=0.05, farVal=10.0)
    w, h, rgb, _, _ = p.getCameraImage(width, height, viewMatrix=view, projectionMatrix=proj,
                                       renderer=p.ER_TINY_RENDERER, physicsClientId=c)
    arr = np.reshape(np.asarray(rgb, dtype=np.uint8), (h, w, 4))[:, :, :3]
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(str(out_png))
    return str(out_png)


def render_robot_pose_png(robot: str, out_png: str | Path, *, urdf_path: str | None = None,
                          standing_pose: dict | None = None, settle_seconds: float = 0.0,
                          **render_kwargs) -> str:
    """Convenience: build a :class:`BalanceEnv` for ``robot``, reset (optionally settle), render a PNG.

    ``settle_seconds`` > 0 steps the passive hold that long before the shot (so the render shows the
    robot AFTER it has settled onto its feet, not at the instant of placement). Closes the env after."""
    from gen.humanoids.balance_env import BalanceEnv, BalanceEnvConfig, recommended_standing_pose
    import numpy as np

    pose = standing_pose if standing_pose is not None else recommended_standing_pose(robot)
    cfg = BalanceEnvConfig(robot=robot, urdf_path=urdf_path, standing_pose=pose,
                           horizon_s=max(0.2, settle_seconds + 0.1))
    env = BalanceEnv(cfg)
    try:
        env.reset()
        n = int(round(settle_seconds / cfg.control_dt))
        for _ in range(n):
            env.step(np.zeros(env.action_dim))
        return render_env_png(env, out_png, **render_kwargs)
    finally:
        env.close()
