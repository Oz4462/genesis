"""Characterization / facade-detector for competitive_humanoid.build_humanoid.

This file is the AUTHORITATIVE depth-audit test (the legacy tests/test_competitive_humanoid.py is
left untouched). It proves the two whole-body humanoid specs are genuinely HumanoidConfig-driven —
the competitive headline numbers really live IN the built Specification, not just in the docstring —
and that a missing factual price fails LOUD instead of silently emitting an unpriced spec.

Two facade-killer properties per the team convention:
  (a) the headline output changes MEANINGFULLY when a driving cfg field changes  → input is consumed,
      not a canned constant;
  (b) a NEGATIVE case fires the documented fail-loud path                         → no silent default.

Offline, deterministic, no LLM in the build path.
Run:  pytest tests/test_competitive_humanoid_characterization.py
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.competitive_humanoid import (  # noqa: E402
    FLAGSHIP,
    PRINTED,
    REQUIRED_PRICE_KEYS,
    HumanoidConfig,
    build_humanoid,
    flagship_humanoid_spec,
    printed_humanoid_spec,
)
from gen.core.state import BomRole  # noqa: E402

# Unitree H2's documented 360 N·m peak joint torque is the 2026 benchmark the flagship must beat
# and the printed class must (honestly) sit below.
_UNITREE_H2_PEAK_TORQUE_NM = 360.0


def _by_id(spec) -> dict:
    """Map quantity-id → Quantity for the built spec (the spec is just a flat list of quantities)."""
    return {q.id: q for q in spec.quantities}


def _by_measurand(spec) -> dict:
    """Map declared measurand → Quantity (only quantities that carry one)."""
    return {q.measurand: q for q in spec.quantities if q.measurand}


# ---------------------------------------------------------------------------------------------------
# (1) the claimed torque edge is PRESENT in the spec and DIFFERENT between configs
# ---------------------------------------------------------------------------------------------------

def test_available_torque_lives_in_the_spec_and_differs_between_configs():
    """The headline '420 N·m beats H2's 360, printed 200 below it' edge is carried by the
    actuator.available_torque measurand of the BUILT spec — not just asserted in prose."""
    flag = _by_measurand(flagship_humanoid_spec())
    printed = _by_measurand(printed_humanoid_spec())

    q_flag = flag["actuator.available_torque"]
    q_printed = printed["actuator.available_torque"]

    # the exact competitive numbers live in the spec
    assert q_flag.value == 420.0
    assert q_printed.value == 200.0
    assert q_flag.unit == "N*m" and q_printed.unit == "N*m"

    # the edge is real AND different: flagship > H2 benchmark > printed
    assert q_flag.value > _UNITREE_H2_PEAK_TORQUE_NM > q_printed.value
    assert q_flag.value != q_printed.value


# ---------------------------------------------------------------------------------------------------
# (2) cfg fields are CONSUMED — changing a lever changes the corresponding built quantity
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name,measurand,new_value",
    [
        ("joint_torque_nm", "actuator.joint_torque", 999.0),
        ("available_torque_nm", "actuator.available_torque", 777.0),
        ("reach_l1", "arm.link1_length", 1.111),
        ("reach_l2", "arm.link2_length", 1.222),
        ("compute_workload_tops", "compute.workload_tops", 3210.0),
        ("compute_chip_tops", "compute.chip_tops", 8765.0),
    ],
)
def test_cfg_field_drives_its_quantity(field_name, measurand, new_value):
    """Each competitive lever flows through to its measurand-tagged quantity in the built spec —
    proving the input is consumed, not a hardcoded constant."""
    base = build_humanoid(PRINTED)
    base_q = _by_measurand(base)[measurand]
    # the chosen probe value must actually differ from the baseline, else the test is vacuous
    assert base_q.value != new_value

    mutated_cfg = dataclasses.replace(PRINTED, **{field_name: new_value})
    mutated = build_humanoid(mutated_cfg)
    assert _by_measurand(mutated)[measurand].value == new_value


def test_available_torque_propagates_into_the_derived_bolt_loadpath():
    """available_torque_nm is not a dead label: it drives the motor-flange reaction force
    (q_mount_reaction = q_avail_tau / 0.035) and thus the per-bolt shear load — a real downstream
    derivation. Doubling the torque doubles the flange reaction."""
    base = _by_id(build_humanoid(PRINTED))
    doubled = _by_id(build_humanoid(
        dataclasses.replace(PRINTED, available_torque_nm=PRINTED.available_torque_nm * 2.0)))
    assert doubled["q_mount_reaction"].value == pytest.approx(base["q_mount_reaction"].value * 2.0)
    assert doubled["q_bolt_load"].value == pytest.approx(base["q_bolt_load"].value * 2.0)


# ---------------------------------------------------------------------------------------------------
# (3) nine printable component types + a fully-priced BOM
# ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("spec_fn", [printed_humanoid_spec, flagship_humanoid_spec])
def test_nine_printable_component_types(spec_fn):
    """Both specs expose exactly nine printable structural component TYPES, each with real CSG
    geometry (the body parts + the gripper hand)."""
    spec = spec_fn()
    assert len(spec.components) == 9
    assert len({c.id for c in spec.components}) == 9          # distinct types
    assert all(c.geometry is not None for c in spec.components)


@pytest.mark.parametrize("spec_fn", [printed_humanoid_spec, flagship_humanoid_spec])
def test_every_sourced_bom_price_resolves_to_a_declared_quantity(spec_fn):
    """Every BOM line that declares a price points at a quantity that actually exists in the spec —
    so the buy-list costs out completely, with no dangling price reference."""
    spec = spec_fn()
    quantity_ids = {q.id for q in spec.quantities}

    priced = [b for b in spec.bom if b.sourcing and b.sourcing.price_quantity_id]
    assert priced, "expected purchased BOM items carrying a price reference"
    for item in priced:
        assert item.sourcing.price_quantity_id in quantity_ids, (
            f"BOM item {item.id!r} references undeclared price quantity "
            f"{item.sourcing.price_quantity_id!r}")

    # every purchased PART (not a TOOL) must be priced — no silently unpriced purchase
    purchased_parts = [b for b in spec.bom
                       if b.role == BomRole.PART and b.component_id is None]
    for item in purchased_parts:
        assert item.sourcing is not None and item.sourcing.price_quantity_id is not None, (
            f"purchased part {item.id!r} has no price reference")


# ---------------------------------------------------------------------------------------------------
# NEGATIVE test: a missing price key must fail LOUD (no silent unpriced spec)
# ---------------------------------------------------------------------------------------------------

def test_missing_price_key_fails_loud_naming_the_key():
    """A HumanoidConfig whose prices dict drops a required key must raise a clear ValueError that
    NAMES the missing key — never silently emit an unpriced spec (Kernprinzip 'keine stillen
    Defaults bei faktischen Dingen')."""
    incomplete_prices = {k: 1.0 for k in REQUIRED_PRICE_KEYS if k != "motor"}
    bad_cfg = dataclasses.replace(PRINTED, prices=incomplete_prices)

    with pytest.raises(ValueError, match="motor"):
        build_humanoid(bad_cfg)


@pytest.mark.parametrize("missing_key", list(REQUIRED_PRICE_KEYS))
def test_each_required_price_key_is_individually_guarded(missing_key):
    """Dropping ANY single required price key fails loud — the guard covers the whole buy-list,
    not just one convenient key."""
    prices = {k: 1.0 for k in REQUIRED_PRICE_KEYS if k != missing_key}
    bad_cfg = dataclasses.replace(PRINTED, prices=prices)
    with pytest.raises(ValueError, match=missing_key):
        build_humanoid(bad_cfg)


def test_empty_prices_reports_all_missing_keys():
    """An empty prices dict names every missing key, so the failure is fully diagnosable at once."""
    bad_cfg = dataclasses.replace(PRINTED, prices={})
    with pytest.raises(ValueError) as exc:
        build_humanoid(bad_cfg)
    msg = str(exc.value)
    assert all(k in msg for k in REQUIRED_PRICE_KEYS)


def test_complete_prices_build_succeeds():
    """Positive control for the guard: a complete prices dict builds without raising."""
    spec = build_humanoid(dataclasses.replace(PRINTED, prices=dict(PRINTED.prices)))
    assert spec.run_id == PRINTED.run_id


# ---------------------------------------------------------------------------------------------------
# property: the available-torque lever is an EXACT pass-through into its quantity for any value
# ---------------------------------------------------------------------------------------------------

@settings(max_examples=40, deadline=None)
@given(tau=st.floats(min_value=1.0, max_value=5000.0, allow_nan=False, allow_infinity=False))
def test_available_torque_is_exact_passthrough_property(tau):
    """INVARIANT: whatever finite positive available_torque_nm the cfg carries appears verbatim as
    the actuator.available_torque quantity value in the built spec — the lever is a true input,
    not snapped to a constant."""
    spec = build_humanoid(dataclasses.replace(FLAGSHIP, available_torque_nm=tau))
    assert _by_measurand(spec)["actuator.available_torque"].value == tau
