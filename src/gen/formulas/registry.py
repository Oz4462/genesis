"""Minimal Formula / Law Registry.

A FormulaRecord represents a sourced, verifiable mathematical relation or constant
that GENESIS treats as known (after verification).

Phase 1 scope:
- Register PhysicalConstant from CODATA (and later DLMF, hand-verified closed forms).
- Simple lookup by name / measurand tag.
- Content-addressable for Ledger.
- No mutation after registration in a run (append-only in spirit).

Later phases will add:
- Sympy expression storage + identity fingerprint.
- Assumptions / domain.
- Automatic cross-check against identity_research.

All entries are candidates until a Ledger Claim + verification gate marks them VERIFIED.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, TYPE_CHECKING

from ..tools.codata import PhysicalConstant, load_codata_constants

if TYPE_CHECKING:
    from ..core.state import Claim, SourceRef


@dataclass(frozen=True)
class FormulaRecord:
    """A single registered formula or constant with full provenance.

    For constants: expr can be the numeric value as string or the symbol.
    For expressions: expr is a sympy-compatible string (or lhs==rhs for identities).

    The record itself does not perform verification — that is the job of
    identity_research + physics gates + Ledger.
    """

    record_id: str
    kind: str                 # "constant" | "closed_form" | "identity" | ...
    name: str
    expr: str                 # human + machine readable (e.g. "e", "1.602176634e-19", "F=ma", "lhs==rhs")
    unit: Optional[str] = None
    uncertainty: Optional[float] = None
    exact: bool = False
    assumptions: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()   # urls, DOIs, "NIST CODATA 2022:...", "DLMF:10.2.3"
    verified_fp: Optional[str] = None  # from identity_research or numeric gate
    ledger_claim_id: Optional[str] = None

    def content_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class FormulaRegistry:
    """In-memory registry. Thread-unsafe by design (single run).

    Usage:
        reg = FormulaRegistry()
        reg.register_constant(const)
        c = reg.get("e")
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, FormulaRecord] = {}
        self._by_name: Dict[str, FormulaRecord] = {}

    def register(self, rec: FormulaRecord) -> str:
        if rec.record_id in self._by_id:
            # first-writer wins (deterministic, matches NoveltyIndex philosophy)
            return self._by_id[rec.record_id].content_hash()
        self._by_id[rec.record_id] = rec
        if rec.name not in self._by_name:  # name is human-preferred key
            self._by_name[rec.name] = rec
        return rec.content_hash()

    def register_constant(self, const: PhysicalConstant, *, record_id: Optional[str] = None) -> FormulaRecord:
        rid = record_id or f"const:{const.name}"
        rec = FormulaRecord(
            record_id=rid,
            kind="constant",
            name=const.name,
            expr=str(const.value),
            unit=const.unit,
            uncertainty=const.uncertainty,
            exact=const.exact,
            sources=(const.source,),
        )
        self.register(rec)
        # first-writer-wins: return the record actually stored under this id, which on a
        # duplicate id is the earlier one (not the freshly-built rec we just discarded).
        return self._by_id[rid]

    def get(self, name_or_id: str) -> FormulaRecord:
        if name_or_id in self._by_id:
            return self._by_id[name_or_id]
        if name_or_id in self._by_name:
            return self._by_name[name_or_id]
        raise KeyError(f"formula not registered: {name_or_id!r}")

    def list_names(self) -> List[str]:
        return sorted(self._by_name.keys())

    def load_codata(self) -> int:
        """Convenience: populate from the current CODATA set. Calls the module-level
        ``load_codata_constants`` (so tests can monkeypatch it on this module)."""
        consts = load_codata_constants()
        count = 0
        for c in consts.values():
            self.register_constant(c)
            count += 1
        return count

    def get_codata_source_ref(self, table_text: str) -> "SourceRef":
        """Return a SourceRef for the table that backs the currently loaded CODATA constants."""
        from ..tools.codata import codata_table_source_ref
        return codata_table_source_ref(table_text)

    def make_claim_for(self, name: str, table_text: str) -> "Claim":
        """Create a proper Claim for a registered constant (ties to Ledger)."""
        from ..tools.codata import get_constant, make_codata_constant_claim
        const = get_constant(name)  # the live one
        # If the record came from this registry, we still use the authoritative const
        return make_codata_constant_claim(const, table_text)
