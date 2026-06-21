"""Controlled verification of the num_ctx truncation fix (root-cause of live claims=0).

Builds a long SOURCE TEXT with the target fact at the END (beyond a small context
window), then runs the REAL scholar extraction prompt via OllamaLLM at num_ctx=2048
(Ollama's small-default regime) vs num_ctx=8192 (the fix). Expectation: the small
window silently truncates the fact -> 0 claims; the large window keeps it -> extracts.
Deterministic content (no live web). Needs Ollama up. Exit 0 iff the fix extracts the
fact AND the small window demonstrably does worse.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_GENESIS_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_GENESIS_REPO / "src"))

from gen.agents.scholar import _SYSTEM  # noqa: E402
from gen.llm.ollama import OllamaLLM  # noqa: E402
from gen.llm.parsing import extract_json  # noqa: E402

FACT = "The speed of light in vacuum is exactly 299792458 metres per second."
# ~long filler so the fact sits well past a 2048-token window
FILLER = ("Historical measurements of optical phenomena were discussed at length in "
          "many nineteenth-century treatises, with extensive tabulation of apparatus, "
          "observers, and atmospheric conditions, none of which state the modern value. ")
QUESTION = "What is the speed of light in vacuum in meters per second?"
SHORT = FACT                                   # control: fits any window
LONG = (FILLER * 70) + "\n\n" + FACT           # ~4k tokens: > 2048 (truncated), < 8192 (kept)


async def _extract(source: str, num_ctx: int) -> list[dict]:
    llm = OllamaLLM("qwen3.5:9b", num_ctx=num_ctx)
    resp = await llm.complete(system=_SYSTEM, user=f"QUESTION:\n{QUESTION}\n\nSOURCE TEXT:\n{source}")
    try:
        val = extract_json(resp.text, agent="scholar")
        return [v for v in val if isinstance(v, dict)] if isinstance(val, list) else []
    except Exception:
        return []


def _has_value(items: list[dict]) -> bool:
    return any("299792458" in (it.get("text", "") + it.get("quote", "")) for it in items)


async def _main() -> int:
    control = _has_value(await _extract(SHORT, 8192))      # model can do it at all?
    small = 0
    large = 0
    for _ in range(2):
        small += int(_has_value(await _extract(LONG, 2048)))
        large += int(_has_value(await _extract(LONG, 8192)))
    print(f"LONG source length: {len(LONG)} chars (~{len(LONG)//4} tokens), fact at the end")
    print(f"control (short source, num_ctx=8192): value extracted = {control}")
    print(f"LONG num_ctx=2048 (old default regime): value extracted in {small}/2 runs")
    print(f"LONG num_ctx=8192 (fix):                value extracted in {large}/2 runs")
    ok = control and large == 2 and large > small
    print(f"GATE: {'PASS' if ok else 'FAIL'} (model capable; fix keeps fact in context, small window truncates)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
