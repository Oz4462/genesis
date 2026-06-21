"""Consolidation: ONE whole-body humanoid Specification fires EVERY registered robot δ-axis.

The system-level proof that the robot δ-axes compose. The flagship ``demo.humanoid_spec()`` carries
measurands for kinematics (2R arm reach), balance (static + dynamic ZMP), actuation (electric joint
torque-speed), compute (throughput, power, control latency) AND — newly — the sensor data bus
(bandwidth + poll-cycle latency). The pipeline's measurand-driven physics selection fires all of them
and the deterministic δ-gate composes them into ONE honest verdict.

This also closes a real gap found during consolidation: the ``digital_bus`` validators were registered
in the physics gate but no Specification carried ``bus.*`` measurands, so the axis never fired. The
flagship humanoid now exercises it. Offline, deterministic.
"""

from gen.demo import humanoid_spec
from gen.physics_selection import evaluate_spec_physics, select_physics_checks


def _fired_names(spec):
    checks, _gaps = select_physics_checks(spec)
    return {c.name for c in checks}


def test_one_humanoid_spec_fires_kinematics_actuation_compute_and_bus_together():
    fired = _fired_names(humanoid_spec())
    expected = {
        "arm reach (2R workspace)",                 # kinematics
        "balance (ZMP in support polygon)",         # static balance
        "electric joint actuator (torque-speed)",   # actuation
        "compute throughput budget",                # compute
        "inference power",
        "inference latency (control loop)",
        "data bus bandwidth",                       # the gap-closing axis: digital_bus
        "data bus poll-cycle latency",
    }
    missing = expected - fired
    assert not missing, f"these robot axes did not fire on the humanoid spec: {sorted(missing)}"


def test_the_composite_delta_gate_passes_over_all_axes_including_the_bus():
    ev = evaluate_spec_physics(humanoid_spec())
    gate = ev["gate"]
    assert gate.passed, f"the composite δ-physics gate failed: {gate.failures}"
    assert gate.failures == []
    # the bus axis is genuinely among the evaluated checks (not just selected)
    evaluated = {c.name for c in ev["checks"]}
    assert "data bus bandwidth" in evaluated and "data bus poll-cycle latency" in evaluated


def test_consolidation_is_deterministic():
    a = _fired_names(humanoid_spec())
    b = _fired_names(humanoid_spec())
    assert a == b
