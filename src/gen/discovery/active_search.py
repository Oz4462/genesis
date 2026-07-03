"""active_search — information-gain candidate selection under a gate budget (InfoBAX adoption).

Self-driving labs spend their budget where they LEARN the most. InfoBAX generalises Bayesian
optimisation: pick the next evaluation that most reduces uncertainty about an algorithm's output —
here, "which candidates the gate passes". The tractable, dependency-light realisation (no GP) is
uncertainty sampling: model the pass-probability of a candidate from the gate verdicts already
collected, and gate next the candidate whose outcome is most UNCERTAIN (binary entropy near its 0.5
maximum = maximum expected information gain). The gate stays the sole oracle — this only chooses the
ORDER of evaluation, never a verdict (CLAUDE.md §1).

Deterministic, offline, pure-python (math only).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar

C = TypeVar("C")
Feature = tuple[float, ...]


def binary_entropy(p: float) -> float:
    """Shannon entropy (bits) of a Bernoulli(p) — the expected information of resolving a pass/fail.
    Maximal (1.0) at p=0.5, zero at a certain 0/1 outcome."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


class PassModel:
    """Inverse-distance-weighted pass-probability over already-gated examples (a light kNN surrogate)."""

    def __init__(self, gated: Sequence[tuple[Feature, bool]]) -> None:
        self._gated = list(gated)

    def predict(self, feature: Feature) -> float:
        """Predicted P(pass) for a feature; 0.5 (maximum uncertainty) when nothing has been gated yet."""
        if not self._gated:
            return 0.5
        weight_sum = 0.0
        pass_sum = 0.0
        for example_feature, passed in self._gated:
            distance = math.dist(feature, example_feature)
            weight = 1.0 / (distance + 1e-9)
            weight_sum += weight
            pass_sum += weight * (1.0 if passed else 0.0)
        return pass_sum / weight_sum if weight_sum > 0.0 else 0.5

    def expected_information_gain(self, feature: Feature) -> float:
        """Binary entropy of the predicted pass-probability — higher means more informative to gate."""
        return binary_entropy(self.predict(feature))


def select_most_informative(features: Sequence[Feature], model: PassModel) -> int:
    """Index of the most informative (highest expected-information-gain) feature; ties break to the
    lowest index for determinism."""
    best_index, best_eig = 0, -1.0
    for index, feature in enumerate(features):
        eig = model.expected_information_gain(feature)
        if eig > best_eig:
            best_eig, best_index = eig, index
    return best_index


@dataclass(frozen=True)
class ActiveResult:
    """The active-selection trajectory: every (candidate, passed) in the order it was gated, the
    passing subset, and how many gate calls were spent."""

    gated: tuple[tuple[object, bool], ...]
    passing: tuple[object, ...]
    gate_calls: int


def active_select(
    candidates: Sequence[C],
    gate: Callable[[C], bool],
    feature: Callable[[C], Feature],
    *,
    budget: int,
) -> ActiveResult:
    """Greedy uncertainty-sampling active loop: repeatedly gate the candidate whose pass/fail is most
    uncertain given what's been gated (max expected information gain), updating the model each step,
    until ``budget`` gate-calls are spent (or the pool is exhausted). The gate is the oracle — selection
    only chooses the evaluation order. Deterministic."""
    if budget < 0:
        raise ValueError("budget must be >= 0")
    features = [tuple(feature(c)) for c in candidates]
    remaining = list(range(len(candidates)))
    gated_examples: list[tuple[Feature, bool]] = []
    order: list[tuple[object, bool]] = []
    passing: list[object] = []
    for _ in range(min(budget, len(candidates))):
        model = PassModel(gated_examples)
        chosen = max(remaining, key=lambda i: (model.expected_information_gain(features[i]), -i))
        remaining.remove(chosen)
        passed = bool(gate(candidates[chosen]))
        gated_examples.append((features[chosen], passed))
        order.append((candidates[chosen], passed))
        if passed:
            passing.append(candidates[chosen])
    return ActiveResult(tuple(order), tuple(passing), len(order))
