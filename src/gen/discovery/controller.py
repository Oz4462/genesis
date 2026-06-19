"""controller — the Compute + Checkpoint Controller (build doc §5 Phase 2, item 3).

A long exploration is a CAMPAIGN of discovery problems. This controller runs that campaign
under three knobs the doc asks for:

  * BUDGET — a cap on candidate evaluations, so an exploration cannot run away. The budget is
    spent where it helps: the cheap single-shot dimensional solve runs for every problem, but
    the expensive Tournament only runs where it can actually improve things — when the
    dimensional system is UNDER-determined (a free π-group the data must choose among) or the
    single-shot did not already nail the fit. Budget flows to the promising candidates, not
    uniformly.
  * DEPTH TIERS — ``fast`` (single-shot only), ``medium`` (+ a short tournament), ``max`` (+ a
    long tournament). One name picks a coherent compute profile.
  * CHECKPOINT / RESUME — the campaign state (which problems are done, the accumulated graph
    records, the budget spent) serialises to JSON and resumes exactly. The DoD: a run
    checkpointed mid-campaign and resumed produces the IDENTICAL result as an uninterrupted
    run. That holds because each problem is solved with its OWN seed (``base_seed + index``),
    so a problem's outcome never depends on the campaign position or on prior RNG state.

Honest scope: this is a DETERMINISTIC budget/depth/checkpoint controller over the existing
engine + tournament; "hours-long" is modelled by the budget accounting, not wall-clock. The
external-simulator offload decision is the Universe Bridge (Phase 5), referenced but not here.
Offline, numpy-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .active_search import active_select
from .archive import EliteArchive
from .engine import DiscoveryProblem, discover_new_formulas, judge_candidate
from .graph import DiscoveryGraph
from .tournament import evolve


@dataclass(frozen=True)
class DepthTier:
    """A coherent compute profile: whether to run the tournament and how hard."""

    name: str
    use_tournament: bool
    generations: int
    population: int


FAST = DepthTier("fast", use_tournament=False, generations=0, population=0)
MEDIUM = DepthTier("medium", use_tournament=True, generations=8, population=16)
MAX = DepthTier("max", use_tournament=True, generations=24, population=32)
TIERS = {t.name: t for t in (FAST, MEDIUM, MAX)}

#: Single-shot R² at/above which a problem is "already solved" — the tournament is then
#: skipped (no budget spent where evolution cannot help).
ALREADY_SOLVED_R2 = 0.999999


@dataclass
class ExplorationState:
    """Serialisable checkpoint of a campaign: the tier, the ids of finished problems, the
    accumulated Anhang-C graph records, the budget already spent, and the base seed."""

    tier: str
    base_seed: int
    budget: int | None
    problems_done: list[str] = field(default_factory=list)
    graph_records: list[dict] = field(default_factory=list)
    budget_spent: int = 0

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps({
            "tier": self.tier, "base_seed": self.base_seed, "budget": self.budget,
            "problems_done": self.problems_done, "graph_records": self.graph_records,
            "budget_spent": self.budget_spent,
        }, indent=indent, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "ExplorationState":
        d = json.loads(text)
        return ExplorationState(
            tier=d["tier"], base_seed=d["base_seed"], budget=d["budget"],
            problems_done=list(d["problems_done"]), graph_records=list(d["graph_records"]),
            budget_spent=d["budget_spent"])


@dataclass(frozen=True)
class ControllerResult:
    """Outcome of a campaign run: the populated graph, the budget spent, the completed problem
    ids, the ids deferred to a later resume (by ``checkpoint_after``), and the resumable state.
    (A budget exhaustion does NOT defer a problem — it only skips its expensive tournament; the
    problem still completes on the single-shot solve.)"""

    graph: DiscoveryGraph
    budget_spent: int
    completed: tuple[str, ...]
    deferred_to_resume: tuple[str, ...]
    state: ExplorationState
    #: MAP-Elites quality-diversity archive of this run's gate-confirmed laws (a convenience over the
    #: graph; on resume it holds the resumed portion — the graph stays the complete, lossless record).
    archive: EliteArchive = field(default_factory=EliteArchive)


def _problem_id(problem: DiscoveryProblem, index: int) -> str:
    return problem.run_id or f"problem-{index}"


class ExplorationController:
    """Runs a campaign of discovery problems under a budget + depth tier, with checkpoint/resume."""

    def __init__(
        self,
        tier: str = "medium",
        *,
        budget: int | None = None,
        base_seed: int = 0,
        prioritize_by_information_gain: bool = False,
    ) -> None:
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}; choose from {sorted(TIERS)}")
        self.tier = TIERS[tier]
        self.budget = budget
        self.base_seed = base_seed
        #: When True, a budget that cannot afford ALL tournaments is spent on the most-informative
        #: eligible problems (InfoBAX uncertainty sampling via active_search) instead of input order.
        #: The gate still decides every verdict — this only chooses which problems get refined.
        self.prioritize_by_information_gain = prioritize_by_information_gain

    def _affordable(self, spent: int, cost: int) -> bool:
        return self.budget is None or spent + cost <= self.budget

    def _tournament(
        self,
        problem: DiscoveryProblem,
        index: int,
        known_laws: dict[str, dict[str, float]] | None,
        graph: DiscoveryGraph,
        archive: EliteArchive,
    ) -> bool:
        """Run the tier's tournament for ONE problem; if it improves on the single-shot best, record
        the evolved candidate — judged by the SAME gates — in the graph and archive. Returns whether it
        improved. Cost accounting stays with the caller. Deterministic (seed = ``base_seed + index``)."""
        report = evolve(problem, generations=self.tier.generations,
                        population=self.tier.population, seed=self.base_seed + index)
        if report.improved:  # record the evolved best, judged by the same gates
            verdict = judge_candidate(problem, report.best, known_laws=known_laws)
            graph.add_verdict(verdict, idea=problem.idea, target_name=problem.target.name,
                              provenance=("controller", f"tier:{self.tier.name}", "tournament"))
            archive.add(verdict.candidate, passed=verdict.passed)
        return report.improved

    def _run_prioritized(
        self,
        problems: list[DiscoveryProblem],
        known_laws: dict[str, dict[str, float]] | None,
        graph: DiscoveryGraph,
        archive: EliteArchive,
        completed: list[str],
    ) -> int:
        """Spend the tournament budget by Expected Information Gain (InfoBAX uncertainty sampling).

        Single-shot-solve EVERY problem first (cheap, always — this defines the graph and archive),
        then spend only the AFFORDABLE number of tournaments on the most-informative eligible problems
        (those whose pass/fail the surrogate is least certain about) instead of in input order. The
        gate stays the sole authority: ``active_search`` only chooses WHICH problems get the expensive
        refinement, never a verdict. Returns the total budget spent. Deterministic.
        """
        spent = 0
        eligible: list[tuple[DiscoveryProblem, int]] = []
        for index, problem in enumerate(problems):
            result = discover_new_formulas(problem, known_laws=known_laws)
            spent += len(result.all_records)
            best_r2 = max((r.candidate.r_squared for r in result.all_records), default=0.0)
            graph.add_result(result, target_name=problem.target.name,
                             provenance=("controller", f"tier:{self.tier.name}"))
            archive.add_result(result)
            completed.append(_problem_id(problem, index))
            if self.tier.use_tournament and best_r2 < ALREADY_SOLVED_R2:
                eligible.append((problem, index))

        tcost = self.tier.generations * self.tier.population
        if eligible and tcost > 0:
            affordable = (
                len(eligible) if self.budget is None
                else max(0, (self.budget - spent) // tcost)
            )
            if affordable > 0:
                # the gate (the expensive tournament) is active_search's oracle; the structural feature
                # (input/constant counts) lets the surrogate generalise "problems like this one".
                selection = active_select(
                    eligible,
                    lambda item: self._tournament(item[0], item[1], known_laws, graph, archive),
                    lambda item: (float(len(item[0].inputs)), float(len(item[0].constants))),
                    budget=int(affordable),
                )
                spent += tcost * selection.gate_calls
        return spent

    def run(
        self,
        problems: list[DiscoveryProblem],
        *,
        resume_from: ExplorationState | None = None,
        checkpoint_after: int | None = None,
        known_laws: dict[str, dict[str, float]] | None = None,
    ) -> ControllerResult:
        """Run (or resume) the campaign. Each problem is discovered single-shot; where the tier
        enables it AND it can help AND the budget allows, the tournament refines it. Every
        candidate is recorded in the graph. If `checkpoint_after` is set, the run STOPS after
        that many freshly-processed problems and returns a resumable state (the rest are left
        for a later `resume_from`). Deterministic: a problem's result depends only on the
        problem and `base_seed + index`, never on campaign position.
        """
        state = resume_from or ExplorationState(tier=self.tier.name, base_seed=self.base_seed,
                                                budget=self.budget)
        # resume: rebuild the live graph from the checkpoint's records (lossless round-trip),
        # so the final graph contains the pre-checkpoint nodes exactly as an uninterrupted run.
        graph = DiscoveryGraph.from_records(state.graph_records)
        archive = EliteArchive()  # quality-diversity collection of this run's confirmed laws

        done = set(state.problems_done)
        completed: list[str] = list(state.problems_done)
        skipped: list[str] = []
        spent = state.budget_spent
        fresh = 0

        if self.prioritize_by_information_gain:
            # InfoBAX path: a budget that cannot afford every tournament is spent on the most-
            # informative problems, not the first ones. Its greedy selection order is not
            # checkpoint-invariant, so it is refused with checkpoint/resume rather than silently
            # breaking the resume==uninterrupted guarantee (an honest limitation, not a hidden bug).
            if resume_from is not None or checkpoint_after is not None:
                raise ValueError(
                    "prioritize_by_information_gain is not supported with checkpoint/resume: its "
                    "greedy information-gain selection order is not checkpoint-invariant and would "
                    "break the resume==uninterrupted guarantee. Use it for single-pass campaigns."
                )
            spent = self._run_prioritized(problems, known_laws, graph, archive, completed)
        else:
            for index, problem in enumerate(problems):
                pid = _problem_id(problem, index)
                if pid in done:
                    continue
                if checkpoint_after is not None and fresh >= checkpoint_after:
                    skipped.append(pid)
                    continue

                result = discover_new_formulas(problem, known_laws=known_laws)
                spent += len(result.all_records)
                best_r2 = max((r.candidate.r_squared for r in result.all_records), default=0.0)

                # spend tournament budget only where evolution can help (under-determined or not
                # already solved) and the budget allows it — budget flows to the promising candidates
                if self.tier.use_tournament and best_r2 < ALREADY_SOLVED_R2:
                    tcost = self.tier.generations * self.tier.population
                    if self._affordable(spent, tcost):
                        self._tournament(problem, index, known_laws, graph, archive)
                        spent += tcost

                graph.add_result(result, target_name=problem.target.name,
                                 provenance=("controller", f"tier:{self.tier.name}"))
                archive.add_result(result)  # only gate-passing laws enter the diversity archive
                done.add(pid)
                completed.append(pid)
                fresh += 1

        new_state = ExplorationState(
            tier=self.tier.name, base_seed=self.base_seed, budget=self.budget,
            problems_done=completed, graph_records=graph.to_ledger_records(), budget_spent=spent)
        return ControllerResult(graph=graph, budget_spent=spent, completed=tuple(completed),
                                deferred_to_resume=tuple(skipped), state=new_state, archive=archive)
