"""H4: harness wire lengths + connector pinouts in package section."""

from __future__ import annotations

from gen.core.state import Net, Netlist
from gen.electronics import Component, HarnessSegment, HarnessSpec, route_harness
from gen.pipelines.realization_package import (
    build_harness_section,
    extract_connector_pinouts,
    extract_wire_runs,
    write_harness_section,
)


def _elec_pieces():
    segs = [
        HarnessSegment(
            from_ref="J1",
            to_ref="ESC1",
            gauge_mm2=1.5,
            length_mm=400.0,
            signals=["PWR+", "PWR-", "GND"],
            current_a=20.0,
            voltage_v=48.0,
            quelle="test",
        ),
        HarnessSegment(
            from_ref="MCU1",
            to_ref="ESC1",
            gauge_mm2=0.25,
            length_mm=150.0,
            signals=["CAN_H", "CAN_L"],
            current_a=0.1,
            voltage_v=5.0,
            quelle="test",
        ),
    ]
    harness = HarnessSpec(
        segments=segs,
        total_mass_est_g=80.0,
        emc_measures=["twisted pair CAN"],
        bus_type="CAN-FD",
        redundancy="none",
        tether_support=False,
        quelle="test",
    )
    routed = route_harness(harness, run_id="h4")
    comps = [
        Component(
            id="ESC1",
            name="ESC",
            kind="esc",
            v_nom=48.0,
            i_max=30.0,
            p_max_dissip=20.0,
            footprint_mm=(40, 30, 10),
            pin_names=["PWR+", "PWR-", "GND", "CAN_H", "CAN_L", "PWM"],
        ),
        Component(
            id="MCU1",
            name="MCU",
            kind="mcu",
            v_nom=3.3,
            i_max=0.2,
            p_max_dissip=0.5,
            footprint_mm=(10, 10, 2),
            pin_names=["CAN_H", "CAN_L", "3V3", "GND"],
        ),
    ]
    nl = Netlist(
        pins=[],
        nets=[
            Net(name="CAN_H", pins=["MCU1.CAN_H", "ESC1.CAN_H"]),
            Net(name="CAN_L", pins=["MCU1.CAN_L", "ESC1.CAN_L"]),
            Net(name="GND", pins=["ESC1.GND", "MCU1.GND"]),
        ],
    )
    return {
        "harness": harness,
        "routed_harness": routed,
        "netlist": nl,
        "components": comps,
        "auto_placement": [],
    }


def test_extract_wire_runs_uses_routed_eff_length():
    ep = _elec_pieces()
    wires = extract_wire_runs(ep)
    assert len(wires) == 2
    assert wires[0]["length_basis"] == "routed_eff_with_slack"
    assert wires[0]["length_mm"] > 400.0  # slack applied
    assert wires[0]["from"] == "J1" and wires[0]["to"] == "ESC1"


def test_extract_pinouts_from_netlist_and_components():
    ep = _elec_pieces()
    pinouts = extract_connector_pinouts(ep)
    refs = {p["ref"] for p in pinouts}
    assert "ESC1" in refs and "MCU1" in refs
    esc = next(p for p in pinouts if p["ref"] == "ESC1")
    nets = {row["pin"]: row["net"] for row in esc["pins"] if row.get("net")}
    assert nets.get("CAN_H") == "CAN_H"
    # PWM declared on component but not on nets → unconnected
    assert any(r.get("status") == "unconnected" for r in esc["pins"])


def test_harness_section_writes_tables(tmp_path):
    sec = build_harness_section(_elec_pieces(), run_id="h4")
    assert sec["wire_count"] == 2
    assert sec["total_wire_length_mm"] > 0
    assert sec["pinout_count"] >= 2
    write_harness_section(tmp_path, sec)
    md = (tmp_path / "HARNESS.md").read_text()
    assert "Wire cut list" in md
    assert "Connector pinouts" in md
    assert "W1" in md
    assert "graphical wiring diagram" in " ".join(sec["gaps"])
