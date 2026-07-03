"""Assumption Annihilator — promote a 'constant' to a variable; high δ -> high evidence bar."""

import math

import numpy as np
import pytest

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery import annihilate_constant


_MU = 1.32712440018e20


def _problem_with_constant_mu(a, mu_true, mu_held):
    """Build a problem whose TRUE data used the (possibly varying) `mu_true`, but which MODELS
    mu as the single held constant `mu_held` — the assumption the annihilator will test."""
    T = 2.0 * math.pi * a ** 1.5 / np.sqrt(mu_true)
    return DiscoveryProblem(
        idea="Umlaufzeit", target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", float(mu_held), "m^3/s^2"),))


def test_annihilates_a_hidden_dependency():
    """Data taken across systems with DIFFERENT mu, but modelled with mu constant: the constant
    assumption fits poorly; promoting mu to a variable rebuilds T ∝ a^1.5·mu^-0.5 and fits — the
    assumption is annihilated."""
    a = np.array([1.0e11, 2.0e11, 1.5e11, 3.0e11, 2.5e11, 1.8e11])
    mu_true = np.array([1.0e20, 2.0e20, 1.3e20, 2.5e20, 1.1e20, 3.0e20])  # really varied ~3x
    problem = _problem_with_constant_mu(a, mu_true, mu_held=float(np.mean(mu_true)))
    res = annihilate_constant(problem, "mu", list(mu_true))
    assert res.verdict == "promoted"
    assert res.base_r2 < res.rebuilt_r2
    assert res.rebuilt_r2 > 0.999
    assert res.improvement >= res.required_improvement
    assert "a^3/2" in res.rebuilt_law and "mu^-1/2" in res.rebuilt_law


def test_upholds_a_genuine_constant():
    """When mu was TRULY constant, promoting it adds a degenerate variable and yields no
    improvement — the constant assumption honestly holds."""
    a = np.array([1.0e11, 2.0e11, 1.5e11, 3.0e11, 2.5e11, 1.8e11])
    mu_const = np.full(6, _MU)
    problem = _problem_with_constant_mu(a, mu_const, mu_held=_MU)
    res = annihilate_constant(problem, "mu", list(mu_const))
    assert res.verdict == "assumption_held"
    assert res.improvement <= 0.01


def test_delta_bar_blocks_a_marginal_improvement():
    """The δ-asymmetry guardrail: a SMALL mu variation gives only a marginal fit gain — far below
    the δ-raised bar — so the extraordinary claim 'the constant is really a variable' is NOT
    accepted (no false discovery)."""
    a = np.array([1.0e11, 2.0e11, 1.5e11, 3.0e11, 2.5e11, 1.8e11])
    mu_true = _MU * np.array([1.0, 1.01, 0.995, 1.008, 0.997, 1.003])  # tiny variation
    problem = _problem_with_constant_mu(a, mu_true, mu_held=float(np.mean(mu_true)))
    res = annihilate_constant(problem, "mu", list(mu_true))
    assert res.verdict != "promoted"                       # guardrail holds
    assert res.delta == 0.8 and res.required_improvement > 0.04


def test_errors_on_a_non_constant():
    a = np.array([1.0, 2.0, 3.0])
    problem = DiscoveryProblem(idea="x", target=Variable("y", "s", (1.0, 2.0, 3.0)),
                               inputs=(Variable("a", "m", tuple(a)),))
    with pytest.raises(ValueError):
        annihilate_constant(problem, "mu", [1.0, 2.0, 3.0])
