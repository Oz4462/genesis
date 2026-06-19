"""Tests for the discovery gate as an RL environment (discovery/rl_env.py).

Pins: reset exposes the target + source units an agent must explain; a correct law gets a high reward
and done=True; a wrong law gets a lower reward and done=False; and a dimensionally-impossible law is
NOT rewarded high even at a perfect numeric fit -- the gate, not the agent, decides. Offline,
deterministic.
"""

from gen.discovery.benchmark import kepler_case
from gen.discovery.rl_env import DiscoveryEnv


def _env() -> DiscoveryEnv:
    return DiscoveryEnv(kepler_case().problem)


def test_reset_exposes_the_problem_to_solve():
    obs = _env().reset()
    assert obs["target_unit"] == "s"
    assert set(obs["source_units"]) == {"a", "mu"}


def test_correct_law_is_rewarded_and_ends_the_episode():
    step = _env().step({"a": 1.5, "mu": -0.5})            # the true Kepler exponents
    assert step.done and step.reward > 0.99               # gate confirmed + high dimensional-consistency reward
    assert step.info["dimension_ok"] is True


def test_wrong_law_is_not_confirmed_and_scores_lower():
    correct = _env().step({"a": 1.5, "mu": -0.5})
    wrong = _env().step({"a": 1.0, "mu": -0.5})
    assert not wrong.done and wrong.reward < correct.reward


def test_the_gate_not_the_agent_decides_reward():
    # a dimensionally-impossible proposal cannot be rewarded high, regardless of how it might fit.
    step = _env().step({"a": 3.0, "mu": -0.5})
    assert not step.done and step.reward < 0.5


def test_is_deterministic():
    a = _env().step({"a": 1.5, "mu": -0.5})
    b = _env().step({"a": 1.5, "mu": -0.5})
    assert (a.reward, a.done) == (b.reward, b.done)
