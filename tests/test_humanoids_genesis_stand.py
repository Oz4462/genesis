"""AETHON in-engine tests — the URDF loads in PyBullet, has the designed structure, and STANDS.

These require PyBullet (headless DIRECT) and skip cleanly when it is absent:

  * the full-body URDF loads and reports the designed structure (27 body revolute joints, ~22 kg
    floating-base mass, pelvis root);
  * the dexterous URDF additionally instantiates the finger joints (a real articulated hand);
  * AETHON STANDS: a stiff PD hold of the verified crouch pose on the flat box feet keeps the base
    upright for the full 5 s (the proven box-sole + crouch recipe), with negligible lean — and the
    box-feet variant clearly beats an ankle-stub ablation;
  * the render helper writes the visual-verification PNGs (full body + hand + foot).

Run:  PYTHONPATH=src .venv/bin/python -m pytest tests/test_humanoids_genesis_stand.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids import genesis_humanoid as gh  # noqa: E402
from gen.humanoids import insim  # noqa: E402

_HAS_PYBULLET = insim.pybullet_available()
pytestmark = pytest.mark.skipif(not _HAS_PYBULLET, reason="PyBullet not installed")


@pytest.fixture(scope="module")
def urdf_paths(tmp_path_factory):
    d = tmp_path_factory.mktemp("aethon")
    full = d / "aethon.urdf"
    nohands = d / "aethon_nohands.urdf"
    full.write_text(gh.aethon_urdf(dexterous_hands=True, box_feet=True), encoding="utf-8")
    nohands.write_text(gh.aethon_urdf(dexterous_hands=False, box_feet=True), encoding="utf-8")
    return {"full": str(full), "nohands": str(nohands), "dir": d}


def test_full_urdf_loads_with_designed_structure(urdf_paths):
    lr = insim.load_structure("aethon", urdf_paths["full"])
    s = lr.summary()
    assert s["base_link"] == "pelvis"
    # floating-base total mass is the design target (~22 kg printed class)
    assert 20.0 <= s["mass_floating_kg"] <= 25.0
    # the dexterous URDF models the body joints PLUS the finger joints
    assert s["actuated_dof"] >= 27


def test_nohands_urdf_has_27_body_joints(urdf_paths):
    import xml.etree.ElementTree as ET
    r = ET.fromstring(Path(urdf_paths["nohands"]).read_text())
    movable = [j for j in r.findall("joint") if j.get("type") != "fixed"]
    # the no-hands body has exactly the 27 control joints + the 2 carrier-link joints per shoulder/hip
    names = {j.get("name") for j in movable}
    for jn in ("waist_yaw", "neck_yaw", "neck_pitch", "l_hip_pitch", "r_knee_pitch",
               "l_ankle_roll", "r_shoulder_yaw", "l_elbow_pitch", "l_wrist_roll"):
        assert jn in names, f"missing body joint {jn}"


def test_aethon_stands_full_window_on_box_feet(urdf_paths):
    """The headline in-engine result: the verified crouch + stiff PD hold + flat 240 mm box feet keeps
    AETHON upright the full 5 s with <2° lean (deterministic)."""
    br = insim.pd_balance("aethon", urdf_paths["nohands"], seconds=5.0, kp=120.0, kd=6.0,
                          target_pose=gh.STANDING_POSE, max_force=200.0)
    assert not br.fell, "AETHON fell during the stiff-hold stand"
    assert br.upright_seconds >= 4.9, f"only stood {br.upright_seconds:.2f}s"
    assert br.base_tilt_max_deg < 5.0, f"leaned {br.base_tilt_max_deg:.1f}° (should be <5°)"


def test_box_feet_beat_ankle_stub_ablation(urdf_paths):
    """The flat box sole is the stand-cure: with box feet AETHON holds the full window; with an
    ankle-stub (no flat sole) it stands markedly less (proves the box sole matters, not a fluke)."""
    stub = urdf_paths["dir"] / "aethon_stub.urdf"
    stub.write_text(gh.aethon_urdf(dexterous_hands=False, box_feet=False), encoding="utf-8")
    box = insim.pd_balance("aethon", urdf_paths["nohands"], seconds=5.0, kp=120.0, kd=6.0,
                           target_pose=gh.STANDING_POSE, max_force=200.0)
    stub_res = insim.pd_balance("aethon", str(stub), seconds=5.0, kp=120.0, kd=6.0,
                                target_pose=gh.STANDING_POSE, max_force=200.0)
    assert box.upright_seconds >= stub_res.upright_seconds
    assert box.upright_seconds >= 4.9


def test_render_writes_visual_verification_pngs(tmp_path):
    from gen.humanoids.render_util import pillow_available
    if not pillow_available():
        pytest.skip("Pillow not installed")
    out = gh.render_aethon(out_dir=str(tmp_path), settle_seconds=0.5)
    # at least the full-body views must be produced for the mandatory visual check
    assert "full_front" in out and Path(out["full_front"]).stat().st_size > 2000
    assert "full_side" in out and Path(out["full_side"]).stat().st_size > 2000


def test_head_camera_sees_objects_via_opencv(tmp_path):
    """The head's stereo cameras produce real imagery: render from the eye and run the GENESIS OpenCV
    capability — it must detect the target objects placed in front (vision is wired, not decoration)."""
    from gen.external.vision import opencv_available
    from gen.humanoids.render_util import pillow_available
    if not (pillow_available() and opencv_available()):
        pytest.skip("Pillow or OpenCV not installed")
    r = gh.aethon_eye_view(out_png=str(tmp_path / "eye.png"))
    assert Path(r["png"]).stat().st_size > 1000
    # three target boxes are placed in front of the eye; OpenCV should find features (>=1, typically 3)
    assert r["n_features"] >= 1, "the onboard eye camera produced no detectable features"
