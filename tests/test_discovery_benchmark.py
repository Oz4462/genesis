"""Rediscovery benchmark + Red-Team — the honest capability proof (build doc Phase 4)."""

from gen.discovery import rediscovery_benchmark, kepler_case, ideal_gas_case
from gen.discovery.benchmark import (
    newton_gravity_case, redteam_impossible_case, redteam_offset_case,
    rediscovery_benchmark as run_bench,
)
from gen.discovery import discover_new_formulas


def test_rediscovers_all_three_known_laws_and_catches_all_red_team():
    report = rediscovery_benchmark()
    assert report.rediscovery_rate == 1.0, [r for r in report.results if not r.success]
    assert report.redteam_catch_rate == 1.0
    assert report.n_pass == report.n_total


def test_kepler_ideal_gas_newton_each_rediscovered_with_textbook_exponents():
    for case in (kepler_case(), ideal_gas_case(), newton_gravity_case()):
        result = discover_new_formulas(case.problem)
        assert result.validated, f"{case.name} not validated"
        best = result.validated[0]
        assert best.verdict == "bestaetigt"
        for name, exp in case.expected_exponents.items():
            assert abs(best.candidate.exponents.get(name, 0.0) - exp) < 0.05, (case.name, name)


def test_red_team_impossible_dimension_is_widerlegt():
    result = discover_new_formulas(redteam_impossible_case().problem)
    assert result.validated == ()
    assert all(r.verdict == "widerlegt" for r in result.all_records)


def test_red_team_hidden_additive_term_is_not_falsely_confirmed():
    """Right dimension, wrong physics: v = g·t + v0. The pure power law must NOT be
    'bestaetigt' just because it is dimensionally allowed — the fit gate keeps it honest."""
    result = discover_new_formulas(redteam_offset_case().problem)
    assert result.validated == ()                          # not confirmed
    assert all(r.verdict != "bestaetigt" for r in result.all_records)


def test_benchmark_report_is_structured():
    report = run_bench()
    assert report.n_total == 6                      # Kepler, ideal gas, Newton, pendulum + 2 red-team
    names = {r.name for r in report.results}
    assert {"Kepler III", "Pendulum period", "Red-team: impossible dimension"} <= names
