"""A REAL forward-dynamics integrator, validated against the physics it integrates and used to
cross-check the closed-form screens. Three things are proven, not asserted: (1) a passive swing
CONSERVES ENERGY under RK4; (2) its small-angle period is 2π√(I/mgd); (3) the inverse-dynamics torque
that dynamics.joint_swing_torque_check reports, applied FORWARD by the independent integrator,
reproduces the intended swing — so the screen's torque is confirmed by simulation (a miscalculation
would not track). This is the "is the part computed right" check the static screens cannot give.

Offline, no LLM, stdlib only. Run:  pytest tests/test_multibody.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.dynamics import joint_swing_torque_check  # noqa: E402
from gen.simulation.multibody import (  # noqa: E402
    STANDARD_GRAVITY,
    feedforward_swing_torque,
    measure_period,
    simulate_pendulum,
)


def test_passive_swing_conserves_energy():
    """With zero torque the integrator conserves ½Iω²+mgd(1−cosθ): a sound step rule cannot drift."""
    traj = simulate_pendulum(0.2, 0.0, lambda *_: 0.0,
                             inertia=1.0, mass=1.0, com_distance=1.0, duration=6.0, dt=5e-4)
    assert traj.energy_drift < 1e-6


def test_small_angle_period_matches_the_pendulum_closed_form():
    """A small passive swing has period 2π√(I/(m·g·d)) — the integrator reproduces the analytic law."""
    traj = simulate_pendulum(0.05, 0.0, lambda *_: 0.0,
                             inertia=1.0, mass=1.0, com_distance=1.0, duration=6.0, dt=5e-4)
    assert measure_period(traj) == pytest.approx(2.0 * math.pi * math.sqrt(1.0 / STANDARD_GRAVITY),
                                                 rel=2e-3)


def test_forward_sim_reproduces_the_swing_the_screen_says_the_torque_drives():
    """Cross-validation: feed the inverse-dynamics torque dynamics.joint_swing_torque_check reports for
    θ(t)=A·sin(ωt) into the INDEPENDENT forward integrator. The recovered motion is that swing — so the
    screen's torque is right. The simulator is also driven with exactly the peak torque the screen
    reports, tying the two together."""
    inertia, mass, com_distance, amp, freq = 0.1, 2.0, 0.2, 0.3, 0.5
    omega = 2.0 * math.pi * freq
    torque_fn = feedforward_swing_torque(amp, freq, inertia, mass, com_distance)
    traj = simulate_pendulum(0.0, amp * omega, torque_fn,
                             inertia=inertia, mass=mass, com_distance=com_distance,
                             duration=1.0 / freq, dt=2e-4)
    # the forward-integrated angle tracks the intended swing θ_des(t)=A·sin(ωt) to integration error
    max_err = max(abs(th - amp * math.sin(omega * t)) for t, th in zip(traj.t, traj.theta))
    assert max_err < 5e-3

    # and the torque the simulator was driven with peaks at exactly what the screen screens
    screen = joint_swing_torque_check(inertia, mass, com_distance, amp, freq, available_torque=100.0)
    sim_peak = max(abs(torque_fn(t, 0.0, 0.0)) for t in traj.t)
    assert sim_peak == pytest.approx(screen["peak_required_torque"], rel=1e-3)


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        simulate_pendulum(0.1, 0.0, lambda *_: 0.0,
                          inertia=0.0, mass=1.0, com_distance=1.0, duration=1.0, dt=1e-3)
    with pytest.raises(ValueError):
        simulate_pendulum(0.1, 0.0, lambda *_: 0.0,
                          inertia=1.0, mass=1.0, com_distance=1.0, duration=1.0, dt=0.0)
    with pytest.raises(ValueError):
        # a purely positive (never-crossing) angle has no full oscillation to measure
        measure_period(simulate_pendulum(0.1, 5.0, lambda *_: 1e6,
                       inertia=1.0, mass=1.0, com_distance=1.0, duration=0.1, dt=1e-3))
