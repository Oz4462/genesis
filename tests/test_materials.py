"""Tests for the grounded material registry (materials.py).

Pins: every material carries provenance (a non-empty source) and physically-sane positive properties;
lookup is case-insensitive; and an unknown material RAISES rather than returning a guessed property.
Offline, deterministic.
"""

import pytest

from gen.materials import MATERIALS, get_material


def test_lookup_is_case_insensitive_and_returns_grounded_properties():
    pla = get_material("pla")
    assert pla is get_material("PLA")
    assert pla.youngs_modulus_mpa > 0 and pla.density_g_cm3 > 0 and pla.yield_strength_mpa > 0
    assert pla.source.strip()                              # provenance is mandatory


def test_unknown_material_raises_no_silent_guess():
    with pytest.raises(ValueError):
        get_material("unobtainium")


def test_every_registered_material_is_grounded_and_physically_sane():
    # FDM plastics ~0.8–1.6 g/cm³; structural metals denser (self-improve 2026-07-13: STEEL).
    metal_keys = {
        "STEEL", "MILD_STEEL", "ALUMINUM", "ALUMINIUM", "COPPER", "TITANIUM", "IRON",
    }
    for name, m in MATERIALS.items():
        assert m.source.strip(), f"{name} has no provenance"
        assert m.youngs_modulus_mpa > 0 and m.yield_strength_mpa > 0
        if name in metal_keys:
            assert 2.0 <= m.density_g_cm3 <= 20.0, f"{name} density out of metal band"
        else:
            assert 0.8 <= m.density_g_cm3 <= 1.6, f"{name} density out of FDM band"
        assert m.name == name


def test_steel_density_si_matches_handbook_midband():
    from gen.materials import density_kg_m3

    assert density_kg_m3("STEEL") == pytest.approx(7850.0)
    assert get_material("carbon_steel").name == "STEEL"
