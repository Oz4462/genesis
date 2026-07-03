"""Tests für Online-Novelty (math-research, Stein a).

Deterministisch/offline: der Netz-Fetcher wird gestubbt. Ehrlicher Contract:
- Volltext kann nie REDISCOVERED beweisen (höchstens NEAR_DUPLICATE).
- 0 Treffer => NOVEL nur INNERHALB der geprüften Corpora-Grenze.
- Fetch-Fehler/Offline => PRIOR_ART_UNCHECKED, NIE ein falsches NOVEL.
- Chain: stärkstes Verdikt gewinnt; PRIOR_ART_UNCHECKED schlägt NOVEL.
"""

from gen.identity_research import (
    AssumptionManifest,
    ChainedNoveltyBackend,
    NoveltyIndex,
    OnlineNoveltyBackend,
    assess_identity,
)


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_online_no_hits_is_novel_within_bound():
    be = OnlineNoveltyBackend(fetch_fn=lambda q, max_hits=5: [], corpus_id="stub")
    r = be.search("nk", "mh", "proved_equal", (), query_text="sin(x)**2 + cos(x)**2 = 1")
    assert r.match_kind == "NOVEL"
    assert "stub" in r.corpora_checked
    assert "not absolute novelty" in r.coverage_bound


def test_online_close_text_is_near_duplicate_never_rediscovered():
    q = "sin(x)**2 + cos(x)**2 = 1"
    be = OnlineNoveltyBackend(fetch_fn=lambda query, max_hits=5: [q], corpus_id="stub")
    r = be.search("nk", "mh", "proved_equal", (), query_text=q)
    assert r.match_kind == "NEAR_DUPLICATE"   # identical text -> jaccard 1.0 >= 0.85
    assert r.match_kind != "REDISCOVERED"     # text can never prove exact rediscovery


def test_online_fetch_failure_is_prior_art_unchecked_not_novel():
    def boom(q, max_hits=5):
        raise ConnectionError("simulated offline")
    be = OnlineNoveltyBackend(fetch_fn=boom, corpus_id="stub")
    r = be.search("nk", "mh", "proved_equal", (), query_text="x = x")
    assert r.match_kind == "PRIOR_ART_UNCHECKED"
    assert r.corpora_checked == ()            # failed source is NOT counted as checked
    assert "FETCH FAILED" in r.coverage_bound


def test_assess_with_failing_online_yields_novelty_unchecked():
    def boom(q, max_hits=5):
        raise TimeoutError("simulated timeout")
    online = OnlineNoveltyBackend(fetch_fn=boom, corpus_id="stub")
    art = assess_identity("u", "sin(x)**2 + cos(x)**2", "1", _mR(), novelty_index=online)
    assert art.status == "SURVIVED_NOVELTY_UNCHECKED"   # survived, but novelty not claimed
    assert art.search.match_kind == "PRIOR_ART_UNCHECKED"


def test_chained_local_rediscovery_beats_online():
    m = _mR()
    local = NoveltyIndex()
    online = OnlineNoveltyBackend(fetch_fn=lambda q, max_hits=5: [], corpus_id="stub")
    chain = ChainedNoveltyBackend([local, online])
    first = assess_identity("c1", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=chain)
    assert first.status == "SURVIVED_NOVEL"
    second = assess_identity("c2", "sin(x)**2 + cos(x)**2", "1", m, novelty_index=chain)
    assert second.status == "SURVIVED_KNOWN"            # local exact match wins over online
    assert second.search.match_kind == "REDISCOVERED"


def test_chained_unchecked_outranks_local_novel():
    """Empty local says NOVEL, but a failed online corpus must downgrade to UNCHECKED
    (we do not claim novelty just because the local index happened to be empty)."""
    def boom(q, max_hits=5):
        raise ConnectionError("offline")
    chain = ChainedNoveltyBackend([NoveltyIndex(), OnlineNoveltyBackend(fetch_fn=boom, corpus_id="stub")])
    art = assess_identity("ch", "(x+1)**2", "x**2 + 2*x + 1", _mR(), novelty_index=chain)
    assert art.search.match_kind == "PRIOR_ART_UNCHECKED"
    assert art.status == "SURVIVED_NOVELTY_UNCHECKED"
