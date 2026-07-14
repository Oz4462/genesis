"""W1–W5: source catalog, patents key gate, ledger/vector honesty, richer seeds."""
from __future__ import annotations

from gen.tools.source_catalog import (
    catalog_report,
    ledger_status,
    patents_status,
    vector_status,
)
from gen.wissensbasis.store import query_component_recipes, seed_electronics_components


def test_w1_catalog_report_lists_search_and_wissensbasis():
    rep = catalog_report()
    names = {c.name for c in rep.connectors}
    assert "openalex" in names
    assert "arxiv" in names
    assert "patentsview" in names
    assert "postgres_ledger" in names
    assert "vector_memory" in names
    assert rep.summary.get("total", 0) >= 8
    text = rep.text()
    assert "SOURCE CATALOG" in text
    d = rep.to_dict()
    assert "connectors" in d and "patents" in d


def test_w3_patents_status_key_gated(monkeypatch):
    monkeypatch.delenv("PATENTSVIEW_API_KEY", raising=False)
    st = patents_status()
    assert st["status"] == "key_missing"
    assert st["key_present"] is False
    monkeypatch.setenv("PATENTSVIEW_API_KEY", "test-key-not-live")
    st2 = patents_status()
    assert st2["status"] == "ready"
    assert st2["key_present"] is True


def test_w4_ledger_status_without_dsn():
    # Do not clear env if operator set DSN; just assert structure
    st = ledger_status()
    assert st["status"] in ("offline_in_memory", "dsn_configured")
    assert "smoke" in st
    assert "schema" in st


def test_w5_vector_status_honest_not_production_qdrant():
    st = vector_status()
    assert st["production_qdrant"] is False
    assert st["production_pgvector"] is False
    assert st["status"] in ("local_vendor", "not_wired")
    assert "note" in st


def test_w2_seed_electronics_includes_improvement_recipes():
    seeded = seed_electronics_components(run_id="w2-seed")
    assert "improve_thermal_pad" in seeded or any("improve" in s for s in seeded)
    assert "esc_48v_80a" in seeded or any("esc" in s for s in seeded)
    recipes = query_component_recipes(kind="improvement_recipe")
    # After seed, improvement recipes should be queryable
    ids = {r.id for r in recipes}
    assert "improve_thermal_pad" in ids or len(recipes) >= 1
