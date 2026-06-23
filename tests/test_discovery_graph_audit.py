"""Depth audit (T04) of ``gen.discovery.graph`` — does the Discovery Graph REALLY do what
its docstring claims, or is it a facade?

Three headline claims are characterised here, each with a NEGATIVE counter-case:

1.  **Dedup collapses re-discoveries.** The same dimensional signature, judged twice, must
    land on ONE node (``encounters`` rises, provenance merges) — never a duplicate.
    NEGATIVE: a genuinely different exponent signature must NOT merge into it.
2.  **Stable, collision-resistant fingerprint.** The fingerprint depends only on the
    canonical (rounded, order-independent, zero-stripped) signature; distinct signatures
    map to distinct fingerprints (proven collision-free over a Hypothesis sample).
3.  **Lossless, deterministic Anhang-C record.** ``to_record`` / ``to_ledger_records``
    emit the full Anhang-C schema and round-trip through JSON byte-for-byte; the timestamp
    is whatever the caller passed (``None`` when omitted) — never minted.

These are behaviour assertions: if the implementation were gutted, they fail.
"""

import json
import math

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from gen.discovery import (
    Constant,
    DiscoveryGraph,
    DiscoveryProblem,
    Variable,
    discover_new_formulas,
)
from gen.discovery.engine import Candidate, DiscoveryVerdict
from gen.discovery.graph import GraphNode, fingerprint, _signature

MU_SUN = 1.32712440018e20


# --------------------------------------------------------------------------- helpers


def _make_verdict(
    exponents: dict[str, float],
    *,
    verdict: str = "bestaetigt",
    expression: str = "T = C·a^1.5",
    delta: float = 0.0,
    gates: dict | None = None,
) -> DiscoveryVerdict:
    """A fully-formed verdict with caller-controlled exponents — lets the fingerprint and
    dedup behaviour be tested in isolation, without re-running the (data-dependent) engine."""
    cand = Candidate(
        expression=expression,
        exponents=dict(exponents),
        coefficient=1.0,
        r_squared=0.999,
        rmse=0.01,
        complexity=sum(1 for p in exponents.values() if abs(p) >= 1e-9),
        dimension_ok=True,
        dimension_residual=0.0,
        dimension_corroborated=True,
    )
    return DiscoveryVerdict(
        candidate=cand,
        passed=True,
        verdict=verdict,
        gates=gates if gates is not None else {"r2": {"ok": True, "value": 0.999}},
        delta_to_consensus=delta,
    )


def _kepler_result():
    """A real discovery run (Kepler's third law) — for the integration-level dedup claims."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a**1.5 / math.sqrt(MU_SUN)
    return discover_new_formulas(
        DiscoveryProblem(
            idea="Kepler",
            target=Variable("T", "s", tuple(T)),
            inputs=(Variable("a", "m", tuple(a)),),
            constants=(Constant("mu", MU_SUN, "m^3/s^2"),),
            run_id="audit-001",
        )
    )


# --------------------------------------------------------------- claim 1: dedup collapse


def test_same_signature_added_twice_collapses_to_one_node():
    """Re-adding the IDENTICAL signature must not create a second node — it increments the
    encounter count and merges provenance. This is the graph's whole reason to exist."""
    g = DiscoveryGraph()
    v = _make_verdict({"a": 1.5, "mu": -0.5})
    first = g.add_verdict(v, idea="Kepler", target_name="T", provenance=("run-1",))
    assert len(g) == 1 and first.encounters == 1

    second = g.add_verdict(v, idea="Kepler", target_name="T", provenance=("run-2",))
    assert len(g) == 1                               # NO duplicate node
    assert second.id == first.id                     # same fingerprint -> same node
    assert second.encounters == 2                    # encounter incremented
    assert second.provenance == ("run-1", "run-2")   # provenance merged, in order


def test_repeated_rediscovery_never_duplicates_and_merges_dedup_provenance():
    """N re-encounters -> still ONE node, encounters == N, and duplicate provenance entries
    are de-duplicated (dict.fromkeys order-preserving merge), never appended blindly."""
    g = DiscoveryGraph()
    v = _make_verdict({"a": 1.5, "mu": -0.5})
    for i in range(5):
        # 'shared' repeats every time -> must appear exactly once; 'run-i' is unique per add
        g.add_verdict(v, idea="Kepler", target_name="T", provenance=("shared", f"run-{i}"))
    assert len(g) == 1
    node = g.nodes()[0]
    assert node.encounters == 5
    assert node.provenance.count("shared") == 1
    assert node.provenance == ("shared", "run-0", "run-1", "run-2", "run-3", "run-4")


def test_real_engine_rediscovery_collapses():
    """End-to-end: the SAME law discovered twice from the same data dedups to one confirmed
    node with encounters >= 2 — the docstring's 'verhindert doppelte Neu-Entdeckung'."""
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T", provenance=("run-1",))
    n_after_first = len(g)
    g.add_result(_kepler_result(), target_name="T", provenance=("run-2",))
    assert len(g) == n_after_first
    confirmed = g.confirmed()
    assert confirmed and confirmed[0].encounters >= 2
    assert "run-1" in confirmed[0].provenance and "run-2" in confirmed[0].provenance


# ---------------------------------------------------- claim 1 NEGATIVE: distinct laws split


def test_different_signature_does_not_merge_into_a_known_node():
    """NEGATIVE: a candidate whose exponents differ must stay a SEPARATE node — distinct
    laws are never collapsed together (otherwise the dedup would erase real discoveries)."""
    g = DiscoveryGraph()
    g.add_verdict(_make_verdict({"a": 1.5, "mu": -0.5}), idea="i", target_name="T")
    g.add_verdict(_make_verdict({"a": 2.0, "mu": -0.5}), idea="i", target_name="T")
    assert len(g) == 2                               # two genuinely different laws -> two nodes
    ids = {n.id for n in g.nodes()}
    assert len(ids) == 2


def test_is_known_is_signature_exact():
    """The rediscovery guard recognises the exact signature and ONLY that — a different
    exponent (even on the same target) is reported unknown."""
    g = DiscoveryGraph()
    g.add_verdict(_make_verdict({"a": 1.5, "mu": -0.5}), idea="i", target_name="T")
    assert g.is_known("T", {"a": 1.5, "mu": -0.5})
    assert not g.is_known("T", {"a": 2.0, "mu": -0.5})   # different exponent
    assert not g.is_known("P", {"a": 1.5, "mu": -0.5})   # different target


# ------------------------------------------------ claim 2: fingerprint stability & collisions


def test_fingerprint_is_stable_and_canonical():
    """Same signature -> same fingerprint, regardless of dict order or zero-exponent padding
    (zeros below 1e-9 are dropped). A 16-hex-char digest as documented."""
    fp = fingerprint("T", {"a": 1.5, "mu": -0.5})
    assert fp == fingerprint("T", {"mu": -0.5, "a": 1.5})          # order-independent
    assert fp == fingerprint("T", {"a": 1.5, "mu": -0.5, "x": 0.0})  # zero dropped
    assert fp == fingerprint("T", {"a": 1.5000000001, "mu": -0.5})   # rounded at 6dp
    assert len(fp) == 16 and all(c in "0123456789abcdef" for c in fp)


def test_fingerprint_separates_distinct_signatures():
    """NEGATIVE: any meaningful change to the signature changes the fingerprint, so distinct
    laws cannot collide onto one node."""
    base = fingerprint("T", {"a": 1.5, "mu": -0.5})
    assert base != fingerprint("T", {"a": 2.0, "mu": -0.5})   # different exponent value
    assert base != fingerprint("T", {"a": 1.5})               # missing term
    assert base != fingerprint("P", {"a": 1.5, "mu": -0.5})   # different target name
    assert base != fingerprint("T", {"a": -1.5, "mu": -0.5})  # sign flip


@settings(max_examples=200)
@given(
    exps=st.dictionaries(
        st.sampled_from(["a", "b", "c", "mu", "r", "rho"]),
        st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        max_size=6,
    )
)
def test_property_fingerprint_invariant_to_order_and_zero_padding(exps):
    """PROPERTY: the fingerprint is a pure function of the canonical signature — permuting
    the dict and appending a zero-exponent term never change it."""
    fp = fingerprint("T", exps)
    permuted = dict(reversed(list(exps.items())))
    assert fingerprint("T", permuted) == fp
    padded = {**exps, "__zero__": 0.0}
    assert fingerprint("T", padded) == fp


@settings(max_examples=300)
@given(
    e1=st.dictionaries(
        st.sampled_from(["a", "b", "c", "mu"]),
        st.floats(min_value=-4.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        max_size=4,
    ),
    e2=st.dictionaries(
        st.sampled_from(["a", "b", "c", "mu"]),
        st.floats(min_value=-4.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        max_size=4,
    ),
)
def test_property_distinct_signatures_never_collide(e1, e2):
    """PROPERTY (collision-freedom): whenever two candidates have DIFFERENT canonical
    signatures their fingerprints differ; when the signatures match, the fingerprints match.
    A facade fingerprint (e.g. constant, or ignoring exponents) fails this immediately."""
    same_signature = _signature("T", e1) == _signature("T", e2)
    same_fingerprint = fingerprint("T", e1) == fingerprint("T", e2)
    assert same_signature == same_fingerprint


# ------------------------------------------------ claim 3: lossless, deterministic record


def _sample_node() -> GraphNode:
    return GraphNode(
        id=fingerprint("T", {"a": 1.5, "mu": -0.5}),
        input_idea="Kepler",
        candidate="T = C·a^1.5·mu^-0.5",
        exponent_signature={"a": 1.5, "mu": -0.5},
        delta_to_consensus=0.0,
        gates={"r2": {"ok": True, "value": 0.999}},
        verdict="bestaetigt",
        provenance=("mensch", "forge"),
        parent_ids=("p1",),
        graph_edges=("analog_zu:deadbeef",),
        timestamp="2026-06-18T00:00:00Z",
        encounters=3,
    )


def test_record_carries_full_anhang_c_schema():
    """to_record emits every Anhang-C field the spec names — none silently dropped."""
    rec = _sample_node().to_record()
    for key in (
        "id", "timestamp", "input_idea", "candidate", "delta_to_consensus",
        "gates", "verdict", "provenance", "parent_ids", "graph_edges",
    ):
        assert key in rec, f"Anhang-C field {key!r} missing from record"
    assert rec["provenance"] == ["mensch", "forge"]
    assert rec["parent_ids"] == ["p1"]
    assert rec["graph_edges"] == ["analog_zu:deadbeef"]
    assert rec["encounters"] == 3


def test_record_round_trips_losslessly():
    """from_record(to_record(n)) reconstructs the node EXACTLY (frozen dataclass equality)."""
    node = _sample_node()
    assert GraphNode.from_record(node.to_record()) == node


def test_graph_json_round_trips_losslessly():
    """A whole graph survives to_ledger_records -> from_records unchanged (resume a checkpoint
    exactly), and to_json is JSON-parseable with all records present."""
    g = DiscoveryGraph()
    g.add_result(_kepler_result(), target_name="T", timestamp="2026-06-18T00:00:00Z")
    g.add_verdict(_make_verdict({"a": 2.0, "mu": -0.5}, verdict="widerlegt"),
                  idea="toy", target_name="T", timestamp="2026-06-18T00:00:00Z")

    rebuilt = DiscoveryGraph.from_records(g.to_ledger_records())
    assert rebuilt.to_ledger_records() == g.to_ledger_records()

    parsed = json.loads(g.to_json())
    assert isinstance(parsed, list) and len(parsed) == len(g)
    assert all("verdict" in r and "id" in r for r in parsed)


def test_timestamp_is_passed_in_never_minted():
    """Determinism: when no timestamp is supplied the record's timestamp is None — the graph
    NEVER mints a wall-clock value (which would break reproducibility)."""
    g = DiscoveryGraph()
    g.add_verdict(_make_verdict({"a": 1.5, "mu": -0.5}), idea="i", target_name="T")
    rec = g.to_ledger_records()[0]
    assert rec["timestamp"] is None


def test_to_json_is_deterministic_across_independent_builds():
    """Two independently-built graphs with the same inputs and the same passed-in timestamp
    serialise byte-for-byte identically (A5 reproducibility)."""
    def build():
        g = DiscoveryGraph()
        g.add_verdict(_make_verdict({"a": 1.5, "mu": -0.5}), idea="Kepler",
                      target_name="T", provenance=("p",), timestamp="2026-06-18T00:00:00Z")
        g.add_verdict(_make_verdict({"a": 2.0}, verdict="widerlegt"), idea="toy",
                      target_name="T", timestamp="2026-06-18T00:00:00Z")
        return g.to_json()

    assert build() == build()


@settings(max_examples=100)
@given(
    exps=st.dictionaries(
        st.sampled_from(["a", "b", "c", "mu"]),
        st.floats(min_value=-4.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=4,
    ),
    encounters=st.integers(min_value=1, max_value=50),
    delta=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_property_record_round_trip(exps, encounters, delta):
    """PROPERTY: every node round-trips through its Anhang-C record without loss, for
    arbitrary exponents / encounter counts / deltas."""
    node = GraphNode(
        id=fingerprint("T", exps),
        input_idea="i",
        candidate="expr",
        exponent_signature={k: round(v, 6) for k, v in exps.items()},
        delta_to_consensus=delta,
        gates={"g": {"ok": True}},
        verdict="bestaetigt",
        provenance=("p1", "p2"),
        parent_ids=("parent",),
        graph_edges=("rel:other",),
        timestamp="2026-01-01T00:00:00Z",
        encounters=encounters,
    )
    assert GraphNode.from_record(node.to_record()) == node
