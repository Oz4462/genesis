"""Tests for the thermal (cooling) invention domain — un-domain-locking `invent`.

A cooling brief must ground through REAL THERMAL physics (cold-plate conduction ΔT, the `overtemperature`
δ-recipe), NOT the mechatronics resonance check. A sound cold plate passes; an over-bold one (too thin/poor
conductor, junction over its limit) yields an honest gap, not a fabricated pass. Offline + deterministic.
"""

from __future__ import annotations

import asyncio

from gen.core.state import Possibility
from gen.inventor.brief import InventionBrief
from gen.inventor.domains.base import ARCHITECT_SYSTEM, parse_quantities
from gen.inventor.domains.thermal import ThermalDomain, scripted_thermal_architect
from gen.llm.parsing import extract_json


def _concept() -> Possibility:
    return Possibility(
        id="c-cool",
        statement="Hochtemperatur-Direktchip-Flüssigkühlung (wasserfrei)",
        mechanism="Warmwasser-Cold-Plates im geschlossenen Kreis + Trockenkühler",
        grounding=["https://openalex.org/W-direct-to-chip"],
    )


def _ground(architect):
    return asyncio.run(
        ThermalDomain().ground(_concept(), InventionBrief(field="cooling", run_id="t-cool"), architect)
    )


def test_cooling_concept_grounds_through_thermal_conduction_gate():
    """The real conduction check fires (overtemperature) and the spec carries thermal measurands — and
    crucially NOT a vibration measurand (the old domain-locked behavior)."""
    inv = _ground(scripted_thermal_architect())
    assert inv.physics_verified is True
    spec = inv.specification
    assert spec is not None
    measurands = {q.measurand for q in spec.quantities}
    assert "thermal.power_dissipation" in measurands
    assert "material.thermal_conductivity" in measurands
    assert not any((m or "").startswith("vibration.") for m in measurands)


def test_overbold_cold_plate_fails_honestly_not_a_fake_pass():
    """A poor/thin cold plate with little headroom pushes the junction over its limit → δ-gate FAILS →
    physics_verified False + an honest gap (the anti-hallucination contract: a failing design is not a pass)."""
    bad = scripted_thermal_architect(
        chip_power_w=2000.0,
        plate_conductivity_w_mk=15.0,    # poor conductor (not copper)
        plate_area_mm2=200.0,            # tiny contact area
        plate_thickness_mm=20.0,         # long conduction path
        coolant_temp_k=323.15,
        max_junction_k=333.15,           # only ~10 K headroom
    )
    inv = _ground(bad)
    assert inv.physics_verified is False
    assert inv.gaps  # honest gap, never a silent pass


def test_thermal_architect_emits_no_vibration_measurand():
    """Direct check on the architect output: thermal measurands present, zero vibration measurands."""
    resp = asyncio.run(scripted_thermal_architect().complete(system=ARCHITECT_SYSTEM, user="x"))
    measurands = {q.measurand for q in parse_quantities(extract_json(resp.text, agent="t")["quantities"])}
    assert "thermal.power_dissipation" in measurands
    assert "thermal.ambient_temp" in measurands
    assert not any((m or "").startswith("vibration.") for m in measurands)
