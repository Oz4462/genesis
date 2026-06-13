"""Tests for SMT constraint feasibility (Tier-3). Skips without the `smt` extra (z3).

The decisive test: a TRANSITIVE infeasible set (a>b, b>c, c>a) is caught by the SMT
check but NOT by the dependency-free pairwise checker — proving the added value.
"""

from __future__ import annotations

import pytest

pytest.importorskip("z3")

from gen.constraint_consistency import find_contradictions  # noqa: E402
from gen.core.state import Constraint  # noqa: E402
from gen.verification.constraint_smt import check_feasibility, is_feasible  # noqa: E402


def _c(cid: str, left: str, kind: str, right: str) -> Constraint:
    return Constraint(id=cid, kind=kind, left=left, right=right, reason="")


def test_transitive_infeasibility_caught_only_by_smt():
    cons = [_c("k1", "a", "gt", "b"), _c("k2", "b", "gt", "c"), _c("k3", "c", "gt", "a")]
    # the pairwise structural checker misses this (different expression pairs)
    assert find_contradictions(cons) == []
    # the SMT checker proves it infeasible and names the conflicting set
    res = check_feasibility(cons)
    assert res.feasible is False
    assert set(res.conflicting_ids) == {"k1", "k2", "k3"}


def test_satisfiable_set_is_feasible():
    assert is_feasible([_c("k1", "a", "gt", "b"), _c("k2", "b", "gt", "c")]) is True


def test_pairwise_contradiction_also_infeasible():
    res = check_feasibility([_c("k1", "a", "ge", "b"), _c("k2", "a", "lt", "b")])
    assert res.feasible is False
    assert set(res.conflicting_ids) == {"k1", "k2"}


def test_numeric_literals_are_constants():
    # a > 5 and a < 3 is infeasible; a > 5 and a < 9 is feasible
    assert is_feasible([_c("k1", "a", "gt", "5"), _c("k2", "a", "lt", "3")]) is False
    assert is_feasible([_c("k1", "a", "gt", "5"), _c("k2", "a", "lt", "9")]) is True


def test_empty_is_feasible():
    assert is_feasible([]) is True
