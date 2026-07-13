"""Materials registry backend + scholar offline claims."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.tools.materials_backend import MaterialsBackend, materials_claim_text  # noqa: E402
from gen.materials import density_kg_m3  # noqa: E402


def test_materials_backend_surfaces_steel_for_density_query():
    be = MaterialsBackend()
    hits = asyncio.run(be.search("What is the density of steel in kg/m3?", 5))
    assert hits
    assert hits[0].url_or_id == "gen-materials://STEEL"
    assert hits[0].backend == "materials_registry"


def test_materials_backend_silent_on_unrelated():
    be = MaterialsBackend()
    assert asyncio.run(be.search("What CAD kernel does build123d use?", 5)) == []


def test_materials_claim_text_si_density():
    text, quote = materials_claim_text("STEEL", language="en")
    assert "7850" in text
    assert quote
    assert density_kg_m3("STEEL") == 7850.0
