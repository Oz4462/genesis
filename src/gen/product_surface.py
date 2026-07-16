"""product_surface — intentional PRODUCT reachability for GENESIS shipping surface.

``scripts/find_islands.py`` only follows static import chains from CLI/web entries.
Several real, tested product modules were only reached dynamically (or from tests),
so they appeared as ISLANDs despite being part of the product (drawing, aero fleet
calibration, ROS2 export, optional integration seams, Monte Carlo uncertainty).

This module is imported by ``gen.cli`` so those modules are WIRED by design.
Runtime-optional deps (trust-core, gmsh, …) use try/except so CLI still starts;
AST imports remain for reachability analysis either way.

KEEP_OPTIN modules that require private/GPU stacks and must not break import
(e.g. materials_oracle GPU path) stay dispositioned in ISLAND_TRIAGE, not forced here.
"""

from __future__ import annotations

# ── Manufacturing / export (product deliverables) ───────────────────────────
from .export import drawing as export_drawing
from .export.ros2_package import export_ros2_package

# ── Aero fleet calibration (feeds flight.min_thrust_weight_for_class path) ──
from .aero import calibration as aero_calibration
from .aero import drone_catalog as aero_drone_catalog
from .aero import model_parser as aero_model_parser
from .aero import scaling_laws as aero_scaling_laws

# ── Physics satellites used as optional engineering screens ─────────────────
from . import montecarlo as montecarlo_mod
from . import plate_hole as plate_hole_mod
from . import bracket_fem as bracket_fem_mod
from . import calibration as sensor_calibration
from . import urdf_bridge as urdf_bridge_mod

# ── Tools / discovery / inventor (product research surface) ─────────────────
from .tools import wikidata as wikidata_mod
from .tools import materials_backend as materials_backend_mod
from .tools import the_well_probe as the_well_probe_mod
from . import materials as materials_registry_mod
from .discovery import first_principles as discovery_first_principles
from .discovery import proof_loop as discovery_proof_loop
from .discovery import uncertainty as discovery_uncertainty
from .discovery import active_resolution as discovery_active_resolution
from .discovery import assumption_annihilator as discovery_assumption_annihilator
from .discovery import cosmic_insight as discovery_cosmic_insight
from .discovery import reality_fork as discovery_reality_fork
from .discovery import surrogate as discovery_surrogate
from .discovery import universe_bridge as discovery_universe_bridge
from .inventor import archive as inventor_archive
from .inventor import evolve_engine as inventor_evolve
from .inventor import refinement as inventor_refinement
from .humanoids import balance_controller as humanoids_balance_controller
from .wissensbasis import evidence as wissensbasis_evidence

# ── Optional integration seams (AST-wired; runtime may lack trust-core) ─────
try:
    from .integration.audited_run import audited_run
except ImportError:  # pragma: no cover - optional verify extra
    audited_run = None  # type: ignore[assignment]

try:
    from .integration.drift import detect_run_drift
except ImportError:  # pragma: no cover - needs private trust-core
    detect_run_drift = None  # type: ignore[assignment]

try:
    from .verification import trustcore_adapter as trustcore_adapter_mod
except ImportError:  # pragma: no cover - optional verify extra
    trustcore_adapter_mod = None  # type: ignore[assignment]


#: Stable names of modules this surface intentionally anchors (for docs/tests).
PRODUCT_SURFACE_MODULES: tuple[str, ...] = (
    "gen.export.drawing",
    "gen.export.ros2_package",
    "gen.aero.calibration",
    "gen.aero.drone_catalog",
    "gen.aero.model_parser",
    "gen.aero.scaling_laws",
    "gen.montecarlo",
    "gen.plate_hole",
    "gen.bracket_fem",
    "gen.calibration",
    "gen.urdf_bridge",
    "gen.integration.audited_run",
    "gen.integration.drift",
    "gen.tools.wikidata",
    "gen.tools.materials_backend",
    "gen.tools.the_well_probe",
    "gen.materials",
    "gen.verification.trustcore_adapter",
    "gen.discovery.first_principles",
    "gen.discovery.proof_loop",
    "gen.discovery.uncertainty",
    "gen.discovery.active_resolution",
    "gen.discovery.assumption_annihilator",
    "gen.discovery.cosmic_insight",
    "gen.discovery.reality_fork",
    "gen.discovery.surrogate",
    "gen.discovery.universe_bridge",
    "gen.inventor.archive",
    "gen.inventor.evolve_engine",
    "gen.inventor.refinement",
    "gen.humanoids.balance_controller",
    "gen.wissensbasis.evidence",
)


def surface_modules() -> tuple[str, ...]:
    """Return the module names anchored by this product surface."""
    return PRODUCT_SURFACE_MODULES
