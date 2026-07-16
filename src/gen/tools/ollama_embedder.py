"""ollama_embedder — local dense embeddings for the RAG backend (the BLOCKED dense path, made native).

The RAG retrieval backend defaults to an offline char-n-gram embedder; for REAL dense retrieval it
accepts any embedder callable. This is the LOCAL one: it embeds text via a local Ollama server
(``POST /api/embeddings``) — no GPU, no cloud key, no external API, because Ollama already runs on
``localhost:11434`` with embedding models (e.g. embeddinggemma). The dense path that was "BLOCKED — needs
an embedding model" thus runs NATIVELY on the existing local infra.

The HTTP POST is injectable (mirrors ``llm/ollama.py``), so unit tests run without a server; the real
embedding call needs Ollama up and is opt-in. It is SYNCHRONOUS so it drops straight into the RAG
backend's embedder slot. Embeddings are L2-normalised so the backend's dot-product cosine is correct. A
transport / non-2xx / empty-vector failure raises ``LLMTransportError`` — a dead embedder must never look
like a zero vector that silently mis-ranks retrieval.
"""

from __future__ import annotations

import json
from typing import Callable

import numpy as np

from ..core.errors import LLMTransportError
from ..tools.http import HttpResponse

#: An injectable SYNC JSON POST: (url, payload) -> HttpResponse. Real impl + test fakes both satisfy it.
SyncHttpPost = Callable[[str, dict], HttpResponse]


def default_sync_post(url: str, payload: dict, *, timeout: float = 300.0) -> HttpResponse:
    """Standard-library synchronous JSON POST (real runs only; the generous timeout covers cold-load)."""
    import urllib.error
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return HttpResponse(
                status=getattr(resp, "status", 200) or 200,
                body=resp.read().decode("utf-8", errors="replace"),
                final_url=resp.geturl(),
            )
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return HttpResponse(status=exc.code, body=body, final_url=url)


class OllamaEmbedder:
    """A synchronous dense embedder backed by a local Ollama server, for ``RagBackend(embedder=...)``."""

    name = "ollama-embed"

    def __init__(
        self,
        model: str = "embeddinggemma",
        *,
        http_post: SyncHttpPost | None = None,
        base_url: str = "http://localhost:11434",
        timeout: float = 300.0,
    ) -> None:
        if not model.strip():
            raise ValueError("embedding model id is empty")
        self.model = model
        self._url = base_url.rstrip("/") + "/api/embeddings"
        self._post: SyncHttpPost = http_post or (lambda u, p: default_sync_post(u, p, timeout=timeout))

    def __call__(self, text: str) -> np.ndarray:
        """Embed ``text`` to an L2-normalised vector. Raises ``LLMTransportError`` on any failure (never a
        silent zero vector)."""
        try:
            resp = self._post(self._url, {"model": self.model, "prompt": text})
        except Exception as exc:
            raise LLMTransportError(self.model, f"ollama embeddings transport: {exc}") from exc
        if not (200 <= resp.status < 300):
            raise LLMTransportError(self.model, f"ollama embeddings HTTP {resp.status}")
        try:
            payload = json.loads(resp.body)
            vector = payload.get("embedding")
            if vector is None:
                embeddings = payload.get("embeddings") or []
                vector = embeddings[0] if embeddings else None
        except Exception as exc:
            raise LLMTransportError(self.model, f"ollama embeddings parse: {exc}") from exc
        if not vector:
            raise LLMTransportError(self.model, "ollama returned an empty embedding")
        array = np.asarray(vector, dtype=float)
        norm = float(np.linalg.norm(array))
        return array / norm if norm > 0.0 else array
