"""Tests für den Conjecture-Generator + Auto-Disproof (math-research, vierter Stein).

Der Forschungsakt: eine parametrisierte Familie wird über ein ENDLICHES Struktur-Param-
Gitter instanziiert, jede Instanz rigoros geprüft und triagiert. Eine Familie bekommt
NIE ein 'bewiesen'-Verdict — nur Finite-Grid-Statistik + ein 'universal_candidate'-Flag
(= lohnt Beweisversuch, nicht Theorem). Over-Claim ist strukturell unmöglich.
"""

from gen.identity_research import (
    AssumptionManifest,
    ConjectureTemplate,
    NoveltyIndex,
    explore_family,
)


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_true_family_all_survive_and_flags_universal_candidate():
    """(x+k)^2 == x^2 + 2kx + k^2 is true for every k -> GRID_ALL_SURVIVED, candidate."""
    t = ConjectureTemplate(
        family_id="binom",
        lhs_template="(x + k)**2",
        rhs_template="x**2 + 2*k*x + k**2",
        param_grid={"k": tuple(range(1, 11))},
        manifest=_mR(),
        min_instances=8,
    )
    rep = explore_family(t)
    assert rep.grid_cardinality == 10
    assert rep.refuted_count == 0
    assert rep.family_verdict == "GRID_ALL_SURVIVED"
    assert rep.universal_candidate is True
    assert rep.survival_rate == 1.0
    assert "not proven universal" in rep.honesty_epistemic


def test_fully_false_family_is_refuted_family():
    """x + k == x + k + 1 is false for every k -> REFUTED_FAMILY, never universal."""
    t = ConjectureTemplate(
        family_id="off1",
        lhs_template="x + k",
        rhs_template="x + k + 1",
        param_grid={"k": (1, 2, 3)},
        manifest=_mR(),
    )
    rep = explore_family(t)
    assert rep.family_verdict == "REFUTED_FAMILY"
    assert rep.refuted_count == 3
    assert rep.universal_candidate is False


def test_partially_refuted_family_triages_correctly():
    """x^k == k*x: true only for k=1 (x==x), false for k>=2 -> PARTIALLY_REFUTED."""
    t = ConjectureTemplate(
        family_id="powlin",
        lhs_template="x**k",
        rhs_template="k*x",
        param_grid={"k": (1, 2, 3, 4)},
        manifest=_mR(),
    )
    rep = explore_family(t)
    assert rep.family_verdict == "PARTIALLY_REFUTED"
    assert rep.refuted_count == 3          # k=2,3,4 refuted
    assert len(rep.surviving_novel) + len(rep.surviving_known) == 1  # k=1 survives
    assert rep.universal_candidate is False


def test_true_family_below_min_instances_is_not_universal_candidate():
    """All survive but grid too small -> GRID_ALL_SURVIVED yet NOT a universal candidate."""
    t = ConjectureTemplate(
        family_id="binom_small",
        lhs_template="(x + k)**2",
        rhs_template="x**2 + 2*k*x + k**2",
        param_grid={"k": (1, 2, 3)},
        manifest=_mR(),
        min_instances=8,
    )
    rep = explore_family(t)
    assert rep.family_verdict == "GRID_ALL_SURVIVED"
    assert rep.universal_candidate is False  # 3 < 8


def test_distinct_instances_are_novel_then_rediscovered_on_rerun():
    """Within a family each k is a distinct statement (NOVEL); re-running the family over a
    shared index marks them REDISCOVERED (no false within-batch merge)."""
    t = ConjectureTemplate(
        family_id="binom",
        lhs_template="(x + k)**2",
        rhs_template="x**2 + 2*k*x + k**2",
        param_grid={"k": (1, 2, 3)},
        manifest=_mR(),
    )
    idx = NoveltyIndex()
    first = explore_family(t, novelty_index=idx)
    assert len(first.surviving_novel) == 3 and len(first.surviving_known) == 0
    second = explore_family(t, novelty_index=idx)
    assert len(second.surviving_known) == 3 and len(second.surviving_novel) == 0


def test_family_verdict_never_claims_proof():
    """Structural guarantee: a family verdict is never PROVED/THEOREM."""
    t = ConjectureTemplate(
        family_id="binom",
        lhs_template="(x + k)**2",
        rhs_template="x**2 + 2*k*x + k**2",
        param_grid={"k": tuple(range(1, 11))},
        manifest=_mR(),
    )
    rep = explore_family(t)
    assert rep.family_verdict in (
        "REFUTED_FAMILY", "PARTIALLY_REFUTED", "GRID_ALL_SURVIVED", "INCONCLUSIVE_DOMINANT",
    )
    assert "PROVED" not in rep.family_verdict and "THEOREM" not in rep.family_verdict
