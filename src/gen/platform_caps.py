"""Platform Caps surface matrix (Phase E S1) + helpers for bundle/CLI honesty.

Caps: ProofPackage, ReadinessLadder, TeacherMode, CommunityEvidence.
This module answers: which CLI modes surface which caps, and extracts a
JSON-safe caps snapshot from live run objects (Assessment / LUMEN / package).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


#: S1 — declarative matrix (evidence: code paths as of 2026-07-15).
#: present=True means the mode *can* attach the cap when the path runs green.
CAPS_SURFACE_MATRIX: dict[str, dict[str, Any]] = {
    "assess": {
        "proof_package": True,
        "readiness": True,
        "teacher": True,
        "community": True,
        "path": "pipeline.assess_specification → grenz proof/readiness/teacher/community",
    },
    "dream": {
        "proof_package": False,
        "readiness": False,
        "teacher": True,
        "community": True,
        "path": "lumencrucible.process_dream (teacher + community; no proof package dir)",
    },
    "horizon-full": {
        "proof_package": False,
        "readiness": False,
        "teacher": True,
        "community": True,
        "path": "horizon_full → process_dream (LUMEN surface + community_score)",
    },
    "realize": {
        "proof_package": True,
        "readiness": True,
        "teacher": True,
        "community": True,
        "path": "integrator.build_full_mini / realize (manifest caps)",
    },
    "bundle": {
        "proof_package": True,
        "readiness": True,
        "teacher": True,
        "community": True,
        "path": "bundle.emit_bundle ← Assessment caps (S4 MANIFEST fields)",
    },
    "invent": {
        "proof_package": False,
        "readiness": False,
        "teacher": False,
        "community": False,
        "path": "inventor loop + δ-physics; caps not primary surface",
    },
    "research": {
        "proof_package": False,
        "readiness": False,
        "teacher": False,
        "community": False,
        "path": "α research report; no platform caps",
    },
    "structural": {
        "proof_package": False,
        "readiness": False,
        "teacher": False,
        "community": False,
        "path": "structural demo; sim gates only",
    },
    "humanoid": {
        "proof_package": True,
        "readiness": True,
        "teacher": True,
        "community": True,
        "path": "humanoid CLI → LUMEN + assess-style caps when wired",
    },
    "sources": {
        "proof_package": False,
        "readiness": False,
        "teacher": False,
        "community": False,
        "path": "source catalog only",
    },
}


@dataclass
class CapsSnapshot:
    """JSON-safe caps presence for a single run/artifact."""

    proof_package: str | None = None
    readiness_level: str | None = None
    teacher_present: bool = False
    community_score: float | None = None
    community_agent_sourced: bool | None = None
    user_data_required: bool | None = None
    present: dict[str, bool] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    quelle: str = "gen.platform_caps.extract_caps_snapshot"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_caps_snapshot(
    *,
    assessment: Any = None,
    lumen: dict | None = None,
    manifest: dict | None = None,
) -> CapsSnapshot:
    """Pull caps from Assessment, LUMEN result, and/or package manifest."""
    gaps: list[str] = []
    proof = None
    readiness = None
    teacher = False
    community_score = None
    agent_sourced = None
    user_req = None

    if assessment is not None:
        proof = getattr(assessment, "proof_package", None)
        readiness = getattr(assessment, "readiness_level", None)
        tn = getattr(assessment, "teacher_notes", None)
        teacher = bool(tn)
        ce = getattr(assessment, "community_evidence", None) or {}
        if isinstance(ce, dict):
            community_score = ce.get("community_score")
            agent_sourced = ce.get("agent_sourced")
            user_req = ce.get("user_data_required")

    if lumen:
        if lumen.get("teacher_notes"):
            teacher = True
        ce = lumen.get("community_evidence") or {}
        if isinstance(ce, dict):
            community_score = ce.get("community_score", community_score)
            agent_sourced = ce.get("agent_sourced", agent_sourced)
            user_req = ce.get("user_data_required", user_req)
        ls = lumen.get("lumen_surface") or {}
        if isinstance(ls, dict) and community_score is None:
            community_score = ls.get("community_score")

    if manifest:
        proof = manifest.get("proof_package", proof)
        readiness = manifest.get("readiness_level", readiness)
        if manifest.get("teacher_notes"):
            teacher = True
        ce = manifest.get("community_evidence") or {}
        if isinstance(ce, dict):
            community_score = ce.get("community_score", community_score)
            agent_sourced = ce.get("agent_sourced", agent_sourced)
            user_req = ce.get("user_data_required", user_req)

    present = {
        "proof_package": bool(proof),
        "readiness": bool(readiness),
        "teacher": teacher,
        "community": community_score is not None,
    }
    if not present["proof_package"]:
        gaps.append("proof_package absent")
    if not present["readiness"]:
        gaps.append("readiness_level absent")
    if not present["teacher"]:
        gaps.append("teacher_notes absent")
    if not present["community"]:
        gaps.append("community_evidence absent")

    return CapsSnapshot(
        proof_package=str(proof) if proof else None,
        readiness_level=str(readiness) if readiness else None,
        teacher_present=teacher,
        community_score=float(community_score) if community_score is not None else None,
        community_agent_sourced=agent_sourced,
        user_data_required=user_req,
        present=present,
        gaps=gaps,
    )


def caps_matrix_report() -> dict[str, Any]:
    """S1: full matrix for operators/CLI."""
    rows = []
    for mode, info in CAPS_SURFACE_MATRIX.items():
        rows.append(
            {
                "mode": mode,
                "proof_package": info["proof_package"],
                "readiness": info["readiness"],
                "teacher": info["teacher"],
                "community": info["community"],
                "path": info["path"],
            }
        )
    n_full = sum(
        1
        for r in rows
        if r["proof_package"] and r["readiness"] and r["teacher"] and r["community"]
    )
    return {
        "schema": "genesis-caps-matrix-v1",
        "rows": rows,
        "modes_with_full_caps": n_full,
        "total_modes": len(rows),
        "quelle": "gen.platform_caps.CAPS_SURFACE_MATRIX",
    }


def caps_matrix_text() -> str:
    rep = caps_matrix_report()
    lines = [
        "═══ GENESIS PLATFORM CAPS MATRIX ═══",
        "",
        f"{'mode':16} proof  ready  teach  comm  path",
        "-" * 72,
    ]
    for r in rep["rows"]:
        lines.append(
            f"{r['mode']:16} "
            f"{'Y' if r['proof_package'] else '·':5}  "
            f"{'Y' if r['readiness'] else '·':5}  "
            f"{'Y' if r['teacher'] else '·':5}  "
            f"{'Y' if r['community'] else '·':5}  "
            f"{r['path'][:40]}"
        )
    lines += [
        "",
        f"full-caps modes: {rep['modes_with_full_caps']}/{rep['total_modes']}",
        "Caps: ProofPackage | ReadinessLadder | TeacherMode | CommunityEvidence",
    ]
    return "\n".join(lines)


__all__ = [
    "CAPS_SURFACE_MATRIX",
    "CapsSnapshot",
    "extract_caps_snapshot",
    "caps_matrix_report",
    "caps_matrix_text",
]
