"""Offline CLI helpers for PRODUCT_WIRE surface (REWORK 2026-07-11).

  * Phase χ frontier map (``build_frontier_map`` + ``gate_chi``)
  * Full Fach-Pipeline family first-stone mappers (architekt → … → wirtschaft)

Pure, LLM-free, demo-friendly. CLI modes import formatters from here so the
wiring is testable without argparse.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from .core.state import (
    Claim,
    ClaimStatus,
    Question,
    Report,
    RunState,
    SourceRef,
)
from .frontier import build_frontier_map
from .pipelines.architekt import map_to_system_concept
from .pipelines.designer import DesignerSpec, map_to_designer_spec
from .pipelines.elektriker import map_to_elektriker_spec
from .pipelines.fertigungs import map_to_fertigungs_spec
from .pipelines.ingenieur import map_to_ingenieur_spec
from .pipelines.physiker import map_to_physiker_spec
from .pipelines.regulatorik import map_to_regulatorik_spec
from .pipelines.software import map_to_software_spec
from .pipelines.techniker import map_to_techniker_spec
from .pipelines.wirtschaft import WirtschaftSpec, map_to_wirtschaft_spec
from .verification.gates import gate_chi

#: Ordered first-stone Fach-Pipeline names (CLI modes + ``fach`` dispatcher).
FACH_PIPELINE_NAMES: tuple[str, ...] = (
    "architekt",
    "ingenieur",
    "physiker",
    "techniker",
    "elektriker",
    "fertigungs",
    "regulatorik",
    "software",
    "designer",
    "wirtschaft",
)


def _src(url: str) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True)


def demo_frontier_state(*, run_id: str = "demo-frontier") -> RunState:
    """Minimal RunState that exercises χ: one VERIFIED fact + one real gap."""
    verified = Claim(
        id="c_verified",
        text="Steel density is about 7850 kg/m3.",
        sources=[_src("https://example.test/steel")],
        status=ClaimStatus.VERIFIED,
        confidence=0.95,
    )
    unsupported = Claim(
        id="c_open",
        text="Long-term creep under this cyclic load is unknown.",
        sources=[_src("https://example.test/gap")],
        status=ClaimStatus.UNSUPPORTED,
        confidence=0.0,
    )
    gap = "fatigue life under reverse bending not yet measured"
    report = Report(
        run_id=run_id,
        question="bracket durability",
        body=verified.text,
        statement_to_claim={verified.text: verified.id},
        gaps=[gap],
    )
    state = RunState(question=Question(raw="bracket durability", run_id=run_id))
    state.claims = [verified, unsupported]
    state.report = report
    return state


@dataclass(frozen=True)
class FrontierCliResult:
    """Honest χ CLI payload — map + gate, never a fabricated frontier."""

    n_known: int
    n_edges: int
    gate_passed: bool
    gate_failures: tuple[str, ...]
    known_labels: tuple[str, ...]
    edge_questions: tuple[str, ...]


def run_frontier_cli(
    state: RunState | None = None,
    *,
    confidence_threshold: float = 0.7,
) -> FrontierCliResult:
    """Build + gate a frontier map. Deterministic, offline."""
    st = state if state is not None else demo_frontier_state()
    fmap = build_frontier_map(st, confidence_threshold=confidence_threshold)
    gate = gate_chi(st, fmap, confidence_threshold=confidence_threshold)
    st.frontier_map = fmap
    return FrontierCliResult(
        n_known=len(fmap.known_regions),
        n_edges=len(fmap.frontier_edges),
        gate_passed=gate.passed,
        gate_failures=tuple(f.code for f in gate.failures),
        known_labels=tuple(r.label for r in fmap.known_regions),
        edge_questions=tuple(e.question for e in fmap.frontier_edges),
    )


def format_frontier(result: FrontierCliResult) -> str:
    lines = [
        "GENESIS — Phase χ: Frontier-Karte (HORIZON §2C)",
        "=" * 64,
        f"Bekannte Regionen: {result.n_known}",
    ]
    for lab in result.known_labels:
        lines.append(f"  · {lab}")
    lines.append(f"Frontier-Kanten (geerdete Lücken): {result.n_edges}")
    for q in result.edge_questions:
        lines.append(f"  · {q}")
    status = "PASS" if result.gate_passed else "FAIL"
    lines.append(f"GATE χ: {status}")
    if result.gate_failures:
        lines.append(f"  failures: {', '.join(result.gate_failures)}")
    lines.append(
        "Hinweis: χ erfindet keine Lücken und keine Fakten — nur Synthesis "
        "aus report/solution/spec Gaps + Claims (reproduzierbar, LLM-frei)."
    )
    lines.append("=" * 64)
    return "\n".join(lines)


def _short(val: Any, n: int = 100) -> str:
    s = str(val).replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def format_pipeline_spec(name: str, spec: Any) -> str:
    """Generic honest renderer for any first-stone Fach-Pipeline dataclass."""
    lines = [
        f"GENESIS — Fach-Pipeline: {name}",
        "=" * 64,
    ]
    if not is_dataclass(spec):
        lines.append(_short(spec, 400))
        lines.append("=" * 64)
        return "\n".join(lines)
    data = asdict(spec)
    for key, val in data.items():
        if key in ("run_id",):
            continue
        if isinstance(val, list):
            lines.append(f"{key}: {len(val)}")
            for item in val[:6]:
                if isinstance(item, dict):
                    label = (
                        item.get("name")
                        or item.get("label")
                        or item.get("id")
                        or item.get("beschreibung")
                        or next(iter(item.values()), "")
                    )
                    lines.append(f"  · {_short(label, 90)}")
                else:
                    lines.append(f"  · {_short(item, 90)}")
            if len(val) > 6:
                lines.append(f"  · … +{len(val) - 6} more")
        elif isinstance(val, dict):
            lines.append(f"{key}:")
            for k, v in list(val.items())[:8]:
                lines.append(f"  {k}: {_short(v, 80)}")
        else:
            lines.append(f"{key}: {_short(val, 200)}")
    lines.append(
        "Gate: first-stone Mapper — ehrliche Lücken, keine stillen Defaults; "
        "keine Fach-Analyse als „vollständig“ behaupten."
    )
    lines.append("=" * 64)
    return "\n".join(lines)


def run_fach_pipeline(name: str, idea: str, *, run_id: str | None = None) -> Any:
    """Run one first-stone Fach-Pipeline by name (deterministic, offline).

    Raises:
        ValueError: unknown pipeline name or empty idea.
    """
    key = name.strip().lower()
    if key not in FACH_PIPELINE_NAMES:
        raise ValueError(
            f"unknown fach pipeline {name!r}; "
            f"expected one of {', '.join(FACH_PIPELINE_NAMES)}"
        )
    if not idea.strip():
        raise ValueError("idea must be non-empty")

    rid = run_id or f"cli-{key}"
    concept = map_to_system_concept(idea, run_id=rid)
    if key == "architekt":
        return concept
    ingenieur = map_to_ingenieur_spec(concept, run_id=rid)
    if key == "ingenieur":
        return ingenieur
    if key == "physiker":
        return map_to_physiker_spec(concept, ingenieur, run_id=rid)
    if key == "techniker":
        phys = map_to_physiker_spec(concept, ingenieur, run_id=rid)
        return map_to_techniker_spec(concept, ingenieur, phys, run_id=rid)
    if key == "elektriker":
        return map_to_elektriker_spec(concept, ingenieur, run_id=rid)
    if key == "fertigungs":
        return map_to_fertigungs_spec(concept, ingenieur, run_id=rid)
    if key == "regulatorik":
        return map_to_regulatorik_spec(concept, ingenieur, run_id=rid)
    if key == "software":
        return map_to_software_spec(concept, ingenieur, run_id=rid)
    if key == "designer":
        return map_to_designer_spec(concept, ingenieur, run_id=rid)
    # wirtschaft
    return map_to_wirtschaft_spec(concept, ingenieur, run_id=rid)


def run_fach_family(idea: str, *, run_id: str | None = None) -> dict[str, Any]:
    """Run all first-stone Fach-Pipelines; return name → spec dict."""
    return {name: run_fach_pipeline(name, idea, run_id=run_id) for name in FACH_PIPELINE_NAMES}


def format_fach_family(results: dict[str, Any]) -> str:
    lines = [
        "GENESIS — Fach-Pipeline family (all first stones)",
        "=" * 64,
        f"pipelines: {len(results)}",
    ]
    for name, spec in results.items():
        summary = getattr(spec, "zusammenfassung", None) or getattr(
            spec, "source_idea", type(spec).__name__
        )
        lines.append(f"  · {name}: {_short(summary, 100)}")
    lines.append(
        "Hinweis: jeder Stein ist deterministisch und ehrlich unvollständig — "
        "Lücken bleiben sichtbar; kein live Wissensbasis-Zwang."
    )
    lines.append("=" * 64)
    return "\n".join(lines)


def run_designer_cli(idea: str, *, run_id: str | None = None) -> DesignerSpec:
    """Architekt → Ingenieur → Designer first-stone chain (deterministic)."""
    return run_fach_pipeline("designer", idea, run_id=run_id)


def format_designer(spec: DesignerSpec) -> str:
    return format_pipeline_spec("Designer (PLAN §4.6)", spec)


def run_wirtschaft_cli(idea: str, *, run_id: str | None = None) -> WirtschaftSpec:
    """Architekt → Ingenieur → Wirtschaft first-stone chain (deterministic)."""
    return run_fach_pipeline("wirtschaft", idea, run_id=run_id)


def format_wirtschaft(spec: WirtschaftSpec) -> str:
    return format_pipeline_spec("Wirtschaft (PLAN §4)", spec)


def research_promotion_stage(art: Any) -> str:
    """Autonomous epistemic stage for a math-research artifact (never ESTABLISHED alone)."""
    from .research_promotion import autonomous_stage, is_anchor

    stage = autonomous_stage(art)
    anchor = is_anchor(stage)
    return (
        f"Promotion (autonomous): {stage}"
        + (" — reusable ANCHOR" if anchor else " — ESTABLISHED requires human SignOff")
    )


__all__ = [
    "FACH_PIPELINE_NAMES",
    "FrontierCliResult",
    "demo_frontier_state",
    "run_frontier_cli",
    "format_frontier",
    "run_fach_pipeline",
    "run_fach_family",
    "format_pipeline_spec",
    "format_fach_family",
    "run_designer_cli",
    "format_designer",
    "run_wirtschaft_cli",
    "format_wirtschaft",
    "research_promotion_stage",
]
