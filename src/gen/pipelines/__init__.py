"""Fach-Pipelines (PLAN §3.4 / 4.).

Erste Steine für die domänenspezifischen Pipelines (Architekt, Ingenieur, Fertigung, ...).
Jede Pipeline erzeugt strukturierte, provenance-starke Outputs, die in den CAD-Kern und Manufacturing-Gates fließen können.
"""

from .architekt import (
    SystemRequirement,
    AssemblyConcept,
    SystemConcept,
    map_to_system_concept,
)
from .ingenieur import (
    LoadCase,
    MaterialSpec,
    ToleranceSpec,
    FailureMode,
    IngenieurSpec,
    map_to_ingenieur_spec,
)
from .integrator import (
    RealizationFragment,
    build_realization_fragment,
    build_full_mini_realization_package,
    realize,
)
from .physiker import (
    PhysikDomäne,
    ModellGleichung,
    UnsicherheitsBudget,
    FalsifikationsPlan,
    PhysikerSpec,
    map_to_physiker_spec,
)
from .techniker import (
    MontageSchritt,
    TechnikerSpec,
    map_to_techniker_spec,
)
from .elektriker import (
    Stromkreis,
    LeistungsBudget,
    EMVCheck,
    SicherheitsAnforderung,
    ElektronikSpec,
    map_to_elektriker_spec,
)
# Deep electronics layer (PLAN §4.5 full) — re-exported for consumers
# (Component, PowerTree, Netlist, PlacementHint, simulation results, etc.)
try:
    from gen.electronics import (
        Component as ElectronicsComponent,
        PowerRail,
        PowerTree,
        HarnessSegment,
        HarnessSpec,
        PlacementHint,
        ElectronicsSimulationCase,
        ElectronicsSimulationResult,
        synthesize_or_select_circuit,
        run_electronics_simulation,
        produce_cad_integration_artifacts,
        generate_falsification_experiments_for_electronics,
        build_rich_electronics_pieces,
        electronics_to_thermal_loads,
    )
except ImportError:  # pragma: no cover — #15: nur fehlende optionale Deps abfangen, echte Fehler propagieren
    ElectronicsComponent = PowerRail = PowerTree = HarnessSegment = HarnessSpec = PlacementHint = None  # type: ignore
    ElectronicsSimulationCase = ElectronicsSimulationResult = None  # type: ignore
    synthesize_or_select_circuit = run_electronics_simulation = None  # type: ignore
    produce_cad_integration_artifacts = generate_falsification_experiments_for_electronics = None  # type: ignore
    build_rich_electronics_pieces = electronics_to_thermal_loads = None  # type: ignore
from .designer import (
    ErgonomieAnforderung,
    FormEntscheidung,
    BedienSzenario,
    DesignerSpec,
    map_to_designer_spec,
)
from .fertigungs import (
    FertigungsProzess,
    KostenModell,
    QAPlan,
    FertigungsSpec,
    map_to_fertigungs_spec,
)
from .software import (
    EmbeddedComponent,
    APISpec,
    UpdatePfad,
    SoftwareSpec,
    map_to_software_spec,
)
from .regulatorik import (
    Norm,
    Risiko,
    RegulatorikSpec,
    map_to_regulatorik_spec,
)
from .wirtschaft import (
    KostenStruktur,
    Markt,
    WirtschaftSpec,
    map_to_wirtschaft_spec,
)

__all__ = [
    "SystemRequirement",
    "AssemblyConcept",
    "SystemConcept",
    "map_to_system_concept",
    "LoadCase",
    "MaterialSpec",
    "ToleranceSpec",
    "FailureMode",
    "IngenieurSpec",
    "map_to_ingenieur_spec",
    "RealizationFragment",
    "build_realization_fragment",
    "build_full_mini_realization_package",
    "realize",
    "PhysikDomäne",
    "ModellGleichung",
    "UnsicherheitsBudget",
    "FalsifikationsPlan",
    "PhysikerSpec",
    "map_to_physiker_spec",
    "MontageSchritt",
    "TechnikerSpec",
    "map_to_techniker_spec",
    "Stromkreis",
    "LeistungsBudget",
    "EMVCheck",
    "SicherheitsAnforderung",
    "ElektronikSpec",
    "map_to_elektriker_spec",
    "ElectronicsComponent",
    "PowerRail",
    "PowerTree",
    "HarnessSegment",
    "HarnessSpec",
    "PlacementHint",
    "ElectronicsSimulationCase",
    "ElectronicsSimulationResult",
    "synthesize_or_select_circuit",
    "run_electronics_simulation",
    "produce_cad_integration_artifacts",
    "generate_falsification_experiments_for_electronics",
    "build_rich_electronics_pieces",
    "electronics_to_thermal_loads",
    "ErgonomieAnforderung",
    "FormEntscheidung",
    "BedienSzenario",
    "DesignerSpec",
    "map_to_designer_spec",
    "FertigungsProzess",
    "KostenModell",
    "QAPlan",
    "FertigungsSpec",
    "map_to_fertigungs_spec",
    "EmbeddedComponent",
    "APISpec",
    "UpdatePfad",
    "SoftwareSpec",
    "map_to_software_spec",
    "Norm",
    "Risiko",
    "RegulatorikSpec",
    "map_to_regulatorik_spec",
    "KostenStruktur",
    "Markt",
    "WirtschaftSpec",
    "map_to_wirtschaft_spec",
]