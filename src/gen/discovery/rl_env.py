"""rl_env — GENESIS's discovery gate as a standardized RL environment (the ecosystem move).

Competitive-intel finding #3: expose GENESIS's deterministic gate as an RL ENVIRONMENT so other people's
proposers train AGAINST it — turning the moat (the gate) into a distribution / ecosystem position that
competitors must route through (the NewtonBench / NeMo-Gym pattern). A Gym-style ``step`` takes a
proposed power law (the action = exponent hypothesis), the gate judges it, and the reward is the
dimensional-consistency reward (``reward.py``): a dimensionally-impossible law cannot be rewarded high
even at a perfect fit. The gate is the environment dynamics — deterministic, non-LLM, the same
authority everywhere; an agent can never be rewarded for a law the gate would reject.

This is the environment INTERFACE (``reset`` / ``step``), offline and dependency-free; plugging in an
actual RL trainer (GPU) is external.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import DiscoveryProblem, candidate_from_exponents, judge_candidate
from .reward import discovery_reward


@dataclass(frozen=True)
class StepResult:
    """One environment step: the observation, the reward, whether the episode is ``done`` (the gate
    CONFIRMED the proposed law), and ``info`` with the gate verdict and its components."""

    observation: dict[str, object]
    reward: float
    done: bool
    info: dict[str, object] = field(default_factory=dict)


class DiscoveryEnv:
    """A Gym-style environment whose dynamics ARE GENESIS's deterministic discovery gate.

    ``reset`` returns the problem an agent must explain (target + input units). ``step(exponents)`` judges
    the proposed power law through the gate and returns the dimensional-consistency reward. The gate —
    never the agent — decides ``done``; the reward shapes toward laws that are both well-fitting AND
    dimensionally sound. Deterministic.
    """

    def __init__(self, problem: DiscoveryProblem) -> None:
        self._problem = problem
        self._source_units = {v.name: v.unit for v in problem.inputs}
        self._source_units.update({c.name: c.unit for c in problem.constants})
        self._obs: dict[str, object] = {
            "idea": problem.idea,
            "target_unit": problem.target.unit,
            "source_units": dict(self._source_units),
        }

    def reset(self) -> dict[str, object]:
        """Return the observation: what the agent must explain (the target and the source units)."""
        return dict(self._obs)

    def step(self, exponents: dict[str, float]) -> StepResult:
        """Judge the proposed power law through the gate and return the dimensional-consistency reward.
        ``done`` is the gate's PASS verdict — the agent is never rewarded high for a law the gate rejects
        as dimensionally impossible (reward → 0) even at a perfect numeric fit."""
        candidate = candidate_from_exponents(self._problem, exponents)
        verdict = judge_candidate(self._problem, candidate)
        reward = discovery_reward(
            r_squared=candidate.r_squared,
            target_unit=self._problem.target.unit,
            source_units=self._source_units,
            exponents=exponents,
        )
        return StepResult(
            observation=dict(self._obs),
            reward=reward,
            done=verdict.passed,
            info={
                "verdict": verdict.verdict,
                "r_squared": candidate.r_squared,
                "dimension_ok": candidate.dimension_ok,
            },
        )
