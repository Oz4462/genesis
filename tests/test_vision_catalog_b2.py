"""Audit B2: vision content is catalogued and typed, not silent ledger claims."""

from __future__ import annotations

from gen import future_ideas, visionary_ideas
from gen.vision_catalog import list_vision_entry_ids, load_vision_catalog, vision_catalog_path


def test_vision_catalog_exists_and_typed():
    assert vision_catalog_path().is_file()
    cat = load_vision_catalog()
    assert cat["content_kind"] == "vision_demo"
    assert "provenance_policy" in cat
    ids = list_vision_entry_ids()
    assert "delivery_drone_spec" in ids
    assert "mars_isru_o2_plant_spec" in ids
    assert len(ids) >= 8


def test_modules_declare_vision_kind():
    assert future_ideas.CONTENT_KIND == "vision_demo"
    assert visionary_ideas.CONTENT_KIND == "vision_demo"
