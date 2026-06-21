"""base — the domain-plugin contract and the shared grounding flow (Architect -> δ-physics gate).

The domain contract (:class:`InventionDomain`) is the loop's third plugin layer: ``prior_art_sources`` (where
to find prior art — the SearchBackend connectors), ``ground`` (turn a concept into a physics-VERIFIED
``Specification``), ``emit_artifact`` (the buildable bundle), and the optional ``external_oracle`` hook (TC3).

The shared grounding flow lives here: an injectable ARCHITECT (an ``LLMClient``; offline default a
``ScriptedLLM``) emits measurand-tagged quantities; they are assembled into a ``Specification``; and the
deterministic δ-physics gate (``physics_selection.evaluate_spec_physics``) verifies it. The honest verdict —
``physics_verified`` — is True ONLY when the gate passes AND at least one check actually fired: a vacuous spec
the engine cannot check is NOT verified (that is the difference between "proven" and "nothing to prove"). An
over-bold concept whose physics fails, or whose quantities fire no check, returns an honest gap, not a pass.
"""

from __future__ import annotations

import json
from typing import Optional, Protocol, Sequence, runtime_checkable

from ...bundle import BundleManifest
from ...core.errors import GenesisError, LLMOutputError
from ...core.interfaces import SearchBackend
from ...core.state import Possibility, Quantity, Specification, ValueOrigin
from ...external.oracle import ExternalOracle
from ...llm.base import LLMClient, ScriptedLLM
from ...llm.parsing import extract_json
from ...physics_selection import evaluate_spec_physics
from ..brief import Invention, InventionBrief

ARCHITECT_SYSTEM = (
    "You are the architect of an anti-hallucination invention engine. Turn a concept into a buildable "
    "specification as measurand-tagged QUANTITIES, so a DETERMINISTIC physics gate can verify it. Each "
    "quantity needs a measurand tag the engine recognizes (e.g. vibration.first_natural_frequency, "
    "shaft.torque, material.shear_modulus). You only PROPOSE numbers; the gate checks the physics. Reply ONLY "
    'with JSON: {"quantities":[{"id":"...","name":"...","value":0.0,"unit":"...","measurand":"...",'
    '"grounding":["..."],"rationale":"..."}],"gaps":["..."]}'
)


@runtime_checkable
class InventionDomain(Protocol):
    """A domain plugin: prior-art sources, grounding, artifact emission, optional external oracle."""

    name: str

    def prior_art_sources(self) -> list[SearchBackend]:
        ...

    async def ground(self, concept: Possibility, brief: InventionBrief, architect: LLMClient) -> Invention:
        ...

    def emit_artifact(self, spec: Specification, out_dir) -> BundleManifest:
        ...

    def external_oracle(self) -> Optional[ExternalOracle]:
        ...


def parse_quantities(items: object) -> list[Quantity]:
    """Build ``Quantity`` objects from the architect's JSON list. A row with a non-numeric value is skipped
    (never coerced to a fabricated number); a missing measurand becomes ``None`` (it then fires no check —
    honest, not a silent pass). The ORIGIN follows the core invariant: a grounded value is ``GROUNDED`` (a
    sourced fact), a value with no anchor is ``DECISION`` (a choice) — a DECISION may not carry grounding."""
    out: list[Quantity] = []
    if not isinstance(items, list):
        return out
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            continue
        measurand = str(item.get("measurand", "")).strip() or None
        qid = str(item.get("id") or f"q{i + 1}")
        grounding = [str(g) for g in (item.get("grounding") or []) if str(g).strip()]
        # core invariant: a GROUNDED value is a sourced fact (no rationale); a DECISION is a choice (rationale,
        # no grounding). Honor it here so the architect's JSON cannot construct a contradictory quantity.
        if grounding:
            origin, rationale = ValueOrigin.GROUNDED, ""
        else:
            # a DECISION must declare a rationale; an architect value with neither source nor reason is
            # honestly labelled as an unsourced declaration, never silently passed off as grounded.
            origin = ValueOrigin.DECISION
            rationale = str(item.get("rationale", "")).strip() or "vom Architekten deklarierter Wert (keine Quelle)"
        out.append(Quantity(
            id=qid, name=str(item.get("name") or qid), value=value,
            unit=str(item.get("unit") or "1"), origin=origin,
            rationale=rationale, measurand=measurand, grounding=grounding))
    return out


def build_specification(concept: Possibility, brief: InventionBrief,
                        quantities: Sequence[Quantity], gaps: Sequence[str]) -> Specification:
    """Assemble a ``Specification`` from the concept + the architect's quantities. The concept's grounding
    anchors become the spec's used claim ids — provenance carried through."""
    return Specification(
        run_id=brief.run_id, idea=concept.statement, approach_id=None,
        quantities=list(quantities), gaps=list(gaps), claim_ids_used=list(concept.grounding),
        produced_by="inventor.architect")


def _payload(data: object, key: str) -> list:
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return data[key]
    return []


def _architect_prompt(concept: Possibility, brief: InventionBrief) -> str:
    parts = [f"Concept: {concept.statement}", f"Mechanism: {concept.mechanism}",
             f"Field: {brief.field}"]
    if brief.constraints:
        parts.append("Hard constraints: " + "; ".join(brief.constraints))
    parts.append("Emit measurand-tagged quantities a deterministic physics gate can verify.")
    return "\n".join(parts)


async def ground_with_architect(concept: Possibility, brief: InventionBrief, architect: LLMClient) -> Invention:
    """The shared grounding flow: architect -> Specification -> δ-physics gate. ``physics_verified`` is True
    only when the gate passes AND at least one check fired (a vacuous spec is NOT verified). An unparseable
    architect reply, a failed check, or a no-check spec each yields an honest gap, never a fabricated pass."""
    response = await architect.complete(system=ARCHITECT_SYSTEM, user=_architect_prompt(concept, brief))
    try:
        data = extract_json(response.text, agent="inventor.architect")
    except LLMOutputError:
        return Invention(concept=concept, specification=None, physics_verified=False,
                         gaps=("Architekt-Antwort unparsebar — keine Spezifikation erzeugt",),
                         prior_art=tuple(concept.grounding))

    quantities = parse_quantities(_payload(data, "quantities"))
    declared_gaps = tuple(str(g) for g in _payload(data, "gaps"))
    try:
        spec = build_specification(concept, brief, quantities, declared_gaps)
        result = evaluate_spec_physics(spec)
    except GenesisError as exc:
        return Invention(concept=concept, specification=None, physics_verified=False,
                         gaps=declared_gaps + (f"Spezifikation nicht baubar: {exc}",),
                         prior_art=tuple(concept.grounding))

    n_checks = len(result["checks"])
    physics_verified = bool(result["gate"].passed and n_checks > 0)
    gaps = declared_gaps + tuple(str(g) for g in result["gaps"])
    if n_checks == 0:
        gaps = gaps + ("δ-Physik-Gate fand keine prüfbaren Größen (vacuous) — nicht physik-verifiziert",)
    elif not result["gate"].passed:
        gaps = gaps + ("δ-Physik-Gate NICHT bestanden — Konzept zu kühn / Auslegung hält nicht",)
    return Invention(concept=concept, specification=spec, physics_verified=physics_verified,
                     gaps=gaps, prior_art=tuple(concept.grounding))


def scripted_architect(quantities: Sequence[dict], *, gaps: Sequence[str] = (),
                       model: str = "scripted-architect") -> ScriptedLLM:
    """The OFFLINE architect default: a deterministic ``ScriptedLLM`` that emits a fixed measurand-tagged
    quantity list — the test/demo backbone for grounding."""
    payload = json.dumps({"quantities": list(quantities), "gaps": list(gaps)})
    return ScriptedLLM(model, payload)


__all__ = [
    "InventionDomain", "ARCHITECT_SYSTEM", "parse_quantities", "build_specification",
    "ground_with_architect", "scripted_architect",
]
