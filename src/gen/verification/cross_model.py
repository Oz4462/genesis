"""Cross-model verification helpers (PHASE_ALPHA §3.4, skeptic.md §4-5).

Two non-negotiable jobs, both pure and LLM-free so they are deterministic and
unit-testable:

  1. **Enforce cross-model.** The verifier (`skeptic`) MUST run on a different
     model *family* than the generator (`scholar`). Same-family self-checking is
     not verification — it shares the same blind spots. Violations raise
     ``ModelConflictError`` instead of silently passing.

  2. **Fold disagreement into confidence.** When a second, independent judge is
     consulted, agreement between independently-derived judgments raises
     confidence (independent corroboration); disagreement lowers it and forces a
     conservative status. The system never asserts a fact as VERIFIED while two
     models disagree about it — "im Zweifel UNSUPPORTED".

Determinism matters: these functions feed claim confidence, and reproducibility
(A5) requires the same inputs to always yield the same number.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..core.errors import ModelConflictError
from ..core.state import ClaimStatus, SourceRef


# --- Model-family identification (enables the cross-model audit, A6) ----------

# Ordered keyword -> family map. First match wins. Lowercased substring test.
#
# `codex` MUST be tested before `openai`: an id like ``gpt-5.5-codex`` carries
# both the ``gpt`` and ``codex`` substrings, and the Codex family is the more
# specific (correct) answer. First-match-wins ordering therefore requires the
# narrower `codex` rule to precede the broader `gpt`->openai rule, otherwise the
# Codex variant would be silently mis-attributed to the OpenAI base family and
# defeat the cross-model audit. Plain ``gpt-4o`` (no ``codex``) still -> openai.
_FAMILY_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("claude", "anthropic"), "claude"),
    (("codex",), "codex"),
    (("gpt", "openai", "davinci", "o1-", "o3-", "o4-"), "openai"),
    (("gemini", "palm", "bison", "gemma"), "google"),
    (("llama", "codellama"), "llama"),
    (("mistral", "mixtral", "codestral"), "mistral"),
    (("qwen",), "qwen"),
    (("deepseek",), "deepseek"),
    (("grok",), "xai"),
    (("command", "cohere"), "cohere"),
    (("phi-", "phi3", "phi4"), "phi"),
]


def model_family(model: str) -> str:
    """Map a concrete model id to its provider/architecture family.

    Examples: ``"claude-opus-4-8" -> "claude"``, ``"gpt-4o" -> "openai"``,
    ``"llama3.1:8b" -> "llama"``. Unknown ids fall back to their first token
    (split on non-alphanumerics), so two unrelated unknown models still compare
    as different families rather than colliding on a shared default.

    Raises:
        ValueError: if `model` is empty — a missing model id must never be
            silently treated as "some family" (that would defeat the audit).
    """
    norm = model.strip().lower()
    if not norm:
        raise ValueError("model id is empty; cannot determine model family.")
    for keywords, family in _FAMILY_KEYWORDS:
        if any(k in norm for k in keywords):
            return family
    # Fallback: leading alphanumeric token.
    token = ""
    for ch in norm:
        if ch.isalnum():
            token += ch
        else:
            break
    return token or norm


def assert_different_families(generator_model: str, verifier_model: str) -> None:
    """Guarantee verifier and generator are different families, or raise.

    This is the structural form of the cross-model rule: it makes same-model
    self-verification impossible to do by accident.

    Raises:
        ModelConflictError: the two ids resolve to the same family.
    """
    g = model_family(generator_model)
    v = model_family(verifier_model)
    if g == v:
        raise ModelConflictError(generator_model, verifier_model)


def assert_pairwise_different_families(models: Sequence[str]) -> None:
    """Guarantee every pair of panel members is a different family, or raise.

    The panel math (weighted mean, noisy-OR corroboration) treats judges as
    INDEPENDENT opinions; two judges from one family share blind spots and
    would silently inflate corroboration. A same-family panel is therefore a
    configuration error — the inter-judge form of the cross-model rule
    (verifier != second != extra), mirroring the generator/verifier check.

    Raises:
        ModelConflictError: two ids resolve to the same family.
        ValueError: a model id is empty.
    """
    for i, a in enumerate(models):
        for b in models[i + 1 :]:
            assert_different_families(a, b)


# --- A single model's verdict on one claim -----------------------------------

@dataclass(frozen=True)
class Judgment:
    """One model's independent verdict on a claim.

    This is the mockable boundary: tests construct ``Judgment`` objects directly,
    so cross-model logic is exercised without any real LLM call.

    `status`      VERIFIED / REFUTED / UNSUPPORTED.
    `confidence`  the judge's own confidence in that status, 0..1.
    `model`       the model id that produced it (for the cross-model audit).
    `rationale`   short reason (not a new fact).
    `sources`     independent sources the judge actually used.
    """

    status: ClaimStatus
    confidence: float
    model: str
    rationale: str = ""
    sources: tuple[SourceRef, ...] = field(default_factory=tuple)


# --- Disagreement & confidence folding ---------------------------------------

# Distance between two statuses: 0 = identical, 1 = maximally opposed.
_STATUS_DISTANCE: dict[frozenset[ClaimStatus], float] = {
    frozenset((ClaimStatus.VERIFIED, ClaimStatus.UNSUPPORTED)): 0.5,
    frozenset((ClaimStatus.UNSUPPORTED, ClaimStatus.REFUTED)): 0.5,
    frozenset((ClaimStatus.VERIFIED, ClaimStatus.REFUTED)): 1.0,
}


def status_disagreement(a: ClaimStatus, b: ClaimStatus) -> float:
    """Symmetric distance in [0,1] between two verification statuses."""
    if a is b:
        return 0.0
    return _STATUS_DISTANCE[frozenset((a, b))]


def corroborated_confidence(c1: float, c2: float) -> float:
    """Confidence from two *independent* agreeing judgments.

    Uses the noisy-OR / complement-product rule: ``1 - (1-c1)(1-c2)``. Two
    independent sources each 0.7 confident yield 0.91 — independent corroboration
    is worth more than either alone, but never exceeds 1.0.
    """
    c1 = _clamp01(c1)
    c2 = _clamp01(c2)
    return 1.0 - (1.0 - c1) * (1.0 - c2)


def _clamp01(x: float) -> float:
    """Map a score into [0, 1]. Non-finite values (NaN/Inf) become 0.0.

    Critical: ``NaN < 0`` and ``NaN > 1`` are both False in IEEE floats, so a
    naive clamp would *return* NaN and silently poison every downstream
    confidence threshold (``NaN < τ`` is always False → false VERIFIED pass).
    """
    try:
        if not math.isfinite(float(x)):
            return 0.0
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


def _conservative_status(a: ClaimStatus, b: ClaimStatus) -> ClaimStatus:
    """Pick the honest status when two judges disagree.

    Principle: never assert as fact under disagreement.
      {VERIFIED, UNSUPPORTED} -> UNSUPPORTED  (cannot claim it's established)
      {UNSUPPORTED, REFUTED}  -> REFUTED       (a credible refutation stands)
      {VERIFIED, REFUTED}     -> UNSUPPORTED   (pure conflict: assert neither)
    """
    pair = frozenset((a, b))
    if pair == frozenset((ClaimStatus.UNSUPPORTED, ClaimStatus.REFUTED)):
        return ClaimStatus.REFUTED
    # Both remaining disagreement cases collapse to the non-committal status.
    return ClaimStatus.UNSUPPORTED


def combine_judgments(primary: Judgment, second: Judgment | None = None) -> Judgment:
    """Fold an optional second judge into the primary verdict.

    - No second judge: return the primary unchanged.
    - Agree: keep the status; if VERIFIED, boost via independent corroboration,
      otherwise average the confidences.
    - Disagree: drop to the conservative status and penalize confidence by the
      disagreement distance (maximal conflict drives confidence toward 0).

    Pure and deterministic. The merged `sources` are the union (dedup by
    url_or_id, order preserved) so the caller can see all independent evidence.
    """
    if second is None:
        return primary

    merged_sources = _dedup_sources((*primary.sources, *second.sources))

    if primary.status is second.status:
        if primary.status is ClaimStatus.VERIFIED:
            conf = corroborated_confidence(primary.confidence, second.confidence)
        else:
            conf = (_clamp01(primary.confidence) + _clamp01(second.confidence)) / 2
        return Judgment(
            status=primary.status,
            confidence=conf,
            model=f"{primary.model}+{second.model}",
            rationale=_join_rationale(primary, second, agree=True),
            sources=merged_sources,
        )

    # Disagreement.
    d = status_disagreement(primary.status, second.status)
    base = min(_clamp01(primary.confidence), _clamp01(second.confidence))
    conf = base * (1.0 - d)
    return Judgment(
        status=_conservative_status(primary.status, second.status),
        confidence=conf,
        model=f"{primary.model}+{second.model}",
        rationale=_join_rationale(primary, second, agree=False),
        sources=merged_sources,
    )


def verify_confidence(
    *,
    generator_model: str,
    verifier: Judgment,
    second_judge: Judgment | None = None,
) -> Judgment:
    """The skeptic's entry point: enforce cross-model, then fold judgments.

    Asserts that every judge ran on a different family than the generator
    (``ModelConflictError`` otherwise), then combines the verdicts.

    Raises:
        ModelConflictError: a judge shares the generator's model family.
    """
    assert_different_families(generator_model, verifier.model)
    if second_judge is not None:
        assert_different_families(generator_model, second_judge.model)
    return combine_judgments(verifier, second_judge)


# --- small helpers -----------------------------------------------------------

def _dedup_sources(refs: tuple[SourceRef, ...]) -> tuple[SourceRef, ...]:
    seen: set[str] = set()
    out: list[SourceRef] = []
    for r in refs:
        if r.url_or_id not in seen:
            seen.add(r.url_or_id)
            out.append(r)
    return tuple(out)


def _join_rationale(a: Judgment, b: Judgment, *, agree: bool) -> str:
    tag = "agree" if agree else "disagree"
    parts = [p for p in (a.rationale, b.rationale) if p]
    joined = " | ".join(parts)
    return f"[{tag}] {joined}" if joined else f"[{tag}]"
