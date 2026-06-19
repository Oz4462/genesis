"""Tests for the subscription-OAuth CLI LLM adapters (ClaudeCLI, GrokCLI) + make_llm factory.

The adapters are exercised with an INJECTED fake runner — no real CLI is launched — so these
run anywhere. The factory's claude/grok routing is honest-skipped when the CLI is absent
(README §7, like the cadquery/build123d-gated tests); the Ollama route always runs.

Offline, no network, no LLM, no subscription needed.
"""

import shutil

import pytest

from gen.core.errors import LLMTransportError
from gen.llm._cli import extract_cli_text
from gen.llm.claude_cli import ClaudeCLI
from gen.llm.factory import make_llm
from gen.llm.grok_cli import GrokCLI
from gen.llm.ollama import OllamaLLM


class _FakeRunner:
    """A callable that satisfies CliRunner and records the argv it was called with."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self._result = (returncode, stdout, stderr)
        self.argv: list[str] | None = None

    async def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.argv = argv
        return self._result


@pytest.mark.asyncio
async def test_grok_cli_parses_json_and_concatenates_prompt():
    r = _FakeRunner(stdout='{"result": "hello from grok"}')
    llm = GrokCLI("grok", runner=r)
    resp = await llm.complete(system="be terse", user="hi")
    assert resp.text == "hello from grok"
    assert resp.model == "grok"
    # grok -p takes ONE prompt -> system + user are concatenated into argv[2]
    assert r.argv is not None
    assert r.argv[0:2] == ["grok", "-p"]
    assert "be terse" in r.argv[2] and "hi" in r.argv[2]
    # grok's --output-format json mode auth-errors + hangs (verified live), so the adapter does NOT
    # pass it; plain mode prints the (JSON) answer on stdout, which extract_cli_text reads.
    assert "--model" in r.argv and "--output-format" not in r.argv


@pytest.mark.asyncio
async def test_claude_cli_keeps_system_separate():
    r = _FakeRunner(stdout='{"result": "hi from claude"}')
    llm = ClaudeCLI("claude-opus-4-8", runner=r)
    resp = await llm.complete(system="be terse", user="hi")
    assert resp.text == "hi from claude"
    assert resp.model == "claude-opus-4-8"
    assert r.argv is not None
    assert "--append-system-prompt" in r.argv
    assert r.argv[r.argv.index("--append-system-prompt") + 1] == "be terse"
    assert "claude-opus-4-8" in r.argv


@pytest.mark.asyncio
async def test_cli_adapter_fails_loud_on_nonzero_exit():
    llm = GrokCLI("grok", runner=_FakeRunner(returncode=1, stderr="re-auth required"))
    with pytest.raises(LLMTransportError):
        await llm.complete(system="", user="hi")


@pytest.mark.asyncio
async def test_cli_adapter_fails_loud_when_runner_raises():
    class _Boom:
        async def __call__(self, argv: list[str]) -> tuple[int, str, str]:
            raise OSError("binary vanished")

    llm = ClaudeCLI("claude-opus-4-8", runner=_Boom())
    with pytest.raises(LLMTransportError):
        await llm.complete(system="", user="hi")


@pytest.mark.asyncio
async def test_cli_adapter_fails_loud_on_empty_stdout():
    llm = GrokCLI("grok", runner=_FakeRunner(stdout="   "))
    with pytest.raises(LLMTransportError):
        await llm.complete(system="", user="hi")


def test_empty_model_id_rejected_at_construction():
    with pytest.raises(ValueError):
        GrokCLI("   ", runner=_FakeRunner())
    with pytest.raises(ValueError):
        ClaudeCLI("", runner=_FakeRunner())


def test_extract_cli_text_is_tolerant():
    assert extract_cli_text('{"result":"a"}', model="m") == "a"
    # streamed event objects then a trailing result object on the last line
    assert extract_cli_text('{"type":"start"}\n{"response":"b"}', model="m") == "b"
    # chat envelope
    assert extract_cli_text('{"message":{"content":"c"}}', model="m") == "c"
    # plain-text fallback (CLI ran in text mode)
    assert extract_cli_text("just text", model="m") == "just text"
    # empty output is an outage, never a silent ""
    with pytest.raises(LLMTransportError):
        extract_cli_text("   ", model="m")


def test_factory_routes_ollama_without_any_cli():
    # A non-claude/non-xai id -> local Ollama; no binary resolution, env-independent.
    assert isinstance(make_llm("qwen2.5:14b"), OllamaLLM)


def test_factory_rejects_empty_model_no_silent_default():
    with pytest.raises(ValueError):
        make_llm("   ")


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI absent (honest-skip, README §7)")
def test_factory_routes_claude_to_cli():
    assert isinstance(make_llm("claude-opus-4-8"), ClaudeCLI)


@pytest.mark.skipif(shutil.which("grok") is None, reason="grok CLI absent (honest-skip, README §7)")
def test_factory_routes_grok_to_cli():
    assert isinstance(make_llm("grok"), GrokCLI)


def test_grok_and_claude_are_a_valid_live_cross_model_pair():
    """End-state readiness (Strang 3): a Claude generator + a Grok verifier satisfy the cross-model
    rule (different families), and when the CLIs are installed the factory routes them to ClaudeCLI /
    GrokCLI — so grok-build + Claude Code CLI form a valid LIVE skeptic pair. The rule is checked
    unconditionally (no binary needed); the live run stays opt-in until GENESIS is finished (owner
    directive: deterministic/offline until done, then the AI co-pilot runs in GENESIS)."""
    from gen.core.errors import ModelConflictError
    from gen.verification.cross_model import assert_different_families, model_family

    gen_id, ver_id = "claude-opus-4-8", "grok-build"
    assert model_family(gen_id) != model_family(ver_id)     # grok and claude are different families
    assert_different_families(gen_id, ver_id)               # a valid cross-model pair -> no raise
    with pytest.raises(ModelConflictError):
        assert_different_families(ver_id, ver_id)           # same-model self-verification -> rejected
    if shutil.which("claude") is not None:
        assert isinstance(make_llm(gen_id), ClaudeCLI)      # routes to the real Claude CLI client
    if shutil.which("grok") is not None:
        assert isinstance(make_llm(ver_id), GrokCLI)        # routes to the real Grok CLI client
