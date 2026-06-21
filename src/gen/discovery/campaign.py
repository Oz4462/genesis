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

from ..verification.units import parse_unit
from .archive import EliteArchive
from .concept_utility import ConceptUtility
from .engine import DiscoveryProblem, discover_new_formulas
from .knowledge_graph import DiscoveryGraph as KnowledgeGraph  # SciAgents KG (distinct from graph.DiscoveryGraph)


@dataclass(frozen=True)
class CampaignReport:
    """The campaign outcome: the diversity archive of confirmed laws, the learned prior, the number of
    validated verdicts across all problems, and the archive coverage (distinct confirmed forms).

    ``cross_domain_hypotheses`` (only when ``run_campaign`` is given a ``cross_domain_target``) are
    dimensionally-FEASIBLE source-variable groupings drawn from across the campaign's confirmed laws —
    SciAgents-style cross-domain breadth with GENESIS's dimensional-type filter disposing the impossible.
    They are HYPOTHESES (gate inputs / open questions), never confirmed laws: there is no joint dataset to
    gate a cross-law grouping on, so the honest output is "dimensionally these could relate", not a finding.
    """

    archive: EliteArchive
    prior: ConceptUtility
    validated_count: int
    coverage: int
    cross_domain_hypotheses: tuple[tuple[str, ...], ...] = ()


def run_campaign(
    problems: Sequence[DiscoveryProblem],
    *,
    known_laws: dict[str, dict[str, float]] | None = None,
    cross_domain_target: str | None = None,
    cross_domain_seed: int = 0,
) -> CampaignReport:
    """Run a discovery campaign over ``problems``, composing the archive + the learned concept prior.

    Each problem is gated with the prior learned from every prior problem's ledger (so accumulated
    pass/fail evidence orders ties); confirmed laws are admitted to the MAP-Elites archive. The gate is
    the sole authority on every verdict.

    When ``cross_domain_target`` (a unit string, e.g. ``"s"``) is given, a SciAgents knowledge graph is
    built over the CONFIRMED laws and ``cross_domain_hypotheses`` is filled with dimensionally-feasible
    source groupings toward that target dimension — the dimensional-type filter disposing the impossible
    before they would ever reach the gate. These are hypotheses, not findings. Default ``None`` leaves the
    report unchanged. Deterministic."""
    archive = EliteArchive()
    ledger: list = []
    prior = ConceptUtility()                       # empty (neutral) prior for the first problem
    validated_count = 0
    kg = KnowledgeGraph()                          # SciAgents KG over this campaign's confirmed laws
    for problem in problems:
        result = discover_new_formulas(problem, known_laws=known_laws, prior=prior)
        archive.add_result(result)
        validated_count += len(result.validated)
        ledger.extend((record.candidate, record.passed) for record in result.all_records)
        prior = ConceptUtility.fit(ledger)         # learn from everything gated so far
        if result.validated:                       # only CONFIRMED laws enter the knowledge graph
            kg.add_law(
                target_name=problem.target.name, target_unit=problem.target.unit,
                source_units={v.name: v.unit for v in problem.inputs}
                | {c.name: c.unit for c in problem.constants},
            )

    hypotheses: tuple[tuple[str, ...], ...] = ()
    if cross_domain_target is not None:
        target_dim = parse_unit(cross_domain_target)
        hypotheses = tuple(
            tuple(group) for group in kg.propose_cross_domain(target_dim, seed=cross_domain_seed)
        )
    return CampaignReport(
        archive=archive, prior=prior,
        validated_count=validated_count, coverage=archive.coverage,
        cross_domain_hypotheses=hypotheses,
    )
