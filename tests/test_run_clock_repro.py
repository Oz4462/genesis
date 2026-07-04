"""D2 — the canonical run clock makes replay-relevant timestamps deterministic.

Wall-clock ``datetime.now`` breaks bit-identical checkpoint replay (Kernprinzip 5).
The fix is ONE mechanism: :func:`gen.core.state.run_clock` pins :func:`now_utc`, and
every class-(a) timestamp emitter (ledger ``created_at``, provenance records, run-id-
derived artifacts) routes through it. These tests prove:

  1. ``run_clock`` pins ``now_utc`` / ``_now`` and overrides wall-clock.
  2. Two runs with the SAME injected timestamp produce bit-identical artifacts, for
     several independent class-(a) modules (core.state, wissensbasis.store,
     wissensbasis.bio_molecular, simulation.runner).
  3. Class-(a) paths actually USE the injected value: with wall-clock monkeypatched
     to a sentinel, the sentinel must NOT appear — the injected clock wins.
  4. The one deliberate class-(b) exception (integrator unlabeled dir name) stays
     wall-clock even under a pinned clock, because its job is per-call uniqueness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import gen.core.state as state
from gen.core.state import Claim, SourceRef, SourceSupport, now_utc, _now, run_clock

FIXED = datetime(2020, 3, 14, 15, 9, 26, 535000, tzinfo=timezone.utc)
FIXED2 = datetime(2021, 6, 28, 8, 30, 0, tzinfo=timezone.utc)
# A wall-clock value distinct from any injected clock, used to prove the run clock wins.
SENTINEL_WALL = datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


class _FakeDatetime:
    """Stand-in whose ``now`` is a fixed sentinel — the "wall clock" for a test."""

    @staticmethod
    def now(tz=None):  # noqa: ANN001 - mirrors datetime.now signature
        return SENTINEL_WALL


def _patch_wallclock(monkeypatch):
    monkeypatch.setattr(state, "datetime", _FakeDatetime)


def _src():
    return [SourceRef(url_or_id="s://x", retrieved=True, support=SourceSupport.SUPPORTS)]


# --- 1. mechanism -----------------------------------------------------------

def test_now_utc_falls_back_to_wallclock_without_a_pinned_clock(monkeypatch):
    _patch_wallclock(monkeypatch)
    # No run clock active → honest wall-clock fallback (the non-replay path).
    assert now_utc() == SENTINEL_WALL
    assert _now() == SENTINEL_WALL


def test_run_clock_pins_and_overrides_wallclock(monkeypatch):
    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        assert now_utc() == FIXED
        assert _now() == FIXED
        assert now_utc() != SENTINEL_WALL
    # restored after the block
    assert now_utc() == SENTINEL_WALL


def test_run_clock_is_reentrant_and_restores(monkeypatch):
    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        with run_clock(FIXED2):
            assert now_utc() == FIXED2
        assert now_utc() == FIXED  # inner block restored the outer clock
    assert now_utc() == SENTINEL_WALL


# --- 2/3. class-(a) module: core.state ledger Claim.created_at ---------------

def test_claim_created_at_uses_injected_clock_not_wallclock(monkeypatch):
    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        c1 = Claim(id="c1", text="atom", sources=_src())
        c2 = Claim(id="c1", text="atom", sources=_src())
    # Deterministic across two independent constructions with the same clock…
    assert c1.created_at == c2.created_at == FIXED
    # …and the wall-clock sentinel never leaked in.
    assert c1.created_at != SENTINEL_WALL


# --- 2/3. class-(a) module: wissensbasis.store provenance --------------------

def test_component_recipe_provenance_timestamp_is_deterministic(tmp_path, monkeypatch):
    from gen.wissensbasis.store import (
        ComponentRecipe,
        FragmentStore,
        save_component_recipe,
    )

    _patch_wallclock(monkeypatch)
    rec = ComponentRecipe(id="r1", name="R1", kind="battery", specs={"v": 3.7})

    def _persist_and_read(base):
        store = FragmentStore(base_dir=str(base))
        with run_clock(FIXED):
            save_component_recipe(rec, store=store)
        return store.load("component_r1")["provenance"]["timestamp"]

    ts_a = _persist_and_read(tmp_path / "a")
    ts_b = _persist_and_read(tmp_path / "b")
    assert ts_a == ts_b == FIXED.isoformat()
    assert SENTINEL_WALL.isoformat() not in ts_a


# --- 2/3. class-(a) module: wissensbasis.bio_molecular provenance ------------

def test_bio_molecular_provenance_uses_injected_clock(monkeypatch):
    from gen.wissensbasis.bio_molecular import _make_provenance

    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        prov_a = _make_provenance("md", run_id="bio-1")
        prov_b = _make_provenance("md", run_id="bio-1")
    assert prov_a["timestamp"] == prov_b["timestamp"] == FIXED.isoformat()
    assert prov_a["timestamp"] != SENTINEL_WALL.isoformat()


# --- 2/3. class-(a) module: simulation.runner SimulationResult.timestamp -----

def test_simulation_result_timestamp_uses_injected_clock(monkeypatch):
    from gen.simulation.runner import SimulationResult

    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        r1 = SimulationResult(run_id="sim-1", cases=[], overall_status="partial", provenance="p")
        r2 = SimulationResult(run_id="sim-1", cases=[], overall_status="partial", provenance="p")
    assert r1.timestamp == r2.timestamp == FIXED.isoformat()
    assert r1.timestamp != SENTINEL_WALL.isoformat()


def test_simulation_runner_run_id_uses_injected_clock(monkeypatch):
    from gen.simulation.runner import SimulationRunner

    _patch_wallclock(monkeypatch)
    with run_clock(FIXED):
        a = SimulationRunner().run_id
        b = SimulationRunner().run_id
    assert a == b == f"sim-{FIXED.strftime('%Y%m%d%H%M%S')}"


# --- 4. deliberate class-(b) exception: integrator unlabeled dir name --------

def test_integrator_unlabeled_dir_stays_unique_wallclock_under_clock(monkeypatch):
    from gen.pipelines import integrator

    # Even with a pinned run clock, the unlabeled fallback must NOT collapse to the
    # fixed instant — its whole purpose is per-call uniqueness (bug #14). An explicit
    # run_id is the reproducible path; this branch is the anonymous fallback.
    with run_clock(FIXED):
        a = integrator._run_dir_name(None, "pkg")
        b = integrator._run_dir_name(None, "pkg")
    assert a != b  # unique per call, deliberately not reproducible
    # An explicit run_id is honoured verbatim (the reproducible path).
    assert integrator._run_dir_name("run-42", "pkg") == "run-42"
