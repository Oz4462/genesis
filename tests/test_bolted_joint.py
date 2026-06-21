"""Bolted-joint preload & load sharing — the failure axis a nominal stress misses.

A torqued bolt is PRELOADED and clamps the members; an external tensile load is SHARED
between bolt and joint per their stiffnesses (the bolt sees only C*P added on top of its
full preload), and the joint must not SEPARATE. Pins the exact closed forms (Shigley /
VDI 2230): preload F_i = T/(K*d), load factor C = k_b/(k_b+k_m), bolt load F_i + C*P,
separation load F_i/(1-C). Anchors: T=10000 N*mm, d=10, K=0.2 -> F_i=5000 N; k_b=k_m ->
C=0.5 -> P_sep=10000 N. The defense is showing the naive nominal P/A_t stress omits the
preload entirely while the real bolt stress (F_i + C*P)/A_t is far higher.

Offline, no LLM, pure python (math only).

Run:  pytest tests/test_bolted_joint.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from gen.bolted_joint import (  # noqa: E402
    bolt_load,
    bolted_joint_check,
    joint_stiffness_factor,
    preload_from_torque,
    separation_load,
)


# --- preload from torque: the F_i = T/(K*d) anchor -----------------------------

def test_preload_anchor():
    # T=10000 N*mm, d=10 mm, K=0.2 -> F_i = 10000/(0.2*10) = 5000 N
    assert math.isclose(preload_from_torque(10000.0, 10.0, 0.2), 5000.0)


def test_preload_scales_inversely_with_k_factor():
    # halving the nut factor doubles the achieved preload at the same torque
    base = preload_from_torque(10000.0, 10.0, 0.2)
    soft = preload_from_torque(10000.0, 10.0, 0.1)
    assert math.isclose(soft, 2.0 * base)


def test_preload_guards():
    with pytest.raises(ValueError):
        preload_from_torque(10000.0, 0.0, 0.2)
    with pytest.raises(ValueError):
        preload_from_torque(10000.0, 10.0, 0.0)


# --- stiffness factor C in [0,1] and its physical limits ------------------------

def test_stiffness_factor_equal_stiffness_is_half():
    assert math.isclose(joint_stiffness_factor(1.0, 1.0), 0.5)


def test_stiffness_factor_in_unit_interval():
    for kb, km in [(1.0, 1.0), (5.0, 1.0), (1.0, 5.0), (1e6, 1.0), (1.0, 1e6)]:
        c = joint_stiffness_factor(kb, km)
        assert 0.0 <= c <= 1.0


def test_stiff_bolt_carries_almost_all_soft_bolt_almost_none():
    stiff = joint_stiffness_factor(1e9, 1.0)   # bolt >> members
    soft = joint_stiffness_factor(1.0, 1e9)    # bolt << members
    assert stiff > 0.999          # stiff bolt -> C near 1
    assert soft < 1e-3            # soft bolt  -> C near 0


def test_stiffness_factor_guards():
    with pytest.raises(ValueError):
        joint_stiffness_factor(0.0, 1.0)
    with pytest.raises(ValueError):
        joint_stiffness_factor(1.0, -1.0)


# --- bolt load F_bolt = F_i + C*P ----------------------------------------------

def test_bolt_load_anchor_and_preload_floor():
    # F_i=5000, P=2000, C=0.5 -> 5000 + 0.5*2000 = 6000 N
    assert math.isclose(bolt_load(5000.0, 2000.0, 0.5), 6000.0)
    # at zero external load the bolt carries exactly its preload
    assert math.isclose(bolt_load(5000.0, 0.0, 0.5), 5000.0)


def test_bolt_load_only_a_fraction_of_p_adds():
    # the bolt sees only C*P of the external load, not all of it
    fi, p = 5000.0, 4000.0
    soft_bolt = bolt_load(fi, p, 0.1)    # C=0.1 -> +400 N
    stiff_bolt = bolt_load(fi, p, 0.9)   # C=0.9 -> +3600 N
    assert math.isclose(soft_bolt, 5400.0)
    assert math.isclose(stiff_bolt, 8600.0)
    assert soft_bolt < stiff_bolt


def test_bolt_load_rejects_invalid_factor():
    with pytest.raises(ValueError):
        bolt_load(5000.0, 1000.0, 1.5)
    with pytest.raises(ValueError):
        bolt_load(5000.0, 1000.0, -0.1)


# --- separation load P_sep = F_i/(1-C) -----------------------------------------

def test_separation_anchor_chain():
    # the concrete anchor: k_b=k_m -> C=0.5, F_i=5000 -> P_sep = 5000/(1-0.5) = 10000 N
    c = joint_stiffness_factor(1.0, 1.0)
    fi = preload_from_torque(10000.0, 10.0, 0.2)
    assert math.isclose(separation_load(fi, c), 10000.0)


def test_member_force_is_zero_exactly_at_separation():
    # member clamp force F_m = F_i - (1-C)*P vanishes precisely at P = P_sep
    fi, c = 5000.0, 0.5
    p_sep = separation_load(fi, c)
    member_force = fi - (1.0 - c) * p_sep
    assert math.isclose(member_force, 0.0, abs_tol=1e-9)


def test_separation_load_grows_as_bolt_stiffens():
    # a stiffer bolt (higher C) raises the separation load (members shed less clamp)
    fi = 5000.0
    assert separation_load(fi, 0.9) > separation_load(fi, 0.5) > separation_load(fi, 0.1)


def test_separation_load_rejects_rigid_limit():
    with pytest.raises(ValueError):
        separation_load(5000.0, 1.0)     # C=1 has no finite separation load


# --- the full DFM check: load sharing, separation, and the missed preload -------

def test_check_holds_when_external_below_separation():
    # M10-ish: T=50000 N*mm, d=10, A_t=58 mm^2, P=10000 N, k_b=1 k_m=2, S_p=640 MPa
    r = bolted_joint_check(50000.0, 10.0, 58.0, 10000.0, 1.0, 2.0, 640.0)
    assert math.isclose(r["preload"], 25000.0)                 # 50000/(0.2*10)
    assert math.isclose(r["stiffness_factor_C"], 1.0 / 3.0)
    assert math.isclose(r["bolt_load"], 25000.0 + (1.0 / 3.0) * 10000.0)
    assert math.isclose(r["separation_load"], 37500.0)         # 25000/(1-1/3)
    assert r["separation_margin"] > 1.0                        # P < P_sep
    assert r["yield_safety"] > 1.0                             # bolt below proof
    assert r["ok"]


def test_check_flags_separation_overload():
    # same joint, P=40000 N > P_sep=37500 N -> the joint opens, not ok
    r = bolted_joint_check(50000.0, 10.0, 58.0, 40000.0, 1.0, 2.0, 640.0)
    assert r["separation_margin"] < 1.0
    assert not r["ok"]


def test_check_flags_bolt_yield_even_without_separation():
    # a tiny proof strength makes the preloaded bolt yield though the joint never opens
    r = bolted_joint_check(50000.0, 10.0, 58.0, 10000.0, 1.0, 2.0, 100.0)
    assert r["separation_margin"] > 1.0           # does NOT separate
    assert r["yield_safety"] < 1.0                # but the bolt stress exceeds proof
    assert not r["ok"]                            # ok needs BOTH to pass


def test_nominal_stress_misses_preload():
    # THE insight: a naive check uses sigma = P/A_t and omits the preload entirely;
    # the true preloaded bolt stress (F_i + C*P)/A_t is far higher.
    p, area = 10000.0, 58.0
    r = bolted_joint_check(50000.0, 10.0, area, p, 1.0, 2.0, 640.0)
    naive_nominal = p / area                       # what the nominal check would see
    assert r["bolt_stress"] > 2.0 * naive_nominal  # ~2.8x here -> preload dominates
    assert math.isclose(r["bolt_stress"], r["bolt_load"] / area)


def test_check_guards():
    with pytest.raises(ValueError):
        bolted_joint_check(50000.0, 10.0, 0.0, 10000.0, 1.0, 2.0, 640.0)   # area
    with pytest.raises(ValueError):
        bolted_joint_check(50000.0, 10.0, 58.0, 0.0, 1.0, 2.0, 640.0)      # P
    with pytest.raises(ValueError):
        bolted_joint_check(50000.0, 10.0, 58.0, 10000.0, 1.0, 2.0, 0.0)    # proof


def test_is_deterministic():
    a = bolted_joint_check(50000.0, 10.0, 58.0, 10000.0, 1.0, 2.0, 640.0)
    b = bolted_joint_check(50000.0, 10.0, 58.0, 10000.0, 1.0, 2.0, 640.0)
    assert a == b
    # numpy is imported (mirrors the sibling tests) and agrees on the anchor
    assert np.isclose(a["preload"], 25000.0)
