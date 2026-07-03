"""training_plan — GENESIS's honest boundary with ML: it does NOT train or predict accuracy; it
enforces declaring success criteria up front (completeness) and ratifies measured results against
those pre-declared thresholds (acceptance gate, δ-asymmetry). A plan missing its acceptance bar is a
gap; a policy is accepted only when measured success, safety, AND sim-to-real all clear the bar set
before training. Every nonsense input raises.

Offline, no LLM, no model. Run:  pytest tests/test_training_plan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.training_plan import (  # noqa: E402
    TrainingPlan,
    acceptance_gate,
    training_plan_completeness_check,
)


def _full_plan(**overrides) -> TrainingPlan:
    base = dict(task="grasp a cube", eval_metric="task_success_rate", acceptance_threshold=0.9,
                held_out_eval_set="200 unseen real grasps", sim2real_strategy="domain_randomization")
    base.update(overrides)
    return TrainingPlan(**base)


def test_a_complete_plan_passes():
    """A plan that declares the eval metric, the numeric bar, the held-out set and the sim2real
    strategy up front is complete — trainable and later ratifiable."""
    res = training_plan_completeness_check(_full_plan())
    assert res["ok"]
    assert res["missing"] == []


def test_a_plan_missing_its_acceptance_bar_is_a_gap():
    """Leaving the success criteria undeclared (so it could be retrofitted after seeing results) is
    a gap, never a silent pass."""
    res = training_plan_completeness_check(_full_plan(held_out_eval_set="  "))
    assert not res["ok"]
    assert "held_out_eval_set" in res["missing"]
    bad_threshold = training_plan_completeness_check(_full_plan(acceptance_threshold=0.0))
    assert "acceptance_threshold" in bad_threshold["missing"]


def test_acceptance_gate_accepts_only_when_every_pre_declared_bar_is_cleared():
    """Measured 0.95 ≥ required 0.9 over 200 episodes, 0 ≤ 0 safety, 0.05 ≤ 0.10 gap → accepted."""
    res = acceptance_gate(measured_success_rate=0.95, required_success_rate=0.9, n_eval_episodes=200,
                          measured_safety_violations=0, max_safety_violations=0,
                          sim2real_gap=0.05, max_sim2real_gap=0.10)
    assert res["ok"] and res["sample_ok"]
    assert res["success_margin"] == pytest.approx(0.05, abs=1e-12)


def test_acceptance_gate_rejects_a_short_policy_on_each_axis():
    """Each axis independently blocks acceptance: low success, too few eval episodes, any
    over-budget safety violation, or too large a sim-to-real gap."""
    low = acceptance_gate(measured_success_rate=0.85, required_success_rate=0.9, n_eval_episodes=200)
    assert not low["ok"] and not low["success_ok"]
    tiny_sample = acceptance_gate(measured_success_rate=0.95, required_success_rate=0.9, n_eval_episodes=5)
    assert not tiny_sample["ok"] and not tiny_sample["sample_ok"]    # 0.95 on 5 rollouts is noise
    unsafe = acceptance_gate(measured_success_rate=0.95, required_success_rate=0.9, n_eval_episodes=200,
                             measured_safety_violations=1, max_safety_violations=0)
    assert not unsafe["ok"] and not unsafe["safety_ok"]
    brittle = acceptance_gate(measured_success_rate=0.95, required_success_rate=0.9, n_eval_episodes=200,
                              sim2real_gap=0.2, max_sim2real_gap=0.1)
    assert not brittle["ok"] and not brittle["sim2real_ok"]


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        acceptance_gate(measured_success_rate=1.5, required_success_rate=0.9, n_eval_episodes=200)
    with pytest.raises(ValueError):
        acceptance_gate(measured_success_rate=0.9, required_success_rate=0.9, n_eval_episodes=0)
    with pytest.raises(ValueError):
        acceptance_gate(measured_success_rate=0.9, required_success_rate=0.9, n_eval_episodes=200,
                        measured_safety_violations=-1)
    with pytest.raises(ValueError):
        acceptance_gate(measured_success_rate=0.9, required_success_rate=0.9, n_eval_episodes=200,
                        sim2real_gap=-0.1)
