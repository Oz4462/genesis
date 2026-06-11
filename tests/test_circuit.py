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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.circuit import (  # noqa: E402
    Capacitor,
    CurrentSource,
    Inductor,
    Resistor,
    VoltageSource,
    solve_ac,
    solve_dc,
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
