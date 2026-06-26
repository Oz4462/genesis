"""gen.inventor.domains — the domain-plugin layer of the invention loop.

A domain (mechatronics, optics, ...) plugs into the loop through one contract (:class:`InventionDomain`):
where to look for PRIOR ART (the SearchBackend connectors), how to GROUND a concept (an injectable architect
emits measurand-tagged quantities -> the deterministic δ-physics gate verifies them), how to EMIT the buildable
ARTIFACT (bundle), and optionally an EXTERNAL ORACLE (TC3). The offline ScriptedLLM/RagBackend path is the test
backbone; any live model/connector/oracle drops into the same seams.
"""

from .base import (
    ARCHITECT_SYSTEM,
    InventionDomain,
    build_specification,
    ground_with_architect,
    parse_quantities,
    scripted_architect,
)
from .mechatronics import MechatronicsDomain, scripted_mechatronics_architect
from .thermal import ThermalDomain, scripted_thermal_architect

__all__ = [
    "InventionDomain",
    "ARCHITECT_SYSTEM",
    "ground_with_architect",
    "parse_quantities",
    "build_specification",
    "scripted_architect",
    "MechatronicsDomain",
    "scripted_mechatronics_architect",
    "ThermalDomain",
    "scripted_thermal_architect",
]
