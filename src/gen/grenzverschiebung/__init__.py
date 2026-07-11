"""Grenzverschiebungs-Layer (Moonshot + Entwicklung der Grenze).

Erste Module gemäß GENESIS_PLATFORM_PLAN.md §3.3.
"""

from .development_front import (
    DevelopmentFrontMap,
    ExperimentleiterSchritt,
    Grenztyp,
    map_development_front,
)
from .capability_gap_analyzer import (
    CapabilityGap,
    CapabilityGapReport,
    GapCategory,
    analyze_capability_gaps,
)
from .milestone_builder import (
    Milestone,
    MilestoneLadder,
    build_milestone_ladder,
)
from .experiment_designer import (
    Experiment,
    ExperimentPlan,
    design_experiment_plan,
)
from .teststand_architect import (
    TestStandSpec,
    build_test_stand,
)
from .proof_package import ProofPackage, generate_proof_package
from .readiness_ladder import ReadinessLevel, assess_readiness, teacher_notes, READINESS_LADDER, TeacherMode, community_evidence
from .technology_roadmapper import (
    TechnologyGap,
    TechnologyRoadmap,
    build_technology_roadmap,
)
from .technology_builder import (
    TechnologyPrototypeSpec,
    TechnologyPrototypePlan,
    build_technology_prototype,
)
from .breakthrough_watch import (
    FrontierItem,
    FrontierUpdate,
    watch_frontier,
)
from .boundary_reviser import (
    BoundaryRevision,
    RevisedFrontMap,
    revise_boundary,
)
from .safety_ladder import (
    SafetyStage,
    SafetyStagePlan,
    build_safety_ladder,
)
from .learning_integrator import (
    LearningRule,
    FailureMode,
    WissensEintrag,
    LearningDelta,
    apply_learning_cycle,
)
from .lumencrucible import (
    LumenCrucible,
    LumenHammer,
    process_dream,
    forge_research,          # ResearchForge / DiscoveryCrucible — hardened Forscher-Erfindungsprozess (fusion + multi-component sim → Studie → Arbei t + neues Rezept + Package mit Mehrwert)
)

# LUMENCRUCIBLE Ω v1 HORIZON entrypoint exposure (first-class dream → hammer gate)
from ..verification.gates import dream_to_hammer_gate  # type: ignore[attr-defined]

# Simulation layer (Punkt 4 – hardened automatic coupling)
from ..simulation.runner import (
    SimulationRunner,
    SimulationCase,
    SimulationResult,
    SimulationReport,
    run_simulations_for_design,
    run_simulations_for_hammer,
    build_simulation_report,
)

__all__ = [
    "DevelopmentFrontMap",
    "ExperimentleiterSchritt",
    "Grenztyp",
    "map_development_front",
    "CapabilityGap",
    "CapabilityGapReport",
    "GapCategory",
    "analyze_capability_gaps",
    "Milestone",
    "MilestoneLadder",
    "build_milestone_ladder",
    "Experiment",
    "ExperimentPlan",
    "design_experiment_plan",
    "TestStandSpec",
    "build_test_stand",
    "TechnologyGap",
    "TechnologyRoadmap",
    "build_technology_roadmap",
    "TechnologyPrototypeSpec",
    "TechnologyPrototypePlan",
    "build_technology_prototype",
    "FrontierItem",
    "FrontierUpdate",
    "watch_frontier",
    "BoundaryRevision",
    "RevisedFrontMap",
    "revise_boundary",
    "SafetyStage",
    "SafetyStagePlan",
    "build_safety_ladder",
    "LearningRule",
    "FailureMode",
    "WissensEintrag",
    "LearningDelta",
    "apply_learning_cycle",
    "LumenCrucible",
    "LumenHammer",
    "process_dream",
    "forge_research",        # Priority 0: the real researcher invention engine (user requirement)
    "SimulationRunner",
    "SimulationCase",
    "SimulationResult",
    "SimulationReport",
    "run_simulations_for_design",
    "run_simulations_for_hammer",
    "build_simulation_report",
]
