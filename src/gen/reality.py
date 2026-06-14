"""Phase δ⁺ — the reality proof (HORIZON.md §2B).

GENESIS designs a falsification experiment for a COMPUTED prediction, then ingests a
REAL measurement and decides — deterministically — whether the prediction is empirically
CORROBORATED (measurement within the acceptance band) or REFUTED (outside it → re-specify),
or INCONCLUSIVE (the measurement cannot even be compared: wrong/unparseable unit). The
verdict is never asserted by a model; it is computed here from the numbers, with a
dimensional-homogeneity guard (the Mars-Climate-Orbiter failure class).

`gate_delta_plus` is the honest-process gate: it does NOT fail on refutation (an honest
"widerlegt" is a valid outcome) — it fails only when the inputs are illegitimate: an
ungrounded experiment, or a measurement without retrieved provenance (a fabricated number).

Pure, deterministic, LLM-free. Same inputs -> same verdict (reproducibility A5).
"""

from __future__ import annotations

from collections.abc import Sequence

from .core.errors import UnitError
from .core.interfaces import GateFailure, GateResult
from .core.state import (
    Claim,
    EmpiricalStatus,
    EmpiricalVerdict,
    FalsificationExperiment,
    Measurement,
)
from .verification.units import parse_unit, unit_scale


def _inconclusive(detail: str) -> EmpiricalVerdict:
    return EmpiricalVerdict(
        status=EmpiricalStatus.INCONCLUSIVE, residual=float("nan"),
        within_tolerance=False, detail=detail,
    )


def evaluate_reality(
    experiment: FalsificationExperiment, measurement: Measurement
) -> EmpiricalVerdict:
    """Compare a real measurement to the experiment's prediction, dimension-safe.

    CORROBORATED iff |measured − predicted| <= tolerance after converting the measurement
    into the predicted unit; REFUTED if outside; INCONCLUSIVE if the units are of different
    dimension or cannot be scaled (never silently compare incommensurable quantities).
    """
    try:
        pred_dim = parse_unit(experiment.predicted_unit)
        meas_dim = parse_unit(measurement.unit)
    except UnitError as exc:
        return _inconclusive(f"unparseable unit: {exc}")
    if pred_dim != meas_dim:
        return _inconclusive(
            f"unit dimension mismatch: predicted {experiment.predicted_unit!r} vs "
            f"measured {measurement.unit!r}"
        )
    pred_scale = unit_scale(experiment.predicted_unit)
    meas_scale = unit_scale(measurement.unit)
    if pred_scale is None or meas_scale is None or pred_scale == 0:
        return _inconclusive("unit cannot be scaled to SI")

    measured_in_pred_unit = measurement.value * meas_scale / pred_scale
    residual = abs(measured_in_pred_unit - experiment.predicted_value)
    within = residual <= experiment.tolerance
    status = EmpiricalStatus.CORROBORATED if within else EmpiricalStatus.REFUTED
    detail = (
        f"measured={measured_in_pred_unit:.6g} {experiment.predicted_unit}, "
        f"predicted={experiment.predicted_value:.6g}, residual={residual:.6g}, "
        f"tolerance={experiment.tolerance:.6g}"
    )
    return EmpiricalVerdict(status=status, residual=residual, within_tolerance=within, detail=detail)


def gate_delta_plus(
    experiment: FalsificationExperiment,
    measurement: Measurement,
    claims: Sequence[Claim],
) -> GateResult:
    """GATE δ⁺ — the honest-process predicate for a reality proof.

    Ensures the reality check itself is legitimate (HORIZON.md §2B):
      DR-1 GROUNDING_UNKNOWN_CLAIM — every experiment grounding id exists in the ledger.
      DR-2 UNSOURCED_MEASUREMENT   — the measurement carries provenance (backstop).
      DR-3 DEAD_MEASUREMENT_SOURCE — every measurement source was actually retrieved.
      DR-4 EXPERIMENT_MISMATCH     — the measurement belongs to this experiment.

    It does NOT fail on REFUTED/INCONCLUSIVE verdicts: an honest "refuted" is a valid
    outcome (re-specify), not a gate failure. Pure; no model calls.
    """
    failures: list[GateFailure] = []
    claim_ids = {c.id for c in claims}

    for cid in experiment.grounding:
        if cid not in claim_ids:
            failures.append(
                GateFailure(
                    code="GROUNDING_UNKNOWN_CLAIM",
                    detail=f"experiment {experiment.id!r} grounds in unknown claim {cid!r}.",
                    claim_id=cid,
                )
            )

    if measurement.experiment_id != experiment.id:
        failures.append(
            GateFailure(
                code="EXPERIMENT_MISMATCH",
                detail=(
                    f"measurement {measurement.id!r} is for experiment "
                    f"{measurement.experiment_id!r}, not {experiment.id!r}."
                ),
            )
        )

    if not measurement.sources:  # constructor guards; gate backstops
        failures.append(
            GateFailure(code="UNSOURCED_MEASUREMENT",
                        detail=f"measurement {measurement.id!r} has no source.")
        )
    for ref in measurement.sources:
        if not ref.retrieved:
            failures.append(
                GateFailure(
                    code="DEAD_MEASUREMENT_SOURCE",
                    detail=(
                        f"measurement {measurement.id!r} cites a non-retrieved source "
                        f"{ref.url_or_id!r} — a measurement must be a real reading."
                    ),
                )
            )

    return GateResult(gate="delta_plus", passed=not failures, failures=failures)


__all__ = ["evaluate_reality", "gate_delta_plus"]
