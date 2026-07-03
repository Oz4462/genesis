"""Regression (2026-06-18 systematic-debugging): simulation/runner.py's structural case used to
report ``max(deflection_mm, stress_MPa)`` and guess the unit by magnitude — a physically meaningless
"wrong function" (a length and a stress are not comparable). The fix reports ONE quantity (the
cantilever deflection) with ONE unit ("mm"). This pins it so the bug cannot return.

Offline, no LLM, no CAD kernel (the BuildArtifact is constructed directly). Run:
  pytest tests/test_simulation_runner_fix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.cad.prototype_cad_builder import BuildArtifact, PrototypeSpec  # noqa: E402
from gen.simulation.runner import optimize_params, run_simulations_for_design  # noqa: E402


def _artifact(bb: tuple[float, float, float] = (120.0, 80.0, 10.0)) -> BuildArtifact:
    spec = PrototypeSpec(name="testplate", description="a load-bearing plate",
                         bounding_box_hint_mm=bb, quelle="test")
    return BuildArtifact(spec=spec, generated_code="", exports={}, dfm_report=[],
                         volume_estimate_cm3=48.0, quelle="test")


def test_structural_case_reports_one_quantity_with_a_consistent_unit():
    """The structural case is a deflection in mm — never a max() of incommensurable quantities, and
    the unit is fixed by the physics, not guessed from the number's magnitude."""
    res = run_simulations_for_design(_artifact(), loads={"force_n": 1000.0})
    struct = next(c for c in res.cases if c.domain == "structural_linear")
    assert struct.predicted_unit == "mm"
    assert struct.predicted_value >= 0.0


def test_optimize_params_exposes_param_names_without_crashing():
    """Regression (2026-06-19): runner.optimize_params returned ``res.param_names``, but
    OptimizationResult had no such field — an AttributeError on every call (a never-tested path).
    param_names is now a first-class field of the result and the call returns it."""
    import math
    res = optimize_params(lambda x: float((x[0] - 1.0) ** 2), [(0.0, 2.0)], param_names=["a"])
    assert res["param_names"] == ["a"]                 # used to raise AttributeError here
    assert set(res["best_params"]) == {"a"} and math.isfinite(res["best_value"])


def test_optimizer_actually_minimises_the_objective():
    """Wrong-function fix (2026-06-19): the 'quantum' selection applied the cost as a pure PHASE,
    which does not change |amplitude|², so argmax(probs) ignored the objective and returned a
    near-worst point (~0.14 for (x−1)²). The selection now starts from the true lowest-cost grid
    point, so the optimizer actually finds the minimum near x=1."""
    res = optimize_params(lambda x: float((x[0] - 1.0) ** 2), [(0.0, 2.0)], param_names=["a"])
    assert res["best_params"]["a"] == pytest.approx(1.0, abs=0.25)
    assert res["best_value"] < 0.07


def test_structural_prediction_scales_with_geometry_not_a_constant():
    """De-fake (Strang 2): the section inertia is now derived I = b·h³/12 from the ACTUAL bounding box,
    so a thicker plate is stiffer (less deflection, since I ∝ h³) — the prediction reflects the part,
    not the old hardcoded 12000 mm⁴ constant (which gave the same answer for every geometry)."""
    thin = run_simulations_for_design(_artifact((120.0, 80.0, 6.0)), loads={"force_n": 1000.0})
    thick = run_simulations_for_design(_artifact((120.0, 80.0, 12.0)), loads={"force_n": 1000.0})
    thin_d = next(c for c in thin.cases if c.domain == "structural_linear").predicted_value
    thick_d = next(c for c in thick.cases if c.domain == "structural_linear").predicted_value
    assert thick_d < thin_d
