"""Depth-audit characterization of ratification.py — the human-in-the-loop sign-off gate.

These tests are facade-detectors for the no-default-approval contract (research #5 / the
Agent-SDK guidance "never fake approval with hidden auto-allow"):

  (a) the packet is DERIVED from its driving inputs — adding a Decision/gap/failed gate changes
      the packet meaningfully (it is not a canned constant), and
  (b) the documented fail-loud/abstention path fires exactly — "done" requires a NAMED approver
      to explicitly sign EVERY blocking item; nothing is approved by default.

A property-based test pins the core invariant of `is_ratified` over a random input space so a
future refactor cannot silently re-introduce a default-approval. Pure functions, no LLM, no I/O.

Run:  pytest tests/test_ratification_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.core.state import Decision, Specification  # noqa: E402
from gen.ratification import (  # noqa: E402
    RatificationItem,
    SignOff,
    is_ratified,
    ratification_packet,
    unratified_items,
)


# --- helpers: build inputs through the REAL constructors (never invent fields) ---------------

def _decision(i: int) -> Decision:
    return Decision(id=f"d{i}", title=f"T{i}", choice=f"c{i}", rationale=f"r{i}", informed_by=[])


def _spec(n_decisions: int = 0, n_gaps: int = 0) -> Specification:
    return Specification(
        run_id="run",
        idea="idea",
        decisions=[_decision(i) for i in range(n_decisions)],
        gaps=[f"gap text {i}" for i in range(n_gaps)],
    )


def _blocking_refs(packet: list[RatificationItem]) -> frozenset[str]:
    return frozenset(it.ref for it in packet if it.blocking)


# === (a) FACADE-KILLER: the packet is consumed from its inputs, not a canned constant =========

def test_packet_grows_when_a_decision_is_added():
    # Driving input #1 (decisions) is genuinely consumed: one more Decision -> one more blocking
    # "decision" item carrying THAT decision's content, not a fixed list.
    small = ratification_packet(_spec(n_decisions=1))
    big = ratification_packet(_spec(n_decisions=3))
    small_decisions = [it for it in small if it.kind == "decision"]
    big_decisions = [it for it in big if it.kind == "decision"]
    assert len(small_decisions) == 1 and len(big_decisions) == 3
    # the content is derived from the Decision (title/choice/rationale appear in the summary)
    assert "T0" in big_decisions[0].summary and "'c0'" in big_decisions[0].summary
    assert all(it.blocking for it in big_decisions)


def test_packet_grows_when_a_gap_is_added():
    # Driving input #2 (gaps) is genuinely consumed: each gap string becomes a blocking item whose
    # summary IS the gap text (residual risk a human must acknowledge).
    packet = ratification_packet(_spec(n_gaps=2))
    gaps = [it for it in packet if it.kind == "gap"]
    assert [it.summary for it in gaps] == ["gap text 0", "gap text 1"]
    assert all(it.blocking for it in gaps)


def test_gate_verdict_drives_blocking_flag():
    # Driving input #3 (gate verdicts) is genuinely consumed: PASS -> non-blocking evidence,
    # FAIL -> blocking. Flipping ONLY the verdict flips ONLY the blocking flag.
    spec = _spec()
    passed = ratification_packet(spec, {"g": GateResult("g", passed=True, failures=[])})
    failed = ratification_packet(
        spec, {"g": GateResult("g", passed=False, failures=[GateFailure("X", "boom")])}
    )
    pass_item = next(it for it in passed if it.kind == "gate")
    fail_item = next(it for it in failed if it.kind == "gate")
    assert pass_item.ref == fail_item.ref == "gate:g"
    assert pass_item.blocking is False and fail_item.blocking is True
    # the failure COUNT is read from the result, not hardcoded
    assert "1 Abweichungen" in fail_item.summary and "0 Abweichungen" in pass_item.summary


def test_packet_is_order_stable_and_deterministic():
    # A5 reproducibility: same spec -> byte-identical packet (decisions sorted by id, stable order).
    spec = Specification(
        run_id="r", idea="x",
        decisions=[_decision(2), _decision(0), _decision(1)],  # deliberately out of order
        gaps=["g0", "g1"],
    )
    a = ratification_packet(spec)
    b = ratification_packet(spec)
    assert [(it.kind, it.ref, it.summary, it.blocking) for it in a] == \
           [(it.kind, it.ref, it.summary, it.blocking) for it in b]
    decision_refs = [it.ref for it in a if it.kind == "decision"]
    assert decision_refs == ["decision:d0", "decision:d1", "decision:d2"]  # sorted by id


# === (b) FACADE-KILLER: the no-default-approval / named-approver contract fires exactly ========

def test_empty_signoff_ratifies_nothing():
    packet = ratification_packet(_spec(n_decisions=2, n_gaps=2))
    assert not is_ratified(packet, SignOff())                     # no auto-approval
    assert len(unratified_items(packet, SignOff())) == len(packet)  # ALL still block


def test_full_explicit_signoff_with_named_approver_ratifies():
    packet = ratification_packet(_spec(n_decisions=2, n_gaps=2))
    all_refs = _blocking_refs(packet)
    signed = SignOff(approved=all_refs, approver="ozan")
    assert is_ratified(packet, signed)
    assert unratified_items(packet, signed) == []


def test_anonymous_full_signoff_is_not_ratified():
    # Approving every blocking ref but with NO named approver is anonymous approval -> NOT done.
    packet = ratification_packet(_spec(n_decisions=2, n_gaps=1))
    all_refs = _blocking_refs(packet)
    assert not is_ratified(packet, SignOff(approved=all_refs, approver=""))
    assert not is_ratified(packet, SignOff(approved=all_refs, approver="   "))  # whitespace != named
    assert is_ratified(packet, SignOff(approved=all_refs, approver="ozan"))


def test_one_unsigned_blocking_item_blocks_done():
    # Dropping a SINGLE blocking ref from the sign-off keeps the spec un-ratified — there is no
    # tolerance / partial-credit path.
    packet = ratification_packet(_spec(n_decisions=3, n_gaps=2))
    all_refs = list(_blocking_refs(packet))
    missing_one = SignOff(approved=frozenset(all_refs[1:]), approver="ozan")
    assert not is_ratified(packet, missing_one)
    remaining = unratified_items(packet, missing_one)
    assert len(remaining) == 1 and remaining[0].ref == all_refs[0]


def test_failed_gate_must_be_signed_too():
    # Approving every decision/gap but NOT the failed gate -> still not ratified; the failed gate
    # is the sole remaining blocker.
    spec = _spec(n_decisions=1, n_gaps=1)
    gates = {"phys": GateResult("phys", passed=False, failures=[GateFailure("F", "x")])}
    packet = ratification_packet(spec, gates)
    non_gate = frozenset(it.ref for it in packet if it.kind != "gate")
    signed = SignOff(approved=non_gate, approver="ozan")
    assert not is_ratified(packet, signed)
    assert [it.ref for it in unratified_items(packet, signed)] == ["gate:phys"]


def test_passed_gate_need_not_be_signed():
    # A passing gate is evidence, not a blocker: signing only decisions/gaps still ratifies.
    spec = _spec(n_decisions=1, n_gaps=1)
    gates = {"gamma": GateResult("gamma", passed=True, failures=[])}
    packet = ratification_packet(spec, gates)
    blocking = _blocking_refs(packet)
    assert "gate:gamma" not in blocking
    assert is_ratified(packet, SignOff(approved=blocking, approver="ozan"))


def test_empty_packet_still_needs_a_human_approver():
    # A spec with nothing blocking is NOT vacuously done: a named human must still acknowledge it.
    packet = ratification_packet(Specification(run_id="r", idea="x"))
    assert packet == []
    assert not is_ratified(packet, SignOff())                 # no human -> not done
    assert is_ratified(packet, SignOff(approver="ozan"))      # a human acknowledged it


def test_signoff_coerces_mutable_set_so_approvals_cannot_grow_post_hoc():
    # The frozenset coercion in SignOff.__post_init__ is a real guard: a mutable set mutated AFTER
    # the sign-off must NOT leak new approvals into the recorded decision.
    live: set[str] = {"gap:0"}
    signoff = SignOff(approved=live, approver="ozan")
    live.add("gap:1")                                         # tamper after the fact
    packet = ratification_packet(_spec(n_gaps=2))
    # gap:1 was never part of the sealed sign-off -> it still blocks.
    assert "gap:1" in {it.ref for it in unratified_items(packet, signoff)}


# === PROPERTY: is_ratified == (named approver) AND (every blocking ref explicitly approved) =====

@settings(max_examples=200)
@given(
    n_decisions=st.integers(min_value=0, max_value=5),
    n_gaps=st.integers(min_value=0, max_value=5),
    n_pass_gates=st.integers(min_value=0, max_value=3),
    n_fail_gates=st.integers(min_value=0, max_value=3),
    approver=st.sampled_from(["", "   ", "ozan", "alice"]),
    approve_fraction=st.floats(min_value=0.0, max_value=1.0),
    drop_seed=st.integers(min_value=0, max_value=10_000),
)
def test_property_ratified_iff_named_approver_and_all_blocking_signed(
    n_decisions, n_gaps, n_pass_gates, n_fail_gates, approver, approve_fraction, drop_seed
):
    spec = _spec(n_decisions=n_decisions, n_gaps=n_gaps)
    gates: dict[str, GateResult] = {}
    for i in range(n_pass_gates):
        gates[f"p{i}"] = GateResult(f"p{i}", passed=True, failures=[])
    for i in range(n_fail_gates):
        gates[f"f{i}"] = GateResult(f"f{i}", passed=False, failures=[GateFailure("C", "d")])

    packet = ratification_packet(spec, gates)
    blocking = sorted(it.ref for it in packet if it.blocking)

    # deterministically pick a subset of blocking refs to approve (no wall-clock / global random)
    take = int(len(blocking) * approve_fraction)
    rotated = blocking[drop_seed % (len(blocking) or 1):] + blocking[: drop_seed % (len(blocking) or 1)]
    approved = frozenset(rotated[:take])

    signoff = SignOff(approved=approved, approver=approver)

    has_named_approver = bool(approver.strip())
    all_blocking_signed = set(blocking).issubset(approved)
    expected = has_named_approver and all_blocking_signed

    assert is_ratified(packet, signoff) is expected

    # unratified_items is EXACTLY the blocking refs not approved (independent of approver identity)
    assert {it.ref for it in unratified_items(packet, signoff)} == set(blocking) - approved
    # every reported unratified item is itself blocking (never surfaces a non-blocker)
    assert all(it.blocking for it in unratified_items(packet, signoff))


@settings(max_examples=100)
@given(
    n_decisions=st.integers(min_value=0, max_value=6),
    n_gaps=st.integers(min_value=0, max_value=6),
)
def test_property_packet_is_a_pure_function_of_its_inputs(n_decisions, n_gaps):
    # Determinism (A5): two independent builds from equal inputs are identical.
    a = ratification_packet(_spec(n_decisions=n_decisions, n_gaps=n_gaps))
    b = ratification_packet(_spec(n_decisions=n_decisions, n_gaps=n_gaps))
    assert [(it.kind, it.ref, it.summary, it.blocking) for it in a] == \
           [(it.kind, it.ref, it.summary, it.blocking) for it in b]
    # every decision and gap is blocking; counts match the inputs exactly
    assert sum(1 for it in a if it.kind == "decision") == n_decisions
    assert sum(1 for it in a if it.kind == "gap") == n_gaps
    assert all(it.blocking for it in a)
