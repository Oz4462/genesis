"""Live-wiring test (Phase L1): pipeline -> verified-facts deposit -> signed audit.

Runs the REAL pipeline in a scripted class-A world (a verifiable claim), then checks
the opt-in integration: the verified claim is deposited into the memory library and a
tamper-evident audit envelope is produced and verifies. Offline (ScriptedLLM), no
network, no Ollama. Skips without the `verify` extra (trust-core).
"""

from __future__ import annotations

import asyncio
import hashlib
import json

import numpy as np
import pytest

# Dotted on purpose: the PyPI 'trust-core' namesake ships no `receipts` — a bare
# importorskip("trust_core") would pass there and turn collection into an ERROR.
pytest.importorskip("trust_core.receipts.keystore")

from gen.core.state import SourceCandidate  # noqa: E402
from gen.integration import audited_run  # noqa: E402
from gen.ledger.store import InMemoryLedgerStore  # noqa: E402
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.memory import VerifiedFactsLibrary  # noqa: E402
from gen.runner import Dependencies  # noqa: E402
from trust_core.receipts.keystore import KeyStore  # noqa: E402
from gen.audit import verify_audit  # noqa: E402

SUBJECT = "standard gravity is 9.80665 meters per second squared"
QUESTION = "What is the value of standard gravity?"
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
        return json.dumps([QUESTION])
    if "extract ATOMIC" in system:
        return json.dumps([{"text": SUBJECT, "quote": SUBJECT}]) if SUBJECT.lower() in user.lower() else "[]"
    return "[]"


def _ver(system, user):
    if "SUPPORT" in user:
        return json.dumps({"relation": "supports", "confidence": 0.85})
    return json.dumps({"relation": "irrelevant", "confidence": 0.0})


def _embedder():
    def embed(text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode()).digest()
        return np.frombuffer(h[:32], dtype=np.uint8).astype(np.float64)
    return embed


def _deps():
    return Dependencies(
        backends=[_Backend()],
        http_get=_http(),
        generator_llm=ScriptedLLM("claude-opus-4-8", _gen),
        verifier_llm=ScriptedLLM("gpt-4o", _ver),
        ledger=InMemoryLedgerStore(),
    )


def test_audited_run_deposits_and_signs():
    ks = KeyStore()
    key = ks.generate(scope="genesis-audit").key_id
    lib = VerifiedFactsLibrary(_embedder(), alpha=0.1)

    res = asyncio.run(audited_run(
        QUESTION, _deps(), created_at="2026-06-14T00:00:00+00:00",
        run_id="itest", library=lib, keystore=ks, audit_key_id=key,
    ))

    # pipeline produced a report and verified the claim
    assert res.report is not None
    assert res.n_remembered == 1, "the VERIFIED claim should be deposited"
    assert res.audit_record.n_verified == 1

    # audit envelope verifies and round-trips
    back = verify_audit(res.audit, ks)
    assert back == res.audit_record

    # the deposited fact is recallable after calibration
    lib.add_calibration([1e-6] * 40)
    recalled = lib.recall(SUBJECT)
    assert not recalled.abstained
    assert recalled.accepted[0].text == SUBJECT

    # recall was not requested -> the honest status says so
    assert res.recall_status == "disabled"
