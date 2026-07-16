"""cluster.py — the missing grenz capability-cluster orchestrator.

The 7 grenz "capability" modules form a real linear pipeline, but they imported only each other
with NO orchestrator chaining them — so they were islands (STATUS.md §4). This wires the real chain
behind one call (`run_capability_cluster`), reachable via ``genesis --mode horizon-full``:

    map_development_front → analyze_capability_gaps → build_milestone_ladder → build_test_stand
      → build_technology_roadmap → build_technology_prototype → run_bench_test
      (+ design_experiment_plan, off the milestone ladder)

HONESTY (STATUS.md §1): every stage calls the real engine. A stage failure is RECORDED and stops
the chain (downstream stages are honestly marked 'skipped — upstream missing'), never swallowed
into a fake success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ClusterStage:
    name: str
    status: str  # 'ok' | 'error' | 'skipped'
    detail: str
    error: str | None = None


@dataclass
class CapabilityClusterResult:
    idea: str
    stages: list[ClusterStage] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s.status != "error" for s in self.stages)

    @property
    def summary(self) -> str:
        mark = {"ok": "✓", "error": "✗", "skipped": "·"}
        n_ok = sum(s.status == "ok" for s in self.stages)
        lines = [f"grenz capability cluster — {n_ok}/{len(self.stages)} stages:"]
        for s in self.stages:
            tail = f" — {s.error}" if s.error else ""
            lines.append(f"    {mark.get(s.status, '?')} {s.name}: {s.detail}{tail}")
        return "\n".join(lines)


def run_capability_cluster(idea: str, *, run_id: str | None = None) -> CapabilityClusterResult:
    """Run the real 8-stage grenz capability pipeline on ``idea``. Honest cascade on failure."""
    from .bench_test_runner import run_bench_test
    from .capability_gap_analyzer import analyze_capability_gaps
    from .development_front import map_development_front
    from .experiment_designer import design_experiment_plan
    from .milestone_builder import build_milestone_ladder
    from .technology_builder import build_technology_prototype
    from .technology_roadmapper import build_technology_roadmap
    from .teststand_architect import build_test_stand

    res = CapabilityClusterResult(idea=idea)
    out = res.outputs

    def stage(name: str, fn: Callable[[], tuple[Any, str]], *, needs: list[str] | None = None) -> None:
        if needs and any(out.get(k) is None for k in needs):
            res.stages.append(ClusterStage(name, "skipped", f"upstream missing: {needs}"))
            return
        try:
            value, detail = fn()
            out[name] = value
            res.stages.append(ClusterStage(name, "ok", detail))
        except Exception as e:
            res.stages.append(ClusterStage(name, "error", "engine raised", error=f"{type(e).__name__}: {e}"))

    def _n(obj: Any, attr: str) -> int:
        return len(getattr(obj, attr, []) or [])

    def _front() -> tuple[Any, str]:
        m = map_development_front(idea, run_id=run_id)
        return m, f"DevelopmentFrontMap (boundaries={_n(m, 'grenzen')}, ladder={_n(m, 'experimentleiter')})"

    def _gaps() -> tuple[Any, str]:
        r = analyze_capability_gaps(out["front_map"], idee=idea, run_id=run_id)
        return r, f"CapabilityGapReport (gaps={_n(r, 'gaps')})"

    def _ladder() -> tuple[Any, str]:
        ladder = build_milestone_ladder(out["front_map"], out["gap_report"], run_id=run_id)
        return ladder, f"MilestoneLadder (milestones={_n(ladder, 'milestones')})"

    def _stand() -> tuple[Any, str]:
        return build_test_stand(out["ladder"], run_id=run_id), "TestStandPlan"

    def _roadmap() -> tuple[Any, str]:
        return build_technology_roadmap(out["test_stand"], run_id=run_id), "TechnologyRoadmap"

    def _proto() -> tuple[Any, str]:
        return build_technology_prototype(out["roadmap"], run_id=run_id), "TechnologyPrototypePlan"

    def _bench() -> tuple[Any, str]:
        return run_bench_test(out["prototype"], run_id=run_id), "BenchTestPlan"

    def _experiment() -> tuple[Any, str]:
        return design_experiment_plan(out["ladder"], run_id=run_id), "ExperimentPlan"

    stage("front_map", _front)
    stage("gap_report", _gaps, needs=["front_map"])
    stage("ladder", _ladder, needs=["front_map", "gap_report"])
    stage("test_stand", _stand, needs=["ladder"])
    stage("roadmap", _roadmap, needs=["test_stand"])
    stage("prototype", _proto, needs=["roadmap"])
    stage("bench_test", _bench, needs=["prototype"])
    stage("experiment_plan", _experiment, needs=["ladder"])

    return res
