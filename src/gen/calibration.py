"""Confidence calibration — choose the accept threshold by measurement (research #6).

GENESIS is strong on NUMERIC uncertainty (GUM C-18, Monte-Carlo), but a factual claim carries a
single skeptic confidence. SOTA hallucination work adds two things: pick the accept threshold by
MEASUREMENT (precision at a threshold on a labelled set) rather than guessing it, and derive
confidence from CONSISTENCY across independent verification samples (a zero-resource signal).
This module is the deterministic, offline core of both.

Given a labelled set of (confidence, is_true) pairs — a held-out gold set in production — it
computes precision/recall at any threshold, finds the LOWEST threshold meeting a precision bar
(so the guarantee's accept rule maximises recall while holding the target precision, e.g. 95 %),
and the Expected Calibration Error (how well the confidence matches the empirical accuracy). And
from N independent verifier verdicts it derives a consistency confidence — the agreement
fraction — which a second judge / repeated sampling supplies. It NEVER invents a threshold that
meets the bar when none does (returns None) — the calibration analogue of honest abstention.
Offline, pure functions, no model calls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OperatingPoint:
    """An accept threshold and the discrimination it yields on the labelled set.

    `threshold`   accept a claim iff confidence >= threshold.
    `precision`   fraction of accepted claims that are actually true.
    `recall`      fraction of all true claims that are accepted.
    `n_accepted`  how many claims clear the threshold.
    """

    threshold: float
    precision: float
    recall: float
    n_accepted: int


def precision_recall_at(scored: list[tuple[float, bool]], threshold: float) -> OperatingPoint:
    """Precision/recall of the rule "accept iff confidence >= threshold" over `scored`
    (confidence, is_true) pairs. Empty acceptance has vacuous precision 1.0, recall 0."""
    accepted = [(c, t) for c, t in scored if c >= threshold]
    true_positives = sum(1 for _c, t in accepted if t)
    total_true = sum(1 for _c, t in scored if t)
    precision = true_positives / len(accepted) if accepted else 1.0
    recall = true_positives / total_true if total_true else 0.0
    return OperatingPoint(threshold, precision, recall, len(accepted))


def threshold_for_precision(
    scored: list[tuple[float, bool]], target_precision: float
) -> OperatingPoint | None:
    """The operating point that holds at least `target_precision` while MAXIMISING recall
    (ties broken toward the lower threshold). Considers thresholds at the observed
    confidences and requires a non-empty acceptance. Returns None if no threshold meets the
    bar — an honest "the labelled set does not support this precision", never a fabricated
    threshold."""
    if not 0.0 <= target_precision <= 1.0:
        raise ValueError("target_precision must be in [0, 1]")
    candidates = sorted({c for c, _ in scored})
    qualifying = [
        op for op in (precision_recall_at(scored, thr) for thr in candidates)
        if op.n_accepted > 0 and op.precision >= target_precision
    ]
    if not qualifying:
        return None
    return max(qualifying, key=lambda op: (op.recall, -op.threshold))


def expected_calibration_error(scored: list[tuple[float, bool]], *, n_bins: int = 10) -> float:
    """Expected Calibration Error: bin the confidences, and average |mean confidence −
    empirical accuracy| over bins weighted by bin size. 0 = confidence matches accuracy
    everywhere; large = over/under-confident. Returns 0 for an empty set."""
    if not scored or n_bins < 1:
        return 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for c, t in scored:
        # clamp BOTH ends: a c<0 must not land (via Python negative indexing) in the TOP bin
        idx = max(0, min(int(c * n_bins), n_bins - 1))
        bins[idx].append((c, t))
    n = len(scored)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        accuracy = sum(1 for _c, t in b if t) / len(b)
        ece += (len(b) / n) * abs(mean_conf - accuracy)
    return ece


def consistency_confidence(verdicts: list[bool]) -> float:
    """Confidence from agreement across N independent verifier verdicts: the fraction that
    agree with the majority (1.0 = unanimous, 0.5 = a tie). The zero-resource consistency
    signal a second judge / repeated sampling supplies. Empty -> 0.0."""
    if not verdicts:
        return 0.0
    n_true = sum(1 for v in verdicts if v)
    majority = max(n_true, len(verdicts) - n_true)
    return majority / len(verdicts)


# --- split conformal prediction: the distribution-free guarantee --------------
#
# threshold_for_precision picks an operating point EMPIRICALLY; split conformal
# adds the finite-sample GUARANTEE: under exchangeability of the calibration
# scores with a new score, the conformal quantile covers the new score with
# probability >= 1 - alpha — no distributional assumption, no asymptotics.
# Source: Vovk et al., *Algorithmic Learning in a Random World*; Angelopoulos &
# Bates, "A Gentle Introduction to Conformal Prediction" (arXiv 2107.07511);
# mirrored in the local MathBrain vault (Konzepte/60-conformal-foundations.md).
# Both functions return None instead of inventing a bound when the calibration
# set is too small for the requested alpha — honest abstention, the same
# discipline as threshold_for_precision.

def conformal_quantile(scores: list[float], alpha: float) -> float | None:
    """The split-conformal UPPER quantile of nonconformity scores.

    q_hat = the ceil((n+1)·(1−alpha))-th smallest of the n calibration scores;
    then P(score_new <= q_hat) >= 1 − alpha for an exchangeable new score (the
    standard finite-sample coverage guarantee). Returns None when
    ceil((n+1)(1−alpha)) > n — the calibration set cannot support this alpha
    (the textbook case where the prediction set would be everything). Raises
    ValueError on alpha outside (0, 1)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    n = len(scores)
    if n == 0:
        return None
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return None
    return sorted(scores)[k - 1]


def conformal_accept_threshold(
    true_confidences: list[float], alpha: float
) -> float | None:
    """A confidence floor with a finite-sample guarantee on TRUE claims.

    Calibrate on the confidences of claims KNOWN to be true: with
    t = the floor(alpha·(n+1))-th smallest, an exchangeable new TRUE claim
    clears the floor with probability >= 1 − alpha (the lower-tail conformal
    bound) — i.e. the accept rule "confidence >= t" misses at most an alpha
    fraction of genuinely true claims, guaranteed without any distribution
    assumption. Returns None when floor(alpha·(n+1)) < 1 — too few calibration
    points for this alpha. Raises ValueError on alpha outside (0, 1)."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    n = len(true_confidences)
    k = math.floor(alpha * (n + 1))
    if k < 1:
        return None
    return sorted(true_confidences)[k - 1]
