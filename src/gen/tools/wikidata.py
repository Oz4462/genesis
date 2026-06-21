"""Thin Wikidata SPARQL client for law/formula metadata and relations.

Used as a *reference / discovery* source in GENESIS (not computation authority).

Typical uses:
- Resolve human name → Wikidata entity + "has formula" / "defined by" statements
- Get canonical name, related laws, units for a physical law
- Feed candidates into FormulaRegistry + identity_research for verification

Endpoint: https://query.wikidata.org/sparql (public, no key)

All results must be turned into Ledger-backed FormulaRecords or Claims.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


@dataclass(frozen=True)
class WikidataLawHit:
    """Lightweight structured hit for a physical law or formula."""
    entity: str          # Q-id
    label: str
    description: str | None = None
    formula: str | None = None   # if a "formula" statement was present (P2535 or similar)
    source: str = "Wikidata"


class WikidataError(RuntimeError):
    pass


def sparql_query(query: str, timeout: float = 20.0) -> List[Dict[str, Any]]:
    """Execute a SPARQL query against Wikidata. Returns list of result bindings.

    Raises WikidataError on transport or non-200.
    Caller is responsible for crafting safe, read-only queries.
    """
    params = {"query": query, "format": "json"}
    url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GENESIS-research/0.1 (https://github.com/genesis; mailto:research@genesis.local)",
            "Accept": "application/sparql-results+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise WikidataError(f"SPARQL HTTP {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", {}).get("bindings", [])
    except Exception as exc:
        raise WikidataError(f"Wikidata SPARQL failed: {exc}") from exc


def search_physical_law(name: str, limit: int = 5) -> List[WikidataLawHit]:
    """Simple search for entities that look like physical laws or formulas.

    Uses label + description search. Returns lightweight hits.
    """
    # Very basic query; in real use one would refine with P279 subclass etc.
    q = f"""
    SELECT ?item ?itemLabel ?itemDescription ?formula WHERE {{
      ?item rdfs:label ?itemLabel .
      ?item schema:description ?itemDescription .
      OPTIONAL {{ ?item wdt:P2535 ?formula . }}  # mathematical formula (P2535)
      FILTER (lang(?itemLabel) = "en")
      FILTER (lang(?itemDescription) = "en")
      FILTER (CONTAINS(LCASE(?itemLabel), LCASE("{name}")) || CONTAINS(LCASE(?itemDescription), LCASE("{name}")))
    }}
    LIMIT {limit}
    """
    rows = sparql_query(q)
    hits: List[WikidataLawHit] = []
    for r in rows:
        entity = r.get("item", {}).get("value", "").rsplit("/", 1)[-1]
        label = r.get("itemLabel", {}).get("value", "")
        desc = r.get("itemDescription", {}).get("value")
        form = r.get("formula", {}).get("value") if "formula" in r else None
        hits.append(WikidataLawHit(entity, label, desc, form))
    return hits


def get_formula_for(entity_qid: str) -> Optional[str]:
    """Return a formula string associated with a Wikidata entity if present."""
    q = f"""
    SELECT ?formula WHERE {{
      wd:{entity_qid} wdt:P2535 ?formula .
    }} LIMIT 1
    """
    rows = sparql_query(q)
    if rows:
        return rows[0].get("formula", {}).get("value")
    return None
