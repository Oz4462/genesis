"""SRBench-hygiene gate (discovery/srbench_hygiene.py) against Schein-Entdeckung.

Pins the honest-benchmark discipline: a real law (Kepler) passes — an alien-dimension dummy gets a ~zero
exponent and the law generalises out-of-sample; a fit on a PURE-NOISE target fails (its held-out R²
collapses), so the gate refuses it. Offline, deterministic.
"""

import numpy as np

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery.benchmark import kepler_case
from gen.discovery.srbench_hygiene import dummy_variable_test, hygiene_gate


def _noise_target_problem():
    p = kepler_case().problem
    n = len(p.target.values)
    rng = np.random.default_rng(7)
    noise = tuple(rng.uniform(1e6, 1e7, size=n))             # a target with no real power law of the inputs
    return DiscoveryProblem(idea="pure noise", target=Variable(p.target.name, p.target.unit, noise),
                            inputs=p.inputs, constants=p.constants, run_id="noise")


def test_kepler_passes_the_hygiene_gate():
    report = hygiene_gate(kepler_case().problem)
    assert report.passed
    assert report.dummy_excluded and report.dummy_exponent < 1e-3
    assert report.generalises and report.oos_test_r2 > 0.99


def test_an_alien_dimension_dummy_is_excluded():
    excluded, exponent = dummy_variable_test(kepler_case().problem)
    assert excluded and exponent < 1e-3                      # a kg dummy cannot enter a seconds law


def test_a_pure_noise_target_fails_the_gate():
    report = hygiene_gate(_noise_target_problem())
    assert not report.passed
    assert not report.generalises                            # held-out R2 collapses on noise


def test_noise_sweep_is_reported_and_clean_level_generalises():
    report = hygiene_gate(kepler_case().problem)
    levels = [lv for lv, _ in report.noise_sweep]
    assert 0.0 in levels
    clean = dict(report.noise_sweep)[0.0]
    assert clean > 0.99                                      # the clean level generalises


def test_hygiene_gate_is_deterministic():
    a = hygiene_gate(kepler_case().problem)
    b = hygiene_gate(kepler_case().problem)
    assert (a.passed, a.dummy_excluded, a.generalises) == (b.passed, b.dummy_excluded, b.generalises)
