"""Tests for residual-certified surrogates (simulation/surrogate.py).

Pins the honesty boundary: a good surrogate output is certified verified by its exact residual, a bad
one is unverified (never asserted), and NOWS warm-starting accepts a sufficient guess but otherwise
falls back to the exact solver that produces the certified answer. Offline, deterministic.
"""

import numpy as np

from gen.simulation.surrogate import nows_warm_start, residual_certify

# a tiny linear system A x = b; the exact x* = [1, 1].
_A = np.array([[2.0, 1.0], [1.0, 3.0]])
_B = np.array([3.0, 4.0])


def _residual(x):
    return float(np.linalg.norm(_A @ np.asarray(x) - _B))


def test_a_good_surrogate_output_is_certified_verified():
    res = residual_certify(np.array([1.0, 1.0]), _residual, tol=1e-9)
    assert res.verified and res.residual < 1e-9


def test_a_bad_surrogate_output_is_unverified_not_asserted():
    res = residual_certify(np.array([0.0, 0.0]), _residual, tol=1e-6)
    assert not res.verified and res.residual > 1e-6


def test_nows_accepts_a_sufficient_guess_without_solving():
    res = nows_warm_start(np.array([1.0, 1.0]), exact_solver=lambda g: None, residual_fn=_residual, tol=1e-9)
    assert res.guess_was_sufficient and res.answer_residual < 1e-9   # exact_solver never called


def test_nows_falls_back_to_the_exact_solver_and_certifies_it():
    solver = lambda guess: np.linalg.solve(_A, _B)        # the exact solve still produces the answer
    res = nows_warm_start(np.array([5.0, -2.0]), exact_solver=solver, residual_fn=_residual, tol=1e-9)
    assert not res.guess_was_sufficient
    assert res.answer_residual < 1e-9                      # the returned answer is certified, not the guess
    assert np.allclose(res.answer, [1.0, 1.0])
