"""Tier-3 live smoke: ArxivBackend against the real arXiv API (read-only).

Proves the ported backend discovers real papers end-to-end. Needs network. Writes
runs/pov/tier3_arxiv/report.json; exit 0 iff >=1 candidate with a real /abs/ id.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_GENESIS_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_GENESIS_REPO / "src"))

from gen.tools.arxiv_backend import ArxivBackend  # noqa: E402
from gen.tools.http import default_http_get  # noqa: E402


def main() -> int:
    be = ArxivBackend(default_http_get)
    cands = asyncio.run(be.search("conformal prediction distribution-free uncertainty", limit=5))
    ok = len(cands) >= 1 and all(c.url_or_id.startswith("https://arxiv.org/abs/") for c in cands)
    sample = [{"id": c.url_or_id, "title": c.title} for c in cands[:3]]
    out = _GENESIS_REPO / "runs" / "pov" / "tier3_arxiv"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(
        json.dumps({"pov": "tier3-arxiv-live", "n": len(cands), "sample": sample, "gate_pass": ok}, indent=2),
        encoding="utf-8",
    )
    print(f"=== Tier-3 arXiv live: {len(cands)} candidates ===")
    for c in cands[:3]:
        print(f"  {c.url_or_id}  {c.title}")
    print(f"GATE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
