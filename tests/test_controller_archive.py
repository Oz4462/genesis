"""Tests that the ExplorationController now yields a MAP-Elites archive of its confirmed laws.

Pins the wiring: running a campaign through the controller collects each gate-confirmed law into a
quality-diversity archive (one elite per distinct form), alongside the existing graph. Offline,
deterministic.
"""

from gen.discovery.benchmark import ideal_gas_case, kepler_case, pendulum_case
from gen.discovery.controller import ExplorationController


def _problems():
    return [kepler_case().problem, ideal_gas_case().problem, pendulum_case().problem]


def test_controller_run_populates_a_quality_diversity_archive():
    result = ExplorationController(tier="fast").run(_problems())
    assert result.archive.coverage == 3                     # three structurally distinct confirmed laws
    assert result.archive.best() is not None and result.archive.best().r_squared > 0.99
    # the archive is consistent with the graph having completed all three problems
    assert len(result.completed) == 3


def test_controller_archive_is_deterministic():
    a = ExplorationController(tier="fast").run(_problems())
    b = ExplorationController(tier="fast").run(_problems())
    assert a.archive.coverage == b.archive.coverage
    assert [c.expression for c in a.archive.elites()] == [c.expression for c in b.archive.elites()]
