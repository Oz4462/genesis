"""Tests for the Feynman SRDB benchmark of GENESIS's discovery arm (discovery/feynman.py).

Pins the HONEST two-rate score: GENESIS recovers the power-law family (gravitation, ideal gas,
pendulum, flux, kinetic energy) AND — the load-bearing honesty assertion — NEVER false-confirms a
non-power-law Feynman equation (Gaussian, Euclidean distance, thin-lens), it abstains. This is what
separates a real discovery score from the recitation that inflates LLM-SR Feynman numbers. Offline,
deterministic, numpy-only.
"""

from gen.discovery.feynman import feynman_benchmark, feynman_cases


def test_recovers_the_entire_power_law_family():
    r = feynman_benchmark()
    assert r.recoverable_total == 5
    assert r.recoverable_recovered == 5 and r.recovery_rate == 1.0


def test_abstains_honestly_on_every_non_power_law_equation():
    r = feynman_benchmark()
    assert r.nonrecoverable_total == 3
    assert r.nonrecoverable_abstained == 3 and r.abstention_rate == 1.0


def test_never_false_confirms_a_non_power_law():
    # The critical anti-hallucination property: no transcendental/additive Feynman equation is ever
    # returned as 'bestaetigt'. A single false confirmation here would be a hallucinated discovery.
    r = feynman_benchmark()
    non_power_law = {"Feynman I.6.20", "Feynman I.8.14", "Feynman I.27.6"}
    for res in r.results:
        if res.name in non_power_law:
            assert res.verdict != "bestaetigt", f"{res.name} was false-confirmed"


def test_the_new_feynman_cases_are_genuinely_recovered():
    # flux (II.3.24) and kinetic energy (I.13.4) are the freshly-sampled additions (not reused cases).
    r = feynman_benchmark()
    by_name = {res.name: res for res in r.results}
    assert by_name["Feynman II.3.24"].success
    assert by_name["Feynman I.13.4"].success


def test_cases_split_into_five_recoverable_and_three_abstain():
    cases = feynman_cases()
    recoverable = [c for c in cases if c.expected_exponents is not None]
    non_power_law = [c for c in cases if c.expected_exponents is None]
    assert len(recoverable) == 5 and len(non_power_law) == 3


def test_benchmark_is_deterministic():
    a, b = feynman_benchmark(seed=0), feynman_benchmark(seed=0)
    assert (a.recoverable_recovered, a.nonrecoverable_abstained) == (
        b.recoverable_recovered, b.nonrecoverable_abstained
    )
    assert [r.success for r in a.results] == [r.success for r in b.results]
