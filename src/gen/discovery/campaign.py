"""campaign — compose the Phase-2 discovery modules into one gated campaign (live wiring).

Runs a set of discovery problems through the gate and COMPOSES the new pieces in the real flow:
collect every confirmed law into a MAP-Elites archive (``archive.py``) for diversity, and learn a
concept-utility prior (``concept_utility.py``) from the accumulated pass/fail ledger so later problems'
candidates are tie-ordered by what has historically passed. The gate stays the sole authority — this
only composes breadth (archive) with a learned ordering (prior); nothing is decided by a model.

Deterministic, offline. The directed BFTS search (``tree_search.directed_search``) and the active-
selection policy (``active_search``) are available to a controller for budget-limited variants; this
campaign is the simplest faithful composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .archive import EliteArchive
from .concept_utility import ConceptUtility
from .engine import DiscoveryProblem, discover_new_formulas


@dataclass(frozen=True)
class CampaignReport:
    """The campaign outcome: the diversity archive of confirmed laws, the learned prior, the number of
    validated verdicts across all problems, and the archive coverage (distinct confirmed forms)."""

    archive: EliteArchive
    prior: ConceptUtility
    validated_count: int
    coverage: int


def run_campaign(
    problems: Sequence[DiscoveryProblem],
    *,
    known_laws: dict[str, dict[str, float]] | None = None,
) -> CampaignReport:
    """Run a discovery campaign over ``problems``, composing the archive + the learned concept prior.

    Each problem is gated with the prior learned from every prior problem's ledger (so accumulated
    pass/fail evidence orders ties); confirmed laws are admitted to the MAP-Elites archive. The gate is
    the sole authority on every verdict. Deterministic."""
    archive = EliteArchive()
    ledger: list = []
    prior = ConceptUtility()                       # empty (neutral) prior for the first problem
    validated_count = 0
    for problem in problems:
        result = discover_new_formulas(problem, known_laws=known_laws, prior=prior)
        archive.add_result(result)
        validated_count += len(result.validated)
        ledger.extend((record.candidate, record.passed) for record in result.all_records)
        prior = ConceptUtility.fit(ledger)         # learn from everything gated so far
    return CampaignReport(
        archive=archive, prior=prior,
        validated_count=validated_count, coverage=archive.coverage,
    )
