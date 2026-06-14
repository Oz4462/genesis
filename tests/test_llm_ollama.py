"""Tests for the Ollama LLM adapter — no real network (the POST transport is faked).

The adapter is the seam between GENESIS and a locally served model. What matters
for the anti-hallucination guarantee: transport/server failures must raise loudly
(``LLMTransportError``) instead of degrading into empty model output — a dead
server must never look like a model that answered nothing (CLAUDE.md: laut statt
still). Live behaviour against a running Ollama is exercised separately in the
smoke run, never here.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import LLMTransportError  # noqa: E402
from gen.llm.base import LLMClient, LLMResponse  # noqa: E402
from gen.llm.ollama import OllamaLLM  # noqa: E402
from gen.tools.http import HttpResponse  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def post_returning(status: int, body: str, calls: list | None = None):
    async def _post(url: str, payload: dict) -> HttpResponse:
        if calls is not None:
            calls.append((url, payload))
        return HttpResponse(status=status, body=body, final_url=url)

    return _post


def chat_body(content: str) -> str:
    return json.dumps({"message": {"role": "assistant", "content": content}, "done": True})


# --- happy path ---------------------------------------------------------------

def test_complete_returns_text_and_model_and_posts_chat_payload():
    calls: list = []
    llm = OllamaLLM("qwen2.5:14b", post=post_returning(200, chat_body("OCCT"), calls))
    res = run(llm.complete(system="sys prompt", user="user prompt"))
    assert isinstance(res, LLMResponse)
    assert res.text == "OCCT"
    assert res.model == "qwen2.5:14b"
    # exactly one POST to the chat endpoint: system+user messages, no streaming,
    # greedy decoding (temperature 0 — extraction/judging, not creative writing).
    (url, payload), = calls
    assert url == "http://localhost:11434/api/chat"
    assert payload["model"] == "qwen2.5:14b"
    assert payload["stream"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert payload["options"]["temperature"] == 0
    # num_ctx is set explicitly so long source text is not silently truncated
    assert payload["options"]["num_ctx"] >= 8192


def test_num_ctx_is_configurable():
    calls: list = []
    llm = OllamaLLM("qwen2.5:14b", num_ctx=16384, post=post_returning(200, chat_body("x"), calls))
    run(llm.complete(system="s", user="u"))
    (_url, payload), = calls
    assert payload["options"]["num_ctx"] == 16384


def test_satisfies_llm_client_protocol():
    llm = OllamaLLM("qwen2.5:14b", post=post_returning(200, chat_body("x")))
    assert isinstance(llm, LLMClient)


# --- every failure mode raises loudly — never empty model output ---------------

def post_raising(exc: Exception):
    async def _post(url: str, payload: dict) -> HttpResponse:
        raise exc

    return _post


def test_non_2xx_raises_transport_error():
    llm = OllamaLLM("qwen2.5:14b", post=post_returning(404, "model not found"))
    with pytest.raises(LLMTransportError) as exc_info:
        run(llm.complete(system="s", user="u"))
    assert "404" in str(exc_info.value)


def test_transport_exception_raises_transport_error_with_cause():
    llm = OllamaLLM("qwen2.5:14b", post=post_raising(ConnectionError("refused")))
    with pytest.raises(LLMTransportError) as exc_info:
        run(llm.complete(system="s", user="u"))
    assert "refused" in str(exc_info.value)  # honest cause, not a generic shrug


def test_non_json_body_raises_transport_error():
    llm = OllamaLLM("qwen2.5:14b", post=post_returning(200, "<html>proxy error</html>"))
    with pytest.raises(LLMTransportError):
        run(llm.complete(system="s", user="u"))


def test_missing_message_content_raises_transport_error():
    body = json.dumps({"done": True})  # envelope without message.content
    llm = OllamaLLM("qwen2.5:14b", post=post_returning(200, body))
    with pytest.raises(LLMTransportError):
        run(llm.complete(system="s", user="u"))


def test_empty_model_id_is_rejected_at_construction():
    # an empty id would defeat the cross-model audit (model_family raises on it);
    # fail at construction, not deep inside a run.
    with pytest.raises(ValueError):
        OllamaLLM("   ", post=post_returning(200, chat_body("x")))
