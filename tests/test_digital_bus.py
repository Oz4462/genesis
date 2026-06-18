"""Digital-bus validators — sensor/actuator traffic vs bus throughput and per-cycle latency.

Exact anchors, not vibes: 10 devices × 6 bytes × 8 bits × 1000 Hz = 480 kbps required (overhead 1),
which a 1 Mbps CAN bus carries but a 400 kbps I²C bus does not; one full poll of those 10 devices is
480 bits = 0.48 ms on a 1 Mbps bus, clearing a 10 ms loop but not a 0.4 ms one. Every nonsense input
raises.

Offline, no LLM. Run:  pytest tests/test_digital_bus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.digital_bus import bus_bandwidth_check, bus_latency_check  # noqa: E402


def test_required_throughput_is_devices_bytes_bits_rate():
    """required = n·bytes·8·rate·overhead; 10×6×8×1000 = 480 kbps, carried by a 1 Mbps bus."""
    res = bus_bandwidth_check(n_devices=10, bytes_per_sample=6, sample_rate_hz=1000,
                              bus_bitrate_bps=1_000_000, overhead_factor=1.0, utilisation_max=1.0)
    assert res["required_bps"] == pytest.approx(480_000.0, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(1_000_000.0 / 480_000.0, rel=1e-12)
    assert res["ok"]


def test_a_too_slow_bus_fails():
    """A 400 kbps I²C bus at 70 % usable (280 kbps) cannot carry the 480 kbps stream."""
    res = bus_bandwidth_check(n_devices=10, bytes_per_sample=6, sample_rate_hz=1000,
                              bus_bitrate_bps=400_000, overhead_factor=1.0, utilisation_max=0.7)
    assert not res["ok"]


def test_poll_cycle_latency_must_clear_the_control_period():
    """One poll of 10×6-byte devices is 480 bits = 0.48 ms on a 1 Mbps bus: clears 10 ms, not 0.4 ms."""
    res = bus_latency_check(n_devices=10, bytes_per_sample=6, bus_bitrate_bps=1_000_000,
                            control_period_s=10e-3, overhead_factor=1.0)
    assert res["cycle_time_s"] == pytest.approx(0.48e-3, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(10e-3 / 0.48e-3, rel=1e-12)
    assert res["ok"]
    tight = bus_latency_check(n_devices=10, bytes_per_sample=6, bus_bitrate_bps=1_000_000,
                              control_period_s=0.4e-3, overhead_factor=1.0)
    assert not tight["ok"]


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        bus_bandwidth_check(n_devices=0, bytes_per_sample=6, sample_rate_hz=1000, bus_bitrate_bps=1e6)
    with pytest.raises(ValueError):
        bus_bandwidth_check(n_devices=10, bytes_per_sample=6, sample_rate_hz=1000,
                            bus_bitrate_bps=1e6, overhead_factor=0.5)        # overhead < 1
    with pytest.raises(ValueError):
        bus_bandwidth_check(n_devices=10, bytes_per_sample=6, sample_rate_hz=1000,
                            bus_bitrate_bps=1e6, utilisation_max=1.5)        # utilisation > 1
    with pytest.raises(ValueError):
        bus_latency_check(n_devices=10, bytes_per_sample=6, bus_bitrate_bps=1e6, control_period_s=0.0)
