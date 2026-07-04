"""Step-9 review fix #1: the cross-run recall prefilter of `audited_run` must be honest
AND proven end-to-end.

Before this fix the recall=True path could never fire in the composed form: the library
abstains until its conformal gate is calibrated, and nothing in gen.integration ever
calibrated it — so `reused_facts` was always empty and looked like "nothing found".
Now the precondition is documented (the CALLER warms the gate via `add_calibration`),
the abstention is visible as `recall_status == "uncalibrated"`, and this file drives
audited_run(recall=True) on a manually warmed library END-TO-END to a real hit.

Offline + deterministic (ScriptedLLM world, basis embedder); numpy-only — a memory-only
composition needs NO `verify` extra (the audit import inside audited_run is lazy and
only fires when a keystore is passed).
"""

from __future__ import annotations

import asyncio
import json

import numpy as np
import pytest

from gen.core.state import SourceCandidate
from gen.integration import audited_run
from gen.ledger.store import InMemoryLedgerStore
from gen.llm.base import ScriptedLLM
from gen.memory import VerifiedFactsLibrary
from gen.runner import Dependencies

SUBJECT = "standard gravity is 9.80665 meters per second squared"
QUESTION = "What is the value of standard gravity?"
DOC = "https://doc.example/grav"
INDEP = {
    "https://i.example/grav-1": "SUPPORT independent corroboration one",
    "https://i.example/grav-2": "SUPPORT independent corroboration two",
}
CREATED = "2026-07-04T00:00:00+00:00"


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


def _deps():
    return Dependencies(
        backends=[_Backend()],
        http_get=_http(),
        generator_llm=ScriptedLLM("claude-opus-4-8", _gen),
        verifier_llm=ScriptedLLM("gpt-4o", _ver),
        ledger=InMemoryLedgerStore(),
    )


def _recall_embedder():
    """Basis embedder mapping the QUESTION onto the same axis as the deposited fact
    (semantic match, score ~0); every other text lands on a shared orthogonal axis
    (score ~1 -> above tau -> honest no-match)."""
    axes = {QUESTION: 0, SUBJECT: 0}

    def embed(text: str) -> np.ndarray:
        v = np.zeros(4, dtype=np.float64)
        v[axes.get(text, 2)] = 1.0
        return v

    return embed


def test_recall_status_uncalibrated_on_cold_library():
    # An uncalibrated library ABSTAINS by design; the composed result must say
    # "uncalibrated" instead of looking like an honest "nothing found".
    lib = VerifiedFactsLibrary(_recall_embedder(), alpha=0.1)

    res = asyncio.run(audited_run(
        QUESTION, _deps(), created_at=CREATED, run_id="itest-cold",
        library=lib, recall=True,
    ))

    assert res.recall_status == "uncalibrated"
    assert res.reused_facts == ()


def test_recall_hit_on_warm_library_end_to_end():
    # END-TO-END: run 1 deposits the verified claim; the caller calibrates the library
    # (the documented precondition); run 2 with recall=True returns the prior fact as
    # reused_facts WITH provenance — the cross-run prefilter actually firing.
    lib = VerifiedFactsLibrary(_recall_embedder(), alpha=0.1)

    first = asyncio.run(audited_run(
        QUESTION, _deps(), created_at=CREATED, run_id="itest", library=lib,
    ))
    assert first.n_remembered == 1
    assert first.recall_status == "disabled"        # recall was not requested
    lib.add_calibration([1e-6] * 40)                # caller-side warm-up of the conformal gate

    second = asyncio.run(audited_run(
        QUESTION, _deps(), created_at=CREATED, run_id="itest",
        library=lib, recall=True,
    ))

    assert second.recall_status == "hit"
    assert len(second.reused_facts) == 1
    fact = second.reused_facts[0]
    assert fact.text == SUBJECT
    assert fact.claim_id in {c.id for c in first.claims}   # maps back to the original claim
    assert fact.sources                                    # provenance preserved
    # same run id -> same capture_id -> the dedupe guard blocks a duplicate deposit
    assert second.n_remembered == 0
    assert lib.n_facts == 1


def test_recall_no_match_on_unrelated_question():
    lib = VerifiedFactsLibrary(_recall_embedder(), alpha=0.1)
    asyncio.run(audited_run(
        QUESTION, _deps(), created_at=CREATED, run_id="itest", library=lib,
    ))
    lib.add_calibration([1e-6] * 40)

    res = asyncio.run(audited_run(
        "Wie hoch ist der Eiffelturm?", _deps(), created_at=CREATED,
        run_id="itest-other", library=lib, recall=True,
    ))

    assert res.recall_status == "no_match"   # calibrated, honestly nothing reusable
    assert res.reused_facts == ()


def _audit_available() -> bool:
    try:
        import gen.audit  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(_audit_available(), reason="verify extra installed — fail-loud path unreachable")
def test_requesting_audit_without_verify_extra_fails_loud():
    # Negative test for the audit seam: making the trust-core import lazy must NOT
    # soften it — requesting a signed audit without the extra raises loudly, never
    # silently returning an unsigned result.
    with pytest.raises(ImportError, match="trust-core"):
        asyncio.run(audited_run(
            QUESTION, _deps(), created_at=CREATED, run_id="itest-noaudit",
            keystore=object(), audit_key_id="k1",
        ))
