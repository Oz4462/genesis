"""Select a concrete ``LLMClient`` from a model id — the config -> client seam.

GENESIS is dependency-injected: the edge (``cli.py``) builds the generator/verifier clients
and hands them to the runner. This factory centralizes the model-id -> adapter mapping so the
cross-model pair declared in ``config.Models`` becomes a real, callable client pair:

  * a "claude" family id -> ``ClaudeCLI`` (Claude subscription via the ``claude`` CLI, OAuth)
  * an "xai"/grok id      -> ``GrokCLI``   (Grok subscription via the ``grok`` CLI, OAuth)
  * anything else         -> ``OllamaLLM`` (local default, e.g. qwen/gemma)

Routing reuses ``verification.cross_model.model_family`` so there is ONE source of truth for
model families — the same function the cross-model audit uses — and adding a backend never
drifts from the audit's notion of "different family".
"""

from __future__ import annotations

from .base import LLMClient
from .claude_cli import ClaudeCLI
from .grok_cli import GrokCLI
from .ollama import OllamaLLM


def make_llm(model: str) -> LLMClient:
    """Build the ``LLMClient`` for a model id, routed by its family.

    Raises ``ValueError`` on an empty id (``model_family`` does), so a misconfigured model
    never silently falls back to a default backend.
    """
    # Lazy import keeps llm package load free of any verification import cycle.
    from ..verification.cross_model import model_family

    family = model_family(model)  # raises on empty id -> no silent default
    if family == "claude":
        return ClaudeCLI(model)
    if family == "xai":
        return GrokCLI(model)
    return OllamaLLM(model)
