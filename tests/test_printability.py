"""Printability validators — the design errors that only show up on the print bed.

Each rule is pinned to its research anchor (sources in printability.py /
docs/research/PRINT_DESIGN_FAILURES.md): bridge 10 mm, clearance 0.2/0.1 mm,
pin 3 mm, free wall 1.0 mm, thread M5, emboss 0.9 / engrave 0.5 mm, Z-retention
0.45. The two distinction tests matter most: a 0.9 mm wall that PASSES the
supported-wall rule (dfm.py, 0.8) still FAILS free-standing (1.0), and a
cross-layer stress that passes against the quoted strength still fails against
the retained 45 % — exactly the failures a print reveals and the CAD hides.

Offline, no LLM, no numpy.

Run:  pytest tests/test_printability.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.dfm import FDM_MIN_WALL_MM  # noqa: E402
from gen.printability import (  # noqa: E402
    FDM_MAX_BRIDGE_MM,
    FDM_MIN_UNSUPPORTED_WALL_MM,
    FDM_Z_STRENGTH_RETENTION,
    bridge_span_check,
    emboss_detail_check,
    fdm_fit_clearance_check,
    layer_adhesion_check,
    pin_diameter_check,
    thread_size_check,
    unsupported_wall_check,
)


# ---------------------------------------------------------------- bridge span
def test_bridge_8mm_prints_30mm_sags():
    ok = bridge_span_check(8.0)
    assert ok["ok"] and ok["safety_factor"] == pytest.approx(10.0 / 8.0)
    bad = bridge_span_check(30.0)                       # the classic sagging table
    assert not bad["ok"] and bad["safety_factor"] == pytest.approx(1.0 / 3.0)


def test_bridge_zero_span_is_no_bridge_and_limit_is_inclusive():
    assert bridge_span_check(0.0)["safety_factor"] == math.inf
    assert bridge_span_check(FDM_MAX_BRIDGE_MM)["ok"]   # exactly at the limit


def test_bridge_rejects_nonsense():
    with pytest.raises(ValueError):
        bridge_span_check(-1.0)
    with pytest.raises(ValueError):
        bridge_span_check(5.0, max_span=0.0)


# ------------------------------------------------------------- fit clearance
def test_clearance_process_floor_loose_and_tight():
    assert fdm_fit_clearance_check(0.25, fit="loose")["ok"]
    mid = fdm_fit_clearance_check(0.15, fit="loose")    # positive stack, still jams
    assert not mid["ok"] and mid["floor"] == 0.2
    assert fdm_fit_clearance_check(0.15, fit="tight")["ok"]


def test_clearance_interference_fails_without_raising():
    r = fdm_fit_clearance_check(-0.05)
    assert not r["ok"] and r["safety_factor"] < 0.0


def test_clearance_unknown_fit_raises():
    with pytest.raises(ValueError):
        fdm_fit_clearance_check(0.3, fit="press")


# ---------------------------------------------------------------- pin / boss
def test_pin_4mm_ok_but_fillet_recommended_6mm_clean():
    r4 = pin_diameter_check(4.0)
    assert r4["ok"] and r4["fillet_recommended"]        # < 5 mm: fillet the base
    r6 = pin_diameter_check(6.0)
    assert r6["ok"] and not r6["fillet_recommended"]


def test_pin_2mm_snaps_and_zero_raises():
    assert not pin_diameter_check(2.0)["ok"]
    with pytest.raises(ValueError):
        pin_diameter_check(0.0)


# ------------------------------------------------------------------- threads
def test_thread_m6_prints_m3_needs_insert():
    assert thread_size_check(6.0)["ok"]                 # M6 modeled thread
    m3 = thread_size_check(3.0)
    assert not m3["ok"] and m3["use_insert_or_tap"]
    with pytest.raises(ValueError):
        thread_size_check(-2.0)


# ---------------------------------------------------------- unsupported wall
def test_free_wall_stricter_than_supported_wall():
    # 0.9 mm passes the supported-wall DFM rule (0.8) but fails free-standing (1.0)
    assert 0.9 >= FDM_MIN_WALL_MM
    assert FDM_MIN_UNSUPPORTED_WALL_MM > FDM_MIN_WALL_MM
    r = unsupported_wall_check(0.9)
    assert not r["ok"] and r["safety_factor"] == pytest.approx(0.9)
    assert unsupported_wall_check(1.5)["ok"]
    with pytest.raises(ValueError):
        unsupported_wall_check(0.0)


# ----------------------------------------------------------- emboss / engrave
def test_detail_width_emboss_vs_engrave():
    assert emboss_detail_check(1.0, kind="emboss")["ok"]
    narrow = emboss_detail_check(0.6, kind="emboss")    # fuses as a raised ridge
    assert not narrow["ok"]
    assert emboss_detail_check(0.6, kind="engrave")["ok"]  # fine as a recess


def test_detail_rejects_nonsense():
    with pytest.raises(ValueError):
        emboss_detail_check(1.0, kind="deboss")
    with pytest.raises(ValueError):
        emboss_detail_check(0.0)


# ------------------------------------------------------------ layer adhesion
def test_cross_layer_load_uses_retained_strength_not_quoted():
    # PLA-like quoted UTS 50 MPa -> retained across layers 0.45 * 50 = 22.5 MPa.
    r = layer_adhesion_check(10.0, 50.0)
    assert r["allowed_stress"] == pytest.approx(22.5)
    assert r["ok"] and r["safety_factor"] == pytest.approx(2.25)
    # 30 MPa would PASS against the quoted 50 -- and the print delaminates anyway.
    bad = layer_adhesion_check(30.0, 50.0)
    assert not bad["ok"] and bad["safety_factor"] == pytest.approx(22.5 / 30.0)


def test_layer_adhesion_zero_stress_and_default_retention():
    r = layer_adhesion_check(0.0, 50.0)
    assert r["safety_factor"] == math.inf and r["z_retention"] == FDM_Z_STRENGTH_RETENTION


def test_layer_adhesion_rejects_nonsense():
    with pytest.raises(ValueError):
        layer_adhesion_check(-5.0, 50.0)                # signed convention refused
    with pytest.raises(ValueError):
        layer_adhesion_check(10.0, 0.0)
    with pytest.raises(ValueError):
        layer_adhesion_check(10.0, 50.0, z_retention=1.2)
    with pytest.raises(ValueError):
        layer_adhesion_check(10.0, 50.0, z_retention=0.0)
