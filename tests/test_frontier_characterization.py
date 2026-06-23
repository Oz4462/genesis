"""Depth-audit / characterization for `gen.frontier.build_frontier_map` (Phase χ).

This is a FACADE-KILLER, not a smoke test. The χ contract claims build_frontier_map is a
*genuine input-driven synthesis* of a run's already-gated outputs (HORIZON §2C) — never a
canned map. To prove that here we assert, beyond the legacy unit test:

  (a) the headline claim REALLY holds against a cross-check: the map is a pure FUNCTION of
      the RunState — every region/edge it emits is traceable to a real input field, and the
      output changes MEANINGFULLY when a driving input changes (different claims/gaps/topic
      ⇒ different map). A canned builder would ignore its input; this one cannot.
  (b) a mandatory NEGATIVE path fires the documented fail-loud guard EXACTLY: the builder
      relies on FrontierEdge's own ValueError to forbid an invented (blank-grounded) edge,
      and proves that its empty-gap *skip* is the only thing standing between a real run and
      that exception — so removing the skip would crash, not silently fabricate.

Only stdlib + `gen.core.state` constructors are used. `gen.frontier` reads as REAL on
inspection, so no source is modified (see docs/audit/DEPTH_AUDIT_frontier.md).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gen.core.state import (
    Approach,
    Claim,
    ClaimStatus,
    FrontierEdge,
    Question,
    Report,
    RunState,
    SolutionReport,
    SourceRef,
    Specification,
)
from gen.frontier import build_frontier_map

RUN_ID = "run-χ-char"
TOPIC = "wie speichert man Wärme über Tage?"


# --- builders ----------------------------------------------------------------

def _src(cid: str) -> SourceRef:
    # Claim.__post_init__ forbids a sourceless fact, so every claim carries >=1 source.
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


def _state(claims: list[Claim] | None = None, *, run_id: str = RUN_ID, topic: str = TOPIC) -> RunState:
    return RunState(question=Question(raw=topic, run_id=run_id), claims=list(claims or []))


def _report_using(*claim_ids: str, gaps: list[str] | None = None) -> Report:
    return Report(
        run_id=RUN_ID,
        question=TOPIC,
        body="b",
        statement_to_claim={f"Satz {cid}": cid for cid in claim_ids},
        gaps=list(gaps or []),
    )


# =============================================================================
# (a) HEADLINE: the map is an input-driven synthesis, not a canned constant
# =============================================================================

def test_different_runs_yield_meaningfully_different_maps():
    """Two distinct runs MUST produce distinct maps — the killer test against a canned map.

    A facade that returned a fixed/templated map would emit identical content for both.
    """
    # Run A: a used VERIFIED claim (region) + a report gap (edge).
    a = _state([_claim("a_v", text="Schmelzwärme von Paraffin ist hoch.")])
    a.report = _report_using("a_v", gaps=["Langzeit-Degradation unbekannt"])
    map_a = build_frontier_map(a)

    # Run B: a different used claim + a REFUTED claim (edge), no report gap.
    b = _state(
        [
            _claim("b_v", text="Wassertank speichert sensible Wärme."),
            _claim("b_r", status=ClaimStatus.REFUTED, confidence=0.0, text="Perpetuum mobile speichert Wärme verlustfrei."),
        ],
        run_id="run-other",
        topic="anderes Thema",
    )
    b.specification = Specification(run_id="run-other", idea="i", claim_ids_used=["b_v"])
    map_b = build_frontier_map(b)

    # Metadata flows from input, not a template.
    assert (map_a.run_id, map_a.topic) == (RUN_ID, TOPIC)
    assert (map_b.run_id, map_b.topic) == ("run-other", "anderes Thema")
    assert map_a.run_id != map_b.run_id and map_a.topic != map_b.topic

    # Region labels are the actual claim texts of THIS run, not a fixed string.
    assert [r.label for r in map_a.known_regions] == ["Schmelzwärme von Paraffin ist hoch."]
    assert [r.label for r in map_b.known_regions] == ["Wassertank speichert sensible Wärme."]

    # Edges trace to THIS run's real gaps / un-established claims, and differ.
    assert [e.grounded_in for e in map_a.frontier_edges] == ["Langzeit-Degradation unbekannt"]
    assert [e.grounded_in for e in map_b.frontier_edges] == ["b_r"]


def test_every_emitted_region_and_edge_traces_to_a_real_input_field():
    """No region/edge may exist that is not backed by a concrete RunState field (no invention)."""
    cv = _claim("c_v", text="Belegt.")
    cr = _claim("c_r", status=ClaimStatus.REFUTED, confidence=0.0)
    st = _state([cv, cr])
    st.report = _report_using("c_v", gaps=["echte Lücke"])
    fmap = build_frontier_map(st)

    used_ids = set(st.report.statement_to_claim.values())
    for region in fmap.known_regions:
        # every region's fact id is a claim that the run actually USED (here: via the report)
        assert set(region.fact_ids) <= used_ids
        assert region.label == cv.text  # label is the claim's real text, not a placeholder

    real_grounds = set(st.report.gaps) | {c.id for c in st.claims if c.status in (ClaimStatus.REFUTED, ClaimStatus.UNSUPPORTED)}
    for edge in fmap.frontier_edges:
        assert edge.grounded_in in real_grounds  # never an invented neighbourhood


def test_changing_a_driving_claim_text_changes_the_region_label():
    """The region label is genuinely READ from the claim — perturb the input, output moves."""
    st1 = _state([_claim("c", text="Alpha")])
    st1.report = _report_using("c")
    st2 = _state([_claim("c", text="Omega")])
    st2.report = _report_using("c")
    assert build_frontier_map(st1).known_regions[0].label == "Alpha"
    assert build_frontier_map(st2).known_regions[0].label == "Omega"


def test_dropping_the_report_drops_the_region():
    """A VERIFIED claim is 'known territory' ONLY because a gated phase USED it.

    Remove the only thing that used it ⇒ the region disappears. Proves the report drives the
    region, instead of every VERIFIED claim being canned into the map.
    """
    cv = _claim("c_v")
    used = _state([cv])
    used.report = _report_using("c_v")
    assert len(build_frontier_map(used).known_regions) == 1

    unused = _state([cv])  # identical claim, but nothing asserts it
    assert build_frontier_map(unused).known_regions == []


def test_synthesis_genuinely_spans_all_three_gated_holders():
    """Regions are drawn from report + solution_report + specification — the real β/γ chain."""
    cr, cg, ct, cs = _claim("c_r"), _claim("c_g"), _claim("c_t"), _claim("c_s")
    st = _state([cr, cg, ct, cs])
    st.report = _report_using("c_r")
    st.solution_report = SolutionReport(
        run_id=RUN_ID,
        problem="p",
        approaches=[Approach(id="a0", name="A", grounding=["c_g"], tradeoffs=["c_t"])],
    )
    st.specification = Specification(run_id=RUN_ID, idea="i", claim_ids_used=["c_s"])
    fmap = build_frontier_map(st)
    # first-seen order across the three holders, deduped — proves all three are consumed.
    assert [r.fact_ids[0] for r in fmap.known_regions] == ["c_r", "c_g", "c_t", "c_s"]


def test_deterministic_same_state_same_content():
    """A5 reproducibility: same RunState ⇒ identical mapped content (created_at aside)."""
    st = _state([_claim("c_v"), _claim("c_u", status=ClaimStatus.UNSUPPORTED, confidence=0.0)])
    st.report = _report_using("c_v", gaps=["offene Frage"])
    first, second = build_frontier_map(st), build_frontier_map(st)
    assert first.run_id == second.run_id and first.topic == second.topic
    assert first.known_regions == second.known_regions
    assert first.frontier_edges == second.frontier_edges


# =============================================================================
# (b) NEGATIVE: the documented fail-loud guard fires EXACTLY, and the skip is real
# =============================================================================

def test_frontieredge_guard_rejects_an_invented_blank_edge():
    """The builder leans on FrontierEdge's OWN guard to forbid an invented edge.

    Documented fail-loud (state.py §2C): a blank question/grounded_in is structurally
    impossible. This proves the guard the builder depends on actually fires.
    """
    with pytest.raises(ValueError, match="non-empty question and grounded_in"):
        FrontierEdge(id="edge_x", question="real?", grounded_in="   ")
    with pytest.raises(ValueError, match="non-empty question and grounded_in"):
        FrontierEdge(id="edge_y", question="", grounded_in="real gap")


def test_empty_gaps_are_skipped_so_no_invented_edge_is_built():
    """The builder's skip is the ONLY thing between a real run and the FrontierEdge ValueError.

    A report can legitimately carry empty/whitespace gap strings (an unfilled slot). The
    builder must DROP them — neither crash nor fabricate an edge from nothing.
    """
    st = _state([])
    st.report = _report_using(gaps=["", "   ", "\t\n", "echte Lücke"])
    fmap = build_frontier_map(st)  # must NOT raise despite the blank gaps
    assert [e.grounded_in for e in fmap.frontier_edges] == ["echte Lücke"]


def test_empty_run_is_honest_abstention_not_a_fabricated_map():
    """No gated outputs ⇒ an honestly EMPTY map (valid χ abstention), never invented content."""
    fmap = build_frontier_map(_state([]))
    assert fmap.known_regions == [] and fmap.frontier_edges == []
    assert fmap.produced_by == "cartographer"


# =============================================================================
# Property-based invariants (synthesis is a faithful function of its input)
# =============================================================================

@given(
    statuses=st.lists(
        st.sampled_from(list(ClaimStatus)), min_size=0, max_size=12
    )
)
def test_edge_count_equals_open_claims_when_unused(statuses):
    """INVARIANT: with no report/solution/spec, exactly the REFUTED+UNSUPPORTED claims
    become edges — VERIFIED/UNVERIFIED never do. The map is a faithful tally of the input.
    """
    claims = [_claim(f"c_{i}", status=s, confidence=0.0) for i, s in enumerate(statuses)]
    st = _state(claims)
    fmap = build_frontier_map(st)
    expected_open = sum(
        1 for s in statuses if s in (ClaimStatus.REFUTED, ClaimStatus.UNSUPPORTED)
    )
    assert len(fmap.frontier_edges) == expected_open
    assert fmap.known_regions == []  # nothing is "used", so nothing is known territory
    # every emitted edge id is dense and every grounding is a real claim id
    assert [e.id for e in fmap.frontier_edges] == [f"edge_{i}" for i in range(expected_open)]
    assert all(e.grounded_in.startswith("c_") for e in fmap.frontier_edges)


@given(
    gaps=st.lists(
        st.sampled_from(["", " ", "\t", "Lücke A", "Lücke B"]), min_size=0, max_size=10
    )
)
def test_edges_are_exactly_the_nonblank_gaps(gaps):
    """INVARIANT: report gaps ⇒ edges iff non-blank; never more, never fewer, never invented."""
    st = _state([])
    st.report = _report_using(gaps=gaps)
    fmap = build_frontier_map(st)
    assert [e.grounded_in for e in fmap.frontier_edges] == [g for g in gaps if g.strip()]
    assert all(e.grounded_in.strip() for e in fmap.frontier_edges)
