"""Ollama adapter — a real, local ``LLMClient`` behind the vendor-agnostic seam.

Why Ollama first: the cross-model rule needs at least two different model
*families*, and a local Ollama serves several (qwen, gemma → google, mistral, …)
without cloud keys — so the whole pipeline can run live on one machine.

Anti-hallucination posture:
  * transport/server failures raise ``LLMTransportError`` — a dead server must
    never look like a model that answered nothing (downstream would honestly
    treat empty output as abstention and thereby mask an outage);
  * greedy decoding (temperature 0) — the agents do extraction and judging,
    not creative writing, and determinism supports reproducibility (A5).

Like ``tools.http``, the POST transport is injectable so unit tests run without
a server; the default implementation uses only the standard library. The default
transport is exercised by the live smoke run, never by unit tests.
"""

from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

from ..core.errors import LLMTransportError
from ..tools.http import HttpResponse
from .base import LLMResponse

# An injectable async JSON POST. Real adapter and test fakes both satisfy this.
HttpPostJson = Callable[[str, dict], Awaitable[HttpResponse]]


async def default_http_post_json(
    url: str, payload: dict, *, timeout: float = 300.0
) -> HttpResponse:
    """Standard-library JSON POST, run in a worker thread (real runs only).

    Mirrors ``tools.http.default_http_get``: a non-2xx response is returned with
    its status code; transport-level failures (refused connection, timeout)
    propagate as exceptions — the adapter wraps both into ``LLMTransportError``.
    The generous default timeout covers local model cold-loads.
    """
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    data = json.dumps(payload).encode("utf-8")

    def _do() -> HttpResponse:
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return HttpResponse(
                    status=getattr(resp, "status", 200) or 200,
                    body=raw.decode("utf-8", errors="replace"),
                    final_url=resp.geturl(),
                )
        except urllib.error.HTTPError as exc:  # non-2xx -> keep the status code
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - body is best-effort only
                pass
            return HttpResponse(status=exc.code, body=body, final_url=url)

    return await asyncio.to_thread(_do)


class OllamaLLM:
    """``LLMClient`` against a local Ollama server (``POST /api/chat``)."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://localhost:11434",
        post: HttpPostJson | None = None,
        timeout: float = 300.0,
    ) -> None:
        if not model.strip():
            # An empty id would defeat the cross-model audit (model_family raises
            # on it); fail at construction, not deep inside a run.
            raise ValueError("model id is empty; the cross-model audit needs a real id.")
        self.model = model
        self._url = base_url.rstrip("/") + "/api/chat"
        self._post: HttpPostJson
        if post is not None:
            self._post = post
        else:
            async def _default_post(url: str, payload: dict) -> HttpResponse:
                return await default_http_post_json(url, payload, timeout=timeout)

            self._post = _default_post

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            resp = await self._post(self._url, payload)
        except Exception as exc:
            raise LLMTransportError(self.model, f"transport failure: {exc}") from exc
        if not 200 <= resp.status < 300:
            raise LLMTransportError(self.model, f"HTTP {resp.status}: {resp.body[:200]}")
        try:
            doc = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise LLMTransportError(self.model, f"non-JSON response: {resp.body[:200]}") from exc
        message = doc.get("message") if isinstance(doc, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LLMTransportError(
                self.model, f"response envelope missing message.content: {resp.body[:200]}"
            )
        return LLMResponse(text=content, model=self.model)
