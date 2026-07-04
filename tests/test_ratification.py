"""Human-in-the-loop ratification — nothing is "done" without an explicit sign-off.

The packet surfaces every Decision and gap (and a failed gate) as a blocking item; an empty
sign-off ratifies nothing (no auto-approval); only when every blocking item is explicitly
approved is the spec ratified. A passed gate is non-blocking evidence; a failed one blocks.
Offline, no LLM, pure functions.

Run:  pytest tests/test_ratification.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.interfaces import GateFailure, GateResult  # noqa: E402
from gen.demo import capstone_spec  # noqa: E402
from gen.ratification import (  # noqa: E402
    SignOff,
    is_ratified,
    ratification_packet,
    unratified_items,
)


def test_packet_surfaces_every_decision_and_gap_as_blocking():
    spec = capstone_spec()                                  # 4 decisions, 5 gaps
    packet = ratification_packet(spec)
    decisions = [it for it in packet if it.kind == "decision"]
    gaps = [it for it in packet if it.kind == "gap"]
    assert len(decisions) == 4 and len(gaps) == 5
    assert all(it.blocking for it in packet)               # all of them require sign-off


def test_empty_signoff_ratifies_nothing():
    packet = ratification_packet(capstone_spec())
    assert not is_ratified(packet, SignOff())              # no auto-approval
    assert len(unratified_items(packet, SignOff())) == len(packet)


def test_explicit_signoff_of_every_blocking_item_ratifies():
    packet = ratification_packet(capstone_spec())
    all_refs = frozenset(it.ref for it in packet if it.blocking)
    signed = SignOff(approved=all_refs, approver="ozan")
    assert is_ratified(packet, signed) and unratified_items(packet, signed) == []


def test_partial_signoff_is_not_ratified():
    packet = ratification_packet(capstone_spec())
    some = frozenset(list(it.ref for it in packet)[:3])    # approve only the first three
    signed = SignOff(approved=some)
    assert not is_ratified(packet, signed)
    assert 0 < len(unratified_items(packet, signed)) < len(packet)


def test_failed_gate_blocks_but_passed_gate_is_evidence():
    spec = capstone_spec()
    gates = {
        "gamma": GateResult(gate="gamma", passed=True, failures=[]),
        "delta-physics": GateResult(gate="delta-physics", passed=False,
                                    failures=[GateFailure("PHYSICS_CHECK_FAILED", "x")]),
    }
    packet = ratification_packet(spec, gates)
    passed_item = next(it for it in packet if it.ref == "gate:gamma")
    failed_item = next(it for it in packet if it.ref == "gate:delta-physics")
    assert not passed_item.blocking                        # a passing gate is just evidence
    assert failed_item.blocking                            # a failing gate blocks "done"
    # approving every decision/gap but NOT the failed gate -> still not ratified
    non_gate = frozenset(it.ref for it in packet if it.kind != "gate")
    assert not is_ratified(packet, SignOff(approved=non_gate))


def test_is_deterministic():
    spec = capstone_spec()
    a = ratification_packet(spec)
    b = ratification_packet(spec)
    assert [(it.kind, it.ref, it.blocking) for it in a] == [(it.kind, it.ref, it.blocking) for it in b]


def test_full_approval_without_an_approver_is_not_ratified():
    # G4: ratifying every blocking ref but with NO named approver is an anonymous approval —
    # is_ratified must be False (no accountable human signed). Before the fix it returned True.
    packet = ratification_packet(capstone_spec())
    all_refs = frozenset(it.ref for it in packet if it.blocking)
    assert not is_ratified(packet, SignOff(approved=all_refs, approver=""))
    assert is_ratified(packet, SignOff(approved=all_refs, approver="ozan"))     # named -> ok


def test_empty_packet_still_needs_a_human_approver():
    # G3: a spec with nothing blocking was auto-ratified with no human at all. 'Done' still
    # needs a named approver to acknowledge it.
    from gen.core.state import Specification
    packet = ratification_packet(Specification(run_id="r", idea="x"))   # no decisions/gaps/gates
    assert packet == []
    assert not is_ratified(packet, SignOff())                           # was True (vacuous done)
    assert is_ratified(packet, SignOff(approver="ozan"))                # a human acknowledged it


def test_duplicate_decision_ids_get_distinct_namespaced_refs():
    # G1/G2: decision refs are namespaced (decision:<id>) so a decision id can never collide
    # with a gap/gate ref, and duplicate ids each get a DISTINCT ref so one sign-off cannot
    # silently ratify an unseen sibling. Before the fix both collapsed to the bare id.
    from gen.core.state import Decision, Specification
    spec = Specification(run_id="r", idea="x", decisions=[
        Decision(id="d", title="A", choice="x", rationale="r", informed_by=[]),
        Decision(id="d", title="B", choice="y", rationale="r", informed_by=[]),
    ])
    refs = [it.ref for it in ratification_packet(spec) if it.kind == "decision"]
    assert len(refs) == 2 and len(set(refs)) == 2          # distinct, not collapsed to one
    assert all(r.startswith("decision:") for r in refs)    # namespaced (no cross-kind collision)


def test_none_gate_result_is_rejected_not_silently_shaped():
    # D16/ratification G7: a None verdict has no honest blocking/non-blocking reading —
    # a gate that did not run must be omitted from the packet, never passed as None.
    import pytest

    with pytest.raises(ValueError, match="None"):
        ratification_packet(capstone_spec(), {"delta-physics": None})
