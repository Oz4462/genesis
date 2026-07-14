"""TechnologyReadinessLadder and TeacherMode (PLAN G1/G4).

Simple ladder: Idee -> Konzept -> Modell -> Simulation -> Pruefstand -> Prototyp -> etc.

TeacherMode: each step produces learning notes.

Honest: no auto promotion without evidence. Community evidence uses a local ledger
file when present — never invents replications.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReadinessLevel:
    level: str  # TRL1 .. TRL9
    name: str
    required_evidence: list[str]
    achieved: bool = False
    evidence: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


READINESS_LADDER: list[ReadinessLevel] = [
    ReadinessLevel("TRL1", "Basic principles observed", ["observation", "claim"]),
    ReadinessLevel("TRL2", "Technology concept formulated", ["concept", "frontier"]),
    ReadinessLevel("TRL3", "Proof of concept", ["model", "simulation", "gate"]),
    ReadinessLevel("TRL4", "Component validation in lab", ["prototype", "dfm", "test"]),
    ReadinessLevel("TRL5", "Component validation in relevant env", ["teststand", "reality_delta"]),
    ReadinessLevel("TRL6", "System prototype demo", ["assembly", "e2e", "package"]),
    ReadinessLevel("TRL7", "System prototype in operational env", ["field", "community"]),
    ReadinessLevel("TRL8", "System complete and qualified", ["cert", "regulatorik"]),
    ReadinessLevel("TRL9", "Actual system proven in operational env", ["production", "real_measurements"]),
]


def assess_readiness(package: dict | Any, gates: list[str] | None = None) -> ReadinessLevel:
    """Return highest achieved TRL with evidence derived from package + gates.

    Gaps list only the *next* missing requirements — not a perpetual "deferred" when
    early TRL is honestly achieved.
    """
    gates = gates or []
    pkg = package if isinstance(package, dict) else {}
    pkg_s = str(package)
    evidence: list[dict] = []
    achieved = "TRL1"
    evidence.append({"type": "baseline", "note": "package assessed"})

    if pkg.get("claims") or pkg.get("claim_ids") or "claim" in pkg_s.lower():
        achieved = "TRL2"
        evidence.append({"type": "claims", "present": True})
    if "simulation" in pkg_s.lower() or any("sim" in g.lower() for g in gates):
        achieved = "TRL3"
        evidence.append({"type": "gates", "passed": [g for g in gates if "sim" in g.lower()]})
    if pkg.get("cad_artifacts") or pkg.get("physics_ok") or "dfm" in pkg_s.lower():
        achieved = "TRL4"
        evidence.append({"type": "cad_or_dfm", "present": True})
    if any("delta" in g.lower() or "reality" in g.lower() for g in gates):
        achieved = "TRL5"
        evidence.append({"type": "reality_delta", "present": True})
    if pkg.get("assembly") or any("e2e" in g.lower() for g in gates) or pkg.get("bundle"):
        achieved = "TRL6"
        evidence.append({"type": "assembly_or_e2e", "present": True})
    if pkg.get("field_test") or pkg.get("community_replications"):
        achieved = "TRL7"
        evidence.append({"type": "field_or_community", "present": True})
    if pkg.get("certification") or any("cert" in g.lower() for g in gates):
        achieved = "TRL8"
        evidence.append({"type": "cert", "present": True})
    if pkg.get("production") or pkg.get("real_measurements"):
        achieved = "TRL9"
        evidence.append({"type": "production", "present": True})

    # Next-level gaps only
    order = [lvl.level for lvl in READINESS_LADDER]
    idx = order.index(achieved)
    next_gaps: list[str] = []
    if idx + 1 < len(READINESS_LADDER):
        nxt = READINESS_LADDER[idx + 1]
        next_gaps = [f"next {nxt.level} needs: {', '.join(nxt.required_evidence)}"]
    if achieved in ("TRL1", "TRL2", "TRL3") and not pkg.get("real_measurements"):
        next_gaps.append("no lab/field measurements attached to this package")

    for lvl in READINESS_LADDER:
        if lvl.level == achieved:
            return ReadinessLevel(
                level=lvl.level,
                name=lvl.name,
                required_evidence=list(lvl.required_evidence),
                achieved=True,
                evidence=evidence,
                gaps=next_gaps,
            )
    return READINESS_LADDER[0]


def teacher_notes(step: str, deltas: list[str]) -> dict:
    """TeacherMode: produce learning notes for step."""
    return {
        "step": step,
        "insights": deltas,
        "next_action": "apply to frontier or reality",
        "quelle": "learning_integrator + teacher_mode",
    }


class TeacherMode:
    """TeacherMode: each build/experiment/simulation step produces learning notes for the human.
    Makes the output make the human smarter (Exoskelett from HORIZON).
    """

    def __init__(self):
        self.notes: list[dict] = []

    def record(self, step: str, deltas: list[str]) -> dict:
        note = teacher_notes(step, deltas)
        self.notes.append(note)
        return note

    def apply(self, package: dict) -> dict:
        """Apply teacher notes to package for richer output."""
        package = dict(package) if isinstance(package, dict) else {"data": str(package)}
        package["teacher_notes"] = self.notes or [
            {"step": "none", "insights": ["no learning recorded"]}
        ]
        return package


def _community_ledger_path() -> Path:
    env = os.environ.get("GENESIS_COMMUNITY_LEDGER", "").strip()
    if env:
        return Path(env)
    return Path("out/community_ledger.json")


def community_evidence(build_report: dict) -> dict:
    """CommunityEvidence from build_report + optional local ledger file.

    Honesty:
    - Never invent replications or a fake 0.5 score.
    - If no ledger and no report counts → score 0.0 and explicit gaps.
    - Ledger format: ``{"replications": int, "field_failures": [...], "entries": [...]}``
    """
    report = build_report if isinstance(build_report, dict) else {}
    replications = int(report.get("replications") or 0)
    field_failures = list(report.get("field_failures") or [])
    gaps: list[str] = []
    quelle = "build_report"

    ledger_path = _community_ledger_path()
    if ledger_path.is_file():
        try:
            data = json.loads(ledger_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                replications = max(replications, int(data.get("replications") or 0))
                field_failures = list(data.get("field_failures") or field_failures)
                quelle = f"build_report+{ledger_path}"
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            gaps.append(f"community ledger unreadable: {exc}")
    else:
        gaps.append(
            f"no community ledger at {ledger_path} — create JSON with "
            f'{{"replications": N, "field_failures": []}} to record field feedback'
        )

    # Score in [0, 1] from evidence only — 0 when nothing recorded
    if replications <= 0 and not field_failures:
        score = 0.0
        if not gaps:
            gaps.append("no replications or field_failures recorded")
    else:
        # diminishing returns: 1 rep → 0.35, 3 → ~0.7, 10 → ~0.95
        score = min(0.95, 0.25 + 0.15 * replications)
        if field_failures:
            score = max(0.0, score - 0.05 * min(len(field_failures), 6))

    # trustcore remains optional companion — gap only if score claims high maturity
    if score >= 0.5:
        gaps.append("trustcore conformal batch scoring optional — install companion for FDR")

    return {
        "replications": replications,
        "field_failures": field_failures,
        "community_score": round(score, 4),
        "gaps": gaps,
        "quelle": quelle,
    }
