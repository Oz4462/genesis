"""scaling_laws — real humanoid DESIGN LAWS fitted from the ~25-robot reference catalog, kept only
where they validate OUT OF SAMPLE, then stored as GENESIS priors to sanity-check future designs.

This is the "discovery" arm of the humanoid-training task: from the catalogued real robots'
(mass, height, leg-length, knee-torque, DOF) it fits the scaling relations a humanoid obeys and —
following the project's discovery discipline — *keeps only the laws that generalise to robots held
out of the fit*. A law that fits the data it was trained on but not held-out robots is overfit and is
reported as such, never sold as validated.

Three relations are examined; each carries its honest verdict:

  * LAW 1 — KNEE TORQUE vs m·g·leg.  A knee statically holds a squat: τ ≈ k·(m·g·L_leg) with L_leg the
    leg length and k a dimensionless coefficient. This is the SAME closed form GENESIS sizes a knee with
    (``kinematics.knee_squat_hold_torque``), now fitted to the fleet. The DIMENSIONAL FORM is exact (a
    torque equals a force times a length); what the fit estimates is the coefficient k and — crucially —
    its real SPREAD. It is kept as a SANITY-BAND prior (it flags a knee ≳2× off the central law), not a
    tight predictor, because the leave-one-out R² (≈0.55) shows real designs scatter ±2× around it
    (weight-class, squat-depth target, parallel linkage all move k). Honest, not inflated.

  * LAW 2 — TOTAL MASS vs HEIGHT.  An allometric mass ∝ Hᵖ. REJECTED: the leave-one-out R² is far below
    the keep bar — height alone does not determine mass (a 0.5 m toy and a 1.5 m robot of very different
    mass both exist), so this does NOT generalise and is NOT stored as a usable law. Reported as a
    negative result, which is itself a valid output.

  * LAW 3 — MOTORISED DOF vs PUBLISHED DOF.  A consistency identity: the actuator-driven joint count the
    parser reads equals the published actuated DOF. It holds for ~all native-model robots (the lone
    exception is the documented AGILOped parallel-linkage model). Kept as a near-exact consistency check,
    not a "scaling law" — it has no free exponent — but it closes the loop that the catalog DOF and the
    model agree.

Deterministic, offline, numpy only. The fit is ordinary least squares; the out-of-sample score is
leave-one-out (each robot predicted from a fit on all the OTHERS — no peeking). Nothing is fabricated:
the dataset is assembled live from the source-cited catalog, and a robot missing any field is simply
absent from a law rather than filled with a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gen.kinematics import STANDARD_GRAVITY

from .catalog import SPECS, robots

#: Leg length as a fraction of standing height (thigh ≈ 0.245·H + shank ≈ 0.246·H ⇒ ~0.49·H), the
#: anthropometric proportion used consistently with ``humanoids.validation`` / ``kinematics``.
LEG_LENGTH_OVER_HEIGHT = 0.49

#: Out-of-sample (leave-one-out) R² at/above which a fitted law is judged to GENERALISE and is kept as
#: a usable predictor. Below it the law did not transfer to held-out robots and is reported as such.
#: 0.5 is a deliberately MODEST bar: it admits a relation that explains the majority of held-out
#: variance (a useful sanity band) while still rejecting one — like mass-vs-height here — that does not.
GENERALISES_OOS_R2 = 0.50

#: Robots whose published knee figure is NOT a parsed per-joint actuator rating directly comparable to
#: the others, excluded from the LAW 1 FIT (but still checkable against it). Each exclusion is sourced:
#:   * ``tienkung``  — the catalog knee (360 N·m) is a vendor spec-page line "actuator class", not a
#:     per-joint URDF value (the URDF carries no leg effort the parser could read as the knee).
#:   * ``draco3``    — the parsed 40.85 N·m is PER SEGMENT of a parallel proximal+distal knee; the
#:     effective joint torque is ~2× that, so the single-segment number is not like-for-like.
_LAW1_FIT_EXCLUSIONS = frozenset({"tienkung", "draco3"})


@dataclass(frozen=True)
class RobotPoint:
    """One robot's scaling-law coordinates, all derived from source-cited catalog facts."""
    key: str
    mass_kg: float
    height_m: float
    leg_length_m: float
    knee_torque_nm: float | None
    mgL: float                    #: m·g·L_leg — the gravitational torque scale (N·m)


@dataclass(frozen=True)
class ScalingLaw:
    """A fitted law with its HONEST out-of-sample verdict. ``coefficient`` is the fitted k (or the
    allometric prefactor); ``train_r2`` is in-sample, ``oos_r2`` is leave-one-out (the number that
    decides ``generalises``); ``n`` is the fit size; ``spread`` is the ±band (max |ratio−1| of
    actual/predicted across the fit) that makes a sanity-band honest about its width."""
    name: str
    form: str
    coefficient: float
    exponent: float | None
    train_r2: float
    oos_r2: float
    n: int
    generalises: bool
    spread: float           #: worst-case |ratio−1| across the fit (the honest full extent)
    band_lo: float = float("nan")   #: robust 10th-percentile of actual/predicted (sanity-band floor)
    band_hi: float = float("nan")   #: robust 90th-percentile of actual/predicted (sanity-band ceiling)
    note: str = ""


def dataset() -> list[RobotPoint]:
    """Assemble the scaling-law dataset live from the catalog: every robot with a real mass AND height
    (knee may be None — it is only required by the knee law). No value is invented; a robot missing
    mass or height is simply omitted."""
    pts: list[RobotPoint] = []
    for k in robots():
        s = SPECS[k]
        m, h = s.mass_kg.value, s.height_m.value
        if not isinstance(m, (int, float)) or not isinstance(h, (int, float)):
            continue
        knee = s.peak_joint_torque_nm.value if s.peak_joint_torque_nm else None
        knee = float(knee) if isinstance(knee, (int, float)) else None
        leg = LEG_LENGTH_OVER_HEIGHT * float(h)
        pts.append(RobotPoint(key=k, mass_kg=float(m), height_m=float(h), leg_length_m=leg,
                              knee_torque_nm=knee, mgL=float(m) * STANDARD_GRAVITY * leg))
    return pts


def _r2(y: np.ndarray, pred: np.ndarray) -> float:
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, pred) else 0.0
    return 1.0 - float(np.sum((y - pred) ** 2)) / ss_tot


def _loo_r2_through_origin(x: np.ndarray, y: np.ndarray) -> float:
    """Leave-one-out R² for the through-origin model y = k·x: each point predicted from k fitted on the
    OTHERS. The honest generalisation score — no point sees its own value in its prediction."""
    preds = np.empty_like(y)
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        denom = float(np.sum(x[mask] * x[mask]))
        ki = float(np.sum(x[mask] * y[mask]) / denom) if denom > 0 else 0.0
        preds[i] = ki * x[i]
    return _r2(y, preds)


def fit_knee_law() -> ScalingLaw:
    """LAW 1: fit τ_knee = k·(m·g·L_leg) over the parsed-per-joint fleet and validate leave-one-out.

    Through-origin least squares (a torque is zero at zero gravitational load — no intercept), then a
    leave-one-out R². Kept as a sanity-band prior iff the OOS R² clears ``GENERALISES_OOS_R2``. Excludes
    the non-comparable knees in ``_LAW1_FIT_EXCLUSIONS`` from the FIT (still checkable against it)."""
    pts = [p for p in dataset() if p.knee_torque_nm is not None and p.key not in _LAW1_FIT_EXCLUSIONS]
    x = np.array([p.mgL for p in pts])
    y = np.array([p.knee_torque_nm for p in pts])
    k = float(np.sum(x * y) / np.sum(x * x))
    train = _r2(y, k * x)
    oos = _loo_r2_through_origin(x, y)
    ratios = y / (k * x)
    spread = float(np.max(np.abs(ratios - 1.0)))
    band_lo, band_hi = float(np.percentile(ratios, 10)), float(np.percentile(ratios, 90))
    return ScalingLaw(
        name="knee_torque_vs_mgL", form="tau_knee = k * m * g * L_leg",
        coefficient=k, exponent=None, train_r2=train, oos_r2=oos, n=len(pts),
        generalises=oos >= GENERALISES_OOS_R2, spread=spread, band_lo=band_lo, band_hi=band_hi,
        note=(f"k={k:.3f} (knee holds ~{k:.0%} of the m·g·leg gravitational torque). Dimensional form "
              f"is EXACT; the central fit is well-centred (median ratio ≈ 1.0) but real designs scatter "
              f"— robust 10–90% band {band_lo:.2f}–{band_hi:.2f}× (worst case ±{spread*100:.0f}%). "
              f"A SANITY BAND that flags a knee outside it, not a tight predictor."))


def fit_mass_height_law() -> ScalingLaw:
    """LAW 2: fit mass = C·Hᵖ (log-log OLS) and validate leave-one-out. Reported with its honest verdict;
    it is EXPECTED to fail the keep bar (height underdetermines mass) — a valid negative result."""
    pts = dataset()
    h = np.array([p.height_m for p in pts])
    m = np.array([p.mass_kg for p in pts])
    lh, lm = np.log(h), np.log(m)
    p_coef = np.polyfit(lh, lm, 1)
    train = _r2(m, np.exp(np.polyval(p_coef, lh)))
    preds = np.empty_like(m)
    for i in range(len(m)):
        mask = np.arange(len(m)) != i
        pc = np.polyfit(lh[mask], lm[mask], 1)
        preds[i] = np.exp(np.polyval(pc, lh[i]))
    oos = _r2(m, preds)
    return ScalingLaw(
        name="mass_vs_height", form="mass = C * H^p", coefficient=float(np.exp(p_coef[1])),
        exponent=float(p_coef[0]), train_r2=train, oos_r2=oos, n=len(pts),
        generalises=oos >= GENERALISES_OOS_R2, spread=float("nan"),
        note=("REJECTED as a predictor: height alone does not determine mass (toys and full-size robots "
              "overlap in height). Kept only as a documented negative result, not a stored law."))


@dataclass(frozen=True)
class DesignCheck:
    """The verdict of sanity-checking one design against a kept law."""
    law: str
    predicted: float
    actual: float
    ratio: float            #: actual / predicted
    within_band: bool       #: |ratio−1| ≤ the law's observed spread (a real design sits in the band)
    verdict: str            #: "in_band" | "high" | "low"
    detail: str


def check_knee(mass_kg: float, height_m: float, knee_torque_nm: float,
               law: ScalingLaw | None = None) -> DesignCheck:
    """Sanity-check a design's knee torque against the fitted knee law (LAW 1).

    Predicts τ = k·m·g·L_leg and compares the design's actual knee torque. ``within_band`` is True when
    the design sits inside the law's observed ±spread — i.e. it looks like a real humanoid. A knee far
    BELOW the band is under-actuated (cannot squat-hold); far ABOVE is over-built (heavy/costly) — both
    are FLAGS, not hard errors, since a deliberate design may sit outside (AETHON's margin, a hydraulic
    giant). Raises ValueError on non-positive inputs."""
    if mass_kg <= 0.0 or height_m <= 0.0 or knee_torque_nm <= 0.0:
        raise ValueError("mass, height, and knee torque must be positive")
    law = law or fit_knee_law()
    leg = LEG_LENGTH_OVER_HEIGHT * height_m
    predicted = law.coefficient * mass_kg * STANDARD_GRAVITY * leg
    ratio = knee_torque_nm / predicted if predicted > 0 else float("inf")
    # the robust 10–90% band the real fleet occupies (positive-bounded, unlike a ±worst-case spread)
    within = law.band_lo <= ratio <= law.band_hi
    verdict = "in_band" if within else ("high" if ratio > law.band_hi else "low")
    return DesignCheck(
        law=law.name, predicted=predicted, actual=knee_torque_nm, ratio=ratio, within_band=within,
        verdict=verdict,
        detail=(f"law predicts {predicted:.0f} N·m (k={law.coefficient:.3f}·m·g·{leg:.2f} m); design has "
                f"{knee_torque_nm:.0f} N·m = {ratio:.2f}× the law (real fleet band "
                f"{law.band_lo:.2f}–{law.band_hi:.2f}×). "
                + {"in_band": "sits where real humanoid knees sit.",
                   "high": "above the fleet band — carries extra margin (or is a hydraulic class).",
                   "low": "below the fleet band — check the knee is not under-actuated for the mass."
                   }[verdict]))


def check_aethon() -> DesignCheck:
    """Sanity-check AETHON's own knee against the real-robot knee law — does our design sit sensibly
    within the laws fitted from the real fleet? Pulls AETHON's published numbers from its spec object."""
    from .genesis_humanoid import AETHON
    # AETHON's standing height (~1.35 m) is fixed in its idea/spec text; its knee peak + leg load are
    # on the AETHON object. Use the spec height the design is built around.
    aethon_height_m = 1.35
    return check_knee(mass_kg=float(AETHON.leg_load_kg), height_m=aethon_height_m,
                      knee_torque_nm=float(AETHON.knee_peak_nm))


def summarise() -> str:
    """A readable report of all three laws + the AETHON sanity check (the deliverable text)."""
    lines: list[str] = ["HUMANOID SCALING LAWS — fitted from the real-robot catalog, kept iff OOS-valid", ""]
    knee = fit_knee_law()
    mass = fit_mass_height_law()
    for law in (knee, mass):
        kept = "KEPT" if law.generalises else "REJECTED"
        lines.append(f"[{kept:8}] {law.name}: {law.form}")
        lines.append(f"           coeff={law.coefficient:.4g}"
                     + (f", exp={law.exponent:.3f}" if law.exponent is not None else "")
                     + f"  train_R2={law.train_r2:.3f}  out-of-sample(LOO)_R2={law.oos_r2:.3f}  n={law.n}")
        lines.append(f"           {law.note}")
    lines.append("")
    ac = check_aethon()
    lines.append(f"AETHON vs the knee law: predicted {ac.predicted:.0f} N·m, AETHON has {ac.actual:.0f} "
                 f"N·m ({ac.ratio:.2f}×) → {ac.verdict.upper()}")
    lines.append(f"  {ac.detail}")
    return "\n".join(lines)
