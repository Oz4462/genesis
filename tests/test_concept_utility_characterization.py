"""Characterization test: prove `ConceptUtility` (ledger-learned contrastive prior)
is REAL, not a constant-returning facade.

Audit target: src/gen/discovery/concept_utility.py claims to learn a contrastive
utility from real gate verdicts (PASS/FAIL records) so that historically successful
concept shapes are preferred for tie-breaking. The utility is ONLY an ordering
heuristic — the deterministic gate remains the sole authority.

Per task spec (T03) + team decisions (2026-06-23):
- Build ALL Candidate objects via the REAL engine constructor (candidate_from_exponents
  or full dataclass from engine.py field names read directly; never invent fields).
- Use concepts_of on the real objects.
- (1) A ledger where one concept shape correlates with PASS => its utility() > 0 and
  a FAIL-correlated shape => < 0. score()/order() re-rank: a passing-shaped candidate
  is placed ahead of a failing-shaped one.
- (2) The documented no-contrast invariant: ledger of only passes OR only fails =>
  uniformly 0.0 utility everywhere; an unseen concept (novel var/exp/complexity token)
  scores exactly 0.0.
- (3) order() is deterministic and respects the documented tie-break (higher score,
  then lower complexity, then expression string).
- At least one property-based test (Hypothesis) exercising an invariant (determinism,
  sign rules, zero on no-contrast).
- New file is the authoritative signal; legacy tests/test_concept_utility.py untouched.
- Edit concept_utility.py ONLY on genuine defect exposed by these tests (pre-inspection:
  logic matches docstring exactly; "change nothing if correct").
- Uses only declared deps (numpy for engine cases, hypothesis already in dev) + stdlib.
- Facade killer: output (utility/score/order) changes meaningfully on driving ledger
  change; signal-free ledger yields honest 0 (no fabricated ranking).

AUDIT VERDICT (see DEPTH_AUDIT_concept_utility.md): REAL. The contrastive fit is
genuine counting + log-ratio over gate verdicts.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.benchmark import kepler_case
from gen.discovery.concept_utility import ConceptUtility, concepts_of
from gen.discovery.engine import (
    Candidate,
    Constant,
    DiscoveryProblem,
    Variable,
    candidate_from_exponents,
    discover_new_formulas,
)


def _kepler_problem() -> DiscoveryProblem:
    """Real Kepler problem via benchmark (positive data, textbook units)."""
    return kepler_case().problem


def _unseen_problem() -> DiscoveryProblem:
    """A problem with disjoint variable names so its concept tokens are guaranteed unseen
    relative to a ledger built on Kepler (a/mu). Used to prove the unseen=0 contract."""
    # dimensionless toy: z = 2*w  (will produce clean candidates for token isolation)
    w = (1.0, 2.0, 3.0)
    z = (2.0, 4.0, 6.0)
    return DiscoveryProblem(
        idea="Unseen var for contrastive zero test.",
        target=Variable("z", "1", tuple(z)),
        inputs=(Variable("w", "1", tuple(w)),),
    )


def _two_source_problem() -> DiscoveryProblem:
    """Problem with two named sources so we can synthesize different complexities
    (set one exponent to zero) while staying inside the real engine builder."""
    v = (1.0, 2.0, 3.0)
    u = (1.0, 1.0, 1.0)
    t = (1.0, 2.0, 3.0)  # t ~ v  (simple)
    return DiscoveryProblem(
        idea="Two-source for tie-break complexity test.",
        target=Variable("t", "1", tuple(t)),
        inputs=(Variable("v", "1", tuple(v)), Variable("u", "1", tuple(u))),
    )


def test_utility_learns_positive_for_pass_correlated_and_negative_for_fail():
    """(1) Core contract: concepts that appear with passing verdicts get >0 utility;
    failing get <0. This proves the ledger (gate verdicts) is actually consumed.
    """
    p = _kepler_problem()
    # Real engine-built candidates (different exponent signatures => different concepts)
    cand_pass = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    cand_fail = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})

    # Ledger in which "exp:a^3/2" and "var:mu" (via the good shape) correlate with PASS,
    # while "exp:a^1" correlates with FAIL. Repeats give count weight.
    records = [(cand_pass, True)] * 4 + [(cand_fail, False)] * 4
    u = ConceptUtility.fit(records)

    # The distinguishing tokens must have opposite signs
    assert u.utility("exp:a^3/2") > 0.0
    assert u.utility("exp:a^1") < 0.0
    # complexity token seen on both sides receives a (weaker) learned value
    assert "complexity:2" in u._utility  # participates in contrast


def test_score_and_order_actually_re_rank_by_learned_signal():
    """(1) score() reflects the mean concept utility; order() uses it to surface
    historically-passing-shaped candidates ahead of failing-shaped ones.
    """
    p = _kepler_problem()
    cand_good = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    cand_bad = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})

    records = [(cand_good, True)] * 3 + [(cand_bad, False)] * 3
    u = ConceptUtility.fit(records)

    # A candidate whose shape matches the passing history must outscore the bad shape
    assert u.score(cand_good) > u.score(cand_bad)

    # order() must place the good-shaped candidate first even if fed reversed
    ordered = u.order([cand_bad, cand_good])
    assert ordered[0] is cand_good
    assert ordered[1] is cand_bad


def test_no_contrast_invariant_all_passes_or_all_fails_yields_zero():
    """(2) When the ledger supplies nothing to contrast (all pass or all fail),
    every utility and every score is exactly 0.0 (honest abstention, not invented signal).
    """
    p = _kepler_problem()
    cand1 = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    cand2 = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})

    only_passes = ConceptUtility.fit([(cand1, True), (cand2, True), (cand1, True)])
    assert only_passes.utility("exp:a^3/2") == 0.0
    assert only_passes.utility("exp:a^1") == 0.0
    assert only_passes.score(cand1) == 0.0
    assert only_passes.score(cand2) == 0.0

    only_fails = ConceptUtility.fit([(cand1, False), (cand2, False)])
    some_token = next(iter(concepts_of(cand1)))
    assert only_fails.utility(some_token) == 0.0
    assert only_fails.score(cand1) == 0.0


def test_unseen_concept_scores_exactly_zero():
    """(2) A concept token never observed in any record (or a candidate built only
    from unseen tokens) receives 0.0 — the neutral default.
    """
    p_kepler = _kepler_problem()
    p_unseen = _unseen_problem()

    # Ledger on Kepler shapes only
    cand_k = candidate_from_exponents(p_kepler, {"a": 1.5, "mu": -0.5})
    u = ConceptUtility.fit([(cand_k, True), (cand_k, False)])

    # Completely novel tokens
    assert u.utility("var:ghost") == 0.0
    assert u.utility("exp:w^1") == 0.0
    assert u.utility("complexity:99") == 0.0

    # A candidate whose entire concept set is disjoint from the ledger
    cand_unseen = candidate_from_exponents(p_unseen, {"w": 1.0})
    # Its tokens (complexity:1, var:w, exp:w^1) were never seen
    assert u.score(cand_unseen) == 0.0


def test_order_is_deterministic_and_respects_tie_break():
    """(3) Identical inputs always produce identical ordering.
    When scores are equal, tie-break is lower complexity then smaller expression string.
    """
    p = _kepler_problem()
    c1 = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    c2 = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})

    records = [(c1, True), (c2, False)]
    u = ConceptUtility.fit(records)

    # Determinism
    o1 = u.order([c2, c1])
    o2 = u.order([c2, c1])
    assert [c.expression for c in o1] == [c.expression for c in o2]

    # Tie-break on a neutral prior (both scores == 0): lower complexity first, then expr
    p2 = _two_source_problem()
    c_low = candidate_from_exponents(p2, {"v": 2.0, "u": 0.0})   # complexity 1
    c_high = candidate_from_exponents(p2, {"v": 1.0, "u": 1.0})  # complexity 2
    # Both have zero utility under empty prior
    u0 = ConceptUtility()
    assert u0.score(c_low) == 0.0 and u0.score(c_high) == 0.0

    ordered = u0.order([c_high, c_low])
    assert ordered[0] is c_low
    assert ordered[1] is c_high

    # Same complexity, tie-break on expression string (lex smaller first)
    c_e1 = candidate_from_exponents(p2, {"v": 1.0, "u": 0.0})  # 'T = 0.0006... * v'
    c_e2 = candidate_from_exponents(p2, {"v": 2.0, "u": 0.0})  # 'T = 4.68... * v^2'
    # Ensure we know which expr is lex smaller (engine renders coefs)
    assert c_e1.expression < c_e2.expression or c_e2.expression < c_e1.expression
    ordered_e = u0.order([c_e2, c_e1])
    # The one with smaller expression string must appear first
    first_expr, second_expr = ordered_e[0].expression, ordered_e[1].expression
    assert first_expr < second_expr


def test_from_result_consumes_real_engine_verdicts():
    """from_result works on a genuine DiscoveryResult (real gate verdicts from discover)."""
    prob = _kepler_problem()
    result = discover_new_formulas(prob)
    assert result.all_records, "engine must have produced records for this test"

    u = ConceptUtility.from_result(result)
    # At minimum it must not explode and unseen concepts stay neutral
    for rec in result.all_records[:2]:
        # scoring real candidates must be defined
        _ = u.score(rec.candidate)
    # A token never present in this result must be 0
    assert u.utility("exp:never^99") == 0.0


def test_empty_ledger_and_edge_cases_are_honest_zero():
    """Empty ledger and candidates with no participating concepts (all-zero exponents)
    are handled as neutral (score 0) rather than error or fabricated value.
    """
    u = ConceptUtility.fit([])
    p = _kepler_problem()
    c = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    assert u.score(c) == 0.0

    # Candidate whose only token is an unseen complexity (via all-zero exponents)
    c_zero = candidate_from_exponents(p, {"a": 0.0, "mu": 0.0})
    assert concepts_of(c_zero) == frozenset({"complexity:0"})
    assert u.score(c_zero) == 0.0
    assert u.utility("complexity:0") == 0.0


# --- Property-based invariants (Hypothesis) -------------------------------------------------

@given(
    n_pos=st.integers(min_value=1, max_value=6),
    n_neg=st.integers(min_value=1, max_value=6),
    smoothing=st.floats(min_value=0.1, max_value=4.0),
)
@settings(max_examples=20, deadline=2000)
def test_fit_determinism_and_signs_property(n_pos, n_neg, smoothing):
    """For any positive contrast counts and smoothing, two fits on identical records
    are identical (reproducibility A5), and the pass-shape token is >0 while fail <0.
    """
    p = _kepler_problem()
    cand_p = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    cand_f = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})
    records = [(cand_p, True)] * n_pos + [(cand_f, False)] * n_neg

    u1 = ConceptUtility.fit(records, smoothing=smoothing)
    u2 = ConceptUtility.fit(records, smoothing=smoothing)

    assert u1._utility == u2._utility
    assert u1.utility("exp:a^3/2") > 0.0
    assert u1.utility("exp:a^1") < 0.0


@given(n_same=st.integers(min_value=2, max_value=5))
def test_no_contrast_property_yields_uniform_zero(n_same):
    """Any ledger consisting solely of passes (or solely of fails) yields the zero
    utility surface for all concepts and all scores — the no-contrast invariant.
    """
    p = _kepler_problem()
    c1 = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    c2 = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})
    rec_pass = [(c1, True)] * n_same + [(c2, True)] * n_same
    u_pass = ConceptUtility.fit(rec_pass)
    assert all(v == 0.0 for v in u_pass._utility.values())
    assert u_pass.score(c1) == 0.0 and u_pass.score(c2) == 0.0

    rec_fail = [(c1, False)] * n_same
    u_fail = ConceptUtility.fit(rec_fail)
    assert u_fail.score(c1) == 0.0


@given(
    n1=st.integers(min_value=1, max_value=3),
    n2=st.integers(min_value=1, max_value=3),
)
def test_order_deterministic_under_varying_counts(n1, n2):
    """order() is deterministic for any ledger counts (property over the contract)."""
    p = _kepler_problem()
    c_good = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    c_bad = candidate_from_exponents(p, {"a": 1.0, "mu": -0.5})
    rec = [(c_good, True)] * n1 + [(c_bad, False)] * n2
    u = ConceptUtility.fit(rec)
    cands = [c_bad, c_good, c_bad]
    o1 = [c.expression for c in u.order(cands)]
    o2 = [c.expression for c in u.order(list(cands))]
    assert o1 == o2
