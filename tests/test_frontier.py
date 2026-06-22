"""Unit tests for `gen.frontier.build_frontier_map` (Phase χ, GATE χ map builder).

These isolate the pure, LLM-free builder itself — distinct from the acceptance test
in test_phase_chi.py, which exercises it *through* GATE χ. Here we pin the builder's
own contract: which claims become KnownRegions, which gaps/claims become FrontierEdges,
that empty gaps are skipped, that the `confidence_threshold` knob is honored, and that
the output is deterministic (reproducibility A5 — same RunState -> same FrontierMap).

Only stdlib + `gen.core.state` constructors are used; no source is modified.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from gen.core.state import (
    Approach,
    Claim,
    ClaimStatus,
    Question,
    Report,
    RunState,
    SolutionReport,
    SourceRef,
    Specification,
)
from gen.frontier import build_frontier_map

RUN_ID = "run-χ-1"
TOPIC = "wie speichert man Wärme?"


# --- builders ----------------------------------------------------------------

def _src(cid: str) -> SourceRef:
    # Claim.__post_init__ rejects sourceless facts, so every claim needs >=1 source.
    return SourceRef(url_or_id=f"s://{cid}", retrieved=True)


def _claim(
    cid: str,
    *,
    status: ClaimStatus = ClaimStatus.VERIFIED,
    confidence: float = 0.9,
    text: str | None = None,
) -> Claim:
    return Claim(
        id=cid,
        text=text if text is not None else f"Fakt {cid}.",
        sources=[_src(cid)],
        status=status,
        confidence=confidence,
    )


def _state(claims: list[Claim] | None = None) -> RunState:
    return RunState(
        question=Question(raw=TOPIC, run_id=RUN_ID),
        claims=list(claims or []),
    )


def _report_using(*claim_ids: str, gaps: list[str] | None = None) -> Report:
    # statement_to_claim maps a human sentence -> claim_id; that's where "used" comes from.
    stmt = {f"Satz {cid}": cid for cid in claim_ids}
    return Report(
        run_id=RUN_ID,
        question=TOPIC,
        body="b",
        statement_to_claim=stmt,
        gaps=list(gaps or []),
    )


# =============================================================================
# Known-region selection
# =============================================================================

def test_used_verified_claim_becomes_known_region():
    cv = _claim("c_v")
    st = _state([cv])
    st.report = _report_using("c_v")
    fmap = build_frontier_map(st)
    assert len(fmap.known_regions) == 1
    region = fmap.known_regions[0]
    assert region.id == "region_0"
    assert region.fact_ids == ["c_v"]
    assert region.label == cv.text  # short text -> label is the full claim text


def test_verified_but_unused_claim_is_not_a_region():
    # A VERIFIED claim that no report/solution/spec asserts is NOT known territory:
    # χ maps only what the run actually built on.
    st = _state([_claim("c_v")])  # no report/solution/spec references it
    fmap = build_frontier_map(st)
    assert fmap.known_regions == []


def test_used_unverified_claim_is_not_a_region():
    st = _state([_claim("c_u", status=ClaimStatus.UNVERIFIED, confidence=0.99)])
    st.report = _report_using("c_u")
    fmap = build_frontier_map(st)
    assert fmap.known_regions == []  # unverified is never "known", however confident


def test_low_confidence_verified_claim_is_not_a_region():
    st = _state([_claim("c_low", confidence=0.5)])  # below default 0.7
    st.report = _report_using("c_low")
    fmap = build_frontier_map(st)
    assert fmap.known_regions == []


def test_used_fact_id_with_no_matching_claim_is_skipped():
    # The report references an id that isn't in state.claims -> builder must not crash,
    # and must not invent a region for a claim it cannot find.
    st = _state([])
    st.report = _report_using("c_ghost")
    fmap = build_frontier_map(st)
    assert fmap.known_regions == []


def test_region_label_truncated_to_80_chars():
    long_text = "L" * 200
    st = _state([_claim("c_long", text=long_text)])
    st.report = _report_using("c_long")
    fmap = build_frontier_map(st)
    assert fmap.known_regions[0].label == "L" * 80


def test_regions_drawn_from_solution_report_and_specification():
    # "used" ids come from three holders: report.statement_to_claim,
    # solution_report approaches (grounding+tradeoffs), spec.claim_ids_used.
    cg, ct, cs = _claim("c_g"), _claim("c_t"), _claim("c_s")
    st = _state([cg, ct, cs])
    st.solution_report = SolutionReport(
        run_id=RUN_ID,
        problem="p",
        approaches=[Approach(id="a0", name="A", grounding=["c_g"], tradeoffs=["c_t"])],
    )
    st.specification = Specification(run_id=RUN_ID, idea="i", claim_ids_used=["c_s"])
    fmap = build_frontier_map(st)
    assert [r.fact_ids[0] for r in fmap.known_regions] == ["c_g", "c_t", "c_s"]


def test_used_fact_ids_deduped_and_first_seen_order_preserved():
    # Same claim asserted by report AND spec must yield exactly one region, in first-seen order.
    c1, c2 = _claim("c_1"), _claim("c_2")
    st = _state([c1, c2])
    st.report = _report_using("c_1", "c_2")
    st.specification = Specification(
        run_id=RUN_ID, idea="i", claim_ids_used=["c_2", "c_1"]
    )
    fmap = build_frontier_map(st)
    assert [r.fact_ids[0] for r in fmap.known_regions] == ["c_1", "c_2"]
    assert [r.id for r in fmap.known_regions] == ["region_0", "region_1"]


# =============================================================================
# Frontier-edge generation
# =============================================================================

def test_report_gap_becomes_edge_grounded_in_gap_text():
    st = _state([])
    st.report = _report_using(gaps=["offene Frage X"])
    fmap = build_frontier_map(st)
    assert len(fmap.frontier_edges) == 1
    edge = fmap.frontier_edges[0]
    assert edge.id == "edge_0"
    assert edge.question == "offene Frage X"
    assert edge.grounded_in == "offene Frage X"  # the gap text IS the real grounding
    assert edge.category == "report_gap"


def test_gap_edges_from_all_three_holders_with_categories():
    st = _state([])
    st.report = _report_using(gaps=["g_report"])
    st.solution_report = SolutionReport(
        run_id=RUN_ID,
        problem="p",
        approaches=[Approach(id="a0", name="A", grounding=["x"])],
        gaps=["g_approach"],
    )
    st.specification = Specification(run_id=RUN_ID, idea="i", gaps=["g_spec"])
    fmap = build_frontier_map(st)
    by_ground = {e.grounded_in: e.category for e in fmap.frontier_edges}
    assert by_ground == {
        "g_report": "report_gap",
        "g_approach": "approach_gap",
        "g_spec": "spec_gap",
    }


def test_empty_and_whitespace_gaps_are_skipped():
    st = _state([])
    st.report = _report_using(gaps=["", "   ", "\t\n", "echte Lücke"])
    fmap = build_frontier_map(st)
    grounds = [e.grounded_in for e in fmap.frontier_edges]
    assert grounds == ["echte Lücke"]  # only the real gap survives


def test_refuted_and_unsupported_claims_become_edges():
    cr = _claim("c_r", status=ClaimStatus.REFUTED, confidence=0.0)
    cu = _claim("c_u", status=ClaimStatus.UNSUPPORTED, confidence=0.0)
    st = _state([cr, cu])
    fmap = build_frontier_map(st)
    edges = {e.grounded_in: e for e in fmap.frontier_edges}
    assert set(edges) == {"c_r", "c_u"}  # the un-established claim id is the grounding
    assert edges["c_r"].category == ClaimStatus.REFUTED.value == "refuted"
    assert edges["c_u"].category == ClaimStatus.UNSUPPORTED.value == "unsupported"
    assert edges["c_r"].question == cr.text


def test_verified_and_unverified_claims_are_not_edges():
    # Only REFUTED/UNSUPPORTED claims are frontier (open) edges; VERIFIED is known,
    # UNVERIFIED is simply not yet mapped — neither is an open question here.
    st = _state(
        [
            _claim("c_v", status=ClaimStatus.VERIFIED),
            _claim("c_n", status=ClaimStatus.UNVERIFIED),
        ]
    )
    fmap = build_frontier_map(st)
    assert fmap.frontier_edges == []


def test_edge_ids_are_sequential_across_gaps_then_claims():
    st = _state([_claim("c_u", status=ClaimStatus.UNSUPPORTED, confidence=0.0)])
    st.report = _report_using(gaps=["g1", "g2"])
    fmap = build_frontier_map(st)
    # two gap edges, then one claim edge -> ids 0,1,2 with no gaps in numbering
    assert [e.id for e in fmap.frontier_edges] == ["edge_0", "edge_1", "edge_2"]
    assert [e.grounded_in for e in fmap.frontier_edges] == ["g1", "g2", "c_u"]


def test_long_gap_question_truncated_to_200():
    st = _state([])
    long_gap = "G" * 500
    st.report = _report_using(gaps=[long_gap])
    fmap = build_frontier_map(st)
    edge = fmap.frontier_edges[0]
    assert edge.question == "G" * 200       # question label is clipped
    assert edge.grounded_in == long_gap     # but grounding keeps the full real gap text


# =============================================================================
# confidence_threshold parameter
# =============================================================================

def test_confidence_threshold_boundary_is_inclusive():
    # A claim exactly at the threshold counts as known (>=, not >).
    st = _state([_claim("c_edge", confidence=0.7)])
    st.report = _report_using("c_edge")
    assert len(build_frontier_map(st).known_regions) == 1
    assert len(build_frontier_map(st, confidence_threshold=0.70001).known_regions) == 0


def test_lower_threshold_admits_more_regions():
    st = _state([_claim("c_mid", confidence=0.6)])
    st.report = _report_using("c_mid")
    assert build_frontier_map(st).known_regions == []                 # default 0.7 excludes
    assert len(build_frontier_map(st, confidence_threshold=0.5).known_regions) == 1


def test_threshold_does_not_affect_edges():
    # confidence_threshold gates KNOWN regions only; REFUTED/UNSUPPORTED edges are
    # status-driven and independent of it.
    st = _state([_claim("c_u", status=ClaimStatus.UNSUPPORTED, confidence=0.0)])
    low = build_frontier_map(st, confidence_threshold=0.1)
    high = build_frontier_map(st, confidence_threshold=0.99)
    assert [e.grounded_in for e in low.frontier_edges] == ["c_u"]
    assert [e.grounded_in for e in high.frontier_edges] == ["c_u"]


# =============================================================================
# Map-level metadata, abstention, determinism
# =============================================================================

def test_map_carries_run_id_topic_and_producer():
    fmap = build_frontier_map(_state([]))
    assert fmap.run_id == RUN_ID
    assert fmap.topic == TOPIC
    assert fmap.produced_by == "cartographer"


def test_empty_run_yields_empty_map_as_abstention():
    # No report/solution/spec and no claims -> honest empty map (valid abstention).
    fmap = build_frontier_map(_state([]))
    assert fmap.known_regions == []
    assert fmap.frontier_edges == []


def test_deterministic_same_state_same_content():
    cv = _claim("c_v")
    cu = _claim("c_u", status=ClaimStatus.UNSUPPORTED, confidence=0.0)
    st = _state([cv, cu])
    st.report = _report_using("c_v", gaps=["offene Frage X"])
    first = build_frontier_map(st)
    second = build_frontier_map(st)
    # created_at is metadata (like Claim); the mapped content must be identical.
    assert first.run_id == second.run_id and first.topic == second.topic
    assert first.known_regions == second.known_regions
    assert first.frontier_edges == second.frontier_edges


# =============================================================================
# Property-based invariants
# =============================================================================

@given(
    confidences=st.lists(
        st.floats(min_value=0.0, max_value=1.0), min_size=0, max_size=12
    ),
    threshold=st.floats(min_value=0.0, max_value=1.0),
)
def test_region_count_equals_used_verified_at_or_above_threshold(confidences, threshold):
    # INVARIANT: a region exists for exactly those USED VERIFIED claims whose
    # confidence is >= threshold — no more, no fewer.
    ids = [f"c_{i}" for i in range(len(confidences))]
    claims = [_claim(cid, confidence=conf) for cid, conf in zip(ids, confidences)]
    st = _state(claims)
    st.report = _report_using(*ids)  # all are "used"
    fmap = build_frontier_map(st, confidence_threshold=threshold)
    expected = sum(1 for conf in confidences if conf >= threshold)
    assert len(fmap.known_regions) == expected
    # ids are assigned densely region_0..region_{n-1}
    assert [r.id for r in fmap.known_regions] == [
        f"region_{i}" for i in range(expected)
    ]


@given(
    confidences=st.lists(
        st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=10
    ),
    lo=st.floats(min_value=0.0, max_value=1.0),
    hi=st.floats(min_value=0.0, max_value=1.0),
)
def test_region_count_monotonic_in_threshold(confidences, lo, hi):
    # INVARIANT: raising the threshold can only remove known regions, never add them.
    lo, hi = min(lo, hi), max(lo, hi)
    ids = [f"c_{i}" for i in range(len(confidences))]
    claims = [_claim(cid, confidence=conf) for cid, conf in zip(ids, confidences)]
    st = _state(claims)
    st.report = _report_using(*ids)
    n_lo = len(build_frontier_map(st, confidence_threshold=lo).known_regions)
    n_hi = len(build_frontier_map(st, confidence_threshold=hi).known_regions)
    assert n_hi <= n_lo


@given(
    gaps=st.lists(
        st.sampled_from(["", "   ", "\t", "real gap", "another gap"]),
        min_size=0,
        max_size=10,
    )
)
def test_every_edge_has_nonblank_grounding(gaps):
    # INVARIANT: the builder never emits an edge whose grounding is blank — blank gaps
    # are dropped (and FrontierEdge's own constructor would reject one anyway).
    st = _state([])
    st.report = _report_using(gaps=gaps)
    fmap = build_frontier_map(st)
    assert all(e.grounded_in.strip() for e in fmap.frontier_edges)
    assert len(fmap.frontier_edges) == sum(1 for g in gaps if g.strip())
