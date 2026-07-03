"""concept_utility — a deterministic, ledger-learned prior over discovery candidates (CCTS).

Adapted from Contrastive Concept-Tree Search (Leleu et al., 2026): tag each candidate with the
discrete "concepts" it uses (which variables participate, the EXACT rationalised exponent on each, a
complexity bucket), then learn from the gate's OWN pass/fail ledger a contrastive log-likelihood
utility per concept — positive for concepts that correlate with PASSING the gate, negative for
concepts that correlate with FAILING. The paper's load-bearing finding is that most of the gain comes
from learning which concepts to AVOID; for GENESIS that is exactly an anti-hallucination prior derived
from real verdicts, not from a model.

Hard invariant (CLAUDE.md §1, like the council): this only ORDERS candidates — a search heuristic,
never a correctness signal. The deterministic gate stays the sole authority on what is ``bestaetigt``;
a high-utility candidate that fails the gate is still ``widerlegt``. The utility is fit ONLY from real
gate verdicts already in the ledger, so it cannot invent confidence — it can only re-rank what the
gate will still judge.

Deterministic, offline, numpy-free (pure counting + ``math.log``). No new dependencies.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from .engine import Candidate, _format_exponent

_EXP_EPS = 1e-9


def concepts_of(candidate: Candidate) -> frozenset[str]:
    """The discrete concept tokens of a candidate: each participating variable, its exact rationalised
    exponent, and the complexity bucket. These are the atoms the contrastive utility is learned over."""
    tokens: set[str] = {f"complexity:{candidate.complexity}"}
    for name, exp in candidate.exponents.items():
        if abs(exp) < _EXP_EPS:
            continue
        tokens.add(f"var:{name}")
        tokens.add(f"exp:{name}^{_format_exponent(exp)}")
    return frozenset(tokens)


@dataclass(frozen=True)
class ConceptUtility:
    """A learned contrastive utility over candidate concepts.

    ``score(candidate)`` is the mean log-likelihood-ratio of its concepts — higher means historically
    more associated with PASSING the gate. An unseen concept scores 0 (neutral); a utility fit from a
    ledger with no passes OR no fails is uniformly 0 (nothing to contrast). Pure ordering signal.
    """

    _utility: dict[str, float] = field(default_factory=dict)
    smoothing: float = 1.0

    @staticmethod
    def fit(records: Iterable[tuple[Candidate, bool]], *, smoothing: float = 1.0) -> "ConceptUtility":
        """Learn from ``(candidate, passed)`` gate records: Laplace-smoothed log( p⁺(c) / p⁻(c) ) per
        concept, where p⁺/p⁻ are its frequency among passing / failing candidates."""
        pos: Counter[str] = Counter()
        neg: Counter[str] = Counter()
        n_pos = n_neg = 0
        for cand, passed in records:
            concepts = concepts_of(cand)
            if passed:
                n_pos += 1
                pos.update(concepts)
            else:
                n_neg += 1
                neg.update(concepts)
        util: dict[str, float] = {}
        if n_pos and n_neg:  # need both sides to contrast; else no signal (all 0)
            for concept in set(pos) | set(neg):
                p_plus = (pos[concept] + smoothing) / (n_pos + 2.0 * smoothing)
                p_minus = (neg[concept] + smoothing) / (n_neg + 2.0 * smoothing)
                util[concept] = math.log(p_plus / p_minus)
        return ConceptUtility(_utility=util, smoothing=smoothing)

    @staticmethod
    def from_result(result, *, smoothing: float = 1.0) -> "ConceptUtility":
        """Learn directly from a ``DiscoveryResult.all_records`` ledger (kept AND rejected)."""
        return ConceptUtility.fit(
            ((r.candidate, r.passed) for r in result.all_records), smoothing=smoothing
        )

    def utility(self, concept: str) -> float:
        """Learned utility of one concept token (0.0 if never seen)."""
        return self._utility.get(concept, 0.0)

    def score(self, candidate: Candidate) -> float:
        """Mean learned utility over a candidate's concepts (0.0 if it has none)."""
        concepts = concepts_of(candidate)
        if not concepts:
            return 0.0
        return sum(self._utility.get(c, 0.0) for c in concepts) / len(concepts)

    def order(self, candidates: Iterable[Candidate]) -> list[Candidate]:
        """Candidates by DESCENDING learned utility — the order to spend gate budget in. Stable and
        deterministic: ties break by parsimony (complexity) then the rendered expression."""
        return sorted(candidates, key=lambda c: (-self.score(c), c.complexity, c.expression))
