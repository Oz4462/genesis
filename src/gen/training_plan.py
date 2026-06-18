"""training_plan — the honest boundary where GENESIS meets machine learning.

Training a control/perception policy is EMPIRICAL: there is no closed form that says "this network,
this data, will reach this success rate". GENESIS does not — and must not — pretend to train a model
or predict its accuracy; that would be exactly the hallucination the engine exists to prevent. So
this module deliberately does NOT estimate sample complexity or guarantee performance.

What it DOES — and what is squarely in GENESIS's wheelhouse — is enforce the discipline around the
empirical step:

  * ``training_plan_completeness_check`` — a trainable plan must declare, BEFORE training, the eval
    metric, the numeric acceptance threshold, the held-out evaluation set, and the sim-to-real
    strategy. Declaring success criteria up front is what stops the classic ML failure of moving the
    goalpost or cherry-picking a seed after the fact. A missing field is a gap, not a silent pass.
  * ``acceptance_gate`` — once training has produced MEASURED numbers, ratify them against the
    pre-declared thresholds: accepted only if the measured success rate clears the required one, the
    safety violations stay within budget, AND the sim-to-real gap is within tolerance. This is the
    same δ-asymmetry as the rest of GENESIS — the bar is set first, the evidence is checked against
    it, and "good enough" is never decided after seeing the result.

Offline, deterministic, no numpy, no model. Honest boundary: GENESIS specifies the success criteria
and ratifies the measured outcome; it does not train, does not estimate how much data a target needs,
and does not predict accuracy. Critically, ``acceptance_gate`` ratifies the NUMBERS it is given — it
enforces a minimum eval sample size (a 0.95 on 5 rollouts is noise, not 0.95 on 500), but it does NOT
and cannot validate measurement PROVENANCE: held-out-set integrity (no leakage from hyperparameter
search or early stopping), the calibration of the sim-to-real gap metric, distribution shift beyond
it, or whether the declared threshold is itself a meaningful bar. A clean ``accepted`` means "the
supplied measurements cleared the pre-declared bars", NEVER "GENESIS validated the experiment".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingPlan:
    """A declared plan for an empirical training step. The fields that MUST be set before training
    are the ones that pin down what "success" means — so it cannot be redefined afterwards."""

    task: str
    eval_metric: str                 # what is measured, e.g. "task_success_rate"
    acceptance_threshold: float      # the numeric bar that must be cleared (e.g. 0.9)
    held_out_eval_set: str           # the evaluation data/episodes NOT used for training
    sim2real_strategy: str           # e.g. "domain_randomization" / "real_only" / "none"
    data_source: str = ""
    notes: str = ""


#: The fields a plan must declare before training is allowed to count (success defined up front).
REQUIRED_FIELDS = ("task", "eval_metric", "acceptance_threshold", "held_out_eval_set", "sim2real_strategy")


def training_plan_completeness_check(plan: TrainingPlan) -> dict:
    """Is the training plan complete enough to be trainable-and-ratifiable?

    Every field in ``REQUIRED_FIELDS`` must be declared (non-empty strings; a positive, finite
    acceptance threshold). Returns ``{"missing", "ok"}`` where `missing` lists the undeclared fields.
    Declaring these BEFORE training is what makes the later acceptance honest — never a silent pass."""
    missing: list[str] = []
    for f in REQUIRED_FIELDS:
        value = getattr(plan, f)
        if f == "acceptance_threshold":
            # value > 0 rejects NaN (NaN > 0 is False); value < inf rejects infinity
            if not (isinstance(value, (int, float)) and value > 0.0 and value < float("inf")):
                missing.append(f)
        elif not (isinstance(value, str) and value.strip()):
            missing.append(f)
    return {"missing": missing, "ok": not missing}


def acceptance_gate(
    measured_success_rate: float,
    required_success_rate: float,
    n_eval_episodes: int,
    *,
    measured_safety_violations: int = 0,
    max_safety_violations: int = 0,
    sim2real_gap: float = 0.0,
    max_sim2real_gap: float = 1.0,
    min_eval_episodes: int = 30,
) -> dict:
    """Ratify a trained policy's MEASURED results against pre-declared acceptance criteria.

    Accepted (``ok``) only if the measured success rate clears the required one, the eval ran on at
    least `min_eval_episodes` episodes (a rate on too few rollouts is noise — n_eval_episodes is
    REQUIRED so a tiny sample cannot be ratified as a large one), the safety violations stay within
    budget, AND the sim-to-real gap is within tolerance — every condition set before training,
    checked after. Ratifies the GIVEN numbers; it does not validate their provenance (leakage,
    metric calibration — see the module honest boundary). Returns ``{"ok", "success_ok", "sample_ok",
    "safety_ok", "sim2real_ok", "n_eval_episodes", "success_margin"}``. Raises ValueError on rates
    outside [0, 1], non-positive episode counts, or negative violation/gap inputs."""
    for name, r in (("measured_success_rate", measured_success_rate),
                    ("required_success_rate", required_success_rate)):
        if not 0.0 <= r <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    if n_eval_episodes <= 0 or min_eval_episodes <= 0:
        raise ValueError("episode counts must be positive")
    if measured_safety_violations < 0 or max_safety_violations < 0:
        raise ValueError("safety violation counts must be non-negative")
    if sim2real_gap < 0.0 or max_sim2real_gap < 0.0:
        raise ValueError("sim-to-real gap and tolerance must be non-negative")

    success_ok = measured_success_rate >= required_success_rate
    sample_ok = n_eval_episodes >= min_eval_episodes
    safety_ok = measured_safety_violations <= max_safety_violations
    sim2real_ok = sim2real_gap <= max_sim2real_gap
    return {
        "ok": success_ok and sample_ok and safety_ok and sim2real_ok,
        "success_ok": success_ok, "sample_ok": sample_ok, "safety_ok": safety_ok,
        "sim2real_ok": sim2real_ok, "n_eval_episodes": n_eval_episodes,
        "success_margin": measured_success_rate - required_success_rate,
    }
