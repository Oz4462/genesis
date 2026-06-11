"""GENESIS pipeline wiring — `run(question) -> Report` (PHASE_ALPHA §8 / Aufgabe 5).

Dependency-injected so the same pipeline runs with real adapters or with the
deterministic offline stand-ins used in tests and the demo. Responsibilities:
  * assign a run_id and compute a config_hash (reproducibility anchor, A5);
  * wire conductor -> scout/scholar/skeptic with the cross-model split
    (generator family for scout/scholar, verifier family for skeptic);
  * log the generator/verifier model ids so cross-model activity is auditable (A6);
  * optionally checkpoint the run for later inspection.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .agents.architect import Architect
from .agents.conductor import Conductor
from .agents.scholar import Scholar
from .agents.scout import Scout
from .agents.skeptic import Skeptic
from .agents.synthesizer import Synthesizer
from .config import Config, config_hash, default_config
from .core.interfaces import LedgerStore, SearchBackend
from .core.state import Question, Report, RunState, SolutionReport, Specification
from .llm.base import LLMClient
from .tools.fetch import WebFetchTool
from .tools.http import HttpGet


@dataclass
class Dependencies:
    """Everything the pipeline needs, injected from the edge.

    `http_get` (not a prebuilt fetch tool) so the runner can wire the ledger +
    run_id into the WebFetchTool, ensuring every fetch is recorded for the run.
    """

    backends: Sequence[SearchBackend]
    http_get: HttpGet
    generator_llm: LLMClient   # scout + scholar
    verifier_llm: LLMClient    # skeptic (different family)
    ledger: LedgerStore
    judge_llm: LLMClient | None = None


def make_run_id(question: str, cfg_hash: str, *, suffix: str | None = None) -> str:
    import hashlib

    base = hashlib.sha1(f"{question}|{cfg_hash}".encode("utf-8")).hexdigest()[:10]
    return f"run-{base}" + (f"-{suffix}" if suffix else "")


async def run(
    question_text: str,
    deps: Dependencies,
    *,
    config: Config | None = None,
    run_id: str | None = None,
    checkpoint_dir: str | None = None,
) -> Report:
    """Execute one Phase α run and return the verified report.

    Pass an explicit `run_id` (with a fresh/snapshotted ledger) to reproduce a
    prior run exactly (A5). Omit it and a run_id is derived from the question +
    config plus a time suffix for uniqueness.
    """
    config = config or default_config()
    pa = config.phase_alpha
    chash = config_hash(config)
    rid = run_id or make_run_id(question_text, chash, suffix=str(time.time_ns()))

    state = RunState(question=Question(raw=question_text, run_id=rid))
    # Auditable proof that verification is cross-model (A6).
    state.log.append(
        f"runner: run_id={rid} config_hash={chash[:12]} "
        f"generator={deps.generator_llm.model} verifier={deps.verifier_llm.model}"
    )

    fetch = WebFetchTool(deps.http_get, ledger=deps.ledger, run_id=rid)
    scout = Scout(deps.backends, llm=deps.generator_llm)
    scholar = Scholar(fetch, deps.generator_llm, deps.ledger)
    skeptic = Skeptic(
        deps.backends,
        fetch,
        deps.verifier_llm,
        deps.ledger,
        generator_model=pa.models.generator,
        second_judge=deps.judge_llm,
        min_sources_for_verified=pa.min_sources_for_verified,
    )
    conductor = Conductor(
        scout,
        scholar,
        skeptic,
        llm=deps.generator_llm,
        confidence_threshold=pa.confidence_threshold,
        max_refine_rounds=pa.max_refine_rounds,
    )

    await conductor.run(state)

    if checkpoint_dir is not None:
        save_checkpoint(checkpoint_dir, state, chash)
    assert state.report is not None  # conductor always assembles a report
    return state.report


async def run_solution(
    question_text: str,
    deps: Dependencies,
    *,
    config: Config | None = None,
    run_id: str | None = None,
    checkpoint_dir: str | None = None,
) -> SolutionReport:
    """Execute one Phase β run and return the grounded solution space.

    Same cross-model α research as `run` (scout/scholar/skeptic) plus the
    `synthesizer`, which structures the verified claims into grounded approaches
    behind GATE β. The synthesizer uses the generator family — structuring is not
    verification, and the underlying claims were already verified cross-model by the
    skeptic, so the cross-model guarantee is preserved.
    """
    config = config or default_config()
    pa = config.phase_alpha
    pb = config.phase_beta
    chash = config_hash(config)
    rid = run_id or make_run_id(question_text, chash, suffix=str(time.time_ns()))

    state = RunState(question=Question(raw=question_text, run_id=rid))
    state.log.append(
        f"runner: [beta] run_id={rid} config_hash={chash[:12]} "
        f"generator={deps.generator_llm.model} verifier={deps.verifier_llm.model}"
    )

    fetch = WebFetchTool(deps.http_get, ledger=deps.ledger, run_id=rid)
    scout = Scout(deps.backends, llm=deps.generator_llm)
    scholar = Scholar(fetch, deps.generator_llm, deps.ledger)
    skeptic = Skeptic(
        deps.backends,
        fetch,
        deps.verifier_llm,
        deps.ledger,
        generator_model=pa.models.generator,
        second_judge=deps.judge_llm,
        min_sources_for_verified=pa.min_sources_for_verified,
    )
    synthesizer = Synthesizer(
        deps.generator_llm, confidence_threshold=pb.confidence_threshold
    )
    conductor = Conductor(
        scout,
        scholar,
        skeptic,
        synthesizer=synthesizer,
        llm=deps.generator_llm,
        confidence_threshold=pb.confidence_threshold,
        max_refine_rounds=pb.max_refine_rounds,
    )

    await conductor.run_solution(state)

    if checkpoint_dir is not None:
        save_checkpoint(checkpoint_dir, state, chash)
    assert state.solution_report is not None  # conductor always assembles one
    return state.solution_report


async def run_specification(
    question_text: str,
    deps: Dependencies,
    *,
    config: Config | None = None,
    run_id: str | None = None,
    checkpoint_dir: str | None = None,
) -> Specification:
    """Execute one Phase γ run and return the gated build specification.

    Same cross-model α research as `run` (scout/scholar/skeptic) plus the proven
    β structuring step (synthesizer) and the `architect`, which structures the
    grounded solution space into a complete specification behind GATE γ. The
    synthesizer and architect use the generator family — structuring is not
    verification; the underlying claims were already verified cross-model by the
    skeptic, so the cross-model guarantee is preserved.
    """
    config = config or default_config()
    pa = config.phase_alpha
    pb = config.phase_beta
    pg = config.phase_gamma
    chash = config_hash(config)
    rid = run_id or make_run_id(question_text, chash, suffix=str(time.time_ns()))

    state = RunState(question=Question(raw=question_text, run_id=rid))
    state.log.append(
        f"runner: [gamma] run_id={rid} config_hash={chash[:12]} "
        f"generator={deps.generator_llm.model} verifier={deps.verifier_llm.model}"
    )

    fetch = WebFetchTool(deps.http_get, ledger=deps.ledger, run_id=rid)
    scout = Scout(deps.backends, llm=deps.generator_llm)
    scholar = Scholar(fetch, deps.generator_llm, deps.ledger)
    skeptic = Skeptic(
        deps.backends,
        fetch,
        deps.verifier_llm,
        deps.ledger,
        generator_model=pa.models.generator,
        second_judge=deps.judge_llm,
        min_sources_for_verified=pa.min_sources_for_verified,
    )
    synthesizer = Synthesizer(
        deps.generator_llm, confidence_threshold=pb.confidence_threshold
    )
    architect = Architect(
        deps.generator_llm,
        confidence_threshold=pg.confidence_threshold,
        derivation_tolerance=pg.derivation_tolerance,
    )
    conductor = Conductor(
        scout,
        scholar,
        skeptic,
        synthesizer=synthesizer,
        architect=architect,
        llm=deps.generator_llm,
        confidence_threshold=pg.confidence_threshold,
        max_refine_rounds=pg.max_refine_rounds,
        derivation_tolerance=pg.derivation_tolerance,
    )

    await conductor.run_specification(state)

    if checkpoint_dir is not None:
        save_checkpoint(checkpoint_dir, state, chash)
    assert state.specification is not None  # conductor always normalizes one
    return state.specification


# --- checkpointing (reproducibility / audit) ---------------------------------

def _claim_to_dict(c) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "status": c.status.value,
        "confidence": c.confidence,
        "quote": c.quote,
        "produced_by": c.produced_by,
        "model": c.model,
        "sources": [r.url_or_id for r in c.sources],
        "verification": [r.url_or_id for r in c.verification],
    }


def _report_to_dict(r: Report) -> dict:
    return {
        "run_id": r.run_id,
        "question": r.question,
        "body": r.body,
        "statement_to_claim": r.statement_to_claim,
        "gaps": r.gaps,
        "sources_used": r.sources_used,
    }


def _solution_report_to_dict(sr: SolutionReport) -> dict:
    return {
        "run_id": sr.run_id,
        "problem": sr.problem,
        "approaches": [
            {
                "id": a.id,
                "name": a.name,
                "grounding": a.grounding,
                "tradeoffs": a.tradeoffs,
                "produced_by": a.produced_by,
                "model": a.model,
            }
            for a in sr.approaches
        ],
        "gaps": sr.gaps,
        "claim_ids_used": sr.claim_ids_used,
    }


def _geometry_to_dict(node) -> dict:
    return {
        "kind": node.kind,
        "params": dict(node.params),
        "children": [_geometry_to_dict(c) for c in node.children],
    }


def _specification_to_dict(spec: Specification) -> dict:
    return {
        "run_id": spec.run_id,
        "idea": spec.idea,
        "approach_id": spec.approach_id,
        "quantities": [
            {
                "id": q.id,
                "name": q.name,
                "value": q.value,
                "unit": q.unit,
                "origin": q.origin.value,
                "grounding": list(q.grounding),
                "derivation": (
                    {"formula": q.derivation.formula, "inputs": list(q.derivation.inputs)}
                    if q.derivation
                    else None
                ),
                "rationale": q.rationale,
            }
            for q in spec.quantities
        ],
        "components": [
            {
                "id": c.id,
                "name": c.name,
                "geometry": _geometry_to_dict(c.geometry) if c.geometry else None,
                "quantity_ids": list(c.quantity_ids),
                "material_density": c.material_density,
            }
            for c in spec.components
        ],
        "bom": [
            {
                "id": b.id,
                "name": b.name,
                "role": b.role.value,
                "count": b.count,
                "component_id": b.component_id,
                "grounding": list(b.grounding),
                "domain": b.domain.value,
                "sourcing": (
                    {
                        "supplier": b.sourcing.supplier,
                        "part_number": b.sourcing.part_number,
                        "price_quantity_id": b.sourcing.price_quantity_id,
                        "grounding": list(b.sourcing.grounding),
                    }
                    if b.sourcing
                    else None
                ),
            }
            for b in spec.bom
        ],
        "steps": [
            {
                "id": s.id,
                "index": s.index,
                "action": s.action,
                "uses": list(s.uses),
                "inputs": list(s.inputs),
                "outputs": list(s.outputs),
                "check": s.check,
                "quantity_refs": list(s.quantity_refs),
                "tool": s.tool,
                "torque_quantity_id": s.torque_quantity_id,
            }
            for s in spec.steps
        ],
        "constraints": [
            {
                "id": k.id,
                "kind": k.kind,
                "left": k.left,
                "right": k.right,
                "reason": k.reason,
            }
            for k in spec.constraints
        ],
        "decisions": [
            {
                "id": d.id,
                "title": d.title,
                "choice": d.choice,
                "rationale": d.rationale,
                "informed_by": list(d.informed_by),
            }
            for d in spec.decisions
        ],
        "site": (
            {
                "available_space": list(spec.site.available_space)
                if spec.site.available_space else None,
                "requirements": [
                    {"id": d.id, "title": d.title, "choice": d.choice,
                     "rationale": d.rationale, "informed_by": list(d.informed_by)}
                    for d in spec.site.requirements
                ],
            }
            if spec.site
            else None
        ),
        "gaps": list(spec.gaps),
        "claim_ids_used": list(spec.claim_ids_used),
        "produced_by": spec.produced_by,
        "model": spec.model,
    }


def save_checkpoint(checkpoint_dir: str, state: RunState, cfg_hash: str) -> str:
    """Write a JSON checkpoint of the run. Returns the file path."""
    out_dir = Path(checkpoint_dir) / state.question.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": state.question.run_id,
        "config_hash": cfg_hash,
        "question": state.question.raw,
        "report": _report_to_dict(state.report) if state.report else None,
        "solution_report": (
            _solution_report_to_dict(state.solution_report)
            if state.solution_report
            else None
        ),
        "specification": (
            _specification_to_dict(state.specification)
            if state.specification
            else None
        ),
        "claims": [_claim_to_dict(c) for c in state.claims],
        "log": state.log,
    }
    path = out_dir / "checkpoint.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def load_checkpoint(path: str) -> dict:
    """Read a checkpoint back (for audit/inspection)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
