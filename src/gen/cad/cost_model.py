"""cost_model — a sourced, ranged manufacturing cost estimate (PLAN §4.7, Stein 4).

"Cost" is a MEASUREMENT with assumptions, not a single number. The old stubs
("8-25 EUR for Jetpack Tether", "TBD") hid the real spread: infill 30-60%,
throughput ~3x, self-run vs service ~10x. This module replaces them with an
honest estimate: the part of cost that IS computable from the spec's quantities
(material mass from the solid volume) is computed; the rest (machine time) is a
ranged estimate from sourced rates; and what genuinely needs more data (exact
slicing time, supports, finishing, labour) is declared as a gap. The result is a
RANGE with explicit assumptions and gaps — never a fabricated point value.

Only FDM is computed here: a mechanical solid's volume maps directly to FDM
material. Subtractive (CNC) / sheet (laser) / PCB costs need process data the
mechanical artifact does not carry (toolpath time, cut length, board layers), so
those are declared as cost gaps by the caller, not guessed.

Sources (verified 2026-06-18):
  * Filament density / price: PLA 1.24 g/cm3, PETG 1.27, ABS 1.04; desktop
    filament PLA ~13-40 EUR/kg, PETG ~13.6-60 EUR/kg (-> per-material EUR/g bands;
    brand/specialty premium NOT modelled). Refs: 3DSourced materials-cost; Omnicalculator.
  * Job-average deposited throughput ~8-30 cm3/h — BELOW the 5-15 mm3/s peak
    extrusion flow because a real job includes travel/retraction/layer-change/
    small-layer overhead. Refs: Polymaker max-volumetric-speed; 3D-printing speed.
  * Machine time cost EXCLUDING material ~0.20 EUR/h (self-run: amortisation ~0.15
    + electricity + consumables, no filament) to ~1.00 EUR/h (small maintained shop);
    commercial bureau all-in pricing (labour+margin, ~1.50-5 EUR/h or EUR/g) is a GAP.
    Refs: 3D Solved cost breakdown; 3D Printing Industry FFF pricing.

The deposited fraction and setup are stated ASSUMPTIONS; the throughput band is a
job-average engineering judgement below the sourced peak flow. The cost band is an
independent-factor outer bound (all-low vs all-high), not a calibrated percentile,
and is SCOPED to a typical infilled prototype — shell-dominated / near-solid
geometry falls outside the deposited-fraction assumption and is surfaced as a gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Material density [g/cm³] and desktop filament price band [EUR/g], per material
#: (PETG runs a touch pricier than PLA; brand / specialty premium is a gap).
FDM_MATERIALS: dict[str, dict[str, float]] = {
    "PLA":  {"density_g_cm3": 1.24, "price_eur_per_g_low": 0.013, "price_eur_per_g_high": 0.040},
    "PETG": {"density_g_cm3": 1.27, "price_eur_per_g_low": 0.014, "price_eur_per_g_high": 0.050},
    "ABS":  {"density_g_cm3": 1.04, "price_eur_per_g_low": 0.013, "price_eur_per_g_high": 0.040},
}
DEFAULT_FDM_MATERIAL = "PLA"

#: JOB-AVERAGE deposited throughput band [cm³/h] — well below peak extrusion flow
#: (5-15 mm³/s) because a real job spends time on travel, retraction, layer changes
#: and small/cooling layers. Exact time still needs a slice (gap).
FDM_THROUGHPUT_CM3_PER_H_LOW = 8.0
FDM_THROUGHPUT_CM3_PER_H_HIGH = 30.0
#: Machine time cost band [EUR/h] EXCLUDING material — self-run desktop (amortisation
#: ~0.15 + electricity + consumables, NO filament) to a small maintained shop.
#: Commercial bureau all-in pricing (labour + margin, often €1.50-5/h or €/g) is a GAP.
FDM_MACHINE_RATE_EUR_PER_H_LOW = 0.20
FDM_MACHINE_RATE_EUR_PER_H_HIGH = 1.00
#: Fraction of the SOLID volume actually deposited (perimeters + ~15-25% infill).
#: An ENGINEERING ASSUMPTION for a typical infilled prototype, NOT a sourced constant:
#: a thin-wall / shell-dominated part deposits MORE, a near-solid part approaches 1.0
#: — the true fraction needs the wall/shell vs infill split from a slice (gap).
FDM_INFILL_FRACTION_LOW = 0.30
FDM_INFILL_FRACTION_HIGH = 0.60
#: Nominal self-run setup / handling per job [EUR] (an assumption — a service adds
#: order + handling fees, a gap; not a sourced constant).
FDM_SETUP_EUR = 1.0

COST_MODEL_SOURCE = "3DSourced / Omnicalculator / Polymaker / 3D-Solved FDM cost data (2026-06-18)"


@dataclass(frozen=True)
class CostEstimate:
    """A ranged cost estimate with its assumptions and honest gaps.

    `low_eur`/`high_eur`  the cost band (never a single fabricated number).
    `breakdown`           per-component (low, high) bands in EUR.
    `assumptions`         the stated inputs the band depends on.
    `gaps`                cost drivers NOT modelled (so the band is a floor-ish guide).
    """

    process: str
    low_eur: float
    high_eur: float
    breakdown: dict[str, tuple[float, float]]
    assumptions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    source: str | None = None

    def summary(self) -> str:
        """One-line band, e.g. ``€1.30–5.46 (FDM; excl. supports/finishing/labour)``."""
        return (f"€{self.low_eur:.2f}–{self.high_eur:.2f} ({self.process}; "
                f"ranged est., excl. {', '.join(g.split(':')[0] for g in self.gaps[:2]) or 'see gaps'})")


def resolve_fdm_material(hint: str | None, default: str = DEFAULT_FDM_MATERIAL) -> str:
    """Resolve a free-text material hint (e.g. 'PLA oder PETG') to a known key.

    Returns the first recognised material in the hint, else `default`. The choice
    is surfaced as an assumption by the caller — never silently decisive."""
    h = (hint or "").upper()
    for key in FDM_MATERIALS:
        if key in h:
            return key
    return default


def estimate_fdm_cost(volume_cm3: float, material: str | None = None, *,
                      setup_eur: float = FDM_SETUP_EUR) -> CostEstimate:
    """Ranged FDM cost for a solid of `volume_cm3`, per the sourced bands above.

    Material mass = volume · density · infill_fraction; material cost = mass ·
    price. Machine time = deposited_volume / throughput, costed at the machine
    rate. The band spans the infill / throughput / rate / price uncertainty. Exact
    slicing time, supports, finishing and labour are NOT modelled — declared as
    gaps. Raises ValueError on a non-positive volume (a guessed cost is worse than
    an honest refusal)."""
    if not math.isfinite(volume_cm3) or volume_cm3 <= 0:
        raise ValueError("estimate_fdm_cost: volume_cm3 must be a finite value > 0")
    key = resolve_fdm_material(material)
    m = FDM_MATERIALS[key]

    mass_low_g = volume_cm3 * m["density_g_cm3"] * FDM_INFILL_FRACTION_LOW
    mass_high_g = volume_cm3 * m["density_g_cm3"] * FDM_INFILL_FRACTION_HIGH
    material_low = mass_low_g * m["price_eur_per_g_low"]
    material_high = mass_high_g * m["price_eur_per_g_high"]

    # deposited volume drives print time; least material + fastest = lowest time/cost
    dep_low_cm3 = volume_cm3 * FDM_INFILL_FRACTION_LOW
    dep_high_cm3 = volume_cm3 * FDM_INFILL_FRACTION_HIGH
    time_h_low = dep_low_cm3 / FDM_THROUGHPUT_CM3_PER_H_HIGH
    time_h_high = dep_high_cm3 / FDM_THROUGHPUT_CM3_PER_H_LOW
    machine_low = time_h_low * FDM_MACHINE_RATE_EUR_PER_H_LOW
    machine_high = time_h_high * FDM_MACHINE_RATE_EUR_PER_H_HIGH

    # setup is itself uncertain: 0 for a self-run marginal print, up to the nominal
    # handling charge for a small shop — so it widens the band, not a fixed offset.
    setup_low, setup_high = 0.0, setup_eur
    low = material_low + machine_low + setup_low
    high = material_high + machine_high + setup_high

    matched = any(k in (material or "").upper() for k in FDM_MATERIALS)
    assumptions = [
        f"material {key} ({'from hint' if matched else 'DEFAULT — hint named no known material'}; "
        f"density {m['density_g_cm3']} g/cm³, {m['price_eur_per_g_low']}–{m['price_eur_per_g_high']} EUR/g)",
        f"deposited fraction {FDM_INFILL_FRACTION_LOW:.0%}–{FDM_INFILL_FRACTION_HIGH:.0%} (typical infilled prototype — an assumption, not measured)",
        f"setup 0–{setup_high:g} EUR (self-run marginal to handling)",
        "band is an independent-factor outer bound (all-low vs all-high), not a calibrated percentile",
    ]
    gaps = [
        f"deposited fraction is assumed {FDM_INFILL_FRACTION_LOW:.0%}–{FDM_INFILL_FRACTION_HIGH:.0%} "
        f"(typical infilled prototype); a shell-dominated thin-wall part (-> near 100%) or a "
        f"near-solid part falls OUTSIDE this band and is UNDER-stated -- give the real infill or a slice",
        "support material and removal: not modelled (orientation-dependent)",
        "post-processing / finishing: not modelled",
        "commercial bureau pricing (labour + margin, ~1.50–5 EUR/h or EUR/g all-in): not modelled",
        "material brand / specialty premium, failure/reprint rate and shipping: not modelled",
    ]
    if not matched:
        gaps.insert(0, f"material hint {material!r} did not resolve — assumed {key}; "
                       f"a different material shifts density and price")
    return CostEstimate(
        process="FDM",
        low_eur=round(low, 2),
        high_eur=round(high, 2),
        breakdown={
            "material": (round(material_low, 2), round(material_high, 2)),
            "machine_time": (round(machine_low, 2), round(machine_high, 2)),
            "setup": (round(setup_low, 2), round(setup_high, 2)),
        },
        assumptions=assumptions,
        gaps=gaps,
        source=COST_MODEL_SOURCE,
    )
