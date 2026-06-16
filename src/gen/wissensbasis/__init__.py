"""Wissensbasis (PLAN §3.5).

Einfacher Store für Fragmente, Specs und Provenance-Daten aus den Fach-Pipelines und CAD.
Kompatibel mit Integrator-Output (RealizationFragment, SystemConcept, IngenieurSpec etc.).
Datei-basiert (JSON) + in-memory Cache für schnellen Zugriff.
"""

from .store import (
    ProvenanceRecord,
    FragmentStore,
    save_fragment,
    load_fragment,
    list_fragments,
    SourceConnector,
    SourceConnectorRegistry,
    MaterialSpec,
    CADRecipe,
    query_fragments,
    list_by_idea,
    save_material,
    save_cad_recipe,
    get_registry,
    ComponentRecipe,
    save_component_recipe,
    seed_electronics_components,
    seed_general_subsystems,
    seed_from_package_results,
    query_component_recipes,
    suggest_inverse_design_components,
    internal_actuator_sim,
    seed_bio_molecular_components,
    query_bio_molecular_recipes,
)

# Bio-molecular leap (numpy 2036 local fidelity) — re-export for generalist access
try:
    from . import bio_molecular
    from .bio_molecular import (
        run_molecular_dynamics,
        run_temporal_gene_circuit,
        run_molecular_actuator,
        run_synthetic_bio_swarm,
        generate_temporal_bio_recipe,
        run_bio_molecular,
        BioMolecularParams,
    )
except Exception:  # noqa: BLE001
    bio_molecular = None  # type: ignore[assignment]
    run_molecular_dynamics = run_temporal_gene_circuit = run_molecular_actuator = None  # type: ignore[assignment]
    run_synthetic_bio_swarm = generate_temporal_bio_recipe = run_bio_molecular = None  # type: ignore[assignment]
    BioMolecularParams = None  # type: ignore[assignment]

__all__ = [
    "ProvenanceRecord",
    "FragmentStore",
    "save_fragment",
    "load_fragment",
    "list_fragments",
    "SourceConnector",
    "SourceConnectorRegistry",
    "MaterialSpec",
    "CADRecipe",
    "query_fragments",
    "list_by_idea",
    "save_material",
    "save_cad_recipe",
    "get_registry",
    # Component + actuator (pre-leap + extended)
    "ComponentRecipe",
    "save_component_recipe",
    "seed_electronics_components",
    "seed_general_subsystems",
    "seed_from_package_results",
    "query_component_recipes",
    "suggest_inverse_design_components",
    "internal_actuator_sim",
    # Bio leap additions
    "seed_bio_molecular_components",
    "query_bio_molecular_recipes",
    "bio_molecular",
    "run_molecular_dynamics",
    "run_temporal_gene_circuit",
    "run_molecular_actuator",
    "run_synthetic_bio_swarm",
    "generate_temporal_bio_recipe",
    "run_bio_molecular",
    "BioMolecularParams",
]