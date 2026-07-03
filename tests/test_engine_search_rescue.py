"""discover_new_formulas(refine_with_search=True): best-first exponent search rescues the SR.

Pins the opt-in AI-Scientist-v2 tree-search wiring (the deterministic gate as the node oracle): when
the cheap single-shot symbolic regression confirms NOTHING — e.g. an under-determined free π-group it
cannot pin — a best-first walk over exponent space, scored by the SAME gate, recovers the confirmed law.
The gate stays the sole authority (the search only ADDS gate-passing laws), a problem the SR already
solved is left untouched, and the default path is byte-identical. Offline, deterministic.
"""

import numpy as np

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery.engine import discover_new_formulas


def _free_pi(run_id="rescue"):
    # y = 3·x1²; x2 is a distractor → a free π-group the dimensional SR cannot pin (it mis-guesses
    # x1¹·x2¹ and fails the fit gate), so the search must rescue it.
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(idea="free pi group", target=Variable("y", "m^2", tuple(y)),
                            inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
                            run_id=run_id)


def _determined(run_id="det"):
    # one input, y = x1² — dimensional analysis alone fixes the exponent, so the SR solves it single-shot.
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    return DiscoveryProblem(idea="square", target=Variable("y", "m^2", tuple(x1 ** 2)),
                            inputs=(Variable("x1", "m", tuple(x1)),), run_id=run_id)


def test_single_shot_sr_alone_does_not_confirm_the_under_determined_law():
    # precondition: without search, the free π-group is NOT solved (validated is empty).
    res = discover_new_formulas(_free_pi())
    assert res.validated == ()


def test_search_rescues_the_under_determined_law():
    res = discover_new_formulas(_free_pi(), refine_with_search=True)
    assert res.validated, "the best-first search did not rescue the under-determined law"
    best = res.validated[0].candidate
    assert abs(best.exponents["x1"] - 2.0) < 1e-3        # the true power
    assert abs(best.exponents.get("x2", 0.0)) < 1e-3     # the distractor drops out
    assert best.r_squared > 0.999 and res.validated[0].passed


def test_search_is_a_noop_when_the_sr_already_solves_it():
    # a determined problem is solved single-shot; the flag must not change the validated result.
    plain = discover_new_formulas(_determined())
    refined = discover_new_formulas(_determined(), refine_with_search=True)
    assert plain.validated and refined.validated
    assert plain.validated[0].candidate.exponents == refined.validated[0].candidate.exponents
    assert len(plain.all_records) == len(refined.all_records)   # no extra search records were added


def test_rescue_is_deterministic():
    a = discover_new_formulas(_free_pi(), refine_with_search=True)
    b = discover_new_formulas(_free_pi(), refine_with_search=True)
    assert [r.candidate.exponents for r in a.validated] == [r.candidate.exponents for r in b.validated]
