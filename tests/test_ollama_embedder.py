"""Tests for the local Ollama dense embedder (tools/ollama_embedder.py).

Exercised with an INJECTED fake POST -- no Ollama server, offline. Pins: the embedding is L2-normalised;
it plugs into the RAG backend so a dense search ranks the matching document first; transport / non-2xx
/ empty-vector failures raise a typed LLMTransportError (never a silent zero vector); an empty model id
is rejected at construction.
"""

import asyncio
import json

import numpy as np
import pytest

from gen.core.errors import LLMTransportError
from gen.tools.http import HttpResponse
from gen.tools.ollama_embedder import OllamaEmbedder
from gen.tools.rag_backend import Document, RagBackend


def _post_returning(vector):
    return lambda url, payload: HttpResponse(status=200, body=json.dumps({"embedding": vector}), final_url=url)


def test_embedding_is_l2_normalised():
    emb = OllamaEmbedder(http_post=_post_returning([3.0, 4.0]))
    v = emb("anything")
    assert np.allclose(v, [0.6, 0.8])                       # 3-4-5 -> normalised


def test_plugs_into_rag_backend_for_dense_search():
    # a keyword-conditioned fake embedder: each topic maps to a distinct one-hot vector.
    def fake(url, payload):
        t = payload["prompt"].lower()
        vec = [1.0, 0.0, 0.0] if "kepler" in t else ([0.0, 1.0, 0.0] if "thermo" in t else [0.0, 0.0, 1.0])
        return HttpResponse(status=200, body=json.dumps({"embedding": vec}), final_url=url)

    corpus = [
        Document("doc:kepler", "Kepler", "kepler orbital period"),
        Document("doc:thermo", "Thermo", "thermodynamics entropy"),
        Document("doc:nn", "Nets", "deep learning networks"),
    ]
    backend = RagBackend(corpus, embedder=OllamaEmbedder(http_post=fake))
    hits = asyncio.run(backend.search("kepler orbital", limit=1))
    assert hits and hits[0].url_or_id == "doc:kepler"        # the dense search found the right doc


def test_transport_and_bad_responses_raise():
    def boom(url, payload):
        raise OSError("connection refused")

    with pytest.raises(LLMTransportError):
        OllamaEmbedder(http_post=boom)("x")
    with pytest.raises(LLMTransportError):
        OllamaEmbedder(http_post=lambda u, p: HttpResponse(500, "err", u))("x")
    with pytest.raises(LLMTransportError):
        OllamaEmbedder(http_post=_post_returning([]))("x")    # empty embedding is an outage, not a zero


def test_empty_model_rejected():
    with pytest.raises(ValueError):
        OllamaEmbedder("   ")
