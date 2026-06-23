"""Characterization tests for ``assumption_annihilator.annihilate_constant`` (build doc 4.3).

Goal of this depth-audit test: PROVE that the three honest δ-verdicts are real — not
constant strings. We construct ``DiscoveryProblem``/``Variable``/``Constant`` inputs (real
``engine.py`` field names) so that the held-constant baseline and the rebuilt law (constant
promoted to a free variable) genuinely differ in fit, and that each verdict is driven by the
actual fit improvement under the δ-raised margin:

  * ``promoted`` — the promoted variable's per-sample values genuinely carry the missing
    dependency, the rebuilt law clears the δ-raised bar and is dimensionally sound;
  * ``assumption_held`` — the "constant" really is constant across samples, so the rebuild
    cannot improve the fit;
  * ``insufficient_evidence`` — a small but real improvement that clears the base margin yet
    stays below the high-δ required bar (the honest "interesting, but not enough").

Plus the two documented fail-loud guards (unknown constant / sample-count mismatch) and a
property-based check of the two arithmetic identities the result must always satisfy.

The numeric data here was chosen by computing the real engine's R² offline; the asserted
``base_r2``/``rebuilt_r2`` band is what the deterministic engine actually returns.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.assumption_annihilator import (
    BASE_IMPROVEMENT_MARGIN,
    DELTA_MARGIN_SCALE,
    PROMOTION_DELTA,
    AnnihilationResult,
    annihilate_constant,
)
from gen.discovery.engine import Constant, DiscoveryProblem, Variable

# The dimensional law behind every case: y[m] = C · x[s] · k[m/s]. With ``k`` held constant the
# fit can only see ``y ∝ x``; promoting ``k`` to a per-sample variable lets the law track the real
# k[i], so the rebuilt R² rises exactly as much as the held-constant assumption was masking.
_X = (1.0, 2.0, 3.0, 4.0, 5.0)

#: The δ-raised bar a rebuild must clear to ``promoted`` (independent of the input data).
_REQUIRED = BASE_IMPROVEMENT_MARGIN + PROMOTION_DELTA * DELTA_MARGIN_SCALE


def _problem(y: tuple[float, ...], *, k_value: float = 1.0) -> DiscoveryProblem:
    """A y = C·x·k discovery problem with ``k`` held as a constant (the assumption to lift)."""
    return DiscoveryProblem(
        idea="y aus x bei gehaltener Konstante k",
        target=Variable("y", "m", y),
        inputs=(Variable("x", "s", _X),),
        constants=(Constant("k", k_value, "m/s"),),
        run_id="run-annihilator",
    )


def test_promoted_when_constant_was_a_hidden_variable() -> None:
    """(a) per_sample_values genuinely carry the missing dependency → rebuilt clears the δ-bar."""
    k_actual = [2.0, 5.0, 3.0, 7.0, 4.0]  # genuinely varies per sample
    y = tuple(xi * ki for xi, ki in zip(_X, k_actual))
    result = annihilate_constant(_problem(y), "k", k_actual)

    assert isinstance(result, AnnihilationResult)
    assert result.verdict == "promoted"
    assert result.promoted == "k"
    # The hidden dependency is fully recovered: rebuilt law fits exactly, baseline cannot.
    assert result.rebuilt_r2 == pytest.approx(1.0)
    assert result.base_r2 < 0.95
    assert result.improvement >= _REQUIRED
    # The promoted quantity actually appears in the rebuilt law (it was consumed, not ignored).
    assert "k" in result.rebuilt_law


def test_assumption_held_when_constant_is_truly_constant() -> None:
    """(b) a genuinely constant quantity → rebuild cannot improve the fit → assumption upheld."""
    k_const = [3.0, 3.0, 3.0, 3.0, 3.0]  # no per-sample dependency at all
    y = tuple(xi * 3.0 for xi in _X)
    result = annihilate_constant(_problem(y, k_value=3.0), "k", k_const)

    assert result.verdict == "assumption_held"
    # Baseline already perfect; promoting a constant-valued quantity changes nothing.
    assert result.base_r2 == pytest.approx(1.0)
    assert result.improvement <= BASE_IMPROVEMENT_MARGIN
    assert result.improvement == pytest.approx(0.0, abs=1e-9)


def test_insufficient_evidence_for_marginal_improvement() -> None:
    """(c) a small real gain above the base margin but below the δ-raised bar → honest abstain."""
    # Only the last sample deviates slightly, so the rebuild improves the fit a little — enough
    # to beat BASE_IMPROVEMENT_MARGIN (0.01) but far below the δ-raised _REQUIRED (0.05).
    k_actual = [3.0, 3.0, 3.0, 3.0, 3.5]
    y = tuple(xi * ki for xi, ki in zip(_X, k_actual))
    result = annihilate_constant(_problem(y, k_value=3.0), "k", k_actual)

    assert result.verdict == "insufficient_evidence"
    assert BASE_IMPROVEMENT_MARGIN < result.improvement < _REQUIRED


def test_required_improvement_is_delta_raised() -> None:
    """The evidence bar is the base margin RAISED by the promotion-δ — the spec's identity."""
    k_actual = [2.0, 5.0, 3.0, 7.0, 4.0]
    y = tuple(xi * ki for xi, ki in zip(_X, k_actual))
    result = annihilate_constant(_problem(y), "k", k_actual)

    assert result.delta == PROMOTION_DELTA
    assert result.required_improvement == pytest.approx(
        BASE_IMPROVEMENT_MARGIN + PROMOTION_DELTA * DELTA_MARGIN_SCALE
    )
    # improvement is exactly the fit delta between rebuilt and held-constant baselines.
    assert result.improvement == pytest.approx(result.rebuilt_r2 - result.base_r2)


def test_custom_margin_shifts_the_bar() -> None:
    """A caller-supplied improvement_margin must move required_improvement (no silent default)."""
    k_actual = [2.0, 5.0, 3.0, 7.0, 4.0]
    y = tuple(xi * ki for xi, ki in zip(_X, k_actual))
    result = annihilate_constant(_problem(y), "k", k_actual, improvement_margin=0.2)

    assert result.required_improvement == pytest.approx(0.2 + PROMOTION_DELTA * DELTA_MARGIN_SCALE)


# --- documented fail-loud guards (negative tests) ---------------------------------------------


def test_unknown_constant_name_raises() -> None:
    """A constant_name that is not a constant of the problem fails loud — no fabricated rebuild."""
    y = tuple(xi * 2.0 for xi in _X)
    with pytest.raises(ValueError, match="is not a constant"):
        annihilate_constant(_problem(y), "does_not_exist", [1.0] * len(_X))


def test_sample_count_mismatch_raises() -> None:
    """per_sample_values must have one entry per data point — a mismatch fails loud."""
    y = tuple(xi * 2.0 for xi in _X)
    with pytest.raises(ValueError, match="one entry per data point"):
        annihilate_constant(_problem(y), "k", [1.0, 1.0])  # too few


# --- property-based invariants (must hold for ALL valid inputs) -------------------------------

# Positive samples only: power-law discovery rejects non-positive magnitudes, and y = x·k keeps
# every quantity positive by construction. Bounds keep the fit numerically well-conditioned.
_pos = st.floats(min_value=0.5, max_value=50.0, allow_nan=False, allow_infinity=False)


@settings(max_examples=60, deadline=None)
@given(
    x_vals=st.lists(_pos, min_size=2, max_size=6),
    k_vals=st.lists(_pos, min_size=2, max_size=6),
    margin=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
)
def test_result_identities_hold_for_all_inputs(
    x_vals: list[float], k_vals: list[float], margin: float
) -> None:
    """For any valid data: improvement == rebuilt_r2 - base_r2, the required bar is the
    δ-raised margin, delta is the promotion-δ, and the verdict is one of the three honest
    outcomes — never a fabricated fourth state."""
    n = min(len(x_vals), len(k_vals))
    x = tuple(x_vals[:n])
    k = list(k_vals[:n])
    y = tuple(xi * ki for xi, ki in zip(x, k))
    problem = DiscoveryProblem(
        idea="property",
        target=Variable("y", "m", y),
        inputs=(Variable("x", "s", x),),
        constants=(Constant("k", 1.0, "m/s"),),
        run_id="prop",
    )

    result = annihilate_constant(problem, "k", k, improvement_margin=margin)

    assert result.delta == PROMOTION_DELTA
    assert result.required_improvement == pytest.approx(margin + PROMOTION_DELTA * DELTA_MARGIN_SCALE)
    assert result.improvement == pytest.approx(result.rebuilt_r2 - result.base_r2, abs=1e-9)
    assert math.isfinite(result.improvement)
    assert result.verdict in {"promoted", "assumption_held", "insufficient_evidence"}
    # Consistency of the verdict with the gate it claims to implement.
    if result.verdict == "promoted":
        assert result.improvement >= result.required_improvement
    elif result.verdict == "assumption_held":
        assert result.improvement <= margin
