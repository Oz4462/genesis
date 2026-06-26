"""
Thin re-export shim for backward compatibility.

The canonical implementation lives in:
    gen.humanoids.humanoid_research

This allows:
    python -m gen.humanoid_research
    from gen import humanoid_research
    from gen.humanoid_research import HumanoidResearchModule
"""

from .humanoids.humanoid_research import (  # noqa: F401
    HUMANOID_TAXONOMY,
    HumanoidResearchModule,
    build_taxonomy,
    create_module,
)

__all__ = [
    "HumanoidResearchModule",
    "create_module",
    "build_taxonomy",
    "HUMANOID_TAXONOMY",
]
