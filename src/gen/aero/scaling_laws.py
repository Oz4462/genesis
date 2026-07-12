"""scaling_laws — real drone DESIGN LAWS fitted from the catalogued fleet, kept only OUT-OF-SAMPLE.

The discovery arm of the drone-training task (the flight analog of ``gen.humanoids.scaling_laws``).
From the catalogued real drones' sourced facts (mass, prop diameter, battery-Wh, hover/flight time) it
fits the scaling relations a multirotor obeys and — following the project's discovery discipline —
KEEPS ONLY the laws that generalise to drones held out of the fit (leave-one-out). A law that fits its
own training data but not held-out drones is overfit and is reported as REJECTED, never sold as valid.

Four relations are examined; each carries its honest verdict:

  * LAW A — ENDURANCE vs SPECIFIC ENERGY.  Hover endurance t ≈ k·(E_battery / m): the usable battery
    energy per unit mass sets how long a multirotor stays up (more Wh per kg → longer hover). The
    DIMENSIONAL form is sound (Wh/kg has units of energy/mass; ÷ a specific-power gives time). The fit
    estimates the slope k = (battery-Wh / mass) → minutes and validates leave-one-out across the
    consumer/cinematic fleet (all publish Wh + mass + a hover/forward time). Kept iff it generalises.

  * LAW B — PROP DIAMETER vs MASS.  To keep disk loading bounded, prop area must grow with weight, so
    for a fixed rotor count D ∝ m^p with p≈0.5 (area ∝ mass). Fitted log-log over the drones with a
    sourced prop diameter, validated leave-one-out. The exponent itself is the discovery (is it ~0.5?).

  * LAW C — BATTERY ENERGY vs MASS.  How much battery a drone carries scales with its take-off mass:
    E_battery ∝ m^p. Fitted log-log, validated leave-one-out. A near-linear p (≈1) would say battery
    is a roughly constant FRACTION of mass across the fleet — a genuinely useful design prior if it
    holds out of sample.

  * LAW D — HOVER THRUST vs MASS.  τ_hover = m·g — a dimensional IDENTITY (the whole craft must lift
    its weight), kept as a near-exact CONSISTENCY check (no free exponent), the analog of the humanoid
    DOF-consistency law. It closes the loop that the catalogued max-thrust always exceeds m·g.

Deterministic, offline, numpy only. The fit is ordinary least squares; the out-of-sample score is
leave-one-out (each drone predicted from a fit on all the OTHERS — no peeking). Nothing is fabricated:
the dataset is assembled live from the source-cited catalog, and a drone missing a field is simply
absent from a law rather than filled with a guess. Fixed-wing drones are EXCLUDED from the hover-driven
laws (A, D) — they do not hover — but included where the relation is airframe-general (B prop/mass is
multirotor-only by nature; C battery/mass can include any electric UAV with a sourced battery).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .drone_catalog import SPECS, drones, multirotors

#: Out-of-sample (leave-one-out) R² at/above which a fitted law is judged to GENERALISE and is kept as
#: a usable predictor. Below it the law did not transfer to held-out drones and is reported as such.
#: 0.5 matches the humanoid module's deliberately MODEST bar (admits a relation explaining the majority
#: of held-out variance, still rejects one that does not).
GENERALISES_OOS_R2 = 0.50

#: Standard gravity [m/s²] (CGPM), for the hover-thrust identity (LAW D).
STANDARD_GRAVITY = 9.80665

#: LiPo usable fraction (matches flight.LIPO_USABLE_FRACTION) — used to turn battery-Wh into the
#: USABLE energy the endurance law is really driven by.
LIPO_USABLE_FRACTION = 0.8


@dataclass(frozen=True)
class DronePoint:
    """One drone's scaling-law coordinates, all derived from source-cited catalog facts (or None)."""
    key: str
    klass: str
    mass_kg: float
    prop_diameter_m: float | None
    battery_wh: float | None
    flight_time_min: float | None
    hovers: bool                  #: True for multirotors (the hover-driven laws apply), False fixed-wing


@dataclass(frozen=True)
class ScalingLaw:
    """A fitted law with its HONEST out-of-sample verdict (mirrors humanoids.scaling_laws.ScalingLaw).
    ``coefficient`` is the fitted prefactor/slope; ``exponent`` the log-log power (None for a linear/
    through-origin slope law); ``train_r2`` in-sample, ``oos_r2`` leave-one-out (decides ``generalises``);
    ``n`` the fit size; ``band_lo``/``band_hi`` the robust 10–90 % actual/predicted band (honest width)."""
    name: str
    form: str
    coefficient: float
    exponent: float | None
    train_r2: float
    oos_r2: float
    n: int
    generalises: bool
    band_lo: float = float("nan")
    band_hi: float = float("nan")
    note: str = ""


def dataset() -> list[DronePoint]:
    """Assemble the scaling-law dataset live from the catalog: every drone with a confirmed mass; the
    other fields are None where the catalog has an honest gap (a law simply omits a None it needs)."""
    pts: list[DronePoint] = []
    hover_keys = set(multirotors())
    for k in drones():
        s = SPECS[k]
        m = s.mass_kg.value
        if not isinstance(m, (int, float)):
            continue
        pd = s.prop_diameter_m.value if s.prop_diameter_m.known else None
        wh = s.battery_wh.value if s.battery_wh.known else None
        ft = s.max_flight_time_min.value if s.max_flight_time_min.known else None
        pts.append(DronePoint(
            key=k, klass=s.klass, mass_kg=float(m),
            prop_diameter_m=float(pd) if isinstance(pd, (int, float)) else None,
            battery_wh=float(wh) if isinstance(wh, (int, float)) else None,
            flight_time_min=float(ft) if isinstance(ft, (int, float)) else None,
            hovers=(k in hover_keys),
        ))
    return pts


def _r2(y: np.ndarray, pred: np.ndarray) -> float:
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    if ss_tot <= 0.0:
        return 1.0 if np.allclose(y, pred) else 0.0
    return 1.0 - float(np.sum((y - pred) ** 2)) / ss_tot


def _loo_r2_through_origin(x: np.ndarray, y: np.ndarray) -> float:
    """Leave-one-out R² for y = k·x (each point predicted from k fitted on the OTHERS)."""
    preds = np.empty_like(y, dtype=float)
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        denom = float(np.sum(x[mask] * x[mask]))
        ki = float(np.sum(x[mask] * y[mask]) / denom) if denom > 0 else 0.0
        preds[i] = ki * x[i]
    return _r2(y, preds)


def _loo_r2_loglog(x: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    """Leave-one-out R² (in LINEAR space) for the power law y = C·x^p fitted by log-log OLS.
    Returns (oos_r2, per-point predictions). No point sees its own value in its prediction."""
    lx, ly = np.log(x), np.log(y)
    preds = np.empty_like(y, dtype=float)
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        pc = np.polyfit(lx[mask], ly[mask], 1)
        preds[i] = float(np.exp(np.polyval(pc, lx[i])))
    return _r2(y, preds), preds


def _band(ratios: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(ratios, 10)), float(np.percentile(ratios, 90))


def fit_endurance_law() -> ScalingLaw:
    """LAW A: hover endurance t ≈ k·(usable battery-Wh / mass), through-origin, validated leave-one-out.

    Driven by the USABLE energy (Wh × LiPo fraction) per kg — the specific-energy a multirotor trades
    for hover time. Multirotors only (fixed-wing 'endurance' is cruise, excluded). Kept iff OOS R² ≥
    the bar."""
    pts = [p for p in dataset()
           if p.hovers and p.battery_wh is not None and p.flight_time_min is not None]
    x = np.array([p.battery_wh * LIPO_USABLE_FRACTION / p.mass_kg for p in pts])   # usable Wh/kg
    y = np.array([p.flight_time_min for p in pts])
    k = float(np.sum(x * y) / np.sum(x * x))
    train = _r2(y, k * x)
    oos = _loo_r2_through_origin(x, y)
    ratios = y / (k * x)
    lo, hi = _band(ratios)
    return ScalingLaw(
        name="endurance_vs_specific_energy", form="t_hover[min] = k * (usable_Wh / mass)",
        coefficient=k, exponent=None, train_r2=train, oos_r2=oos, n=len(pts),
        generalises=oos >= GENERALISES_OOS_R2, band_lo=lo, band_hi=hi,
        note=(f"k={k:.3f} min per (usable Wh/kg). A multirotor flies ~{k:.1f} min for each usable "
              f"Wh-per-kg it carries. Robust 10–90% band {lo:.2f}–{hi:.2f}× (efficiency/disk-loading "
              f"spread). {'Generalises out-of-sample → KEPT as a sizing prior.' if oos >= GENERALISES_OOS_R2 else 'Does NOT generalise → rejected.'}"))


def fit_prop_mass_law() -> ScalingLaw:
    """LAW B: prop diameter D = C·m^p (log-log OLS), validated leave-one-out. The exponent is the
    discovery — disk-loading-bounded design predicts p≈0.5 (area ∝ weight) for a fixed rotor count."""
    pts = [p for p in dataset() if p.prop_diameter_m is not None]
    x = np.array([p.mass_kg for p in pts])
    y = np.array([p.prop_diameter_m for p in pts])
    pc = np.polyfit(np.log(x), np.log(y), 1)
    train = _r2(y, np.exp(np.polyval(pc, np.log(x))))
    oos, _ = _loo_r2_loglog(x, y)
    ratios = y / np.exp(np.polyval(pc, np.log(x)))
    lo, hi = _band(ratios)
    return ScalingLaw(
        name="prop_diameter_vs_mass", form="D_prop = C * mass^p", coefficient=float(np.exp(pc[1])),
        exponent=float(pc[0]), train_r2=train, oos_r2=oos, n=len(pts),
        generalises=oos >= GENERALISES_OOS_R2, band_lo=lo, band_hi=hi,
        note=(f"C={np.exp(pc[1]):.3f}, p={pc[0]:.3f} (disk-loading-bounded design predicts p≈0.5: prop "
              f"AREA ∝ weight). Robust 10–90% band {lo:.2f}–{hi:.2f}×. "
              f"{'Generalises → KEPT.' if oos >= GENERALISES_OOS_R2 else 'Does NOT generalise → rejected.'}"))


def fit_battery_mass_law() -> ScalingLaw:
    """LAW C: battery energy E = C·m^p (log-log OLS), validated leave-one-out. A near-linear p≈1 would
    mean battery is a roughly constant fraction of take-off mass across the fleet (any electric UAV with
    a sourced battery-Wh is included — this relation is airframe-general, not hover-specific)."""
    pts = [p for p in dataset() if p.battery_wh is not None]
    x = np.array([p.mass_kg for p in pts])
    y = np.array([p.battery_wh for p in pts])
    pc = np.polyfit(np.log(x), np.log(y), 1)
    train = _r2(y, np.exp(np.polyval(pc, np.log(x))))
    oos, _ = _loo_r2_loglog(x, y)
    ratios = y / np.exp(np.polyval(pc, np.log(x)))
    lo, hi = _band(ratios)
    return ScalingLaw(
        name="battery_energy_vs_mass", form="E_battery[Wh] = C * mass^p", coefficient=float(np.exp(pc[1])),
        exponent=float(pc[0]), train_r2=train, oos_r2=oos, n=len(pts),
        generalises=oos >= GENERALISES_OOS_R2, band_lo=lo, band_hi=hi,
        note=(f"C={np.exp(pc[1]):.3f}, p={pc[0]:.3f} (p≈1 ⇒ battery a ~constant fraction of mass). "
              f"Robust 10–90% band {lo:.2f}–{hi:.2f}×. "
              f"{'Generalises → KEPT.' if oos >= GENERALISES_OOS_R2 else 'Does NOT generalise → rejected.'}"))


def hover_thrust_identity() -> ScalingLaw:
    """LAW D: hover thrust τ = m·g — a dimensional IDENTITY (every drone lifts its own weight), kept as
    a near-exact consistency check that the catalogued max-thrust always exceeds the hover demand."""
    pts = [p for p in dataset() if p.hovers]
    # consistency: for drones with a sourced max thrust, max_thrust ≥ m·g must hold (T/W ≥ 1)
    checked = 0
    ok = 0
    for p in pts:
        mt = SPECS[p.key].max_total_thrust_n
        if mt and mt.known and isinstance(mt.value, (int, float)):
            checked += 1
            ok += int(float(mt.value) >= STANDARD_GRAVITY * p.mass_kg)
    frac = (ok / checked) if checked else float("nan")
    return ScalingLaw(
        name="hover_thrust_identity", form="tau_hover = m * g  (T/W >= 1 must hold)",
        coefficient=STANDARD_GRAVITY, exponent=1.0, train_r2=1.0, oos_r2=1.0,
        n=checked, generalises=True,
        note=(f"Dimensional identity (no free parameter): every hovering drone must produce at least "
              f"its own weight. {ok}/{checked} catalogued drones with a sourced max-thrust clear T/W≥1 "
              f"({frac:.0%}) — the loop-closing consistency check."))


def summarise() -> str:
    """A readable report of all four laws (the discovery deliverable text)."""
    lines: list[str] = ["DRONE SCALING LAWS — fitted from the real-drone catalog, kept iff OOS-valid", ""]
    for law in (fit_endurance_law(), fit_prop_mass_law(), fit_battery_mass_law(), hover_thrust_identity()):
        kept = "KEPT" if law.generalises else "REJECTED"
        lines.append(f"[{kept:8}] {law.name}: {law.form}")
        lines.append(f"           coeff={law.coefficient:.4g}"
                     + (f", exp={law.exponent:.3f}" if law.exponent is not None else "")
                     + f"  train_R2={law.train_r2:.3f}  out-of-sample(LOO)_R2={law.oos_r2:.3f}  n={law.n}")
        lines.append(f"           {law.note}")
    return "\n".join(lines)
