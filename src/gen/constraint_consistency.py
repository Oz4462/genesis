"""Constraint consistency — structural contradiction detection (TIER 3 #2).

GATE γ C-13 checks each constraint against the CURRENT declared values: if a value violates a
constraint, it fails. But two constraints can be mutually contradictory by DESIGN INTENT —
``a >= b`` and ``a < b`` can never both hold for any a, b — and C-13 only exposes that through
whichever one the current values happen to violate, missing the deeper "the requirements
themselves conflict" defect. This module adds the structural check: it detects pairs of
constraints whose solution sets are DISJOINT, independent of the current values.

It does this without a solver, dependency-free. Each comparison constraint over a pair of
expressions is reduced to the allowed SIGNS of (left − right): ``<`` -> {−1}, ``<=`` -> {−1,0},
``=`` -> {0}, ``>=`` -> {0,1}, ``>`` -> {1}. Two constraints on the SAME expression pair (after
canonicalising the written direction) contradict exactly when those sign sets are disjoint — so
``a>=b`` (sign {0,1}) with ``a<b`` (sign {−1}) is caught, while ``a>=b`` with ``a<=b`` (sign
{−1,0}) is consistent (it forces a=b). Reversed wordings (``a>b`` and ``b>a``) are caught because
the pair is canonicalised first.

Honest boundary: this finds PAIRWISE contradictions on the same two expressions — the common
design-intent typo. It does not solve TRANSITIVE multi-constraint infeasibility (a>b, b>c, c>a)
or general non-linear satisfiability; that needs a full SMT solver (e.g. z3) and is a deferred
optional layer. Offline, pure functions, no model calls.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .core.state import Constraint

# allowed signs of (left - right) for each comparison kind
_SIGN: dict[str, frozenset[int]] = {
    "lt": frozenset({-1}),
    "le": frozenset({-1, 0}),
    "eq": frozenset({0}),
    "ge": frozenset({0, 1}),
    "gt": frozenset({1}),
}
# the kind when the two sides are swapped (a<b becomes b>a)
_FLIP: dict[str, str] = {"lt": "gt", "le": "ge", "gt": "lt", "ge": "le", "eq": "eq"}


@dataclass(frozen=True)
class Contradiction:
    """Two constraints that can never both hold. `left`/`right` are the shared expression
    pair (canonicalised); `constraint_ids` are the conflicting constraints."""

    constraint_ids: tuple[str, str]
    left: str
    right: str


def _canonical(c: Constraint) -> tuple[str, str, frozenset[int]]:
    """Reduce a constraint to (expr_lo, expr_hi, allowed-signs-of(expr_lo − expr_hi)) with the
    two expressions ordered, flipping the sign set if the written order was reversed."""
    left, right = c.left.strip(), c.right.strip()
    sign = _SIGN[c.kind]
    if left <= right:
        return left, right, sign
    return right, left, _SIGN[_FLIP[c.kind]]


def find_contradictions(constraints: list[Constraint]) -> list[Contradiction]:
    """All pairwise structural contradictions among `constraints`: pairs on the same expression
    pair whose allowed-sign sets are disjoint (can never both hold). Deterministic, order-stable.
    Only comparison kinds in `_SIGN` participate; an unknown kind is ignored here (GATE γ
    validates kinds separately)."""
    by_pair: dict[tuple[str, str], list[tuple[str, frozenset[int]]]] = defaultdict(list)
    for c in constraints:
        if c.kind not in _SIGN:
            continue
        lo, hi, sign = _canonical(c)
        by_pair[(lo, hi)].append((c.id, sign))

    out: list[Contradiction] = []
    for (lo, hi), items in by_pair.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if not (items[i][1] & items[j][1]):          # disjoint -> can't both hold
                    out.append(Contradiction((items[i][0], items[j][0]), lo, hi))
    return out


def is_consistent(constraints: list[Constraint]) -> bool:
    """True if no two constraints structurally contradict each other (no disjoint pair on a
    shared expression pair). Vacuously true for an empty or single-relation set."""
    return not find_contradictions(constraints)
