"""GrokCLI model aliases + timeout env — live catalog only has grok-4.5."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.llm._cli import resolve_llm_timeout  # noqa: E402
from gen.llm.grok_cli import GrokCLI, _resolve_model_id  # noqa: E402


def test_grok_build_aliases_to_grok_45():
    assert _resolve_model_id("grok-build") == "grok-4.5"
    assert _resolve_model_id("Grok-Build") == "grok-4.5"
    assert _resolve_model_id("grok-4.5") == "grok-4.5"


def test_grok_cli_applies_alias_without_binary():
    # inject fake runner so no real CLI is needed
    async def fake(_argv):
        return 0, '{"result":"ok"}', ""

    cli = GrokCLI(model="grok-build", runner=fake)
    assert cli.model == "grok-4.5"


def test_resolve_llm_timeout_env(monkeypatch):
    monkeypatch.delenv("GENESIS_LLM_TIMEOUT", raising=False)
    assert resolve_llm_timeout(None) == 300.0
    assert resolve_llm_timeout(120.0) == 120.0
    monkeypatch.setenv("GENESIS_LLM_TIMEOUT", "480")
    assert resolve_llm_timeout(None) == 480.0
    # floor
    assert resolve_llm_timeout(5.0) == 30.0
