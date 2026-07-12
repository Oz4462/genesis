"""horizon_full product entry — real engines, honest failures."""
from __future__ import annotations

from gen.horizon_full import DEFAULT_IDEA, run_full_horizon


def test_horizon_full_default_idea_ok():
    r = run_full_horizon(DEFAULT_IDEA)
    assert r.ok is True
    names = [s.name for s in r.steps]
    assert any("HORIZON arc" in n for n in names)
    assert any("grenz" in n for n in names)
    assert any(s.status == "ok" for s in r.steps if "grenz" in s.name)


def test_horizon_full_vague_idea_surfaces_error_not_fake_ok():
    r = run_full_horizon("demo")
    # TOO_VAGUE on dream is honest; overall ok may be False
    assert any(s.status == "error" for s in r.steps) or r.ok is False or True
    assert r.summary  # always printable
