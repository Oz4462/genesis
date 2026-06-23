"""Characterization / facade-audit for circuit.py (MNA DC/AC/transient/nonlinear).

This is the authoritative facade-detector for the pure-numpy MNA solver. The
legacy test_circuit.py already pins several closed forms; this file independently
proves — for the depth audit — that the headline numbers are GENUINELY COMPUTED
from the input components (not canned), and that every documented fail-loud /
abstention path actually fires.

Facade-killer per the team convention:
  (a) the headline output changes MEANINGFULLY when a driving input changes
      (proves the component values are consumed), and
  (b) at least one NEGATIVE test fires the documented ValueError /
      numpy.linalg.LinAlgError / RuntimeError (proves the guards exist).

Offline, deterministic, no LLM, no external SPICE engine.

Run:  pytest tests/test_circuit_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.circuit import (  # noqa: E402
    Capacitor,
    CurrentSource,
    Diode,
    Inductor,
    Resistor,
    VoltageSource,
    solve_ac,
    solve_dc,
    solve_dc_nonlinear,
    solve_transient,
)


# --- (1) Ohm's law: source across one resistor ---------------------------------


def test_single_resistor_gives_ohms_law_current_and_node_voltage():
    # I = V/R and the driven node sits at the source voltage.
    v, i = solve_dc([VoltageSource("N", "0", 10.0, "S"), Resistor("N", "0", 5.0)])
    assert math.isclose(v["N"], 10.0, rel_tol=1e-12)
    assert math.isclose(i["S"], 10.0 / 5.0, rel_tol=1e-12)   # 2.0 A


def test_source_current_scales_inversely_with_resistance_input_consumed():
    # Halving R must double the delivered current — proves R is actually used,
    # not a constant baked into the solver.
    _, i_big = solve_dc([VoltageSource("N", "0", 10.0, "S"), Resistor("N", "0", 100.0)])
    _, i_small = solve_dc([VoltageSource("N", "0", 10.0, "S"), Resistor("N", "0", 50.0)])
    assert math.isclose(i_big["S"], 0.1, rel_tol=1e-12)
    assert math.isclose(i_small["S"], 0.2, rel_tol=1e-12)
    assert math.isclose(i_small["S"], 2.0 * i_big["S"], rel_tol=1e-12)


# --- (2) Two-resistor divider: analytic mid-node + input-consumed proof ---------


def test_divider_matches_analytic_mid_node():
    r1, r2, vin = 1000.0, 3000.0, 8.0
    v, _ = solve_dc([
        VoltageSource("IN", "0", vin, "S"),
        Resistor("IN", "M", r1), Resistor("M", "0", r2),
    ])
    assert math.isclose(v["M"], vin * r2 / (r1 + r2), rel_tol=1e-12)


def test_divider_mid_node_changes_when_a_resistor_changes():
    # Changing only R2 must move the mid-node voltage — the input is consumed.
    def mid(r2: float) -> float:
        v, _ = solve_dc([
            VoltageSource("IN", "0", 9.0, "S"),
            Resistor("IN", "M", 1000.0), Resistor("M", "0", r2),
        ])
        return v["M"]

    low = mid(1000.0)     # 9 * 1k/2k = 4.5
    high = mid(8000.0)    # 9 * 8k/9k = 8.0
    assert math.isclose(low, 4.5, rel_tol=1e-12)
    assert math.isclose(high, 8.0, rel_tol=1e-12)
    assert high > low     # raising R2 raises the divider output


@settings(max_examples=50, deadline=None)
@given(
    r1=st.floats(min_value=1.0, max_value=1e6),
    r2=st.floats(min_value=1.0, max_value=1e6),
    vin=st.floats(min_value=-50.0, max_value=50.0),
)
def test_divider_invariant_property(r1: float, r2: float, vin: float):
    # Invariant for ALL positive resistances: V_mid = Vin * R2/(R1+R2).
    v, _ = solve_dc([
        VoltageSource("IN", "0", vin, "S"),
        Resistor("IN", "M", r1), Resistor("M", "0", r2),
    ])
    expected = vin * r2 / (r1 + r2)
    assert math.isclose(v["M"], expected, rel_tol=1e-9, abs_tol=1e-12)


# --- (3) Transient: RC converges toward the DC steady state ---------------------


def test_rc_transient_converges_to_dc_steady_state():
    R, C, vsrc = 1000.0, 1e-6, 5.0
    tau = R * C
    # Run many time-constants: the capacitor node must approach the source voltage
    # (the DC steady state, where no current flows through R).
    _, h = solve_transient(
        [VoltageSource("IN", "0", vsrc, "S"), Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)],
        t_end=20 * tau, dt=tau / 50,
    )
    # cross-check the DC steady state the transient should be heading toward
    v_dc, _ = solve_dc([VoltageSource("IN", "0", vsrc, "S"), Resistor("IN", "OUT", R)])
    assert math.isclose(v_dc["OUT"], vsrc, rel_tol=1e-12)
    assert h["OUT"][-1] == pytest.approx(vsrc, abs=1e-3)
    # monotone charging: the final sample is much closer to steady state than an early one
    assert abs(vsrc - h["OUT"][-1]) < abs(vsrc - h["OUT"][1])


def test_rc_transient_target_tracks_source_voltage_input_consumed():
    # The steady-state the transient converges to must follow the source value.
    def final(vsrc: float) -> float:
        R, C = 1000.0, 1e-6
        tau = R * C
        _, h = solve_transient(
            [VoltageSource("IN", "0", vsrc, "S"), Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)],
            t_end=20 * tau, dt=tau / 50,
        )
        return h["OUT"][-1]

    assert final(3.0) == pytest.approx(3.0, abs=1e-3)
    assert final(7.5) == pytest.approx(7.5, abs=1e-3)


# --- (4) AC: reactive phasor magnitude of an RC low-pass ------------------------


def test_ac_rc_lowpass_phasor_magnitude():
    # |H(jw)| = 1/sqrt(1+(wRC)^2). Pick w = 2/RC so the answer is a non-trivial value.
    R, C = 2200.0, 4.7e-9
    omega = 2.0 / (R * C)
    v = solve_ac([VoltageSource("IN", "0", 1.0, "S"),
                  Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)], omega)
    wrc = omega * R * C                      # == 2 by construction
    expected_mag = 1.0 / math.sqrt(1.0 + wrc ** 2)
    assert math.isclose(abs(v["OUT"]), expected_mag, rel_tol=1e-9)
    assert math.isclose(abs(v["OUT"]), 1.0 / math.sqrt(5.0), rel_tol=1e-9)


def test_ac_magnitude_drops_as_frequency_rises_input_consumed():
    # A larger omega must attenuate the RC low-pass more — proves omega is consumed.
    R, C = 1000.0, 1e-6
    net = [VoltageSource("IN", "0", 1.0, "S"), Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)]
    lo = abs(solve_ac(net, 1.0 / (R * C))["OUT"])        # at cutoff: 1/sqrt(2)
    hi = abs(solve_ac(net, 100.0 / (R * C))["OUT"])      # 100x cutoff: heavily attenuated
    assert lo > hi
    assert math.isclose(lo, 1.0 / math.sqrt(2.0), rel_tol=1e-9)


# --- NEGATIVE tests: documented fail-loud / abstention paths --------------------


def test_nonpositive_resistor_raises_value_error():
    for bad in (0.0, -10.0):
        with pytest.raises(ValueError):
            solve_dc([VoltageSource("N", "0", 5.0, "S"), Resistor("N", "0", bad)])


def test_nonpositive_capacitor_raises_value_error():
    with pytest.raises(ValueError):
        solve_transient(
            [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "OUT", 1e3), Capacitor("OUT", "0", -1e-6)],
            t_end=1e-3, dt=1e-5,
        )


def test_nonpositive_inductor_raises_value_error():
    with pytest.raises(ValueError):
        solve_ac(
            [VoltageSource("IN", "0", 1.0, "S"), Inductor("IN", "OUT", 0.0), Resistor("OUT", "0", 50.0)],
            omega=1e3,
        )


def test_nonpositive_diode_isat_raises_value_error():
    with pytest.raises(ValueError):
        solve_dc_nonlinear([
            VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "D", 1000.0),
            Diode("D", "0", i_sat=0.0),
        ])


def test_floating_network_raises_linalg_error():
    # A resistor between two nodes with NO DC path to ground -> singular MNA matrix.
    with pytest.raises(np.linalg.LinAlgError):
        solve_dc([Resistor("X", "Y", 100.0)])


def test_nonconvergent_nonlinear_raises_runtime_error():
    # A forward-biased diode needs several Newton steps; max_iter=1 cannot converge.
    with pytest.raises(RuntimeError):
        solve_dc_nonlinear(
            [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "D", 1000.0), Diode("D", "0", 1e-12)],
            max_iter=1,
        )
