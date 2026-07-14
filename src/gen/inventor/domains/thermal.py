"""thermal — the cooling / thermal-management invention domain.

The second concrete :class:`InventionDomain` (alongside mechatronics). It un-domain-locks the invention
loop: a cooling brief now grounds through a thermal architect that emits THERMAL measurands the real δ-physics
gate recognizes — so the deterministic gate fires a genuine **conduction** check (cold-plate ΔT = P·L/(k·A),
junction kept under its service limit), NOT the mechatronics resonance check.

Honest scope (mirrors GENESIS's own limits, see physics_selection RECIPES): the δ-gate certifies the
**component** conduction path here. The **system** thermodynamics of a full cooling loop (Q = ṁ·cp·ΔT,
dry-cooler approach, heat-pump COP, water↔energy balance, CFD) have no validator — they are computed from
cited sources elsewhere and flagged "computed, not δ-gated". A vacuous spec is never reported as verified.

Plugs in exactly like :mod:`mechatronics`: prior art via SearchBackends (offline a small RagBackend; live
OpenAlex + arXiv), grounding via the shared ``ground_with_architect`` flow, artifact via ``emit_bundle``.
"""

from __future__ import annotations

from typing import Optional, Sequence

from ...bundle import BundleManifest, emit_bundle
from ...core.interfaces import SearchBackend
from ...core.state import Possibility, Specification
from ...external.oracle import ExternalOracle
from ...llm.base import LLMClient, ScriptedLLM
from ...materials import MATERIALS, density_kg_m3
from ...tools.materials_backend import MaterialsBackend
from ...tools.rag_backend import Document, RagBackend
from ..brief import Invention, InventionBrief
from .base import ground_with_architect, scripted_architect

_PRIOR_ART_CORPUS = [
    Document(url_or_id="https://openalex.org/W-direct-to-chip",
             title="High-temperature direct-to-chip liquid cooling for high-density compute",
             text="single-phase cold plates; warm-water 45-60C supply; raises dry heat-rejection envelope; "
                  "eliminates evaporative water at the chip; handles >100 kW/rack"),
    Document(url_or_id="https://openalex.org/W-immersion-two-phase",
             title="Two-phase immersion cooling of accelerators",
             text="dielectric boiling on the die; very high heat flux; closed condenser loop; no water use"),
    Document(url_or_id="https://openalex.org/W-dry-cooler-free-cooling",
             title="Dry coolers and economizer free-cooling without evaporation",
             text="closed-loop fluid coolers reject heat to air with fans only; zero consumptive water; "
                  "approach temperature limited in hot climates"),
    Document(url_or_id="https://openalex.org/W-datacenter-heat-reuse",
             title="Waste-heat reuse and heat-pump upgrade from data centers",
             text="heat-pump lifts reject temperature for district heat / industrial process; turns cooling "
                  "energy cost into delivered value"),
    Document(url_or_id="https://openalex.org/W-thermal-desalination",
             title="Low-grade-heat thermal desalination (MED / membrane distillation)",
             text="reused data-center waste heat drives desalination at ~10-20 kWh_th per m3; coastal sites "
                  "can become net fresh-water producers"),
    Document(url_or_id="https://openalex.org/W-ates-radiative",
             title="Aquifer thermal energy storage and radiative sky cooling",
             text="closed-loop ground/aquifer storage and night-time radiative panels shift and shave the "
                  "peak heat-rejection load with no water consumption"),
]


def _materials_thermal_prior_art_docs() -> list[Document]:
    """Offline prior-art cards for cold-plate / heat-spreader materials (self-improve 2026-07-14).

    Thermal invent used RAG cooling papers only; mechatronics already had materials cards.
    Copper/aluminum density + modulus + k (W/m·K) anchor conduction-plate design without network.
    """
    docs: list[Document] = []
    for key in ("COPPER", "ALUMINUM", "STEEL", "TITANIUM"):
        m = MATERIALS[key]
        rho = density_kg_m3(key)
        k = m.thermal_conductivity_w_mk
        k_txt = f"thermal conductivity k={k:g} W/m·K (nominal handbook); " if k is not None else ""
        docs.append(
            Document(
                url_or_id=f"gen-materials://{key}",
                title=f"GENESIS materials registry (thermal): {m.name}",
                text=(
                    f"{m.name} cold-plate / spreader material: density {rho:.0f} kg/m3 "
                    f"({m.density_g_cm3} g/cm3); {k_txt}"
                    f"Young modulus {m.youngs_modulus_mpa:g} MPa; "
                    f"yield {m.yield_strength_mpa:g} MPa. Source: {m.source}. Note: {m.note}."
                ),
            )
        )
    return docs


def _default_rag() -> RagBackend:
    """Offline cooling prior-art corpus + materials cards. Live runs may inject OpenAlex/arXiv."""
    return RagBackend(_PRIOR_ART_CORPUS + _materials_thermal_prior_art_docs())


class ThermalDomain:
    """Cooling / thermal-management domain. Satisfies :class:`InventionDomain`.

    ``backends`` (optional) are the prior-art SearchBackends; the offline default is a small RagBackend
    plus MaterialsBackend (parity with mechatronics). Live runs may inject OpenAlex/arXiv for real prior art."""

    name = "thermal"

    def __init__(self, *, backends: Optional[Sequence[SearchBackend]] = None) -> None:
        if backends is not None:
            self._backends = list(backends)
        else:
            self._backends = [_default_rag(), MaterialsBackend()]

    def prior_art_sources(self) -> list[SearchBackend]:
        return list(self._backends)

    async def ground(self, concept: Possibility, brief: InventionBrief, architect: LLMClient) -> Invention:
        return await ground_with_architect(concept, brief, architect)

    def emit_artifact(self, spec: Specification, out_dir) -> BundleManifest:
        return emit_bundle(spec, out_dir)

    def external_oracle(self) -> Optional[ExternalOracle]:
        return None


def scripted_thermal_architect(
    *,
    chip_power_w: float = 1000.0,
    plate_conductivity_w_mk: Optional[float] = None,  # default: registry COPPER k
    plate_area_mm2: float = 2500.0,           # 50 x 50 mm contact under the die spreader
    plate_thickness_mm: float = 3.0,          # conduction length, socket -> coolant channel
    coolant_temp_k: float = 323.15,           # 50 C high-temperature warm-water supply (the dry-rejection enabler)
    max_junction_k: float = 373.15,           # 100 C conservative case/junction service limit
    grounding: Sequence[str] = ("https://openalex.org/W-direct-to-chip",),
    model: str = "scripted-architect",
) -> ScriptedLLM:
    """A deterministic OFFLINE architect for the thermal domain: emits the cold-plate **conduction** check the
    real δ-gate recognizes (``overtemperature`` recipe). A sound design (effective copper plate, warm-water
    coolant) keeps the junction far below its limit and PASSES; a too-thin/too-small plate (or too-low service
    limit) pushes the junction over the limit and the gate FAILS honestly — same machinery, two honest verdicts.

    Default ``plate_conductivity_w_mk`` is the grounded COPPER registry k (self-improve 2026-07-14), not a
    magic number. Honest gaps are declared on the spec: the loop heat balance, dry-cooler approach, heat-pump
    COP and water balance are SYSTEM-level and have no validator — they are computed from cited sources, not δ-gated.
    """
    if plate_conductivity_w_mk is None:
        k_reg = MATERIALS["COPPER"].thermal_conductivity_w_mk
        plate_conductivity_w_mk = float(k_reg) if k_reg is not None else 401.0
    quantities = [
        {"id": "q_power", "name": "Chip-Verlustleistung pro Cold-Plate", "value": chip_power_w, "unit": "W",
         "measurand": "thermal.power_dissipation", "grounding": list(grounding),
         "rationale": "TDP eines KI-Beschleuniger-Packages (Wärmelast am Cold-Plate)"},
        {"id": "q_k", "name": "Cold-Plate-Wärmeleitfähigkeit (Kupfer)", "value": plate_conductivity_w_mk,
         "unit": "W/m/K", "measurand": "material.thermal_conductivity",
         "grounding": list(grounding) + ["gen-materials://COPPER"]},
        {"id": "q_area", "name": "Cold-Plate-Kontaktfläche", "value": plate_area_mm2, "unit": "mm^2",
         "measurand": "thermal.conduction_area", "rationale": "Grundfläche unter dem Die-Spreader"},
        {"id": "q_len", "name": "Cold-Plate-Basisdicke (Leitweg)", "value": plate_thickness_mm, "unit": "mm",
         "measurand": "thermal.conduction_length", "rationale": "Leitweg Sockel -> Kühlkanal"},
        {"id": "q_amb", "name": "Kühlmittel-Eintrittstemperatur (Hochtemperatur-Warmwasser)",
         "value": coolant_temp_k, "unit": "K", "measurand": "thermal.ambient_temp",
         "rationale": "50 C Warmwasser-Direktkühlung — hebt das Trocken-Rückkühl-Fenster"},
        {"id": "q_tmax", "name": "max. zulässige Sperrschicht-/Gehäusetemperatur", "value": max_junction_k,
         "unit": "K", "measurand": "material.max_service_temp", "grounding": list(grounding)},
    ]
    gaps = [
        "System-Thermodynamik der Kühlschleife (Q=ṁ·cp·ΔT), Trockenkühler-Annäherung, Wärmepumpen-COP "
        "und Wasserbilanz: aus Quellen berechnet, NICHT δ-gegatet (kein Validator vorhanden).",
    ]
    return scripted_architect(quantities, gaps=gaps, model=model)


__all__ = ["ThermalDomain", "scripted_thermal_architect"]
