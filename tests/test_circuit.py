"""DC operating-point solver (MNA, the SPICE delta-layer) verified against Ohm.

circuit.py is Modified Nodal Analysis in pure numpy - the linear-DC core of every
SPICE engine, with no external simulator (ngspice was not installed). The tests
pin it against closed-form circuit theory: Ohm's law, a resistive divider, an
independent current source, and the capstone's own numbers - the 12 V PSU across
the LED strip's operating-point resistance delivers exactly its rated 1.5 A, which
is the current the electrical constraint (PSU 2 A >= LED 1.5 A) assumes.

Offline, no LLM, no external engine.

Run:  pytest tests/test_circuit.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.circuit import (  # noqa: E402
    THERMAL_VOLTAGE,
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


def test_ohms_law():
    v, i = solve_dc([VoltageSource("VCC", "0", 12.0, "PSU"), Resistor("VCC", "0", 8.0)])
    assert math.isclose(v["VCC"], 12.0, rel_tol=1e-9)
    assert math.isclose(i["PSU"], 1.5, rel_tol=1e-9)        # I = V/R = 12/8


def test_resistive_divider():
    v, i = solve_dc([
        VoltageSource("A", "0", 12.0, "S"),
        Resistor("A", "M", 1000.0), Resistor("M", "0", 2000.0),
    ])
    assert math.isclose(v["M"], 8.0, rel_tol=1e-9)          # 12 * 2k/(1k+2k)
    assert math.isclose(i["S"], 12.0 / 3000.0, rel_tol=1e-9)


def test_current_source_drives_resistor():
    # 2 mA into a 1k resistor to ground -> 2 V
    v, _ = solve_dc([CurrentSource("0", "N", 0.002), Resistor("N", "0", 1000.0)])
    assert math.isclose(v["N"], 2.0, rel_tol=1e-9)


def test_capstone_psu_delivers_the_rated_led_current():
    from gen.demo import capstone_state
    q = {x.id: x for x in capstone_state().specification.quantities}
    v_led = q["q_led_v"].value        # 12 V
    a_led = q["q_led_a"].value        # 1.5 A
    r_led = v_led / a_led             # operating-point resistance of the strip, 8 ohm
    v, i = solve_dc([
        VoltageSource("VCC", "0", q["q_psu_v"].value, "PSU"),
        Resistor("VCC", "0", r_led),
    ])
    assert math.isclose(v["VCC"], 12.0, rel_tol=1e-9)
    assert math.isclose(i["PSU"], a_led, rel_tol=1e-9)      # PSU delivers exactly 1.5 A
    assert i["PSU"] <= q["q_psu_a"].value                   # within the 2 A rating


# --- Schritt-7-Härtungen (Review 2026-07-04): Eingangs-Validierung -------------

def test_duplicate_source_names_fail_loud():
    """C1: zwei gleichnamige Quellen überschrieben sich still in source_i —
    das muss ein lauter ValueError sein, kein verschwundener Strom."""
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        solve_dc([
            VoltageSource("A", "0", 5.0, "S"), VoltageSource("B", "0", 3.0, "S"),
            Resistor("A", "0", 10.0), Resistor("B", "0", 10.0),
        ])


def test_two_default_named_sources_fail_loud():
    """C1b: der Default-Name 'V' ist truthy — zwei unbenannte Quellen kollidieren
    genauso und müssen genauso laut scheitern."""
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        solve_dc([
            VoltageSource("A", "0", 5.0), VoltageSource("B", "0", 3.0),
            Resistor("A", "0", 10.0), Resistor("B", "0", 10.0),
        ])


def test_empty_source_name_falls_back_to_indexed_key():
    """C1c: der f'V{k}'-Fallback war toter Code — bei leerem Namen ist er jetzt live."""
    _, i = solve_dc([VoltageSource("A", "0", 5.0, name=""), Resistor("A", "0", 10.0)])
    assert math.isclose(i["V0"], 0.5, rel_tol=1e-9)


def test_invalid_resistance_raises_value_error():
    """C2: ohms=0 war ZeroDivisionError, negative/NaN ohms wurden still gestempelt."""
    for bad in (0.0, -8.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="ohms"):
            solve_dc([VoltageSource("A", "0", 12.0, "S"), Resistor("A", "0", bad)])


def test_transient_rejects_bad_dt_and_reactives():
    """C2b: dt<=0/NaN crashte; negative farads/henries liefen still durch."""
    parts = [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "OUT", 1000.0),
             Capacitor("OUT", "0", 1e-6)]
    for bad_dt in (0.0, -1e-6, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="dt"):
            solve_transient(parts, t_end=1e-3, dt=bad_dt)
    with pytest.raises(ValueError, match="t_end"):
        solve_transient(parts, t_end=float("nan"), dt=1e-6)
    with pytest.raises(ValueError, match="farads"):
        solve_transient([VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "OUT", 1e3),
                         Capacitor("OUT", "0", -1e-6)], t_end=1e-3, dt=1e-6)
    with pytest.raises(ValueError, match="henries"):
        solve_transient([VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "M", 1e3),
                         Inductor("M", "0", 0.0)], t_end=1e-3, dt=1e-6)


def test_ac_rejects_omega_zero_with_inductor_and_bad_parts():
    """C5: omega=0 mit L war ZeroDivisionError — jetzt ein klarer ValueError;
    C2c: auch die AC-Stempel validieren ohms/farads/henries."""
    with pytest.raises(ValueError, match="omega"):
        solve_ac([VoltageSource("IN", "0", 1.0, "S"), Inductor("IN", "0", 1e-3)], 0.0)
    for bad_w in (float("nan"), float("inf"), -100.0):
        with pytest.raises(ValueError, match="omega"):
            solve_ac([VoltageSource("IN", "0", 1.0, "S"), Resistor("IN", "0", 1.0)], bad_w)
    with pytest.raises(ValueError, match="ohms"):
        solve_ac([VoltageSource("IN", "0", 1.0, "S"), Resistor("IN", "0", 0.0)], 100.0)
    with pytest.raises(ValueError, match="henries"):
        solve_ac([VoltageSource("IN", "0", 1.0, "S"), Inductor("IN", "0", -1e-3)], 100.0)
    with pytest.raises(ValueError, match="farads"):
        solve_ac([VoltageSource("IN", "0", 1.0, "S"), Capacitor("IN", "0", 0.0)], 100.0)


def test_nonlinear_dc_with_zero_unknown_nodes_converges_trivially():
    """C4: Diode von Ground nach Ground → leere nodes-Liste → max() warf ValueError
    statt trivial zu konvergieren."""
    node_v, _ = solve_dc_nonlinear([Diode("0", "0", 1e-12, 1.0)])
    assert node_v["0"] == 0.0


def test_empty_network_is_vacuous_not_an_error():
    """C3 (Doc-Truth): solve_dc([]) ist als Solver ok (leeres System), aber als
    Gate vakuös — der Docstring deklariert das; dieser Test pinnt das Verhalten."""
    v, i = solve_dc([])
    assert v == {"0": 0.0} and i == {}


# --- AC (frequency-domain) MNA vs the analytic transfer function ---------------

def test_rc_lowpass_at_cutoff():
    # RC low-pass H(jw) = 1/(1 + jwRC); at w = 1/RC, |H| = 1/sqrt(2), phase = -45 deg
    R, C = 1000.0, 1e-6
    wc = 1.0 / (R * C)
    v = solve_ac([VoltageSource("IN", "0", 1.0, "S"),
                  Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)], wc)
    H = v["OUT"]
    assert math.isclose(abs(H), 1.0 / math.sqrt(2), rel_tol=1e-9)
    assert math.isclose(math.degrees(math.atan2(H.imag, H.real)), -45.0, abs_tol=1e-6)


def test_rc_lowpass_matches_theory_across_band():
    R, C = 2200.0, 4.7e-9
    for w in (1e3, 1e5, 1e7):
        v = solve_ac([VoltageSource("IN", "0", 1.0, "S"),
                      Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)], w)
        theory = 1.0 / (1.0 + 1j * w * R * C)
        assert math.isclose(abs(v["OUT"]), abs(theory), rel_tol=1e-9)


def test_lc_resonance_blocks_then_passes():
    # series L with shunt R: at low w the inductor passes, at high w it blocks
    R, L = 50.0, 1e-3
    lo = solve_ac([VoltageSource("IN", "0", 1.0, "S"), Inductor("IN", "OUT", L),
                   Resistor("OUT", "0", R)], 10.0)
    hi = solve_ac([VoltageSource("IN", "0", 1.0, "S"), Inductor("IN", "OUT", L),
                   Resistor("OUT", "0", R)], 1e6)
    assert abs(lo["OUT"]) > 0.9          # inductor ~ short at low frequency
    assert abs(hi["OUT"]) < 0.1          # inductor ~ open at high frequency


# --- non-linear DC (diode, Newton-Raphson) vs the analytic operating point -----

def _diode_op_reference(vs, r, i_sat, n=1.0):
    """The exact operating point: the diode current equals the load-line current."""
    import math

    vt = n * THERMAL_VOLTAGE
    lo, hi = 0.0, vs
    for _ in range(200):                              # bisection on the residual
        vd = 0.5 * (lo + hi)
        resid = i_sat * (math.exp(vd / vt) - 1.0) - (vs - vd) / r
        if resid > 0:
            hi = vd
        else:
            lo = vd
    return 0.5 * (lo + hi)


def test_diode_operating_point_matches_load_line():
    for vs, r, i_sat in ((5.0, 1000.0, 1e-12), (3.3, 220.0, 1e-14), (12.0, 4700.0, 1e-9)):
        v, _ = solve_dc_nonlinear([
            VoltageSource("IN", "0", vs, "S"), Resistor("IN", "D", r),
            Diode("D", "0", i_sat, 1.0),
        ])
        assert math.isclose(v["D"], _diode_op_reference(vs, r, i_sat), abs_tol=1e-7)


def test_diode_blocks_reverse():
    # source reversed: the diode is reverse-biased, only ~ -i_sat flows
    v, _ = solve_dc_nonlinear([
        VoltageSource("IN", "0", -5.0, "S"), Resistor("IN", "D", 1000.0),
        Diode("D", "0", 1e-12, 1.0),
    ])
    assert v["D"] < 0.0                                # no forward conduction


def test_no_diode_falls_back_to_linear_dc():
    _, i = solve_dc_nonlinear([VoltageSource("VCC", "0", 12.0, "PSU"), Resistor("VCC", "0", 8.0)])
    assert math.isclose(i["PSU"], 1.5, rel_tol=1e-9)


# --- transient (time-domain) analysis vs the analytic RC / RL response ----------

def test_rc_charging_follows_the_exponential():
    R, C = 1000.0, 1e-6
    tau = R * C
    t, h = solve_transient(
        [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)],
        t_end=5 * tau, dt=tau / 200,
    )
    import numpy as np
    t = np.array(t)
    vout = np.array(h["OUT"])
    for k in (1, 3, 5):                              # at t = 1,3,5 tau
        i = int(np.argmin(np.abs(t - k * tau)))
        analytic = 5.0 * (1.0 - math.exp(-t[i] / tau))
        assert abs(vout[i] - analytic) < 0.02 * 5.0  # within 2% of full scale


def test_rc_charging_converges_with_smaller_step():
    R, C = 1000.0, 1e-6
    tau = R * C
    analytic = 5.0 * (1.0 - math.exp(-1.0))         # at t = tau
    errs = []
    for n in (50, 400):
        t, h = solve_transient(
            [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "OUT", R), Capacitor("OUT", "0", C)],
            t_end=tau, dt=tau / n,
        )
        errs.append(abs(h["OUT"][-1] - analytic))
    assert errs[1] < errs[0]                          # finer step -> smaller error


def test_rl_voltage_decays_as_the_inductor_saturates():
    R, L = 1000.0, 1e-3
    tau = L / R
    _, h = solve_transient(
        [VoltageSource("IN", "0", 5.0, "S"), Resistor("IN", "M", R), Inductor("M", "0", L)],
        t_end=6 * tau, dt=tau / 100,
    )
    assert h["M"][1] > 4.5                            # inductor blocks initially
    assert h["M"][-1] < 0.2                           # then saturates (short)
