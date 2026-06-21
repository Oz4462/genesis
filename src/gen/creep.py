"""Creep and creep-rupture — slow time-dependent failure at high temperature (closed form).

The stress check (structural.py) compares a peak stress to a strength at ROOM
temperature; fatigue.py adds cyclic failure below that strength. Neither sees a third,
slower lifetime axis: a part held under a STEADY load far below yield, but HOT, slowly
and continuously deforms (creep) and eventually ruptures after enough time at
temperature. A turbine blade, a boiler tube, a bolt in a hot flange: each can pass every
room-temperature stress check and still rupture months or years later purely because it
ran hot under load. This module adds that check — invisible to any isothermal,
room-temperature analysis.

Three textbook closed forms:
  • the LARSON-MILLER PARAMETER LMP = T·(C + log10(t_r)) — the time-temperature
    equivalence that collapses many (stress, temperature, rupture-time) data points onto
    a single master curve, so a short hot test predicts long-life behavior (Larson &
    Miller 1952). C ≈ 20 for many steels.
  • its EXACT INVERSE t_r = 10^(LMP/T − C) — given the LMP a material's master curve
    reports at the applied stress, the rupture time at the service temperature.
  • the NORTON power law ε̇ = A·σ^n·exp(−Q/RT) — the secondary (steady-state) creep
    strain rate: a power law in stress (exponent n, typically 3-8) times an Arrhenius
    factor in temperature (activation energy Q) (Norton 1929).

Plus a DFM-style life check: given the LMP the material reports at the applied stress,
compute the rupture time and compare it to the design life.

Auto-selected via physics_selection RECIPE "creep-rupture life" (validator="creep", trigger="creep.design_life") when "creep.design_life" measurand present; invoked via gate_delta_physics in pipeline.

Verified, not asserted: LMP and its inverse round-trip EXACTLY (t_r → LMP → t_r), the
Norton rate scales as (σ2/σ1)^n with stress and follows the exact Arrhenius ratio in
temperature, and the concrete anchor T=811 K (~1000 °F), t_r=1e5 h, C=20 gives
LMP=20275 — all pinned in the test.

Units: stress in MPa, temperature in KELVIN, time in HOURS, activation energy Q in
J/mol, R = 8.314 J/(mol·K); A carries whatever units make ε̇ come out per the chosen
time base (the Norton constant is material/fit-specific). Honest boundary: these are the
classic engineering correlations for SECONDARY (steady-state) creep and rupture
extrapolation. They do NOT model primary (transient) or tertiary (accelerating, damage)
creep, multiaxial stress states, oxidation/environmental attack, or microstructural
change — and the Larson-Miller constant C and the master-curve LMP(σ) come from real
material rupture data (this module computes WITH them, it does not invent them).
"""

from __future__ import annotations

import math


def larson_miller_parameter(
    temperature_K: float, rupture_time_hours: float, constant_C: float = 20.0
) -> float:
    """Larson-Miller parameter LMP = T·(C + log10(t_r)), T in Kelvin, t_r in hours.

    The time-temperature equivalence (Larson & Miller 1952) that maps a rupture time at
    a temperature onto a single parameter; a material's master curve gives LMP as a
    function of applied stress. Raises ValueError on a non-positive temperature or
    rupture time (log10 of a non-positive time is undefined; absolute temperature must
    be positive).
    """
    if temperature_K <= 0.0:
        raise ValueError("temperature must be positive (absolute Kelvin)")
    if rupture_time_hours <= 0.0:
        raise ValueError("rupture time must be positive (hours)")
    return temperature_K * (constant_C + math.log10(rupture_time_hours))


def rupture_time_from_lmp(
    lmp: float, temperature_K: float, constant_C: float = 20.0
) -> float:
    """Rupture time t_r = 10^(LMP/T − C) [hours] — the exact inverse of
    `larson_miller_parameter`.

    Given the LMP a material's master curve reports at the applied stress, the predicted
    rupture time at the service temperature `temperature_K` (Kelvin). Raises ValueError
    on a non-positive temperature.
    """
    if temperature_K <= 0.0:
        raise ValueError("temperature must be positive (absolute Kelvin)")
    return 10.0 ** (lmp / temperature_K - constant_C)


def norton_creep_rate(
    stress: float,
    A: float,
    n: float,
    Q_activation: float,
    temperature_K: float,
    R: float = 8.314,
) -> float:
    """Norton-law secondary creep strain rate ε̇ = A·σ^n·exp(−Q/RT) (Norton 1929).

    Power law in stress (exponent `n`, typically 3-8 for metals) times an Arrhenius
    factor in temperature (activation energy `Q_activation` in J/mol). σ in MPa, T in
    Kelvin; `A` carries whatever units make ε̇ come out per the chosen time base. Returns
    the steady-state (secondary) strain rate. Raises ValueError on a non-positive stress
    (σ^n is undefined for σ≤0 with a fractional n) or a non-positive temperature.
    """
    if stress <= 0.0:
        raise ValueError("stress must be positive (MPa)")
    if temperature_K <= 0.0:
        raise ValueError("temperature must be positive (absolute Kelvin)")
    return A * stress ** n * math.exp(-Q_activation / (R * temperature_K))


def creep_life_check(
    applied_stress: float,
    temperature_K: float,
    design_life_hours: float,
    lmp_at_stress: float,
    constant_C: float = 20.0,
) -> dict:
    """Creep-rupture life check at high temperature.

    `lmp_at_stress` is the Larson-Miller parameter the material's master curve reports at
    `applied_stress` (MPa); from it the rupture time at `temperature_K` (Kelvin) is
    t_r = 10^(LMP/T − C). Returns ``{"rupture_time", "design_life", "safety_factor",
    "ok"}``: safety_factor = rupture_time / design_life, ok = safety_factor ≥ 1 (the part
    is predicted to outlast its design life). `applied_stress` is carried for
    traceability — the LMP already encodes the stress dependence. Deterministic. Raises
    ValueError on a non-positive temperature or a non-positive design life.
    """
    if design_life_hours <= 0.0:
        raise ValueError("design life must be positive (hours)")
    rupture_time = rupture_time_from_lmp(lmp_at_stress, temperature_K, constant_C)
    return {
        "applied_stress": applied_stress,
        "rupture_time": rupture_time,
        "design_life": design_life_hours,
        "safety_factor": rupture_time / design_life_hours,
        "ok": rupture_time >= design_life_hours,
    }
