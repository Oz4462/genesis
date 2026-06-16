"""Tests für den Bounded Identity Falsifier (math-research branch, erster Stein).

Gate-first. Deckt die mit dem Co-Architekten konvergierten Invarianten:
- Falsifikation REFUTED mit Witness; überlebende Identität SURVIVED_NOVEL/KNOWN.
- Fingerprint mergt nur 'proved_equal' (x+y == y+x), niemals über Buckets.
- AssumptionManifest beschränkt die Domäne wirklich (gültig auf R+, falsch auf R).
- Severity bestraft Trivialität (x==x → ~0), belohnt informative Identität.
- Unbekannte freie Symbole / Parse-Fehler → INCONCLUSIVE (kein geratener Wert).
- Novelty ist ein Gate-Ergebnis (Index-Treffer → KNOWN), kein LLM-Label.
"""

from gen.identity_research import (
    AssumptionManifest,
    assess_identity,
    fingerprint,
    _make_symbols,
    _parse,
)


def _mR(**vars_):
    return AssumptionManifest(domain_id="R", variables=vars_ or {"x": "real"})


def test_true_trig_identity_survives_and_is_novel():
    art = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1", _mR(x="real"))
    assert art.status == "SURVIVED_NOVEL"
    assert art.falsify.passed and art.falsify.witness is None
    assert art.claim.fp_tier == "proved_equal"
    assert art.proof_tier == 3
    assert art.severity > 0.0
    assert "admit" in art.lean_statement


def test_false_identity_is_refuted_with_witness():
    art = assess_identity("false1", "x", "x + 1", _mR(x="real"))
    assert art.status == "REFUTED"
    assert art.falsify.passed is False
    assert art.falsify.witness is not None and "x" in art.falsify.witness
    assert art.severity == 0.0


def test_manifest_domain_constrains_truth():
    """sqrt(x**2) == x ist FALSCH auf R (x=-1 ist Gegenbeispiel), WAHR auf R+."""
    on_R = assess_identity("sqrt_R", "sqrt(x**2)", "x", AssumptionManifest(domain_id="R", variables={"x": "real"}))
    assert on_R.status == "REFUTED"
    assert on_R.falsify.witness["x"] < 0  # the counterexample is a negative x

    on_Rp = assess_identity("sqrt_Rp", "sqrt(x**2)", "x", AssumptionManifest(domain_id="R+", variables={"x": "positive"}))
    assert on_Rp.status == "SURVIVED_NOVEL"


def test_fingerprint_merges_only_proved_equal():
    m = _mR(x="real", y="real")
    syms = _make_symbols(m)
    mh = m.manifest_hash()
    t1, fp1 = fingerprint(_parse("x + y", syms), _parse("y + x", syms), mh)
    t2, fp2 = fingerprint(_parse("2*x", syms), _parse("x + x", syms), mh)
    assert t1 == "proved_equal" and t2 == "proved_equal"
    assert fp1 == fp2  # both reduce to 0 under the same manifest -> identical fingerprint

    # a genuinely different (false) relation must NOT share that fingerprint
    t3, fp3 = fingerprint(_parse("x + y", syms), _parse("x - y", syms), mh)
    assert fp3 != fp1


def test_severity_penalises_triviality():
    trivial = assess_identity("triv", "x", "x", _mR(x="real"))
    informative = assess_identity("info", "(x+1)**2", "x**2 + 2*x + 1", _mR(x="real"))
    assert trivial.status == "SURVIVED_NOVEL" and informative.status == "SURVIVED_NOVEL"
    # x==x carries no information (raw diff has 0 ops) -> severity ~0; the expansion is informative
    assert trivial.severity == 0.0
    assert informative.severity > trivial.severity


def test_undeclared_symbol_is_inconclusive():
    # 'y' is used but not declared in the manifest -> no guessed variable nature
    art = assess_identity("undecl", "x + y", "y + x", _mR(x="real"))
    assert art.status == "INCONCLUSIVE"
    assert art.severity == 0.0


def test_unparseable_is_inconclusive():
    art = assess_identity("bad", "x +", "1", _mR(x="real"))
    assert art.status == "INCONCLUSIVE"


def test_novelty_index_rediscovery_across_runs():
    from gen.identity_research import NoveltyIndex
    m = _mR(x="real")
    idx = NoveltyIndex()
    first = assess_identity("k1", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=idx)
    assert first.status == "SURVIVED_NOVEL"
    second = assess_identity("k2", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=idx)
    assert second.status == "SURVIVED_KNOWN"
    assert second.search.match_kind == "REDISCOVERED"
    assert second.search.matched_claim_id == "k1"


def test_distinct_true_identities_are_not_mutual_rediscoveries():
    """The proved_equal |0 truth-collapse must NOT make every new true identity look
    rediscovered — REDISCOVERED is decided on the structural novelty_key (locked w/ co-architect)."""
    from gen.identity_research import NoveltyIndex
    m = _mR(x="real")
    idx = NoveltyIndex()
    a = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=idx)
    b = assess_identity("binom", "(x+1)**2", "x**2 + 2*x + 1", m, novelty_index=idx)
    assert a.status == "SURVIVED_NOVEL"
    assert b.status == "SURVIVED_NOVEL"  # a DIFFERENT theorem, not a rediscovery of pyth
    assert a.claim.novelty_key != b.claim.novelty_key
    assert a.claim.fingerprint == b.claim.fingerprint  # both truth-collapse to |0 (by design)


def test_commutative_reordered_statement_is_rediscovered():
    """cos^2+sin^2 is the SAME statement as sin^2+cos^2 (commutative) -> rediscovered."""
    from gen.identity_research import NoveltyIndex
    m = _mR(x="real")
    idx = NoveltyIndex()
    assess_identity("c1", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=idx)
    r = assess_identity("c2", "cos(x)**2 + sin(x)**2", "1", m, novelty_index=idx)
    assert r.status == "SURVIVED_KNOWN"
    assert r.claim.novelty_key == assess_identity("c3", "sin(x)**2 + cos(x)**2", "1", m).claim.novelty_key


def test_true_double_angle_survives_via_interval():
    """A true transcendental identity survives; the rigorous interval path is exercised."""
    art = assess_identity("dbl", "sin(2*x)", "2*sin(x)*cos(x)", _mR(x="real"))
    assert art.status == "SURVIVED_NOVEL"
    assert art.falsify.refutation_mode is None
    c = art.falsify.counts
    assert c.get("interval_inconclusive", 0) >= 1 or c.get("exact_zero", 0) >= 1
    assert "finite-grid" in art.falsify.coverage_claim


def test_false_transcendental_refuted_rigorously():
    """A false transcendental identity is refuted with a rigorous (non-float-tol) witness."""
    art = assess_identity("ftr", "sin(2*x)", "sin(x)", _mR(x="real"))
    assert art.status == "REFUTED"
    assert art.falsify.refutation_mode in ("exact", "interval")
    assert art.falsify.witness is not None and art.falsify.witness_residual is not None


def test_exact_rational_refutation_mode():
    """A false algebraic identity is refuted EXACTLY (no tolerance, rigorous nonzero)."""
    art = assess_identity("er", "x**2", "x**2 + 1", _mR(x="real"))
    assert art.status == "REFUTED"
    assert art.falsify.refutation_mode == "exact"
    assert art.falsify.counts.get("exact_nonzero", 0) >= 1


def test_manifest_hash_is_deterministic_and_order_independent():
    a = AssumptionManifest(domain_id="R", variables={"x": "real", "y": "real"}, predicates=("x > 0", "y > 0"))
    b = AssumptionManifest(domain_id="R", variables={"y": "real", "x": "real"}, predicates=("y > 0", "x > 0"))
    assert a.manifest_hash() == b.manifest_hash()
