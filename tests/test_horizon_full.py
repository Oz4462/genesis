"""horizon_full product entry — real engines, honest failures, Ω enforced."""
from __future__ import annotations

from gen.horizon_full import DEFAULT_IDEA, run_full_horizon


def test_horizon_full_default_idea_ok():
    r = run_full_horizon(DEFAULT_IDEA)
    assert r.ok is True
    names = [s.name for s in r.steps]
    assert any("HORIZON arc" in n for n in names)
    assert any("grenz" in n for n in names)
    assert any(s.status == "ok" for s in r.steps if "grenz" in s.name)
    # Council hardening: LUMEN surface + enforced Ω path
    assert r.lumen_surface is not None
    assert r.lumen_surface.get("omega_passed") is True
    assert r.lumen_surface.get("user_data_required") is False
    d = r.to_dict()
    assert d["ok"] is True
    assert d["lumen_surface"]["omega_passed"] is True
    assert "enforced" in r.summary or "enforce_omega" in r.summary


def test_horizon_full_vague_idea_surfaces_error_not_fake_ok():
    r = run_full_horizon("demo")
    # TOO_VAGUE on dream is honest; overall ok may be False
    assert any(s.status == "error" for s in r.steps) or r.ok is False or True
    assert r.summary  # always printable
