"""Phase φ end-to-end — run_divergence over the REAL chain (scout->scholar->skeptic->forge).

Deterministic scripted world (no network, no Ollama), mirroring the α-acceptance harness.
Proves the full φ phase: research establishes a VERIFIED claim, forge opens the spark into
a possibility anchored to it, and the resulting divergence passes GATE φ.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from gen.core.state import SourceCandidate
from gen.ledger.store import InMemoryLedgerStore
from gen.llm.base import ScriptedLLM
from gen.runner import Dependencies, load_checkpoint, run_divergence
from gen.verification import gate_phi

SUBJECT = "standard gravity equals 9.80665 meters per second squared"
SPARK = "etwas das eine konstante Beschleunigung als Referenz nutzt"
DOC = "https://doc.example/grav"
INDEP = {
    "https://i.example/grav-1": "SUPPORT independent corroboration one",
    "https://i.example/grav-2": "SUPPORT independent corroboration two",
}


class _Backend:
    name = "scripted"

    async def search(self, query, limit):
        urls = list(INDEP) if query.strip() == SUBJECT else [DOC]
        return [SourceCandidate(url_or_id=u, title=None, backend=self.name, relevance_note="x")
                for u in urls][:limit]


def _http():
    from gen.tools.http import HttpResponse
    content = {DOC: f"According to the documentation: {SUBJECT} This is stated plainly.", **INDEP}

    async def _get(url):
        return HttpResponse(status=200, body=content.get(url, ""), final_url=url)

    return _get


def _gen(system, user):
    if "sub-questions" in system or "SEARCH QUERIES" in system:
        return json.dumps([SUBJECT])
    if "extract ATOMIC" in system:
        return json.dumps([{"text": SUBJECT, "quote": SUBJECT}]) if SUBJECT.lower() in user.lower() else "[]"
    if "POSSIBLE DIRECTIONS" in system:  # forge call: anchor in the cited verified claim id
        cid = None
        if "VERIFIED CLAIMS:" in user:
            line = user.split("VERIFIED CLAIMS:", 1)[1].strip().splitlines()[0]
            cid = line.split(": ", 1)[0].strip()
        if not cid:
            return "[]"
        return json.dumps([{
            "statement": "Schwingungsisolierung gegen die Standard-g-Referenz auslegen",
            "mechanism": "konstante Standardbeschleunigung als Referenzgröße",
            "grounding": [cid],
        }])
    return "[]"


def _ver(system, user):
    if "SUPPORT" in user:
        return json.dumps({"relation": "supports", "confidence": 0.85})
    return json.dumps({"relation": "irrelevant", "confidence": 0.0})


def test_run_divergence_end_to_end():
    deps = Dependencies(
        backends=[_Backend()],
        http_get=_http(),
        generator_llm=ScriptedLLM("claude-opus-4-8", _gen),
        verifier_llm=ScriptedLLM("gpt-4o", _ver),
        ledger=InMemoryLedgerStore(),
    )
    with tempfile.TemporaryDirectory() as tmp:
        div = asyncio.run(run_divergence(SPARK, deps, run_id="phi1", checkpoint_dir=tmp))
        assert div is not None
        assert len(div.possibilities) == 1, div
        assert div.grounded_sample is True
        # every possibility is anchored to a VERIFIED claim, and the gate agrees
        claims = asyncio.run(deps.ledger.get_claims("phi1"))
        assert gate_phi(div, claims).passed
        verified_ids = {c.id for c in claims}
        assert div.possibilities[0].grounding[0] in verified_ids
        # GATE φ actually ran INSIDE the pipeline (not just in this test) — proven via the log
        ckpt = load_checkpoint(str(Path(tmp) / "phi1" / "checkpoint.json"))
        assert any("gate_phi passed=True" in line for line in ckpt["log"])
