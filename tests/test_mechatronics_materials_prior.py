"""Mechatronics invent domain includes materials registry prior-art (self-improve)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.inventor.domains.mechatronics import MechatronicsDomain  # noqa: E402
from gen.tools.materials_backend import MaterialsBackend  # noqa: E402


def test_default_backends_include_materials_registry():
    d = MechatronicsDomain()
    names = [b.name for b in d.prior_art_sources()]
    assert "materials_registry" in names
    assert any(getattr(b, "name", "") == "rag" or "Rag" in type(b).__name__ for b in d.prior_art_sources())


def test_materials_backend_finds_steel_in_domain_stack():
    d = MechatronicsDomain()
    mats = [b for b in d.prior_art_sources() if isinstance(b, MaterialsBackend)]
    assert mats
    hits = asyncio.run(mats[0].search("density of steel for 50 kg load", 3))
    assert hits and hits[0].url_or_id == "gen-materials://STEEL"
