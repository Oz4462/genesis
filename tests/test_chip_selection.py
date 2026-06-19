"""chip_selection — pick the robot's compute chip by requirement, gated by compute.py.

Pins the proposer/gate split: the catalog is the candidate space, compute.py's throughput/power/latency
checks are the gate, and a chip is selected only when it independently clears all three. The cheapest
feasible chip is the default choice; a requirement no chip meets yields an honest None with the binding
reason — never a fabricated part. Offline, deterministic.
"""

import pytest

from gen.chip_selection import select_chip
from gen.compute import compute_budget_check, inference_latency_check, inference_power_check

# a humanoid-scale requirement two of the catalog chips can meet, two cannot.
_REQ = dict(workload_tops=30.0, power_budget_w=40.0, inference_ops=50e9, control_period_s=0.01)


def test_selected_chip_independently_clears_all_three_compute_gates():
    res = select_chip(**_REQ)
    assert res.selected is not None
    chip = res.selected.chip
    # re-verify with compute.py directly — the selection's verdict must match the independent gate.
    assert compute_budget_check(_REQ["workload_tops"], chip.peak_tops, 0.6)["ok"]
    assert inference_power_check(_REQ["workload_tops"], chip.efficiency_tops_per_w,
                                 _REQ["power_budget_w"], chip.static_power_w)["ok"]
    assert inference_latency_check(_REQ["inference_ops"], chip.throughput_ops_per_s,
                                   _REQ["control_period_s"])["ok"]


def test_price_picks_the_cheapest_feasible_chip():
    res = select_chip(**_REQ, prefer="price")
    assert res.selected.chip.name == "Jetson Orin NX"        # cheapest of the feasible {Orin NX, AGX Orin}
    # it is genuinely the minimum-price feasible chip
    assert res.selected.chip.price_eur == min(e.chip.price_eur for e in res.feasible)


def test_headroom_prefers_more_margin_than_price_does():
    cheap = select_chip(**_REQ, prefer="price").selected
    roomy = select_chip(**_REQ, prefer="headroom").selected
    assert roomy.chip.name == "Jetson AGX Orin"              # more binding headroom than the cheap pick
    assert roomy.min_safety_factor >= cheap.min_safety_factor


def test_no_chip_fits_is_honest_not_fabricated():
    res = select_chip(workload_tops=10_000.0, power_budget_w=40.0, inference_ops=50e9, control_period_s=0.01)
    assert res.selected is None                              # no fabricated chip
    assert res.feasible == ()
    assert all(e.limiting for e in res.evaluated)           # every chip has a stated binding reason
    assert all(not e.feasible for e in res.evaluated)


def test_selected_chip_carries_provenance():
    res = select_chip(**_REQ)
    assert res.selected.chip.source                         # a chip spec without a citation is rejected upstream


def test_unknown_prefer_and_empty_catalog_and_bad_requirement_raise():
    with pytest.raises(ValueError):
        select_chip(**_REQ, prefer="cheapest")              # not a known preference
    with pytest.raises(ValueError):
        select_chip(**_REQ, catalog=())                     # nothing to select from
    with pytest.raises(ValueError):
        select_chip(workload_tops=0.0, power_budget_w=40.0, inference_ops=50e9, control_period_s=0.01)


def test_selection_is_deterministic():
    a = select_chip(**_REQ)
    b = select_chip(**_REQ)
    assert a.selected.chip.name == b.selected.chip.name
    assert [e.chip.name for e in a.feasible] == [e.chip.name for e in b.feasible]
