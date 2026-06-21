"""canonical — collapse algebraically-equivalent power-law candidates to one key (EGG-SR adoption).

EGG-SR uses e-graphs / equality saturation to keep the search from re-evaluating algebraically-equal
expressions. GENESIS's candidate grammar is a single monomial ``C·∏ var^exp``, so the equality that
matters is exact: two forms are the same iff they have the same rationalised, zero-stripped exponent
signature (``1.5`` ≡ ``3/2``; an explicit ``b^0`` is no term at all). Canonicalising on that signature
lets the proposer drop duplicates so the (more expensive) deterministic gate never judges the same law
twice. Pure efficiency — it changes WHICH candidates are evaluated, never the gate's verdict on any of
them. Offline, deterministic, no new dependencies.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Callable, Iterable, TypeVar

from .engine import EXPONENT_MAX_DENOMINATOR

T = TypeVar("T")

#: A canonical power-law signature: a frozenset of (name, numerator, denominator) for non-zero terms.
Signature = frozenset


def canonical_signature(exponents: dict[str, float]) -> frozenset[tuple[str, int, int]]:
    """The canonical key of a power-law form: each non-zero exponent rationalised (denominator ≤
    EXPONENT_MAX_DENOMINATOR, mirroring the engine), so ``1.4999…``/``1.5``/``3/2`` collapse together and
    a zero exponent contributes nothing."""
    signature: set[tuple[str, int, int]] = set()
    for name, exp in exponents.items():
        frac = Fraction(exp).limit_denominator(EXPONENT_MAX_DENOMINATOR)
        if frac != 0:
            signature.add((name, frac.numerator, frac.denominator))
    return frozenset(signature)


def dedupe_by_exponents(items: Iterable[T], key: Callable[[T], dict[str, float]]) -> list[T]:
    """Keep the FIRST item of each canonical signature (order-preserving), so equivalent power-law
    forms are evaluated by the gate only once. ``key`` extracts an item's exponent mapping."""
    seen: set[frozenset[tuple[str, int, int]]] = set()
    out: list[T] = []
    for item in items:
        signature = canonical_signature(key(item))
        if signature not in seen:
            seen.add(signature)
            out.append(item)
    return out
