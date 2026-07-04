"""Subsystem / colony / nano extension types — moved OUT of the framework-free core (D1).

These are domain-extension dataclasses (generalist subsystem abstraction, 2036
space-colony and nano-recipe leaps). They carry no core invariants (no ledger
coupling, no gate contracts), so they do not belong in ``core/state.py`` — the
typed core stays lean (WORK_QUEUE D1, resolved 2026-07-04). ``core.state`` keeps
a lazy PEP-562 re-export for backwards compatibility; new code imports from here.

Stdlib-only on purpose: importable from anywhere without cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ModuleSpec:
    """A general, reusable description of a subsystem/module in a larger system.
    Ports/budgets are domain-agnostic (power, thermal, data, mechanical interface, safety level, software API).
    Enables Subsystem-Abstraktion, multi-board reasoning, and inverse design across all ideas.
    """
    name: str
    kind: str  # e.g. "power_distribution", "sensor_array", "control_unit", "structure", "energy_storage", "biological_reactor"
    interfaces: dict[str, Any] = field(default_factory=dict)  # e.g. {"mech": "mounting_points", "elec": "48V_rail", "data": "CAN", "thermal": "heatsink", "safety": "S3", "software": "firmware_v1"}
    power_budget_w: float = 0.0
    thermal_budget_w: float = 0.0
    mass_kg: float = 0.0
    volume_cm3: float = 0.0
    safety_level: str = "S0"
    open_issues: list[str] = field(default_factory=list)
    quelle: str = "generalist subsystem abstraction"


# =============================================================================
# Nano + Space-Colony Extensions (2036 10y leap, Genesis 2026 core)
# Bio full, local, 4 Linsen provenance. For planetary engineering, closed-loop
# habitats, molecular machines / self-assembling structures.
# =============================================================================

@dataclass
class ColonyModule:
    """Colony / habitat subsystem for space-colony and planetary engineering sims.
    Extends generalist ModuleSpec for ECLSS bio-loops, radiation shielding,
    micro-g countermeasures, self-assembling nano-hab components.
    All fields carry explicit quelle for L1. Sim-ready (local numpy dispatch).
    """
    name: str
    kind: str  # e.g. "eclss_algae_loop", "radiation_shield_regolith_pe", "microg_centrifuge", "self_assemble_nano_hab", "life_support_compartment", "planetary_isru_nano"
    interfaces: dict[str, Any] = field(default_factory=dict)
    power_budget_w: float = 0.0
    thermal_budget_w: float = 0.0
    mass_kg: float = 0.0
    volume_cm3: float = 0.0
    safety_level: str = "S0"
    # Space-colony specifics (grounded in real concepts: MELiSSA/ACLS, regolith+PE/water shielding, micro-g countermeasures)
    bio_yield_g_per_day: float = 0.0          # algae/biomass output for closed O2/food loop
    o2_gen_rate_g_per_h: float = 0.0          # net O2 from bio-loop under given light/CO2
    co2_scrub_rate_g_per_h: float = 0.0
    shield_thickness_mm: float = 0.0
    shield_material: str = ""                 # "regolith", "polyethylene", "water_wall", "regolith_pe_composite"
    radiation_dose_reduction: float = 1.0     # 1.0 = unshielded; factor <1 after shielding (primary GCR/SPE + secondaries)
    microg_mitigation: str = ""               # "centrifuge_1g", "resistance_exercise", "pharma_loading", "none"
    self_assemble_rate: float = 0.0           # proxy for nano self-assembly kinetics (steps/h or %/day)
    open_issues: list[str] = field(default_factory=list)
    quelle: str = "colony module 2036 leap (MELiSSA ESA + regolith/PE shielding NTRS + micro-g countermeasures + nano self-assemble)"
    source: str = "Genesis Nano-Designer & Space-Colony Engineer integration"


@dataclass(frozen=True)
class NanoRecipe:
    """Nano-scale design recipe for molecular machines and self-assembling structures.
    Used in wissensbasis seeding, colony habitat assembly, planetary ISRU nano-factories.
    Carries molecular_fidelity from bio_molecular MD/ODE dispatch (local numpy).
    No facts without quelle (L1); assembly conditions are DECISION or GROUNDED.
    """
    id: str
    name: str
    kind: str  # "rotary_molecular_motor", "dna_origami_scaffold", "self_healing_nano_binder", "flagellar_pump_actuator", "quorum_nano_swarm", "isru_nano_factory"
    specs: dict[str, Any]  # e.g. stall_torque_pN_nm, step_size, assembly_temp_C, yield_pct, binding_energy_kT
    assembly_conditions: dict[str, Any] = field(default_factory=dict)  # pH, temp, ions, light, quorum signal
    molecular_fidelity: Optional[dict[str, Any]] = None  # from bio_molecular.run_* (trajectory, period, force, 4_lenses)
    footprint_nm: Optional[tuple[float, float, float]] = None
    source: str = "representative_synthetic_bio_or_nano_2036_local"
    quelle: str = "nano recipes 2036 leap (F1-ATPase/flagellar motors + DNA origami self-assembly literature + bio_molecular.numpy + 4_LINSEN)"

