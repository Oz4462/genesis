"""loop — the invention orchestrator: safety -> generate -> ground -> (novelty) -> score -> artifacts.

Composes the built pieces into one deterministic run (INVENTOR §3). The control flow is fixed and non-LLM;
only generation and grounding call the (injectable) models, and a deterministic gate decides at every step:

  1. SAFETY first (TS slot): an optional structural screen runs BEFORE any concept is generated — a refused
     brief never reaches the proposer.
  2. GENERATE: the council widens to grounded concepts (``generate_concepts``).
  3. GROUND: the domain grounds each concept through the architect -> δ-physics gate (``domain.ground``).
  4. NOVELTY (TN slot): an optional per-invention novelty check annotates each result.
  5. SCORE: keep the non-dominated grounded inventions (``pareto_inventions``).
  6. ARTIFACTS: emit a buildable bundle for each front member when ``out_dir`` is given.

Everything is injectable; with a ScriptedLLM council + architect and a fixed seed the whole run is byte-for-byte
reproducible (the M1 Definition of Done). The safety/novelty hooks default to no-ops so this loop is the stable
spine that TN and TS wire into without a rewrite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from ..core.state import Possibility
from ..llm.base import LLMClient
from .brief import Invention, InventionBrief
from .domains.base import InventionDomain
from .generate import generate_concepts
from .score import pareto_inventions

#: Optional hooks the later phases wire in. SafetyScreen runs on the brief BEFORE generation; NoveltyCheck
#: annotates each grounded invention; Checkpoint is called after each concept is grounded (resume/audit).
SafetyScreen = Callable[[InventionBrief], bool]
NoveltyCheck = Callable[[Invention], Invention]
Checkpoint = Callable[[Invention], None]


@dataclass(frozen=True)
class InventionRun:
    """The result of one invention run: the ``brief``, every proposed ``concept``, every ``invention``
    (grounded or an honest gap), the non-dominated grounded ``front``, the emitted ``artifact_dirs``, and
    whether the run was ``refused`` by the safety screen before generation."""

    brief: InventionBrief
    concepts: tuple[Possibility, ...]
    inventions: tuple[Invention, ...]
    front: tuple[Invention, ...]
    artifact_dirs: tuple[str, ...]
    refused: bool = False

    @property
    def grounded_count(self) -> int:
        return sum(1 for i in self.inventions if i.grounded)


async def run_invention(
    brief: InventionBrief,
    *,
    domain: InventionDomain,
    council: LLMClient,
    architect: LLMClient,
    out_dir: Optional[str] = None,
    safety_screen: Optional[SafetyScreen] = None,
    novelty_check: Optional[NoveltyCheck] = None,
    checkpoint: Optional[Checkpoint] = None,
) -> InventionRun:
    """Run the loop end to end. Returns an :class:`InventionRun`. If ``safety_screen`` rejects the brief, the
    run is ``refused`` and the proposer is NEVER called (safety-first). Deterministic given deterministic
    ``council``/``architect`` and the brief — re-running yields an identical front. ``out_dir`` emits a bundle
    per front member under ``out_dir/<concept-id>/``."""
    if safety_screen is not None and not safety_screen(brief):
        return InventionRun(brief, (), (), (), (), refused=True)

    concepts = await generate_concepts(brief, council)
    inventions: list[Invention] = []
    for concept in concepts:
        invention = await domain.ground(concept, brief, architect)
        if novelty_check is not None:
            invention = novelty_check(invention)
        inventions.append(invention)
        if checkpoint is not None:
            checkpoint(invention)

    front = pareto_inventions(inventions)

    artifact_dirs: list[str] = []
    if out_dir is not None:
        for invention in front:
            if invention.specification is None:
                continue
            part_dir = os.path.join(out_dir, invention.concept.id)
            domain.emit_artifact(invention.specification, part_dir)
            artifact_dirs.append(part_dir)

    return InventionRun(brief, tuple(concepts), tuple(inventions), tuple(front),
                        tuple(artifact_dirs), refused=False)


__all__ = ["InventionRun", "run_invention", "SafetyScreen", "NoveltyCheck", "Checkpoint"]
