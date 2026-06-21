"""cosmic_insight — the Cosmic Insight Engine (build doc 4.1, Phase 4).

An analogy/transfer layer over the Discovery Graph. As the graph fills with confirmed laws,
this engine finds CROSS-DOMAIN connections that no single discovery run could see: two laws
from different domains that share the same STRUCTURAL shape. The canonical example is the
inverse-square family — Newton's gravitation ``F ∝ m1·m2·r^(-2)`` and Coulomb's law
``F ∝ q1·q2·r^(-2)`` carry the identical exponent multiset ``(-2, 1, 1, 1)``, so the engine
reports them as structurally analogous even though their variables and units are unrelated.

The structural signature deliberately ABSTRACTS AWAY the variable names and units and keeps
only the multiset of exponents — the shape of the law. Two laws with the same shape are an
analogy candidate; when they come from distinct ideas, that is a genuine cross-domain bridge.

Honesty: the engine PROPOSES connections, it never confirms a new law. A cross-domain
hypothesis is a hint ("this new relation has the same shape as a known law in another
domain") routed back for the human/loop to pursue — every actual law still goes through the
discovery gate. It reads only CONFIRMED graph nodes, so an analogy is built on verified laws,
not speculation. Offline, deterministic, dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import DiscoveryProblem, symbolic_regress
from .graph import DiscoveryGraph


def structural_signature(exponents: dict[str, float]) -> tuple[float, ...]:
    """The SHAPE of a law: the sorted multiset of its non-zero exponents, variable names and
    units abstracted away. Newton ``{m1:1, m2:1, r:-2, G:1}`` and Coulomb ``{q1:1, q2:1, r:-2,
    k:1}`` both give ``(-2.0, 1.0, 1.0, 1.0)`` — the inverse-square shape."""
    return tuple(sorted(round(e, 6) for e in exponents.values() if abs(e) >= 1e-9))


@dataclass(frozen=True)
class Analogy:
    """A structural analogy: several confirmed laws from distinct domains sharing one shape."""

    signature: tuple[float, ...]
    member_expressions: tuple[str, ...]
    domains: tuple[str, ...]


@dataclass(frozen=True)
class CrossDomainHypothesis:
    """A hint that a target relation mirrors a known law in another domain — a proposal for
    the loop, never a confirmation."""

    target_idea: str
    proposed_expression: str
    analogous_to: str
    source_domain: str
    shared_signature: tuple[float, ...]


def find_analogies(graph: DiscoveryGraph, *, min_members: int = 2) -> list[Analogy]:
    """Cluster the graph's CONFIRMED laws by structural signature and report every shape shared
    by at least `min_members` laws spanning at least two distinct domains (ideas) — the
    cross-domain structural bridges (e.g. gravity ~ electrostatics). Deterministic order."""
    by_sig: dict[tuple[float, ...], list] = {}
    for node in graph.confirmed():
        by_sig.setdefault(structural_signature(node.exponent_signature), []).append(node)

    analogies: list[Analogy] = []
    for sig, nodes in by_sig.items():
        domains = sorted({n.input_idea for n in nodes})
        if len(nodes) >= min_members and len(domains) >= 2:
            analogies.append(Analogy(
                signature=sig,
                member_expressions=tuple(sorted(n.candidate for n in nodes)),
                domains=tuple(domains)))
    analogies.sort(key=lambda a: (-len(a.domains), a.signature))
    return analogies


def cross_domain_hypotheses(graph: DiscoveryGraph, target_problem: DiscoveryProblem) -> list[CrossDomainHypothesis]:
    """Compute the target problem's dimensional law and, if its shape matches a CONFIRMED law
    from a DIFFERENT domain in the graph, surface a cross-domain hypothesis: the new relation
    is structurally analogous to a known one. A proposal for the loop — the target's law is
    still validated by the gate, not by the analogy. Raises ValueError on empty/bad target data
    (via the engine)."""
    candidate = symbolic_regress(target_problem)[0]
    sig = structural_signature(candidate.exponents)
    out: list[CrossDomainHypothesis] = []
    for node in graph.confirmed():
        if node.input_idea == target_problem.idea:
            continue
        if structural_signature(node.exponent_signature) == sig:
            out.append(CrossDomainHypothesis(
                target_idea=target_problem.idea,
                proposed_expression=candidate.expression,
                analogous_to=node.candidate,
                source_domain=node.input_idea,
                shared_signature=sig))
    out.sort(key=lambda h: (h.source_domain, h.analogous_to))
    return out
