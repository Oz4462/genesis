"""End-to-end delta-physics on a real spec — the drive shaft from demo.py.

This is the whole chain on an ACTUAL specification (not synthetic test data): the
measurand-tagged quantities of demo.drive_shaft_spec() drive physics_selection to
auto-build exactly the applicable checks, gate_delta_physics runs them, and the verdict
plus its evidence are asserted. Proves the engine works spec -> selection -> gate ->
verdict on a part the validators genuinely fit. Offline, no LLM.

Run:  pytest tests/test_drive_shaft_physics.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.demo import drive_shaft_spec  # noqa: E402
from gen.physics_selection import evaluate_spec_physics, select_physics_checks  # noqa: E402
from gen.physics_validation import run_physics_checks  # noqa: E402


def test_auto_selects_exactly_the_three_applicable_checks():
    checks, gaps = select_physics_checks(drive_shaft_spec())
    # a shaft has torsion, rotating-bending fatigue and whirl resonance; it has no
    # column (buckling), vessel (pressure) or declared Kt (notch) -> those don't appear
    assert {c.validator for c in checks} == {"torsion", "fatigue", "resonance"}
    assert gaps == []


def test_end_to_end_verdict_passes():
    result = evaluate_spec_physics(drive_shaft_spec())
    assert result["gate"].passed
    assert result["gate"].failures == []
    assert len(result["checks"]) == 3 and result["gaps"] == []


def test_torque_is_unit_converted_to_n_mm():
    checks, _ = select_physics_checks(drive_shaft_spec())
    torsion = next(c for c in checks if c.validator == "torsion")
    assert torsion.inputs["torque"] == 150000.0          # 150 N*m -> 150000 N*mm


def test_computed_safety_factors_are_sound():
    checks, _ = select_physics_checks(drive_shaft_spec())
    by_validator = {r["validator"]: r["result"] for r in run_physics_checks(checks)}
    # tau_max = 16*150000/(pi*25^3) ~ 48.9 MPa, strength 260 -> SF ~ 5.32
    assert math.isclose(by_validator["torsion"]["safety_factor"], 5.318, rel_tol=1e-3)
    # Goodman: 1/(80/290 + 20/585) ~ 3.225
    assert math.isclose(by_validator["fatigue"]["safety_factor"], 3.225, rel_tol=1e-3)
    # whirl 150 Hz over 50 Hz running -> ratio 3.0
    assert math.isclose(by_validator["resonance"]["ratio"], 3.0, rel_tol=1e-9)


def test_is_deterministic():
    a = evaluate_spec_physics(drive_shaft_spec())
    b = evaluate_spec_physics(drive_shaft_spec())
    assert a["gate"] == b["gate"] and [c.inputs for c in a["checks"]] == [
        c.inputs for c in b["checks"]]
