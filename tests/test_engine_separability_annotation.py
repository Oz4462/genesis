"""discover_new_formulas(target_fn=...): annotate the target's AI-Feynman separability.

Pins the opt-in separability wiring: when a queryable ``target_fn`` is supplied, the result carries the
target's multiplicative decomposition into independent variable groups (does the law factor — engine-
representable — or are variables coupled, needing the declared multi-term extension?). It is purely
informational: it never changes a verdict, the default path (no target_fn) is byte-identical, and a
broken target_fn degrades to None rather than crashing the discovery. Offline, deterministic.
"""

import numpy as np

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery.engine import discover_new_formulas


def _free_pi(run_id="sep"):
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(idea="free pi group", target=Variable("y", "m^2", tuple(y)),
                            inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
                            run_id=run_id)


def test_no_target_fn_means_no_separability_annotation():
    res = discover_new_formulas(_free_pi())
    assert res.separability is None


def test_separable_target_is_annotated_as_factoring():
    # y = 3·x1² factors completely: x1 and x2 are independent groups (x2 has no effect).
    res = discover_new_formulas(_free_pi(), target_fn=lambda x1, x2: 3.0 * x1 ** 2)
    sep = res.separability
    assert sep is not None and sep.mode == "multiplicative"
    assert {frozenset({"x1"}), frozenset({"x2"})} == set(sep.groups)
    assert sep.max_interaction < 1e-6


def test_coupled_target_is_annotated_as_one_group():
    # y = (x1 + x2)² does NOT factor under multiplication → x1 and x2 stay in one coupled group.
    res = discover_new_formulas(_free_pi(), target_fn=lambda x1, x2: (x1 + x2) ** 2)
    sep = res.separability
    assert sep is not None and set(sep.groups) == {frozenset({"x1", "x2"})}
    assert sep.max_interaction > 1e-3


def test_annotation_is_best_effort_a_broken_target_fn_yields_none_not_a_crash():
    # a target_fn with the wrong signature must not crash discovery — the annotation degrades to None.
    res = discover_new_formulas(_free_pi(), target_fn=lambda z: z)
    assert res.separability is None
    assert res.all_records                                    # the discovery itself still ran


def test_annotation_never_changes_the_verdict():
    # the records/validated are identical with and without the annotation (it is purely informational).
    plain = discover_new_formulas(_free_pi())
    annotated = discover_new_formulas(_free_pi(), target_fn=lambda x1, x2: 3.0 * x1 ** 2)
    assert len(plain.all_records) == len(annotated.all_records)
    assert plain.validated == annotated.validated


def test_separability_annotation_is_deterministic():
    a = discover_new_formulas(_free_pi(), target_fn=lambda x1, x2: 3.0 * x1 ** 2)
    b = discover_new_formulas(_free_pi(), target_fn=lambda x1, x2: 3.0 * x1 ** 2)
    assert set(a.separability.groups) == set(b.separability.groups)
