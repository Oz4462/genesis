"""Cross-run verified-facts memory for GENESIS (PoV-2).

GENESIS gap #1 was: the ledger is per-run in-memory, so every run re-researches
everything. This module adds a DURABLE, conformal-bounded library of previously
VERIFIED claims that a run can consult before doing live research — accelerating
repeats while staying honest (it ABSTAINS rather than hand back an unrelated fact).

It is an ADDITIVE layer, not a replacement for the per-run ``LedgerStore``: claims
still flow through the ledger with full provenance; only claims that reached
``ClaimStatus.VERIFIED`` are deposited here for future reuse, keyed by claim id so a
recall maps straight back to the original sourced claim.

Honesty model (proven in PoV-2 with a real Ollama embedder: 0 false reuse):
  * reuse is gated by a split-conformal threshold (`ConformalRetriever`); until the
    calibrator is warm the library ABSTAINS (no bound -> no reuse), never guesses.
  * embedder quality governs the honesty gate — use a real semantic embedder in
    production (see `ollama_embedder`); the toy bag-of-token embedder is for tests only.

The conformal math is vendored from ANAMNESIS (see `_vendor/WHY.md`): numpy+stdlib,
no cloud-SDK deps, preserving GENESIS's local-first ethos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..core.state import Claim, ClaimStatus
from ._vendor.anamnesis_mem import (
    ConformalCalibrator,
    ConformalRetriever,
    Embedder,
    ReasoningStep,
    TraceStore,
)


@dataclass(frozen=True)
class RecalledFact:
    """A prior verified claim returned by a recall, with its reuse score.

    `sources` carries the ORIGINAL claim's provenance (source ids), so a reused fact
    keeps "kein Fakt ohne Quelle" — it is verified-in-a-prior-run, not source-less.
    """

    claim_id: str
    text: str
    score: float
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecallResult:
    """Outcome of a recall: accepted prior facts (may be empty = abstained)."""

    query: str
    accepted: tuple[RecalledFact, ...]
    tau: float | None

    @property
    def abstained(self) -> bool:
        return len(self.accepted) == 0


class VerifiedFactsLibrary:
    """Durable, conformal-bounded store of previously verified claims."""

    def __init__(
        self,
        embedder: Embedder,
        *,
        db_path: str | Path = ":memory:",
        alpha: float = 0.1,
        k: int = 3,
        min_calibration: int = 30,
    ) -> None:
        self._store = TraceStore(embedder, db_path=db_path)
        self._calibrator = ConformalCalibrator(alpha=alpha, min_calibration=min_calibration)
        self._retriever = ConformalRetriever(store=self._store, calibrator=self._calibrator, k=k)
        self._alpha = alpha

    @property
    def n_facts(self) -> int:
        return self._store.n_steps

    @property
    def calibrated(self) -> bool:
        return self._calibrator.ready

    def remember(self, claims: Sequence[Claim]) -> int:
        """Deposit VERIFIED claims for future reuse. Returns how many were stored.

        Only ``ClaimStatus.VERIFIED`` claims are kept — the library is a library of
        facts that already cleared verification, never of unbacked assertions.

        Deduplicates by claim id (= step ``capture_id``): re-running the same
        reproducible run re-produces the same claim ids, and depositing them again
        would create duplicate steps that inflate recall with identical neighbours.
        The guard lives HERE (vendored storage stays untouched); a claim id already
        present in the store — or seen earlier in the same call — is skipped.
        """
        seen: set[str] = set()
        steps = []
        for c in claims:
            if c.status is not ClaimStatus.VERIFIED:
                continue
            if c.id in seen or self._store.list_steps_for_trace(c.id):
                continue  # already deposited (same capture_id) -> no duplicate step
            seen.add(c.id)
            steps.append(
                ReasoningStep.make(
                    capture_id=c.id,
                    text=c.text,
                    intent="verified_fact",
                    produces=tuple(s.url_or_id for s in c.sources),  # keep provenance
                    tags=(c.status.value,),
                )
            )
        if steps:
            self._store.add_steps(steps)
        return len(steps)

    def add_calibration(self, scores: Sequence[float]) -> None:
        """Feed observed genuine fresh-vs-retrieved nonconformity scores to warm the
        conformal threshold. Until enough are seen, recall abstains."""
        self._calibrator.extend(scores)

    def recall(self, query: str, *, alpha: float | None = None) -> RecallResult:
        """Return prior verified facts within the calibrated reuse band, else abstain."""
        res = self._retriever.retrieve(query, alpha=alpha or self._alpha)
        accepted = tuple(
            RecalledFact(
                claim_id=c.step.capture_id,
                text=c.step.text,
                score=c.score,
                sources=tuple(c.step.produces),  # original provenance preserved
            )
            for c in res.accepted
        )
        return RecallResult(query=query, accepted=accepted, tau=res.bound.tau if res.bound else None)


def ollama_embedder(
    model: str = "embeddinggemma:latest",
    url: str = "http://localhost:11434/api/embed",
) -> Embedder:
    """Real local semantic embedder via Ollama (deterministic, no cloud egress).

    The production embedder for the verified-facts library. Proven in PoV-2 to give
    clean genuine/novel separation (0 false reuse). Stdlib transport, no extra deps.
    """
    import json as _json
    import urllib.request as _ur

    import numpy as _np

    def embed(text: str):
        payload = _json.dumps({"model": model, "input": text or " "}).encode("utf-8")
        req = _ur.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        vec = _np.asarray(data["embeddings"][0], dtype=_np.float64)
        n = _np.linalg.norm(vec)
        if n == 0.0:
            vec[0] = 1.0
            return vec
        return vec / n

    return embed


__all__ = ["VerifiedFactsLibrary", "RecalledFact", "RecallResult", "ollama_embedder"]
