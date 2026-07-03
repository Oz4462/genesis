"""Checkpoint round-trip — Specification -> dict -> Specification is lossless.

A reproducible run rests on a faithful record: serializing a spec and reading it
back must lose nothing (acceptance A5). This proves the inverse
specification_from_dict against _specification_to_dict over the full capstone spec
(which exercises every field: grounded/derived/decision quantities, geometry,
sourcing, domains, steps with tool/torque, site, decisions), and that a checkpoint
file written by save_checkpoint reloads into an equal spec that still passes the
gates.

Run:  pytest tests/test_roundtrip.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.demo import capstone_spec, capstone_state  # noqa: E402
from gen.runner import (  # noqa: E402
    _specification_to_dict,
    save_checkpoint,
    specification_from_dict,
)
from gen.verification.gates import gate_gamma  # noqa: E402


def test_dict_roundtrip_is_lossless():
    spec = capstone_spec()
    d1 = _specification_to_dict(spec)
    spec2 = specification_from_dict(d1)
    d2 = _specification_to_dict(spec2)
    assert d1 == d2                                  # nothing lost on the round trip


def test_reconstructed_spec_still_passes_gate():
    state = capstone_state()
    d = _specification_to_dict(state.specification)
    state.specification = specification_from_dict(d)
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_reconstructed_fields_match():
    spec = specification_from_dict(_specification_to_dict(capstone_spec()))
    # spot-check the depth fields survived
    screw = next(b for b in spec.bom if b.id == "b_screw")
    assert screw.sourcing is not None
    assert screw.sourcing.supplier == "McMaster-Carr"
    assert screw.sourcing.price_quantity_id == "q_price"
    led = next(b for b in spec.bom if b.id == "b_led")
    assert led.domain.value == "electronic"
    s2 = next(s for s in spec.steps if s.id == "s2")
    assert s2.tool == "4-mm-Innensechskantschlüssel" and s2.torque_quantity_id == "q_torque"
    assert spec.site is not None and spec.site.available_space == ("sx", "sy", "sz")
    bracket = next(c for c in spec.components if c.id == "c_bracket")
    assert bracket.material_density == "q_density"
    assert bracket.geometry.kind == "difference"


def test_checkpoint_file_roundtrip(tmp_path):
    from gen.runner import load_checkpoint
    state = capstone_state()
    save_checkpoint(str(tmp_path), state, "cfg")
    loaded = load_checkpoint(str(tmp_path / "capstone" / "checkpoint.json"))
    spec = specification_from_dict(loaded["specification"])
    assert _specification_to_dict(spec) == loaded["specification"]
