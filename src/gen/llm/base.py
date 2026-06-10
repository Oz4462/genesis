"""LLM boundary — the mockable seam between agents and any model.

Agents depend on this Protocol, never on a vendor SDK (CLAUDE.md §6). Two things
matter for the anti-hallucination guarantee:

  * every client carries a ``model`` id, so the cross-model rule (skeptic's family
    must differ from scholar's) can be enforced and audited (A6);
  * a deterministic ``ScriptedLLM`` lets the whole pipeline run offline and
    reproducibly in tests and demos — no network, no nondeterminism (A5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str


@runtime_checkable
class LLMClient(Protocol):
    """Minimal completion interface. Real adapters wrap a vendor SDK behind this."""

    model: str

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        ...


# A responder maps (system, user) -> raw text. Used by ScriptedLLM.
Responder = Callable[[str, str], str]


class ScriptedLLM:
    """Deterministic, offline LLM stand-in. Satisfies ``LLMClient``.

    Construct with either a fixed string or a ``responder(system, user) -> str``.
    Because it is pure and local, a run wired with ScriptedLLM is fully
    reproducible — the same inputs always yield the same report.
    """

    def __init__(self, model: str, responder: "str | Responder") -> None:
        self.model = model
        self._responder = responder

    async def complete(self, *, system: str, user: str) -> LLMResponse:
        if callable(self._responder):
            text = self._responder(system, user)
        else:
            text = self._responder
        return LLMResponse(text=text, model=self.model)
