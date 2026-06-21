"""Tests for the CCTS-style ledger-learned concept utility (discovery/concept_utility.py).

Pins: concept extraction, the contrastive utility LEARNING WHAT TO AVOID (failure-correlated concepts
get negative utility), deterministic ordering, the no-contrast/unseen neutral cases, and — the load-
bearing honesty test — that supplying the prior to the engine NEVER changes which candidates pass the
gate (it only breaks ties). Offline, deterministic, no network.
"""

from types import SimpleNamespace

from gen.discovery.concept_utility import ConceptUtility, concepts_of
from gen.discovery.engine import Candidate


def _cand(exponents: dict[str, float], *, r2: float = 1.0) -> Candidate:
    complexity = sum(1 for v in exponents.values() if abs(v) >= 1e-9)
    expr = "T = " + " * ".join(f"{n}^{v}" for n, v in exponents.items())
    return Candidate(
        expression=expr, exponents=dict(exponents), coefficient=1.0, r_squared=r2,
        rmse=0.0, complexity=complexity, dimension_ok=True, dimension_residual=0.0,
    )


def test_concepts_of_extracts_variable_exponent_and_complexity_tokens():
    cs = concepts_of(_cand({"a": 1.5, "mu": -0.5}))
    assert {"var:a", "exp:a^3/2", "var:mu", "exp:mu^-1/2", "complexity:2"} <= cs
    # a zero exponent does not participate -> no token for it
    assert "var:b" not in concepts_of(_cand({"a": 1.5, "b": 0.0}))


def test_utility_learns_to_avoid_failure_correlated_concepts():
    # exp:a^3/2 appears only in passes; exp:a^1 appears only in fails.
    records = (
        [(_cand({"a": 1.5, "mu": -0.5}), True)] * 3
        + [(_cand({"a": 1.0, "mu": -0.5}), False)] * 3
    )
    u = ConceptUtility.fit(records)
    assert u.utility("exp:a^3/2") > 0.0 > u.utility("exp:a^1")   # learned what to prefer AND avoid


def test_order_prefers_pass_correlated_candidate():
    records = (
        [(_cand({"a": 1.5, "mu": -0.5}), True)] * 3
        + [(_cand({"a": 1.0, "mu": -0.5}), False)] * 3
    )
    u = ConceptUtility.fit(records)
    good, bad = _cand({"a": 1.5, "mu": -0.5}), _cand({"a": 1.0, "mu": -0.5})
    assert u.order([bad, good])[0] is good                       # higher learned utility first


def test_unseen_and_no_contrast_score_is_neutral_zero():
    assert ConceptUtility().score(_cand({"a": 1.5})) == 0.0       # empty model -> neutral
    # a ledger with only passes (no fails) has nothing to contrast -> all utilities 0.
    only_pass = ConceptUtility.fit([(_cand({"a": 1.5}), True), (_cand({"a": 1.0}), True)])
    assert only_pass.utility("exp:a^3/2") == 0.0
    assert only_pass.score(_cand({"a": 1.5})) == 0.0


def test_fit_and_order_are_deterministic():
    records = [(_cand({"a": 1.5}), True), (_cand({"a": 1.0}), False), (_cand({"a": 2.0}), False)]
    a, b = ConceptUtility.fit(records), ConceptUtility.fit(records)
    assert a._utility == b._utility
    cands = [_cand({"a": 2.0}), _cand({"a": 1.5}), _cand({"a": 1.0})]
    assert [c.expression for c in a.order(cands)] == [c.expression for c in b.order(cands)]


def test_from_result_learns_from_a_ledger():
    # from_result duck-types over anything with .all_records of (.candidate, .passed).
    res = SimpleNamespace(all_records=[
        SimpleNamespace(candidate=_cand({"a": 1.5, "mu": -0.5}), passed=True),
        SimpleNamespace(candidate=_cand({"a": 1.0, "mu": -0.5}), passed=False),
    ])
    u = ConceptUtility.from_result(res)
    assert u.utility("exp:a^3/2") > 0.0 > u.utility("exp:a^1")


def test_prior_never_changes_gate_verdicts_only_breaks_ties():
    from gen.discovery.benchmark import kepler_case
    from gen.discovery.engine import discover_new_formulas

    problem = kepler_case().problem
    base = discover_new_formulas(problem)
    prior = ConceptUtility.from_result(base)
    with_prior = discover_new_formulas(problem, prior=prior)
    # the SET of validated formulas and that they all passed is identical — the prior only reorders.
    assert {r.candidate.expression for r in with_prior.validated} == {
        r.candidate.expression for r in base.validated
    }
    assert with_prior.validated and all(r.passed for r in with_prior.validated)
