"""Constraint consistency — structural contradiction detection, independent of values.

Two constraints on the same expression pair with disjoint solution sets (a>=b and a<b) can never
both hold and must be flagged - even when the current values satisfy one of them (which is all
GATE gamma C-13 sees). Reversed wordings are caught; a forced equality (a>=b and a<=b) is
consistent. Offline, no LLM, pure functions.

Run:  pytest tests/test_constraint_consistency.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import Constraint  # noqa: E402
from gen.constraint_consistency import (  # noqa: E402
    find_contradictions,
    is_consistent,
)
from gen.demo import capstone_spec  # noqa: E402


def _c(cid, kind, left, right):
    return Constraint(id=cid, kind=kind, left=left, right=right)


def test_the_capstone_constraints_are_consistent():
    assert is_consistent(capstone_spec().constraints)
    assert find_contradictions(capstone_spec().constraints) == []


def test_opposing_constraints_are_a_contradiction():
    cs = [_c("k1", "ge", "a", "b"), _c("k2", "lt", "a", "b")]   # a>=b AND a<b
    assert not is_consistent(cs)
    contradictions = find_contradictions(cs)
    assert len(contradictions) == 1
    assert set(contradictions[0].constraint_ids) == {"k1", "k2"}
    assert (contradictions[0].left, contradictions[0].right) == ("a", "b")


def test_forced_equality_is_consistent():
    # a>=b AND a<=b is satisfiable (a == b), not a contradiction
    assert is_consistent([_c("k1", "ge", "a", "b"), _c("k2", "le", "a", "b")])


def test_equality_versus_strict_is_a_contradiction():
    assert not is_consistent([_c("k1", "eq", "x", "y"), _c("k2", "gt", "x", "y")])


def test_reversed_wording_contradiction_is_caught():
    # a>b AND b>a -> the pair is canonicalised, the disjoint signs are detected
    assert not is_consistent([_c("k1", "gt", "a", "b"), _c("k2", "gt", "b", "a")])


def test_three_way_conflict_reports_each_pair():
    cs = [_c("k1", "lt", "a", "b"), _c("k2", "eq", "a", "b"), _c("k3", "gt", "a", "b")]
    contradictions = find_contradictions(cs)
    pairs = {frozenset(c.constraint_ids) for c in contradictions}
    assert pairs == {frozenset({"k1", "k2"}), frozenset({"k1", "k3"}), frozenset({"k2", "k3"})}


def test_empty_and_single_are_vacuously_consistent():
    assert is_consistent([])
    assert is_consistent([_c("k1", "ge", "a", "b")])


def test_is_deterministic():
    cs = [_c("k1", "ge", "a", "b"), _c("k2", "lt", "a", "b")]
    a = find_contradictions(cs)
    b = find_contradictions(cs)
    assert [(c.constraint_ids, c.left, c.right) for c in a] == [(c.constraint_ids, c.left, c.right) for c in b]
