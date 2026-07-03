"""Compute — first-order screens for the robot's brain: throughput, power, control latency (δ-layer).

A humanoid runs perception + control on an onboard SoC/GPU. Three closed-form screens say whether a
chip is in the right CLASS for the job — NECESSARY checks, not a sufficient sizing — and they CHAIN
into axes GENESIS already has: the inference power feeds ``thermal.py`` (can the chip be cooled?) and
the power budget (``flight``/actuation energy draw). A clean pass here means "not obviously
undersized", never "validated"; real sizing needs a measured roofline (the boundary below).

  * ``compute_budget_check`` — sustained THROUGHPUT: the workload demands `workload_tops` (tera-ops/s)
    and the chip provides `chip_tops` peak, but real sustained utilisation is below peak (memory
    bandwidth, scheduling), so the usable throughput is chip_tops·utilisation. The workload must fit.
  * ``inference_power_check`` — the power the chip draws at that workload, P = workload_tops /
    efficiency (TOPS/W); checked against a power budget, and the SAME number is what ``thermal.py``
    must dissipate and the battery must supply.
  * ``inference_latency_check`` — one inference is `workload_flops` total operations; on a chip of
    `chip_flops` ops/s it takes workload_flops/chip_flops seconds, which must finish inside the
    control-loop period (a 100 Hz balance loop cannot wait 20 ms for a vision frame).

Offline, deterministic, no numpy. Honest boundary: first-order rate/power/latency screens — peak
ratings scaled by a declared utilisation, not a measured profile. NOT modelled: memory capacity vs
model size (a model that does not fit thrashes and effective throughput collapses), bandwidth
roofline, batching/multi-stream, accelerator mix, precision (TOPS assume INT8 — FP16/FP32 paths
differ), thermal throttling over a duty cycle (the power number is steady-state), and idle/static
power unless ``static_power_w`` is supplied. Each check is necessary, not sufficient alone.
"""

from __future__ import annotations


def compute_budget_check(workload_tops: float, chip_tops: float, utilisation_max: float = 0.6) -> dict:
    """Does the chip sustain the workload's throughput? usable = chip_tops·utilisation_max.

    `workload_tops`, `chip_tops` in tera-ops/s; `utilisation_max` the realistically sustainable
    fraction of peak (∈ (0, 1]). Returns ``{"usable_tops", "workload_tops", "safety_factor", "ok"}``
    with safety_factor = usable/workload. Raises ValueError on non-positive throughputs or a
    utilisation outside (0, 1]."""
    if workload_tops <= 0.0 or chip_tops <= 0.0:
        raise ValueError("workload and chip throughput must be positive")
    if not 0.0 < utilisation_max <= 1.0:
        raise ValueError("utilisation_max must be in (0, 1]")
    usable = chip_tops * utilisation_max
    safety_factor = usable / workload_tops
    return {"usable_tops": usable, "workload_tops": workload_tops,
            "safety_factor": safety_factor, "ok": usable >= workload_tops}


def inference_power_check(
    workload_tops: float,
    efficiency_tops_per_w: float,
    power_budget_w: float,
    static_power_w: float = 0.0,
) -> dict:
    """Power the chip draws at the workload vs a power budget: P = workload_tops/efficiency +
    static_power_w.

    The first term is DYNAMIC compute power; `static_power_w` is the idle/leakage/DRAM/IO floor
    (often 20–50 % of a chip's budget) — omit it and `power_w` is the dynamic part only. The
    returned `power_w` is also the heat ``thermal.py`` must dissipate and the load the battery must
    supply. Returns ``{"power_w", "dynamic_power_w", "power_budget_w", "safety_factor", "ok"}`` with
    safety_factor = power_budget_w/power_w. Raises ValueError on non-positive ratings or negative
    static power."""
    if workload_tops <= 0.0 or efficiency_tops_per_w <= 0.0 or power_budget_w <= 0.0:
        raise ValueError("workload, efficiency, and power budget must be positive")
    if static_power_w < 0.0:
        raise ValueError("static power must be non-negative")
    dynamic_power_w = workload_tops / efficiency_tops_per_w
    power_w = dynamic_power_w + static_power_w
    safety_factor = power_budget_w / power_w
    return {"power_w": power_w, "dynamic_power_w": dynamic_power_w, "power_budget_w": power_budget_w,
            "safety_factor": safety_factor, "ok": power_w <= power_budget_w}


def inference_latency_check(inference_ops: float, throughput_ops_per_s: float, control_period_s: float) -> dict:
    """Does one inference finish inside the control-loop period? latency = inference_ops/throughput.

    Names are deliberate to avoid the FLOPs/FLOPS trap: `inference_ops` is the TOTAL operations for
    ONE inference (a count), `throughput_ops_per_s` is the chip's RATE (ops/s); their quotient is a
    time. `control_period_s` is the loop deadline (e.g. 0.01 s for 100 Hz). Returns ``{"latency_s",
    "control_period_s", "safety_factor", "ok"}`` with safety_factor = control_period/latency. Raises
    ValueError on non-positive inputs."""
    if inference_ops <= 0.0 or throughput_ops_per_s <= 0.0 or control_period_s <= 0.0:
        raise ValueError("inference ops, throughput, and control period must be positive")
    latency_s = inference_ops / throughput_ops_per_s
    safety_factor = control_period_s / latency_s
    return {"latency_s": latency_s, "control_period_s": control_period_s,
            "safety_factor": safety_factor, "ok": latency_s <= control_period_s}
