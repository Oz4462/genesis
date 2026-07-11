"""TechnologyReadinessLadder and TeacherMode basics (PLAN G1/G4).

Simple ladder: Idee -> Konzept -> Modell -> Simulation -> Pruefstand -> Prototyp -> etc.

TeacherMode: each step produces learning notes.

Honest: no auto promotion without evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Simple assessor. Returns highest achieved level with evidence.

    Uses package contents + passed gates.
    """
    gates = gates or []
    achieved = "TRL1"
    evidence = []
    gaps = ["real operational data deferred"]

    if package.get("claims"):
        achieved = "TRL2"
    if "simulation" in str(package) or any("sim" in g for g in gates):
        achieved = "TRL3"
    if package.get("cad_artifacts") or "dfm" in str(package):
        achieved = "TRL4"
    if any("delta" in g or "reality" in g for g in gates):
        achieved = "TRL5"
    if package.get("assembly") or "e2e" in str(package):
        achieved = "TRL6"

    for lvl in READINESS_LADDER:
        if lvl.level == achieved:
            lvl.achieved = True
            lvl.evidence = evidence or [{"type": "gates", "passed": gates}]
            lvl.gaps = gaps
            return lvl

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
        package["teacher_notes"] = self.notes or [{"step": "none", "insights": ["no learning recorded"]}]
        return package


def community_evidence(build_report: dict) -> dict:
    """Basic CommunityEvidence: simulate community replication/field feedback.
    Honest: no real community data yet, marks as gap.
    """
    return {
        "replications": build_report.get("replications", 0),
        "field_failures": build_report.get("field_failures", []),
        "community_score": 0.5,  # placeholder
        "gaps": ["real community data deferred", "trustcore integration pending"],
        "quelle": "basic community evidence stub per PLAN G5",
    }

