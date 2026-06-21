"""CAD / CAE / Fertigung core for GENESIS (PLAN §3.6, §3.7, 4.7, 8.4).

This package implements the real parametric CAD capability using the best-matching
open-source stack (build123d on OCCT — directly referenced in the PLAN).

First stone: prototype_cad_builder (per 8.4 table).
"""

from .prototype_cad_builder import (
    PrototypeSpec,
    BuildArtifact,
    build_prototype_cad,
)
from .manufacturing_check import (
    ManufacturingCheck,
    check_manufacturing,
    AdvancedDFMReport,
    ProcessDFM,
    check_advanced_dfm,
)
from .assembly import (
    AssemblyPart,
    AssemblySpec,
    AssemblyArtifact,
    build_assembly,
)

__all__ = [
    "PrototypeSpec",
    "BuildArtifact",
    "build_prototype_cad",
    "ManufacturingCheck",
    "check_manufacturing",
    "AdvancedDFMReport",
    "ProcessDFM",
    "check_advanced_dfm",
    "AssemblyPart",
    "AssemblySpec",
    "AssemblyArtifact",
    "build_assembly",
]
