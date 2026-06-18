"""Compute validators — throughput budget, inference power, control-loop latency.

Exact anchors, not vibes: a 100-TOPS chip at 50 % sustained utilisation gives exactly 50 usable
TOPS (40 fits, 60 does not); a 40-TOPS workload at 5 TOPS/W draws exactly 8 W (the heat thermal.py
must shed); a 1-GFLOP inference on a 1-TFLOPS chip takes exactly 1 ms and clears a 10 ms (100 Hz)
loop but not a 0.5 ms one. Every nonsense input raises.

Offline, no LLM. Run:  pytest tests/test_compute.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.compute import (  # noqa: E402
    compute_budget_check,
    inference_latency_check,
    inference_power_check,
)


def test_throughput_budget_uses_sustainable_utilisation():
    """Usable throughput is chip_tops·utilisation; a 40-TOPS workload fits 50 usable, 60 does not."""
    ok = compute_budget_check(workload_tops=40.0, chip_tops=100.0, utilisation_max=0.5)
    assert ok["usable_tops"] == pytest.approx(50.0, rel=1e-12)
    assert ok["safety_factor"] == pytest.approx(1.25, rel=1e-12)
    assert ok["ok"]
    over = compute_budget_check(workload_tops=60.0, chip_tops=100.0, utilisation_max=0.5)
    assert not over["ok"]


def test_inference_power_is_dynamic_plus_static():
    """P = workload_tops/efficiency (+ static idle floor) — the heat thermal.py sheds and the
    battery supplies. 40 TOPS at 5 TOPS/W is 8 W dynamic; a 4 W idle floor makes it 12 W."""
    res = inference_power_check(workload_tops=40.0, efficiency_tops_per_w=5.0, power_budget_w=15.0)
    assert res["power_w"] == pytest.approx(8.0, rel=1e-12)
    assert res["dynamic_power_w"] == pytest.approx(8.0, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(15.0 / 8.0, rel=1e-12)
    assert res["ok"]
    with_idle = inference_power_check(workload_tops=40.0, efficiency_tops_per_w=5.0,
                                      power_budget_w=15.0, static_power_w=4.0)
    assert with_idle["power_w"] == pytest.approx(12.0, rel=1e-12)   # 8 dynamic + 4 idle
    assert with_idle["dynamic_power_w"] == pytest.approx(8.0, rel=1e-12)
    tight = inference_power_check(workload_tops=40.0, efficiency_tops_per_w=5.0, power_budget_w=5.0)
    assert not tight["ok"]


def test_inference_latency_must_clear_the_control_period():
    """latency = inference_ops/throughput; 1e9 ops on 1e12 ops/s = 1 ms, clears 10 ms, not 0.5 ms."""
    res = inference_latency_check(inference_ops=1e9, throughput_ops_per_s=1e12, control_period_s=10e-3)
    assert res["latency_s"] == pytest.approx(1e-3, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(10.0, rel=1e-12)
    assert res["ok"]
    too_slow = inference_latency_check(inference_ops=1e9, throughput_ops_per_s=1e12, control_period_s=0.5e-3)
    assert not too_slow["ok"]


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        compute_budget_check(workload_tops=-1.0, chip_tops=100.0)
    with pytest.raises(ValueError):
        compute_budget_check(workload_tops=40.0, chip_tops=100.0, utilisation_max=1.5)
    with pytest.raises(ValueError):
        inference_power_check(workload_tops=40.0, efficiency_tops_per_w=0.0, power_budget_w=15.0)
    with pytest.raises(ValueError):
        inference_latency_check(inference_ops=1e9, throughput_ops_per_s=1e12, control_period_s=0.0)
