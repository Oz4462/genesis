"""chip_selection — pick the robot's compute chip by requirement, gated by compute.py (δ-layer).

``compute.py`` CHECKS one given chip against a workload (throughput, power, control latency). The
missing step is SELECTION: given a humanoid's compute requirement, which chip from a catalog actually
clears all three screens — and which is the cheapest that does? This is the proposer/gate split GENESIS
uses everywhere (mirrors ``section_optimizer``): the catalog is the candidate space, ``compute.py``'s
deterministic checks are the gate, and a chip is never "selected" until those checks pass. If no chip
clears the bar, the honest answer is "none fits" with the binding reason — never a fabricated part.

Each chip's throughput in ops/s is derived from its peak TOPS (``peak_tops·1e12``), consistent with
compute.py's peak model (whose honest boundary about marketing-peak TOPS carries over here). The catalog
figures are ILLUSTRATIVE NOMINAL robotics-SoC values, each carrying provenance — confirm against the
vendor datasheet and the actual power mode for a real part, exactly as ``materials.py`` flags nominal
FDM values. Offline, deterministic, no numpy.
"""

from __future__ import annotations

from dataclasses import dataclass

#: ops/s per TOPS — a tera-op is 1e12 ops, so a chip's raw op-rate is peak_tops · this.
_OPS_PER_TOPS = 1.0e12

PREFER = ("price", "power", "headroom")


@dataclass(frozen=True)
class Chip:
    """A candidate compute chip with NOMINAL specs and provenance. ``source`` is mandatory — a chip
    spec without a citation is the anonymous constant this catalog replaces (cf. ``materials.Material``)."""

    name: str
    peak_tops: float
    efficiency_tops_per_w: float
    static_power_w: float
    price_eur: float
    source: str

    @property
    def throughput_ops_per_s(self) -> float:
        """Raw op-rate derived from peak TOPS (consistent with compute.py's peak model)."""
        return self.peak_tops * _OPS_PER_TOPS


_NOMINAL = "illustrative nominal NVIDIA-Jetson-class figure (sparse-INT8 peak); confirm vs. vendor datasheet + power mode"

#: Illustrative catalog of robotics compute chips. Values are nominal peak figures, each sourced.
CHIPS: tuple[Chip, ...] = (
    Chip("Jetson Nano (legacy)", 0.5, 0.05, 2.0, 120.0, _NOMINAL),
    Chip("Jetson Orin Nano", 40.0, 2.7, 2.0, 300.0, _NOMINAL),
    Chip("Jetson Orin NX", 100.0, 4.0, 3.0, 700.0, _NOMINAL),
    Chip("Jetson AGX Orin", 275.0, 4.6, 5.0, 2000.0, _NOMINAL),
)


@dataclass(frozen=True)
class ChipEvaluation:
    """One chip judged against the requirement by compute.py's three gates. ``limiting`` names the first
    failing screen (``""`` when feasible) — the honest "why this chip did not fit"."""

    chip: Chip
    throughput: dict
    power: dict
    latency: dict
    feasible: bool
    limiting: str

    @property
    def min_safety_factor(self) -> float:
        """The binding headroom: the smallest of the three checks' safety factors."""
        return min(self.throughput["safety_factor"], self.power["safety_factor"],
                   self.latency["safety_factor"])


@dataclass(frozen=True)
class SelectionResult:
    """Outcome of a selection: the chosen evaluation (or None = no chip fits), the feasible subset, every
    evaluation (for transparency), and the preference that ordered the feasible set."""

    selected: ChipEvaluation | None
    feasible: tuple[ChipEvaluation, ...]
    evaluated: tuple[ChipEvaluation, ...]
    prefer: str


def _evaluate(chip: Chip, *, workload_tops: float, power_budget_w: float, inference_ops: float,
              control_period_s: float, utilisation_max: float) -> ChipEvaluation:
    from .compute import compute_budget_check, inference_latency_check, inference_power_check

    throughput = compute_budget_check(workload_tops, chip.peak_tops, utilisation_max)
    power = inference_power_check(workload_tops, chip.efficiency_tops_per_w, power_budget_w,
                                  chip.static_power_w)
    latency = inference_latency_check(inference_ops, chip.throughput_ops_per_s, control_period_s)
    if not throughput["ok"]:
        limiting = "throughput"
    elif not power["ok"]:
        limiting = "power"
    elif not latency["ok"]:
        limiting = "latency"
    else:
        limiting = ""
    return ChipEvaluation(chip, throughput, power, latency, feasible=not limiting, limiting=limiting)


def select_chip(
    *,
    workload_tops: float,
    power_budget_w: float,
    inference_ops: float,
    control_period_s: float,
    utilisation_max: float = 0.6,
    catalog: tuple[Chip, ...] = CHIPS,
    prefer: str = "price",
) -> SelectionResult:
    """Select the best catalog chip that clears compute.py's throughput, power and latency gates.

    The requirement is the workload (``workload_tops``), the power budget (W), one inference's total ops
    (``inference_ops``) and the control-loop deadline (``control_period_s``). Every chip is judged by the
    SAME compute.py checks; the feasible ones are ordered by ``prefer`` — ``"price"`` (cheapest),
    ``"power"`` (lowest draw at the workload) or ``"headroom"`` (largest binding safety factor) — ties
    broken by name for determinism. ``selected`` is ``None`` when no chip fits (honest, never fabricated).
    Raises ValueError on an unknown ``prefer``, an empty catalog, or a non-positive requirement (the
    compute.py checks reject the latter)."""
    if prefer not in PREFER:
        raise ValueError(f"unknown prefer {prefer!r}; choose from {PREFER}")
    if not catalog:
        raise ValueError("catalog is empty — no chips to select from")

    evaluated = tuple(
        _evaluate(chip, workload_tops=workload_tops, power_budget_w=power_budget_w,
                  inference_ops=inference_ops, control_period_s=control_period_s,
                  utilisation_max=utilisation_max)
        for chip in catalog
    )
    feasible = tuple(e for e in evaluated if e.feasible)

    if prefer == "price":
        key = lambda e: (e.chip.price_eur, e.chip.name)
    elif prefer == "power":
        key = lambda e: (e.power["power_w"], e.chip.name)
    else:  # headroom
        key = lambda e: (-e.min_safety_factor, e.chip.name)

    selected = min(feasible, key=key) if feasible else None
    return SelectionResult(selected=selected, feasible=feasible, evaluated=evaluated, prefer=prefer)
