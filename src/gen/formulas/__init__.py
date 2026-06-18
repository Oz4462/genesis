"""Formula and physical law registry for GENESIS.

Central place for verified, sourced mathematical expressions and physical constants
that the system may use in derivations, physics checks, and identity research.

All entries must carry provenance that can be turned into Ledger Claims.
No silent defaults. "I don't know / not registered" is explicit.
"""

from __future__ import annotations

# Re-export the concrete CODATA loader as the first authoritative set.
from ..tools.codata import (
    PhysicalConstant,
    load_codata_constants,
    get_constant,
    parse_allascii,
)

from .registry import FormulaRecord, FormulaRegistry

__all__ = [
    "PhysicalConstant",
    "load_codata_constants",
    "get_constant",
    "parse_allascii",
    "codata_table_source_ref",
    "make_codata_constant_claim",
    "content_hash_of",
    "DlmfEntry",
    "fetch_dlmf_entry",
    "dlmf_source_ref",
    "load_curated_dlmf",
    "WikidataLawHit",
    "search_physical_law",
    "get_formula_for",
    "sparql_query",
    "FormulaRecord",
    "FormulaRegistry",
]

# Re-export helpers
from ..tools.codata import (
    codata_table_source_ref,
    make_codata_constant_claim,
    content_hash_of,
)
from ..tools.dlmf import (
    DlmfEntry,
    fetch_dlmf_entry,
    dlmf_source_ref,
    load_curated_dlmf,
    dlmf_latex_to_sympy,
)
from ..tools.wikidata import (
    sparql_query,
    search_physical_law,
    get_formula_for,
    WikidataLawHit,
)
