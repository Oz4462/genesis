"""build_live research-breadth wiring — arXiv + OpenAlex (keyless) always, PatentsView keyed.

The three backends were island connectors (imported only by package __init__ / tests) while
docs (EXTERNAL_INTEGRATION.md) claimed arXiv/OpenAlex were already live — a false claim. Wiring
them into build_live makes the claim honest. PatentsView needs an X-Api-Key, so it is registered
ONLY when PATENTSVIEW_API_KEY is set (we never wire a backend we cannot honestly run).
"""

from __future__ import annotations

from gen.cli import build_live

_PAIR = ("qwen2.5:14b", "gemma4:latest")  # different families — build_live's hard gate passes


def test_default_backends_include_arxiv_and_openalex_not_patents(monkeypatch):
    # Arrange — no patent key in the environment
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)

    # Act
    deps, _ = build_live(*_PAIR)
    names = [b.name for b in deps.backends]

    # Assert — keyless breadth is wired; the keyed patent backend is absent (honest)
    assert names == ["wikipedia", "semantic_scholar", "formula", "arxiv", "openalex"]
    assert "patents" not in names


def test_patents_backend_registered_only_when_key_present(monkeypatch):
    # Arrange — a key makes the patent endpoint reachable (baked into the injected transport)
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key-123")

    # Act
    deps, _ = build_live(*_PAIR)
    names = [b.name for b in deps.backends]

    # Assert — patents now joins the pool, last (prior-art discovery)
    assert names == ["wikipedia", "semantic_scholar", "formula", "arxiv", "openalex", "patents"]
