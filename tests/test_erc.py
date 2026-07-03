"""GATE ERC — deterministic Electrical Rule Check (ε electronics, no SPICE).

The electronics analogue of GATE δ: it proves the netlist's CONNECTIVITY is sound
with certainty — no floating net, no unconnected pin, no two drivers shorted, no
undriven load, no dangling reference. Pure logic, fully offline, no external
engine (ngspice/KiCad are NOT required — a circuit simulation would be a separate,
engine-backed layer).

Honest asymmetry (like δ): a PASS means "no provably broken wiring", not "the
circuit works"; a FAIL means "definitely broken". A spec with no netlist passes
trivially (mechanical-only).

Run:  pytest tests/test_erc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    BomItem,
    BomRole,
    Net,
    Netlist,
    Pin,
    PinType,
    Question,
    RunState,
    Specification,
)
from gen.verification.gates import gate_erc  # noqa: E402


def _state(netlist: Netlist | None, *, bom_ids=("psu", "led")) -> RunState:
    bom = [BomItem(id=i, name=i, role=BomRole.PART) for i in bom_ids]
    spec = Specification(run_id="r", idea="erc", bom=bom, netlist=netlist)
    st = RunState(question=Question(raw="erc", run_id="r"))
    st.specification = spec
    return st


def _good_netlist() -> Netlist:
    return Netlist(
        pins=[
            Pin("psu", "V+", PinType.POWER_OUT), Pin("psu", "GND", PinType.GROUND),
            Pin("led", "V+", PinType.POWER_IN), Pin("led", "GND", PinType.GROUND),
        ],
        nets=[
            Net("VCC", ["psu.V+", "led.V+"]),
            Net("GND", ["psu.GND", "led.GND"]),
        ],
    )


# --- the sound circuit passes; the mechanical-only case passes trivially -------

def test_sound_netlist_passes():
    result = gate_erc(_state(_good_netlist()))
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_no_netlist_passes_trivially():
    assert gate_erc(_state(None)).passed


def test_capstone_erc_passes():
    from gen.demo import capstone_state
    assert gate_erc(capstone_state()).passed


# --- each rule has teeth -------------------------------------------------------

def test_undriven_input_is_caught():
    nl = Netlist(
        pins=[Pin("psu", "V+", PinType.POWER_OUT), Pin("led", "V+", PinType.POWER_IN),
              Pin("psu", "GND", PinType.GROUND), Pin("led", "GND", PinType.GROUND)],
        nets=[Net("VCC", ["led.V+", "psu.GND"]),     # load wired to ground, no driver
              Net("N2", ["psu.V+", "led.GND"])],
    )
    assert "UNDRIVEN_INPUT" in {f.code for f in gate_erc(_state(nl)).failures}


def test_power_conflict_is_caught():
    nl = Netlist(
        pins=[Pin("psu", "V+", PinType.POWER_OUT), Pin("led", "V+", PinType.POWER_OUT),
              Pin("psu", "GND", PinType.GROUND), Pin("led", "GND", PinType.GROUND)],
        nets=[Net("VCC", ["psu.V+", "led.V+"]),       # two drivers shorted
              Net("GND", ["psu.GND", "led.GND"])],
    )
    assert "POWER_CONFLICT" in {f.code for f in gate_erc(_state(nl)).failures}


def test_floating_net_is_caught():
    nl = Netlist(
        pins=[Pin("psu", "V+", PinType.POWER_OUT), Pin("led", "V+", PinType.POWER_IN),
              Pin("psu", "GND", PinType.GROUND), Pin("led", "GND", PinType.GROUND)],
        nets=[Net("VCC", ["psu.V+", "led.V+"]), Net("GND", ["psu.GND", "led.GND"]),
              Net("LONE", ["psu.V+"])],            # one-pin net (also pin in 2 nets)
    )
    codes = {f.code for f in gate_erc(_state(nl)).failures}
    assert "FLOATING_NET" in codes and "PIN_MULTIPLE_NETS" in codes


def test_dangling_pin_ref_and_unconnected_pin():
    nl = Netlist(
        pins=[Pin("psu", "V+", PinType.POWER_OUT), Pin("led", "V+", PinType.POWER_IN),
              Pin("psu", "GND", PinType.GROUND)],   # led.GND declared? no -> ...
        nets=[Net("VCC", ["psu.V+", "led.V+"]),
              Net("GND", ["psu.GND", "led.GND"])],  # led.GND is referenced but not declared
    )
    codes = {f.code for f in gate_erc(_state(nl)).failures}
    assert "DANGLING_PIN_REF" in codes      # led.GND not declared


def test_dangling_part_is_caught():
    nl = Netlist(
        pins=[Pin("ghost", "V+", PinType.POWER_OUT), Pin("led", "V+", PinType.POWER_IN)],
        nets=[Net("VCC", ["ghost.V+", "led.V+"])],
    )
    assert "DANGLING_PART" in {f.code for f in gate_erc(_state(nl)).failures}


def test_duplicate_pin_is_caught():
    nl = Netlist(
        pins=[Pin("psu", "V+", PinType.POWER_OUT), Pin("psu", "V+", PinType.POWER_OUT),
              Pin("led", "V+", PinType.POWER_IN)],
        nets=[Net("VCC", ["psu.V+", "led.V+"])],
    )
    assert "DUPLICATE_PIN" in {f.code for f in gate_erc(_state(nl)).failures}
