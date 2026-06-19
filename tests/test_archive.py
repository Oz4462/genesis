"""Tests for the MAP-Elites quality-diversity archive (discovery/archive.py).

Pins: only gate-PASSING candidates are admitted (the invariant), the higher-R² candidate wins its
cell, structurally distinct laws occupy distinct cells (diversity), and a real multi-problem discovery
run populates the archive with one elite per confirmed law. Offline, deterministic.
"""

from gen.discovery.archive import EliteArchive, descriptor_of
from gen.discovery.engine import Candidate


def _cand(exponents: dict[str, float], *, r2: float) -> Candidate:
    complexity = sum(1 for v in exponents.values() if abs(v) >= 1e-9)
    expr = "y = " + " * ".join(f"{n}^{v}" for n, v in exponents.items())
    return Candidate(
        expression=expr, exponents=dict(exponents), coefficient=1.0, r_squared=r2,
        rmse=0.0, complexity=complexity, dimension_ok=True, dimension_residual=0.0,
    )


def test_only_gate_passing_candidates_are_admitted():
    arc = EliteArchive()
    assert arc.add(_cand({"a": 1.5}, r2=1.0), passed=False) is False   # not gate-passing -> rejected
    assert arc.coverage == 0 and arc.best() is None


def test_higher_r2_replaces_the_cell_elite():
    arc = EliteArchive()
    assert arc.add(_cand({"a": 1.5, "b": -0.5}, r2=0.90), passed=True) is True
    assert arc.add(_cand({"a": 1.5, "b": -0.5}, r2=0.80), passed=True) is False  # same cell, worse fit
    assert arc.add(_cand({"a": 1.5, "b": -0.5}, r2=0.99), passed=True) is True   # same cell, better fit
    assert arc.coverage == 1 and arc.best().r_squared == 0.99


def test_structurally_distinct_laws_occupy_distinct_cells():
    arc = EliteArchive()
    arc.add(_cand({"a": 1.0}, r2=0.95), passed=True)
    arc.add(_cand({"a": 1.0, "b": 1.0}, r2=0.97), passed=True)     # different variable set -> new cell
    assert arc.coverage == 2


def test_descriptor_ignores_zero_exponents():
    assert descriptor_of(_cand({"a": 1.5, "b": 0.0}, r2=1.0)) == (1, frozenset({"a"}))


def test_add_result_populates_from_real_discovery():
    from gen.discovery.benchmark import ideal_gas_case, pendulum_case
    from gen.discovery.engine import discover_new_formulas

    arc = EliteArchive()
    for case in (pendulum_case(), ideal_gas_case()):
        arc.add_result(discover_new_formulas(case.problem))
    assert arc.coverage == 2                                       # two distinct confirmed laws
    assert arc.best() is not None and arc.best().r_squared > 0.99  # high-fit elite
    assert len(arc.elites()) == arc.coverage
