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


def _sparql_string_literal(value: str) -> str:
    """Escape a user string for use inside a SPARQL double-quoted literal.

    Prevents injection via quotes / backslashes in search names (REWORK integrity).
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _assert_qid(entity_qid: str) -> str:
    """Accept only Wikidata entity ids like Q456 — never raw SPARQL fragments."""
    qid = (entity_qid or "").strip()
    if not qid or qid[0] not in "Qq" or not qid[1:].isdigit():
        raise WikidataError(f"invalid Wikidata entity id: {entity_qid!r}")
    return "Q" + qid[1:]


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
    except WikidataError:
        raise
    except Exception as exc:
        raise WikidataError(f"Wikidata SPARQL failed: {exc}") from exc


def search_physical_law(name: str, limit: int = 5) -> List[WikidataLawHit]:
    """Simple search for entities that look like physical laws or formulas.

    Uses label + description search. Returns lightweight hits.
    """
    if not isinstance(name, str) or not name.strip():
        raise WikidataError("search name must be a non-empty string")
    lim = int(limit)
    if lim < 1 or lim > 50:
        raise WikidataError(f"limit out of range (1..50): {limit!r}")
    safe = _sparql_string_literal(name.strip())
    # Very basic query; in real use one would refine with P279 subclass etc.
    q = f"""
    SELECT ?item ?itemLabel ?itemDescription ?formula WHERE {{
      ?item rdfs:label ?itemLabel .
      ?item schema:description ?itemDescription .
      OPTIONAL {{ ?item wdt:P2535 ?formula . }}  # mathematical formula (P2535)
      FILTER (lang(?itemLabel) = "en")
      FILTER (lang(?itemDescription) = "en")
      FILTER (CONTAINS(LCASE(?itemLabel), LCASE("{safe}")) || CONTAINS(LCASE(?itemDescription), LCASE("{safe}")))
    }}
    LIMIT {lim}
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
    qid = _assert_qid(entity_qid)
    q = f"""
    SELECT ?formula WHERE {{
      wd:{qid} wdt:P2535 ?formula .
    }} LIMIT 1
    """
    rows = sparql_query(q)
    if rows:
        return rows[0].get("formula", {}).get("value")
    return None


# --- density (P2054) for material α grounding (gap-close 2026-07-14) -----------
# Wikipedia plain extracts omit infobox density; Wikidata carries P2054 numerically.

#: Common engineering materials → Wikidata entity (for density P2054).
MATERIAL_DENSITY_QIDS: dict[str, str] = {
    "COPPER": "Q753",
    "ALUMINUM": "Q663",
    "ALUMINIUM": "Q663",
    "IRON": "Q677",
    "STEEL": "Q11427",
    "MILD_STEEL": "Q11427",
    "TITANIUM": "Q716",  # may lack P2054 — then None
}

#: Unit Q-ids for density quantities on Wikidata.
_UNIT_G_CM3 = "Q13147228"   # gram per cubic centimetre
_UNIT_KG_M3 = "Q844211"     # kilogram per cubic metre


@dataclass(frozen=True)
class WikidataDensityHit:
    """Independent density from Wikidata P2054 (not the GENESIS materials registry)."""

    material_key: str
    entity_qid: str
    density_kg_m3: float
    density_g_cm3: float
    raw_amount: float
    unit_qid: str
    source_url: str
    quote: str


def get_density_kg_m3(entity_qid: str, *, timeout: float = 20.0) -> Optional[WikidataDensityHit]:
    """Fetch mass density (P2054) for a Wikidata entity; return SI kg/m³ or None.

    Uses the wbgetclaims API (no SPARQL). Converts g/cm³ → kg/m³ (×1000). Raises
    WikidataError only on transport/parse failure — missing property returns None.
    """
    qid = _assert_qid(entity_qid)
    # material key unknown here — fill when called via material map
    url = (
        "https://www.wikidata.org/w/api.php"
        f"?action=wbgetclaims&entity={qid}&property=P2054&format=json"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GENESIS-research/0.1 (https://github.com/genesis; mailto:research@genesis.local)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise WikidataError(f"wbgetclaims HTTP {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
    except WikidataError:
        raise
    except Exception as exc:
        raise WikidataError(f"Wikidata density fetch failed: {exc}") from exc

    claims = (data.get("claims") or {}).get("P2054") or []
    if not claims:
        return None
    snak = claims[0].get("mainsnak") or {}
    if snak.get("snaktype") != "value":
        return None
    val = (snak.get("datavalue") or {}).get("value") or {}
    try:
        amount = float(str(val.get("amount", "")).lstrip("+"))
    except (TypeError, ValueError):
        return None
    unit = str(val.get("unit", ""))
    unit_qid = unit.rsplit("/", 1)[-1] if unit else ""
    if unit_qid == _UNIT_G_CM3 or unit.endswith("Q13147228"):
        dens_g = amount
        dens_si = amount * 1000.0
    elif unit_qid == _UNIT_KG_M3 or unit.endswith("Q844211"):
        dens_si = amount
        dens_g = amount / 1000.0
    else:
        # unknown unit — refuse rather than guess
        return None
    quote = (
        f"Wikidata {qid} P2054 amount={val.get('amount')} unit={unit_qid} "
        f"(density mass)"
    )
    return WikidataDensityHit(
        material_key="",
        entity_qid=qid,
        density_kg_m3=dens_si,
        density_g_cm3=dens_g,
        raw_amount=amount,
        unit_qid=unit_qid,
        source_url=f"https://www.wikidata.org/wiki/{qid}#P2054",
        quote=quote[:200],
    )


def density_claims_for_material(material_key: str, *, language: str = "en") -> Optional[tuple[str, str, str]]:
    """Return (claim_text, quote, url) for independent Wikidata density of a registry key.

    Independent of gen-materials:// — used so α skeptic can corroborate registry bands.
    """
    key = material_key.strip().upper().replace(" ", "_")
    qid = MATERIAL_DENSITY_QIDS.get(key)
    if not qid:
        return None
    try:
        hit = get_density_kg_m3(qid)
    except WikidataError:
        return None
    if hit is None:
        return None
    if language == "de":
        text = (
            f"Laut Wikidata ({qid}, Eigenschaft P2054) beträgt die Massendichte von "
            f"{key} {hit.density_kg_m3:.0f} kg/m³ ({hit.density_g_cm3:g} g/cm³)."
        )
    else:
        text = (
            f"According to Wikidata ({qid}, property P2054), the mass density of "
            f"{key} is {hit.density_kg_m3:.0f} kg/m³ ({hit.density_g_cm3:g} g/cm³)."
        )
    return text, hit.quote, hit.source_url
