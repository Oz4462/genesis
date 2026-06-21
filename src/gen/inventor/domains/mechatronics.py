"""mechatronics — the first concrete invention domain (printable mechatronic parts).

Plugs into the loop through :class:`InventionDomain`: prior art via the SearchBackend connectors (offline a
small RagBackend; live OpenAlex + PatentsView), grounding via the shared architect -> δ-physics flow, and a
buildable artifact via ``bundle.emit_bundle`` (STL + BOM + build manual). The offline default architect emits
a RESONANCE check (a printable mount whose first natural frequency must stay above its operating excitation) —
a real δ-physics gate: a sound design passes, an over-bold one (resonance at/below the operating speed) fails,
honestly. No external oracle is wired offline (``external_oracle`` returns None).
"""

from __future__ import annotations

from typing import Optional, Sequence

from ...bundle import BundleManifest, emit_bundle
from ...core.interfaces import SearchBackend
from ...core.state import Possibility, Specification
from ...external.oracle import ExternalOracle
from ...llm.base import LLMClient, ScriptedLLM
from ...tools.rag_backend import Document, RagBackend
from ..brief import Invention, InventionBrief
from .base import ground_with_architect, scripted_architect

_PRIOR_ART_CORPUS = [
    Document(url_or_id="https://openalex.org/W-compliant-mech",
             title="Compliant mechanisms for robotic grippers",
             text="printed flexures store elastic energy; pseudo-rigid-body model; resonance of compliant mounts"),
    Document(url_or_id="patentsview:US-electroadhesion",
             title="Electroadhesive gripping pad",
             text="electrostatic clamping; controllable adhesion; low-power hold for handling"),
    Document(url_or_id="https://openalex.org/W-actuator-mount",
             title="Vibration design of printed actuator mounts",
             text="first natural frequency above operating excitation; FDM bracket stiffness; modal margin"),
]


def _default_rag() -> RagBackend:
    """A tiny offline prior-art corpus so the domain is fully testable without the network. Live runs inject
    the OpenAlex + PatentsView connectors instead."""
    return RagBackend(_PRIOR_ART_CORPUS)


class MechatronicsDomain:
    """Printable mechatronic parts domain. Satisfies :class:`InventionDomain`.

    ``backends`` (optional) are the prior-art SearchBackends; the offline default is a small RagBackend, so a
    live run injects ``[OpenAlexBackend(...), PatentsViewBackend(...)]`` to search real prior art."""

    name = "mechatronics"

    def __init__(self, *, backends: Optional[Sequence[SearchBackend]] = None) -> None:
        self._backends: list[SearchBackend] = list(backends) if backends is not None else [_default_rag()]

    def prior_art_sources(self) -> list[SearchBackend]:
        return list(self._backends)

    async def ground(self, concept: Possibility, brief: InventionBrief, architect: LLMClient) -> Invention:
        return await ground_with_architect(concept, brief, architect)

    def emit_artifact(self, spec: Specification, out_dir) -> BundleManifest:
        return emit_bundle(spec, out_dir)

    def external_oracle(self) -> Optional[ExternalOracle]:
        return None


def scripted_mechatronics_architect(*, first_natural_hz: float = 150.0, excitation_hz: float = 50.0,
                                    grounding: Sequence[str] = ("https://openalex.org/W-actuator-mount",),
                                    model: str = "scripted-architect") -> ScriptedLLM:
    """A deterministic offline architect for the mechatronics domain: emits a resonance-check spec (a printable
    mount whose first natural frequency must stay above its operating excitation). A sound design
    (``first_natural_hz`` well above ``excitation_hz``) passes the δ-physics gate; setting it at/below the
    excitation models an over-bold concept the gate rejects — the same machinery, two honest verdicts."""
    quantities = [
        {"id": "q_excite", "name": "Betriebs-Anregungsfrequenz", "value": excitation_hz, "unit": "Hz",
         "measurand": "vibration.excitation_frequency", "rationale": "Betriebsdrehzahl der Halterung"},
        {"id": "q_fn", "name": "erste Eigenfrequenz der Halterung", "value": first_natural_hz, "unit": "Hz",
         "measurand": "vibration.first_natural_frequency", "grounding": list(grounding),
         "rationale": "Closed-form/FE-Schätzung der ersten Mode"},
    ]
    return scripted_architect(quantities, gaps=[], model=model)


__all__ = ["MechatronicsDomain", "scripted_mechatronics_architect"]
