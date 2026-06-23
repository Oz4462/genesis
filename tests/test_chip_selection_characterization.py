"""Characterization / facade-detector for ``chip_selection.select_chip``.

This is the authoritative depth-audit test (distinct from the legacy ``test_chip_selection.py``).
It proves ``select_chip`` is a genuine *proposer/gate*, not a canned pick:

  (a) DRIVEN BY INPUT — the selected chip changes when the requirement changes (a small/cheap chip for
      a tiny workload; ``None`` once the workload exceeds every catalog chip's gated capacity), and the
      ``prefer`` key genuinely re-orders the choice (price vs power vs headroom pick *different* chips).
  (b) FAIL-LOUD (``keine stillen Defaults``) — unknown ``prefer``, an empty catalog, and a non-positive
      requirement each raise ``ValueError`` (the last propagating from ``compute.py``'s own guards), and
      a requirement no chip meets yields honest abstention (``selected is None``, empty feasible set),
      never a fabricated part.

Plus PROPERTY-BASED invariants (Hypothesis): whatever the requirement/prefer, the selected chip — when
one exists — is always feasible and is always the minimum of the feasible set under that prefer's
documented ordering key. If the proposer/gate logic were a constant, these would fail.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.chip_selection import CHIPS, PREFER, Chip, select_chip
from gen.compute import compute_budget_check, inference_latency_check, inference_power_check

# A requirement on which exactly three of the four catalog chips are feasible (the 0.5-TOPS legacy Nano
# fails the throughput gate), chosen so the three prefer keys each pick a DIFFERENT chip — see below.
_THREE_FEASIBLE = dict(
    workload_tops=10.0, power_budget_w=1000.0, inference_ops=1e12, control_period_s=0.1
)

# ordering keys the SELECTED chip must minimise, per select_chip's documented contract.
_PREFER_KEY = {
    "price": lambda e: (e.chip.price_eur, e.chip.name),
    "power": lambda e: (e.power["power_w"], e.chip.name),
    "headroom": lambda e: (-e.min_safety_factor, e.chip.name),
}


# ---------------------------------------------------------------------------
# (a) the SELECTED chip is driven by the requirement, not a canned constant
# ---------------------------------------------------------------------------

def test_tiny_workload_picks_a_small_cheap_chip_big_workload_picks_a_bigger_one():
    """The selection tracks the requirement: a tiny workload admits the cheapest small chip, a larger
    workload forces a more capable (and pricier) chip — proving the requirement is genuinely consumed."""
    tiny = select_chip(workload_tops=0.2, power_budget_w=50.0, inference_ops=1e9,
                       control_period_s=0.1, prefer="price")
    big = select_chip(workload_tops=50.0, power_budget_w=200.0, inference_ops=1e12,
                      control_period_s=0.1, prefer="price")
    assert tiny.selected is not None and big.selected is not None
    # different requirements -> different cheapest feasible chip
    assert tiny.selected.chip.name != big.selected.chip.name
    # and the bigger workload's pick has the higher peak throughput (it had to)
    assert big.selected.chip.peak_tops > tiny.selected.chip.peak_tops


def test_prefer_key_reorders_the_selection():
    """For a requirement where >=2 chips are feasible, price / power / headroom each pick a DIFFERENT
    chip — a canned constant could not do this. Each pick is verified to minimise its prefer's key."""
    picks = {}
    for pref in PREFER:
        res = select_chip(**_THREE_FEASIBLE, prefer=pref)
        assert len(res.feasible) >= 2
        # the selected chip is genuinely the minimum of the feasible set under this prefer's key
        assert res.selected is min(res.feasible, key=_PREFER_KEY[pref])
        picks[pref] = res.selected.chip.name
    # the three preferences resolve to three genuinely distinct chips
    assert len(set(picks.values())) == 3, picks
    # spot-pin the documented intent: cheapest != lowest-power != most-headroom
    assert picks["price"] == "Jetson Orin Nano"
    assert picks["power"] == "Jetson Orin NX"
    assert picks["headroom"] == "Jetson AGX Orin"


def test_selected_chip_independently_clears_all_three_compute_gates():
    """The gate is real: re-running compute.py directly on the selected chip reproduces the pass."""
    res = select_chip(**_THREE_FEASIBLE, prefer="headroom")
    chip = res.selected.chip
    assert compute_budget_check(_THREE_FEASIBLE["workload_tops"], chip.peak_tops, 0.6)["ok"]
    assert inference_power_check(_THREE_FEASIBLE["workload_tops"], chip.efficiency_tops_per_w,
                                 _THREE_FEASIBLE["power_budget_w"], chip.static_power_w)["ok"]
    assert inference_latency_check(_THREE_FEASIBLE["inference_ops"], chip.throughput_ops_per_s,
                                   _THREE_FEASIBLE["control_period_s"])["ok"]


# ---------------------------------------------------------------------------
# (b) NEGATIVE / honest-abstention paths
# ---------------------------------------------------------------------------

def test_workload_past_every_chip_is_honest_none_not_fabricated():
    """Raise the workload past every catalog chip's gated capacity (max usable = 275*0.6 = 165 TOPS):
    selected is None, feasible is empty, and every chip carries a stated binding reason."""
    res = select_chip(workload_tops=500.0, power_budget_w=1000.0, inference_ops=1e12,
                      control_period_s=0.1)
    assert res.selected is None             # no fabricated chip
    assert res.feasible == ()
    assert all(not e.feasible for e in res.evaluated)
    # every chip names WHY it failed — the throughput screen is binding at this workload
    assert all(e.limiting == "throughput" for e in res.evaluated)


def test_unknown_prefer_raises():
    with pytest.raises(ValueError, match="unknown prefer"):
        select_chip(**_THREE_FEASIBLE, prefer="cheapest")


def test_empty_catalog_raises():
    with pytest.raises(ValueError, match="empty"):
        select_chip(**_THREE_FEASIBLE, catalog=())


@pytest.mark.parametrize("bad", [
    dict(workload_tops=0.0),
    dict(workload_tops=-3.0),
    dict(power_budget_w=0.0),
    dict(power_budget_w=-1.0),
    dict(control_period_s=0.0),
    dict(control_period_s=-0.01),
    dict(inference_ops=0.0),
])
def test_non_positive_requirement_propagates_valueerror_from_compute(bad):
    """A non-positive requirement is rejected by compute.py's guards and must surface, not be silently
    coerced — ``keine stillen Defaults``. Each axis is exercised independently."""
    req = dict(workload_tops=10.0, power_budget_w=1000.0, inference_ops=1e12, control_period_s=0.1)
    req.update(bad)
    with pytest.raises(ValueError):
        select_chip(**req)


# ---------------------------------------------------------------------------
# PROPERTY-BASED invariants — hold for ALL requirements / prefers
# ---------------------------------------------------------------------------

_positive = st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False)


@settings(max_examples=200, deadline=None)
@given(
    workload_tops=_positive,
    power_budget_w=_positive,
    inference_ops=st.floats(min_value=1.0, max_value=1e15, allow_nan=False, allow_infinity=False),
    control_period_s=_positive,
    prefer=st.sampled_from(PREFER),
)
def test_property_selected_is_feasible_and_minimal_under_prefer(
    workload_tops, power_budget_w, inference_ops, control_period_s, prefer
):
    """Invariant: whatever the requirement, (i) selected is None iff the feasible set is empty, (ii) a
    non-None selected is itself feasible and IS the minimum of the feasible set under the prefer's
    documented ordering key. A canned/constant selector cannot satisfy this across the input space."""
    res = select_chip(workload_tops=workload_tops, power_budget_w=power_budget_w,
                      inference_ops=inference_ops, control_period_s=control_period_s, prefer=prefer)
    assert (res.selected is None) == (len(res.feasible) == 0)
    if res.selected is not None:
        assert res.selected.feasible
        assert res.selected is min(res.feasible, key=_PREFER_KEY[prefer])
    # feasible is exactly the gate-passing subset of evaluated (proposer/gate consistency).
    # ChipEvaluation holds dict fields (unhashable), so compare by identity, not set membership.
    assert list(res.feasible) == [e for e in res.evaluated if e.feasible]


@settings(max_examples=100, deadline=None)
@given(
    prefer=st.sampled_from(PREFER),
    workload_tops=_positive,
    power_budget_w=_positive,
)
def test_property_selection_is_deterministic(prefer, workload_tops, power_budget_w):
    """A5 reproducibility: identical input -> identical selection (no wall-clock / nondeterminism)."""
    kw = dict(workload_tops=workload_tops, power_budget_w=power_budget_w,
              inference_ops=1e12, control_period_s=0.05, prefer=prefer)
    a = select_chip(**kw)
    b = select_chip(**kw)
    name = lambda r: None if r.selected is None else r.selected.chip.name
    assert name(a) == name(b)
    assert [e.chip.name for e in a.feasible] == [e.chip.name for e in b.feasible]


def test_chip_is_frozen_and_carries_provenance():
    """Each catalog Chip is an immutable, sourced spec — a chip without a citation is the anonymous
    constant this catalog replaces."""
    assert all(isinstance(c, Chip) and c.source for c in CHIPS)
    with pytest.raises(Exception):  # frozen dataclass -> FrozenInstanceError
        CHIPS[0].peak_tops = 999.0  # type: ignore[misc]
