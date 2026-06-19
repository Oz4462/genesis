"""brief — the request and result types of the invention loop (composing core.state, no new fact types).

A bold invention CONCEPT is already a ``core.state.Possibility`` (statement + mechanism + grounding); a
GROUNDED invention is already a ``core.state.Specification``. So the inventor adds only two ORCHESTRATION
hulls — never a new fact type:

  * :class:`InventionBrief` — the human input (a field to invent in, an optional goal, hard constraints). It
    is a REQUEST, not a fact: it carries no ledger entry of its own.
  * :class:`Invention` — the per-concept RESULT bundle: the proposed concept, the grounded spec (or ``None``
    — an honest gap when the deterministic gate killed an over-bold concept), the gate verdict, and the
    novelty / safety / score / artifact fields the later phases fill in.

Honest by construction: ``specification=None`` with ``physics_verified=False`` is a valid, first-class outcome
("concept too bold, not grounded"), not an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.state import Possibility, Specification


@dataclass(frozen=True)
class InventionBrief:
    """The input to the invention loop: a ``field`` to invent in, an optional explicit ``goal``, and hard
    ``constraints`` the result must respect. ``run_id`` ties the run together; ``max_concepts`` bounds the
    proposer. A request, not a fact — no ledger entry."""

    field: str
    run_id: str
    goal: str = ""
    constraints: tuple[str, ...] = ()
    max_concepts: int = 8

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("InventionBrief needs a non-empty field to invent in")
        if not self.run_id.strip():
            raise ValueError("InventionBrief needs a run_id")
        if self.max_concepts < 1:
            raise ValueError("max_concepts must be >= 1")


@dataclass(frozen=True)
class Invention:
    """One concept carried through the loop: the proposed ``concept`` (a ``Possibility``), its grounded
    ``specification`` (or ``None`` if grounding failed — an honest gap), the deterministic gate verdict
    ``physics_verified``, and the fields the later phases attach: ``novelty_verdict`` (Phase N), ``safety_ok``
    (Phase S, default True until screened), a ``score`` tuple (Phase I scoring), ``gaps``, and an
    ``artifact_dir`` once a bundle is emitted. Frozen; phases produce a NEW Invention via ``dataclasses.replace``."""

    concept: Possibility
    specification: Optional[Specification] = None
    physics_verified: bool = False
    novelty_verdict: Optional[str] = None
    safety_ok: bool = True
    score: Optional[tuple[float, ...]] = None
    gaps: tuple[str, ...] = ()
    prior_art: tuple[str, ...] = ()
    artifact_dir: Optional[str] = None

    @property
    def grounded(self) -> bool:
        """True iff this concept survived grounding into a physics-verified specification."""
        return self.specification is not None and self.physics_verified


__all__ = ["InventionBrief", "Invention"]
