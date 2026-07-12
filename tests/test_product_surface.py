"""product_surface — CLI reachability anchors for product modules."""

from __future__ import annotations

from gen.product_surface import PRODUCT_SURFACE_MODULES, surface_modules
from gen.physics_validation import VALIDATORS, PhysicsCheck, run_physics_checks


def test_surface_modules_nonempty_and_stable():
    mods = surface_modules()
    assert mods == PRODUCT_SURFACE_MODULES
    assert len(mods) >= 15
    assert "gen.export.drawing" in mods
    assert "gen.montecarlo" in mods


def test_cli_imports_product_surface():
    # Importing cli must succeed (optional seams must not crash startup).
    import gen.cli as cli

    assert hasattr(cli, "_product_surface")
    assert "gen.export.drawing" in cli._product_surface.surface_modules()


def test_montecarlo_validator_registered_and_runs():
    assert "montecarlo_uncertainty" in VALIDATORS
    results = run_physics_checks([
        PhysicsCheck(
            name="mc screen",
            validator="montecarlo_uncertainty",
            inputs={
                "formula": "a + b",
                "values": {"a": 1.0, "b": 2.0},
                "uncertainties": {"a": 0.01, "b": 0.01},
                "n_samples": 100,
                "seed": 1,
            },
        )
    ])
    assert len(results) == 1
    assert results[0]["status"] == "ran"
    assert results[0]["ok"] is True
    assert results[0]["result"]["mean"] > 0
