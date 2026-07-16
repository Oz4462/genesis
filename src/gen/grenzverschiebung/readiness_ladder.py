"""TechnologyReadinessLadder and TeacherMode (PLAN G1/G4).

Simple ladder: Idee -> Konzept -> Modell -> Simulation -> Pruefstand -> Prototyp -> etc.

TeacherMode: each step produces learning notes.

Honest community evidence:
- GENESIS / Grok / Claude fetch public literature (OpenAlex CC0) — **user supplies no data**.
- Optional local cache (agent-written) may enrich findings; never required from the human.
- Never invent replications or fake community scores.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


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
    if pkg.get("field_test") or pkg.get("community_replications") or pkg.get("literature_hits"):
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
        next_gaps.append(
            "no lab/field measurements in package yet "
            "(agent discovers public sources; private lab data is not user-required for public TRL steps)"
        )

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


def _community_cache_path() -> Path:
    """Optional agent-written cache (not a user data entry form)."""
    env = os.environ.get("GENESIS_COMMUNITY_LEDGER", "").strip()
    if env:
        return Path(env)
    return Path("out/community_ledger.json")


def _live_community_enabled() -> bool:
    """Live OpenAlex when agents enable it — never blocks offline demos/smoke.

    On: GENESIS_COMMUNITY_LIVE=1 or GENESIS_ALLOW_LIVE=1 (Grok/Claude live sessions).
    Off: default product path (deterministic, no network).
    Tests inject ``fetch_fn`` which bypasses this gate.
    """
    flag = os.environ.get("GENESIS_COMMUNITY_LIVE", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    if os.environ.get("GENESIS_OFFLINE", "").strip().lower() in ("1", "true", "yes"):
        return False
    allow = os.environ.get("GENESIS_ALLOW_LIVE", "").strip().lower()
    return allow in ("1", "true", "yes", "on")


def _query_from_report(report: dict) -> str:
    """Build a literature query from package context — no human-filled form."""
    for key in ("idea", "query", "topic", "raw_dream", "brief", "question"):
        val = report.get(key)
        if isinstance(val, str) and val.strip():
            return " ".join(val.strip().split())[:200]
    gates = report.get("gates")
    if isinstance(gates, list) and gates:
        return " ".join(str(g) for g in gates[:6]) + " engineering validation"
    claims = report.get("claims")
    if isinstance(claims, int) and claims > 0:
        return "additive manufacturing structural validation community replication"
    if isinstance(claims, list) and claims:
        return " ".join(str(c) for c in claims[:3])[:200]
    return "robotics mechatronics experimental validation community replication"


def discover_community_literature(
    query: str,
    *,
    max_hits: int = 8,
    timeout: float = 8.0,
    fetch_fn: Callable[..., list[dict]] | None = None,
) -> list[dict]:
    """Agent discovery of public community literature via OpenAlex (CC0, no API key).

    Returns hit dicts with openalex_id, title, year, cited_by, doi.
    Injectable ``fetch_fn`` for offline tests. Never invents ids.
    """
    if fetch_fn is not None:
        return list(fetch_fn(query, max_hits=max_hits) or [])

    url = (
        "https://api.openalex.org/works?per-page="
        + str(max(1, max_hits))
        + "&search="
        + urllib.parse.quote_plus(query)
        + "&mailto="
        + urllib.parse.quote_plus("genesis@local")
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GENESIS/0.1 (agent-sourced community evidence; mailto:genesis@local)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    hits: list[dict] = []
    for work in data.get("results") or []:
        work_id = (work.get("id") or "").strip()
        if not work_id:
            continue
        title = work.get("title")
        title = " ".join(title.split()) if isinstance(title, str) and title.strip() else None
        doi = work.get("doi") if isinstance(work.get("doi"), str) else None
        cited = work.get("cited_by_count")
        hits.append(
            {
                "openalex_id": work_id,
                "title": title,
                "year": work.get("publication_year"),
                "cited_by": cited if isinstance(cited, int) else None,
                "doi": doi,
            }
        )
    return hits


def community_evidence(
    build_report: dict,
    *,
    live: bool | None = None,
    fetch_fn: Callable[..., list[dict]] | None = None,
) -> dict:
    """CommunityEvidence — **agent-sourced**, not user-supplied.

    Data sources (priority):
    1. Live OpenAlex literature discovery (Grok/Claude/GENESIS fetch public CC0 graph)
    2. Optional agent cache at GENESIS_COMMUNITY_LEDGER / out/community_ledger.json
       (written by agents after discovery — **never** a human homework form)
    3. Counts already attached on build_report by upstream agents

    Honesty:
    - Never invent replications or a fake mid-score.
    - Literature hits ≠ private lab replications; labeled separately.
    - Gaps never tell the user to hand-write JSON.
    """
    report = build_report if isinstance(build_report, dict) else {}
    replications = int(report.get("replications") or 0)
    field_failures = list(report.get("field_failures") or [])
    literature_hits: list[dict] = list(report.get("literature_hits") or [])
    gaps: list[str] = []
    sources: list[str] = []
    if replications or field_failures or literature_hits:
        sources.append("build_report")

    # Optional agent cache (not user-required)
    cache_path = _community_cache_path()
    if cache_path.is_file():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                replications = max(replications, int(data.get("replications") or 0))
                field_failures = list(data.get("field_failures") or field_failures)
                cached_hits = data.get("literature_hits") or data.get("entries") or []
                if isinstance(cached_hits, list) and cached_hits and not literature_hits:
                    literature_hits = [h for h in cached_hits if isinstance(h, dict)]
                sources.append(f"agent_cache:{cache_path}")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            gaps.append(f"agent community cache unreadable: {exc}")

    # Primary path: agent live discovery (OpenAlex)
    do_live = _live_community_enabled() if live is None else live
    if fetch_fn is not None:
        do_live = True
    query = _query_from_report(report)
    live_error: str | None = None
    if do_live and not literature_hits:
        try:
            literature_hits = discover_community_literature(
                query, max_hits=8, fetch_fn=fetch_fn
            )
            if literature_hits:
                sources.append("openalex:live")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            live_error = f"{type(exc).__name__}: {exc}"
            gaps.append(
                f"agent OpenAlex discovery failed ({live_error}) — "
                "retry with network; user need not supply data"
            )
        except Exception as exc:
            live_error = f"{type(exc).__name__}: {exc}"
            gaps.append(
                f"agent community discovery error ({live_error}) — "
                "user need not supply data"
            )

    n_lit = len(literature_hits)
    # Literature community proxy (public papers) + any recorded field replications
    community_n = replications + n_lit

    if community_n <= 0 and not field_failures:
        score = 0.0
        if not any("discovery" in g or "OpenAlex" in g for g in gaps):
            if not do_live:
                gaps.append(
                    "community discovery offline (GENESIS_COMMUNITY_LIVE=0 / GENESIS_OFFLINE) — "
                    "enable live for agent OpenAlex fetch; user supplies nothing"
                )
            else:
                gaps.append(
                    "agent found no public literature hits for this query yet — "
                    "not a user data task"
                )
    else:
        # diminishing: 1 hit → ~0.35, 3 → ~0.7, 10 → ~0.95
        score = min(0.95, 0.25 + 0.15 * community_n)
        if field_failures:
            score = max(0.0, score - 0.05 * min(len(field_failures), 6))
        # Literature-only: honest cap — public papers ≠ operational field proof
        if replications <= 0 and n_lit > 0:
            score = min(score, 0.55)
            gaps.append(
                "literature community found (OpenAlex); field lab replications still open "
                "(private lab measurements cannot be invented — agent uses public sources only)"
            )

    if score >= 0.5:
        gaps.append(
            "trustcore conformal batch scoring optional companion — not user-supplied data"
        )

    quelle = "+".join(sources) if sources else "none"
    return {
        "replications": replications,
        "literature_hits": literature_hits[:12],
        "literature_count": n_lit,
        "field_failures": field_failures,
        "community_score": round(score, 4),
        "query": query,
        "gaps": gaps,
        "quelle": quelle,
        "agent_sourced": True,
        "user_data_required": False,
        "live_error": live_error,
    }


# Back-compat alias used in older docs/tests
_community_ledger_path = _community_cache_path
