"""Offline tests for Wikidata SPARQL thin client."""

import pytest

from gen.tools.wikidata import (
    sparql_query,
    search_physical_law,
    get_formula_for,
    WikidataLawHit,
    WikidataError,
)
from gen.formulas.registry import FormulaRegistry, FormulaRecord


def test_sparql_query_monkey(monkeypatch):
    def fake_urlopen(req, timeout=None):
        class Resp:
            status = 200
            def read(self):
                return b'{"results":{"bindings":[{"item":{"value":"http://www.wikidata.org/entity/Q123"},"itemLabel":{"value":"Euler buckling load"}}]}}'
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return Resp()
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    rows = sparql_query("SELECT ?x WHERE {}")
    assert len(rows) == 1


def test_search_physical_law_monkey(monkeypatch):
    def fake_query(q):
        return [{"item": {"value": "http://www.wikidata.org/entity/Q456"}, "itemLabel": {"value": "Euler's critical load"}}]
    monkeypatch.setattr("gen.tools.wikidata.sparql_query", fake_query)

    hits = search_physical_law("Euler buckling")
    assert isinstance(hits[0], WikidataLawHit)
    assert "Euler" in hits[0].label


def test_wikidata_to_formula_record():
    reg = FormulaRegistry()
    hit = WikidataLawHit("Q456", "Euler critical load", formula="P_cr = (pi^2 E I)/L^2")
    rec = FormulaRecord(
        record_id=f"wikidata:{hit.entity}",
        kind="closed_form",
        name=hit.label,
        expr=hit.formula or "",
        sources=(f"Wikidata {hit.entity}",),
    )
    reg.register(rec)
    assert "Euler critical load" in reg.list_names()
