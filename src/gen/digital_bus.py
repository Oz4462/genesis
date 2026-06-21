"""digital_bus — can the robot's data bus carry the sensor/actuator traffic? (δ-layer).

``electronics.py`` sizes the analog/power side and ``compute.py`` the chip; the missing digital
screen is the COMMUNICATION bus. A humanoid streams dozens of joint encoders, IMUs and force
sensors into the control loop over I²C/SPI/CAN/EtherCAT; if the bus cannot carry the bytes at the
loop rate — in THROUGHPUT or in per-cycle LATENCY — the controller starves regardless of how fast
the chip is. Two closed-form screens, each pinned to an exact anchor.

  * ``bus_bandwidth_check`` — required throughput = n_devices · bytes_per_sample · 8 · sample_rate ·
    overhead must fit under the bus's usable bitrate (raw bitrate × utilisation, since arbitration/
    framing never lets a shared bus run at 100 %).
  * ``bus_latency_check`` — one full poll of every device is n_devices · bytes_per_sample · 8 ·
    overhead bits; at the bus bitrate that transmission time must finish inside the control period.

Offline, deterministic, no numpy. Honest boundary: first-order throughput/latency screens with a
declared protocol-overhead factor — not a bit-accurate frame/arbitration model (CAN bit-stuffing,
I²C clock-stretching, EtherCAT distributed clocks), not jitter, contention, or error-retransmission.
"""

from __future__ import annotations


def bus_bandwidth_check(
    n_devices: int,
    bytes_per_sample: float,
    sample_rate_hz: float,
    bus_bitrate_bps: float,
    overhead_factor: float = 1.2,
    utilisation_max: float = 0.7,
) -> dict:
    """Does the bus carry the streamed sensor/actuator data? required = n_devices·bytes·8·rate·overhead.

    `overhead_factor` ≥ 1 accounts for protocol framing/addressing; `utilisation_max` ∈ (0, 1] the
    realistically usable fraction of the raw bitrate (a shared bus never runs at 100 %). Returns
    ``{"required_bps", "usable_bps", "safety_factor", "ok"}`` with safety_factor = usable/required.
    Raises ValueError on non-positive counts/rates/bitrate, an overhead < 1, or a utilisation outside
    (0, 1]."""
    if n_devices <= 0 or bytes_per_sample <= 0.0 or sample_rate_hz <= 0.0 or bus_bitrate_bps <= 0.0:
        raise ValueError("device count, bytes, sample rate, and bitrate must be positive")
    if overhead_factor < 1.0:
        raise ValueError("overhead_factor must be >= 1.0")
    if not 0.0 < utilisation_max <= 1.0:
        raise ValueError("utilisation_max must be in (0, 1]")
    required_bps = n_devices * bytes_per_sample * 8.0 * sample_rate_hz * overhead_factor
    usable_bps = bus_bitrate_bps * utilisation_max
    safety_factor = usable_bps / required_bps
    return {"required_bps": required_bps, "usable_bps": usable_bps,
            "safety_factor": safety_factor, "ok": usable_bps >= required_bps}


def bus_latency_check(
    n_devices: int,
    bytes_per_sample: float,
    bus_bitrate_bps: float,
    control_period_s: float,
    overhead_factor: float = 1.2,
) -> dict:
    """Does one full poll of every device fit inside the control period? cycle_time = total_bits/bitrate.

    total_bits = n_devices · bytes_per_sample · 8 · overhead_factor; the transmission time must clear
    the loop deadline. Returns ``{"cycle_time_s", "control_period_s", "safety_factor", "ok"}`` with
    safety_factor = control_period/cycle_time. Raises ValueError on non-positive inputs or an overhead
    < 1."""
    if n_devices <= 0 or bytes_per_sample <= 0.0 or bus_bitrate_bps <= 0.0 or control_period_s <= 0.0:
        raise ValueError("device count, bytes, bitrate, and control period must be positive")
    if overhead_factor < 1.0:
        raise ValueError("overhead_factor must be >= 1.0")
    cycle_time_s = n_devices * bytes_per_sample * 8.0 * overhead_factor / bus_bitrate_bps
    safety_factor = control_period_s / cycle_time_s
    return {"cycle_time_s": cycle_time_s, "control_period_s": control_period_s,
            "safety_factor": safety_factor, "ok": cycle_time_s <= control_period_s}
