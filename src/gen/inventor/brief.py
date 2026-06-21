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
from typing import TYPE_CHECKING, Optional, Sequence

from ..core.state import Possibility, Specification

if TYPE_CHECKING:
    from ..core.interfaces import SearchBackend


@dataclass(frozen=True)
class InventionBrief:
    """The input to the invention loop: a ``field`` to invent in, an optional explicit ``goal``, and hard
    ``constraints`` the result must respect. ``run_id`` ties the run together; ``max_concepts`` bounds the
    proposer. A request, not a fact — no ledger entry.

    `frontier_context` (new for explicit Prior-Art step per INVENTOR_ARCHITEKTUR §3 ❶):
    A short, grounded summary of what is already known / the open edge in this field.
    Injected into generation prompts so proposals are frontier-aware (not hallucinated novelty).
    """

    field: str
    run_id: str
    goal: str = ""
    constraints: tuple[str, ...] = ()
    max_concepts: int = 8
    frontier_context: str = ""

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


def build_basic_frontier_context(field: str, goal: str = "") -> str:
    """Pragmatic starter for step ❶ Prior-Art & Frontier (INVENTOR_ARCHITEKTUR).
    In real use this should call scout + scholar + search backends to produce a short,
    sourced summary of known territory + open edge.

    Current MVP version just frames the question — callers should replace with real retrieval.
    """
    base = f"Field: {field}."
    if goal:
        base += f" Goal: {goal}."
    base += " (Real implementation: retrieve recent papers/patents in this exact field and summarize the leading approaches + remaining gaps.)"
    return base


async def build_frontier_context(
    field: str,
    goal: str,
    backends: Sequence["SearchBackend"],
    *,
    limit: int = 5,
) -> str:
    """Step ❶ Prior-Art & Frontier: query the domain's prior-art backends for ``field``/``goal``
    and summarize the real candidates into a short, SOURCED frontier context.

    Deterministic given the backends (the offline default is an in-memory RagBackend) — no LLM,
    no fabrication: every line names a real candidate id a backend returned. A failing backend is
    skipped (never invents a frontier). On zero hits it falls back to the framing-only basic
    context — an honest "no prior art retrieved", not a guess.
    """
    from ..core.errors import SearchBackendError

    query = f"{field}. {goal}".strip(". ").strip() or field
    seen: set[str] = set()
    found = []
    for backend in backends:
        try:
            for cand in await backend.search(query, limit):
                if cand.url_or_id not in seen:
                    seen.add(cand.url_or_id)
                    found.append(cand)
        except SearchBackendError:
            continue  # a failing prior-art source must never fabricate a frontier
    if not found:
        return build_basic_frontier_context(field, goal)

    header = f"Field: {field}." + (f" Goal: {goal}." if goal else "")
    lines = [header, "Known prior art retrieved for this field "
                     "(target genuine gaps, do not reinvent these):"]
    for c in found[:limit]:
        label = (c.title or c.url_or_id).strip()
        lines.append(f"  - {label} [{c.url_or_id}]")
    return "\n".join(lines)


__all__ = ["InventionBrief", "Invention", "build_basic_frontier_context", "build_frontier_context"]
