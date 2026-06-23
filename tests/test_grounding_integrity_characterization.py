"""Characterization / facade-detector for grounding_integrity (depth-audit T04).

This is the authoritative facade-detector for the two graph-level integrity checks; the
legacy tests/test_grounding_integrity.py stays untouched. Every test here proves the headline
output is genuinely DERIVED from the input — i.e. the rates and ok flags MOVE when a driving
input field changes — rather than echoing a canned constant, plus the mandatory negative path.

Headline #1 (corroboration_independence): a VERIFIED claim whose verification sources REUSE any
original source is flagged circular (corroboration not independent); fully-disjoint verification
is clean; the independent_rate is computed from the verified population.

Headline #2 (report_grounding): every Report statement->claim sentence must map to a real,
non-REFUTED claim; dangling (missing) and refuted-backed sentences are flagged and coverage
reported.

Property-based invariants pin the partition/ratio contracts across the whole input space.

Run:  pytest tests/test_grounding_integrity_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hypothesis import given, strategies as st  # noqa: E402

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Report,
    SourceRef,
    SourceSupport,
)
from gen.grounding_integrity import (  # noqa: E402
    CorroborationReport,
    GroundingCoverage,
    corroboration_independence,
    report_grounding,
)


def _src(url: str) -> SourceRef:
    return SourceRef(url, True, support=SourceSupport.SUPPORTS)


def _claim(cid: str, status: ClaimStatus, sources: list[str], verification: list[str]) -> Claim:
    return Claim(
        id=cid,
        text=f"claim {cid}",
        sources=[_src(u) for u in sources],
        status=status,
        verification=[_src(u) for u in verification],
    )


def _report(mapping: dict[str, str]) -> Report:
    return Report(run_id="r", question="?", body="...", statement_to_claim=mapping)


# === Headline #1: corroboration independence ==================================

def test_circular_when_verification_reuses_an_original_source():
    """A VERIFIED claim whose verification re-cites one of its own sources is circular."""
    c = _claim("x", ClaimStatus.VERIFIED, sources=["https://a"], verification=["https://a"])
    rep = corroboration_independence([c])
    assert rep.n_verified == 1
    assert rep.circular == ["x"]
    assert rep.ok is False
    assert rep.independent_rate == 0.0


def test_independent_when_verification_is_disjoint():
    """Disjoint verification sources => genuine cross-corroboration, not flagged."""
    c = _claim("x", ClaimStatus.VERIFIED, sources=["https://a"], verification=["https://b"])
    rep = corroboration_independence([c])
    assert rep.circular == []
    assert rep.ok is True
    assert rep.independent_rate == 1.0


def test_partial_reuse_is_still_flagged_strict_disjointness():
    """ANY reused source (even alongside a new one) breaks independence — strict disjointness.

    Proves the contract is set-overlap, not "has at least one new source".
    """
    c = _claim("x", ClaimStatus.VERIFIED, sources=["https://a", "https://b"],
               verification=["https://b", "https://c"])  # 'b' reused
    rep = corroboration_independence([c])
    assert rep.circular == ["x"]
    assert rep.ok is False


def test_independent_rate_moves_with_input_facade_killer():
    """The rate is computed from the verified population, not a constant.

    Same two claim ids, only the verification source flipped between reuse and disjoint;
    the rate must move 0.5 -> 1.0 and ok False -> True.
    """
    circular = _claim("c1", ClaimStatus.VERIFIED, sources=["https://a"], verification=["https://a"])
    clean = _claim("c2", ClaimStatus.VERIFIED, sources=["https://x"], verification=["https://y"])
    mixed = corroboration_independence([circular, clean])
    assert mixed.n_verified == 2
    assert mixed.circular == ["c1"]
    assert mixed.independent_rate == 0.5
    assert mixed.ok is False

    # Flip the one driving field (c1's verification source) to a fresh one -> all independent.
    repaired = _claim("c1", ClaimStatus.VERIFIED, sources=["https://a"], verification=["https://z"])
    allclean = corroboration_independence([repaired, clean])
    assert allclean.circular == []
    assert allclean.independent_rate == 1.0
    assert allclean.ok is True


def test_only_verified_claims_are_audited():
    """Non-VERIFIED claims are out of scope even when their verification reuses a source.

    A REFUTED/UNVERIFIED/UNSUPPORTED claim must not be counted or flagged — the property
    "verified means something" only constrains VERIFIED claims.
    """
    reused = ["https://a"]
    others = [
        _claim("u", ClaimStatus.UNVERIFIED, sources=reused, verification=reused),
        _claim("r", ClaimStatus.REFUTED, sources=reused, verification=reused),
        _claim("n", ClaimStatus.UNSUPPORTED, sources=reused, verification=reused),
    ]
    rep = corroboration_independence(others)
    assert rep.n_verified == 0
    assert rep.circular == []
    assert rep.ok is True


def test_no_verified_claims_abstains():
    """NEGATIVE/abstention: with nothing to audit the rate is the honest vacuous 1.0, ok."""
    assert corroboration_independence([]).independent_rate == 1.0
    assert corroboration_independence([]).ok is True
    only_unverified = [_claim("u", ClaimStatus.UNVERIFIED, ["https://a"], [])]
    rep = corroboration_independence(only_unverified)
    assert rep.n_verified == 0 and rep.ok is True and rep.independent_rate == 1.0


# === Headline #2: report grounding coverage ===================================

def test_dangling_sentence_is_flagged_negative():
    """NEGATIVE: a sentence mapped to a claim id absent from the ledger is dangling."""
    real = _claim("c_real", ClaimStatus.VERIFIED, ["https://a"], ["https://b"])
    cov = report_grounding(_report({"Invented fact.": "c_missing"}), [real])
    assert cov.dangling == [("Invented fact.", "c_missing")]
    assert cov.refuted_backed == []
    assert cov.ok is False
    assert cov.coverage == 0.0


def test_refuted_backed_sentence_is_flagged_negative():
    """NEGATIVE: a sentence backed by a REFUTED claim is a contradiction asserted as fact."""
    refuted = _claim("c_bad", ClaimStatus.REFUTED, ["https://a"], [])
    cov = report_grounding(_report({"A refuted thing.": "c_bad"}), [refuted])
    assert cov.refuted_backed == [("A refuted thing.", "c_bad")]
    assert cov.dangling == []
    assert cov.ok is False
    assert cov.coverage == 0.0


def test_non_refuted_statuses_count_as_grounded():
    """UNVERIFIED and UNSUPPORTED claims are 'non-refuted' => grounded (per the documented
    FActScore 'real, non-refuted claim' contract). Only REFUTED/missing break grounding."""
    claims = [
        _claim("v", ClaimStatus.VERIFIED, ["https://a"], ["https://b"]),
        _claim("u", ClaimStatus.UNVERIFIED, ["https://a"], []),
        _claim("n", ClaimStatus.UNSUPPORTED, ["https://a"], []),
    ]
    cov = report_grounding(_report({"S1.": "v", "S2.": "u", "S3.": "n"}), claims)
    assert cov.n_grounded == 3
    assert cov.coverage == 1.0
    assert cov.ok is True


def test_coverage_moves_with_input_facade_killer():
    """Coverage is n_grounded/n_statements, derived from the map — not a constant.

    Start with 1 of 4 statements sound (coverage 0.25), then repoint the three bad
    sentences at a sound claim and coverage must climb to 1.0 with ok flipping True.
    """
    sound = _claim("ok", ClaimStatus.VERIFIED, ["https://a"], ["https://b"])
    refuted = _claim("bad", ClaimStatus.REFUTED, ["https://a"], [])
    partial = _report({
        "good": "ok",
        "dead1": "missing1",
        "dead2": "missing2",
        "contradiction": "bad",
    })
    cov = report_grounding(partial, [sound, refuted])
    assert cov.n_statements == 4
    assert cov.n_grounded == 1
    assert cov.coverage == 0.25
    assert len(cov.dangling) == 2 and len(cov.refuted_backed) == 1
    assert cov.ok is False

    repaired = _report({"good": "ok", "dead1": "ok", "dead2": "ok", "contradiction": "ok"})
    cov2 = report_grounding(repaired, [sound, refuted])
    assert cov2.coverage == 1.0
    assert cov2.ok is True


def test_empty_report_abstains():
    """NEGATIVE/abstention: a report with no mapped sentences is vacuously fully covered."""
    cov = report_grounding(_report({}), [])
    assert cov.n_statements == 0
    assert cov.coverage == 1.0
    assert cov.ok is True


def test_report_grounding_is_deterministic():
    sound = _claim("ok", ClaimStatus.VERIFIED, ["https://a"], ["https://b"])
    rep = _report({"good": "ok", "dead": "missing"})
    a = report_grounding(rep, [sound])
    b = report_grounding(rep, [sound])
    assert (a.n_grounded, a.dangling, a.refuted_backed, a.coverage) == (
        b.n_grounded, b.dangling, b.refuted_backed, b.coverage)


# === Property-based invariants ================================================

# Each verified claim is constructed with a known "reuse" flag; corroboration_independence
# must flag exactly the reusing claims and the rate must equal the closed-form ratio.
@given(flags=st.lists(st.booleans(), min_size=0, max_size=12))
def test_property_circular_count_matches_constructed_reuse(flags: list[bool]):
    claims = []
    for i, reuse in enumerate(flags):
        own = f"https://own/{i}"
        verif = own if reuse else f"https://new/{i}"  # reuse => same url as a source
        claims.append(_claim(f"c{i}", ClaimStatus.VERIFIED, [own], [verif]))
    rep = corroboration_independence(claims)
    expected_circular = sum(1 for f in flags if f)
    assert rep.n_verified == len(flags)
    assert len(rep.circular) == expected_circular
    # Closed-form ratio + bounds + ok/flag consistency.
    if flags:
        assert rep.independent_rate == (len(flags) - expected_circular) / len(flags)
    else:
        assert rep.independent_rate == 1.0
    assert 0.0 <= rep.independent_rate <= 1.0
    assert rep.ok is (expected_circular == 0)


# report_grounding must PARTITION every statement into exactly one of
# grounded / dangling / refuted_backed, and coverage must equal the ratio.
_BUCKET = st.sampled_from(["grounded", "dangling", "refuted"])


@given(buckets=st.lists(_BUCKET, min_size=0, max_size=15))
def test_property_statements_partition_and_coverage(buckets: list[str]):
    claims: list[Claim] = []
    mapping: dict[str, str] = {}
    for i, bucket in enumerate(buckets):
        sentence = f"sentence #{i}"  # unique key per statement
        if bucket == "grounded":
            cid = f"g{i}"
            claims.append(_claim(cid, ClaimStatus.VERIFIED, ["https://a"], ["https://b"]))
            mapping[sentence] = cid
        elif bucket == "refuted":
            cid = f"r{i}"
            claims.append(_claim(cid, ClaimStatus.REFUTED, ["https://a"], []))
            mapping[sentence] = cid
        else:  # dangling -> id never added to claims
            mapping[sentence] = f"missing{i}"

    cov = report_grounding(_report(mapping), claims)
    n = len(buckets)
    # Conservation: the three buckets partition all statements exactly once.
    assert cov.n_grounded + len(cov.dangling) + len(cov.refuted_backed) == n
    assert cov.n_statements == n
    assert cov.n_grounded == sum(1 for b in buckets if b == "grounded")
    assert len(cov.dangling) == sum(1 for b in buckets if b == "dangling")
    assert len(cov.refuted_backed) == sum(1 for b in buckets if b == "refuted")
    assert cov.coverage == (cov.n_grounded / n if n else 1.0)
    assert 0.0 <= cov.coverage <= 1.0
    assert cov.ok is (not cov.dangling and not cov.refuted_backed)


def test_dataclasses_expose_documented_surface():
    """Smoke that the public report dataclasses keep their documented field/property names."""
    cr = CorroborationReport(n_verified=0)
    assert cr.ok and cr.independent_rate == 1.0
    gc = GroundingCoverage(n_statements=0, n_grounded=0)
    assert gc.ok and gc.coverage == 1.0
