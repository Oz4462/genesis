"""GENESIS core interfaces — framework-agnostic contracts.

These Protocols define WHAT every component must provide, independent of any
orchestration framework (LangGraph, CrewAI, ...). Concrete implementations live
behind adapters. Code in the rest of the system depends on THESE, never on a
framework directly.

Design rule (see CLAUDE.md §6): if you find yourself importing a framework here,
stop — it belongs in an adapter, not in core.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Sequence

from .state import (
    Question,
    SubQuestion,
    SourceCandidate,
    Claim,
    Report,
    RunState,
)


@runtime_checkable
class Tool(Protocol):
    """A capability an agent can invoke (search, fetch, read, compute).

    Tools must be honest about failure: a tool that cannot complete returns a
    typed failure, never a fabricated result. See core/errors.py.
    """

    name: str

    async def __call__(self, **kwargs) -> object:
        ...


@runtime_checkable
class Agent(Protocol):
    """An agent transforms a typed input into a typed output.

    Every agent declares:
      - input_schema / output_schema (for validation & docs)
      - tools it is allowed to use (capability boundary)
      - failure_modes it can raise (documented, not silent)

    Agents that produce factual content MUST route every factual statement
    through the Ledger as a Claim. An agent that emits a fact without a Claim
    is a bug (CLAUDE.md §1).
    """

    name: str

    async def run(self, state: RunState) -> RunState:
        """Advance the run by performing this agent's responsibility.

        Implementations read what they need from `state`, do their work, write
        results back into `state`, and return the updated state. They must not
        mutate fields owned by other agents.
        """
        ...


@runtime_checkable
class LedgerStore(Protocol):
    """Append-mostly store for Claims with mandatory provenance.

    The store enforces the non-negotiable rule: no Claim without at least one
    source reference. Enforcement happens both here and as a DB constraint
    (sql/001_ledger.sql) — belt and suspenders.
    """

    async def add_claims(self, run_id: str, claims: Sequence[Claim]) -> None:
        """Persist new claims. MUST reject any claim with empty `sources`."""
        ...

    async def update_claim(self, claim: Claim) -> None:
        """Persist a status/confidence/verification update for an existing claim."""
        ...

    async def get_claims(self, run_id: str) -> list[Claim]:
        """Return all claims for a run (for gate evaluation and reporting)."""
        ...

    async def record_fetch(
        self, run_id: str, url: str, ok: bool, content_hash: str | None
    ) -> None:
        """Record that a source was (or was not) successfully retrieved.

        Used by the gate to reject 'dead' citations (PHASE_ALPHA §4 condition 5).
        """
        ...


@runtime_checkable
class Gate(Protocol):
    """A pure, LLM-free predicate that decides whether a phase may complete.

    Gates are deterministic and unit-tested without any model. A gate returns a
    structured result (pass/fail + reasons), never just a boolean, so the
    conductor can act on WHY it failed.
    """

    name: str

    def evaluate(self, state: RunState) -> "GateResult":
        ...


@runtime_checkable
class SearchBackend(Protocol):
    """A source of candidate references (web, arXiv, PubMed, Semantic Scholar)."""

    name: str

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        ...


# --- Gate result -------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GateResult:
    """Outcome of a gate evaluation.

    `passed` is the decision. `failures` explains every reason it did not pass,
    keyed so the conductor can decide per-claim whether to re-research or to
    surface the item as an explicit gap (PHASE_ALPHA §4).
    """

    gate: str
    passed: bool
    failures: list["GateFailure"] = field(default_factory=list)


@dataclass(frozen=True)
class GateFailure:
    code: str  # e.g. "UNSOURCED_STATEMENT", "REFUTED_AS_FACT", "DEAD_CITATION"
    detail: str
    claim_id: str | None = None
