"""Live Ollama run: real Phase-alpha pipeline + arXiv backend + memory + signed audit.

Exercises the WHOLE integrated stack end-to-end against real local models and the real
web: build_live (Ollama qwen3.5:9b generator / gemma4:12b verifier, cross-model) +
Wikipedia + Semantic Scholar + the new ArxivBackend, driven through gen.integration.
audited_run so every VERIFIED claim is deposited into the memory library and a
tamper-evident audit is signed.

Honest: this proves the pipeline RUNS live end to end and the integrations fire; it does
not assert research quality. Whatever the models verify (possibly nothing — honest
abstention) is reported as measured. Needs Ollama up + network. Writes
runs/pov/live_alpha/report.json. Exit 0 iff the run completes and the audit verifies.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_GENESIS_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_GENESIS_REPO / "src"))

from gen.audit import verify_audit  # noqa: E402
from gen.cli import build_live  # noqa: E402
from gen.core.state import ClaimStatus  # noqa: E402
from gen.integration import audited_run  # noqa: E402
from gen.memory import VerifiedFactsLibrary, ollama_embedder  # noqa: E402
from gen.tools.arxiv_backend import ArxivBackend  # noqa: E402
from gen.tools.http import default_http_get  # noqa: E402
from trust_core.receipts.keystore import KeyStore  # noqa: E402

QUESTION = "What is the speed of light in vacuum in meters per second?"
GENERATOR = "qwen3.5:9b"
VERIFIER = "gemma4:12b"


async def _main() -> int:
    deps, config = build_live(GENERATOR, VERIFIER)
    deps.backends.append(ArxivBackend(default_http_get))  # Tier-3 backend, live

    ks = KeyStore()
    audit_key = ks.generate(scope="genesis-audit").key_id
    library = VerifiedFactsLibrary(ollama_embedder(), alpha=0.1)

    res = await audited_run(
        QUESTION, deps,
        created_at=datetime.now(timezone.utc).isoformat(),
        config=config, run_id="live-alpha-1",
        library=library, keystore=ks, audit_key_id=audit_key,
    )

    statuses = {s.value: sum(1 for c in res.claims if c.status is s) for s in ClaimStatus}
    audit_ok = False
    if res.audit is not None:
        audit_ok = verify_audit(res.audit, ks).ledger_digest == res.audit_record.ledger_digest

    report = {
        "run_id": res.run_id,
        "question": QUESTION,
        "models": {"generator": GENERATOR, "verifier": VERIFIER},
        "n_claims": len(res.claims),
        "status_counts": statuses,
        "n_remembered": res.n_remembered,
        "audit_verifies": audit_ok,
        "ledger_digest": res.audit_record.ledger_digest if res.audit_record else None,
        "report_body_head": (res.report.body or "")[:400],
        "gaps_head": list(res.report.gaps)[:5],
    }
    out = _GENESIS_REPO / "runs" / "pov" / "live_alpha"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== LIVE Ollama alpha run ({GENERATOR} / {VERIFIER}) ===")
    print(f"claims={len(res.claims)} statuses={statuses}")
    print(f"remembered={res.n_remembered}  audit_verifies={audit_ok}")
    print(f"body[:200]: {(res.report.body or '')[:200]}")
    print(f"(report: {out / 'report.json'})")
    # success = the live pipeline completed and the audit chain is intact
    return 0 if audit_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
