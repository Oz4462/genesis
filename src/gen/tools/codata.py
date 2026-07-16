"""CODATA 2022 (NIST) fundamental physical constants loader.

Authoritative, free, offline-cacheable source for physical constants.
Primary URL (no auth, stable):
    https://physics.nist.gov/cuu/Constants/Table/allascii.txt

Contract:
- Deterministic parsing (spaces in numbers are digit grouping, removed for float()).
- "(exact)" uncertainty marks 2019 SI defining constants (value is exact by definition).
- Returns PhysicalConstant with provenance.
- Supports injected raw text for fully offline / reproducible tests.
- Cache written to out/codata/allascii_2022.txt (content-hashable).
- Never invents values; parse failure on a line -> that constant is omitted with log (caller decides).

This is reference data only. Any *use* of a constant in a Claim must record the
source via the Ledger (content_hash of the fetched/cached table).

Sources:
- NIST CODATA 2022 adjustment (web version 9.0, May 2024 update).
  https://physics.nist.gov/constants
  "The 2022 CODATA Recommended Values of the Fundamental Physical Constants"
  Tiesinga et al.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.request import Request, urlopen

from ..core.state import SourceRef

if TYPE_CHECKING:  # only for the "Claim" return annotation below; the runtime import is
    from ..core.state import Claim  # kept local in the function body to avoid an import cycle

DEFAULT_URL = "https://physics.nist.gov/cuu/Constants/Table/allascii.txt"
CACHE_DIR = Path("out/codata")
CACHE_FILE = CACHE_DIR / "allascii_2022.txt"


class CodataError(RuntimeError):
    """Raised for unrecoverable issues loading CODATA (network, parse, etc.).
    Callers should treat this as an honest gap (similar to SearchBackendError)."""
    pass


@dataclass(frozen=True)
class PhysicalConstant:
    """One CODATA constant.

    value and uncertainty are in the declared unit (usually SI coherent).
    uncertainty=None + exact=True for the seven defining constants (post-2019 SI).
    """

    name: str                 # machine key e.g. "electron_mass"
    quantity: str             # original human description
    value: float
    uncertainty: Optional[float]
    unit: str
    exact: bool = False
    source: str = "NIST CODATA 2022 https://physics.nist.gov/cuu/Constants/Table/allascii.txt"


def _clean_name(qty: str) -> str:
    """Stable, full machine identifier from the quantity text, e.g. 'elementary charge' ->
    'elementary_charge'. Used verbatim as the dict key, the registry name, and the record id
    ('const:elementary_charge'), so it must stay the descriptive name — no short aliases."""
    s = qty.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _parse_number(token: str) -> float:
    """Remove digit-grouping spaces and parse float. Handles '1.234 567 e-10' and 'exact' cases."""
    cleaned = token.replace(" ", "").replace("...", "")
    if cleaned.lower() in ("(exact)", "exact"):
        raise ValueError("exact token passed to numeric parser")
    return float(cleaned)


def parse_allascii(text: str) -> dict[str, PhysicalConstant]:
    """Pure deterministic parser. Returns name -> PhysicalConstant.

    Lines with unparseable values/unc are silently dropped (they are not core
    engineering constants for GENESIS use).
    """
    constants: dict[str, PhysicalConstant] = {}
    lines = text.splitlines()
    data_started = False

    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        if "-----" in line:
            data_started = True
            continue
        if not data_started:
            continue

        # Quantity is left side; value/unc/unit follow after 2+ spaces.
        m = re.match(r"^(?P<qty>.+?)\s{2,}(?P<rest>.+)$", line)
        if not m:
            continue

        qty = m.group("qty").strip()
        rest = m.group("rest").strip()

        # Split into at most value, uncertainty, unit (unit may contain spaces).
        parts = re.split(r"\s{2,}", rest, maxsplit=2)
        if len(parts) < 2:
            continue

        val_str = parts[0].strip()
        unc_str = parts[1].strip() if len(parts) > 1 else ""
        unit = parts[2].strip() if len(parts) > 2 else ""

        exact = "(exact)" in unc_str.lower() or unc_str.lower() == "exact"

        try:
            value = _parse_number(val_str)
            uncertainty = None if exact else _parse_number(unc_str)
        except Exception:
            # Malformed line in the authoritative table -> omit (conservative).
            continue

        name = _clean_name(qty)
        if name in constants:
            # Prefer first occurrence (table order is stable).
            continue

        constants[name] = PhysicalConstant(
            name=name,
            quantity=qty,
            value=value,
            uncertainty=uncertainty,
            unit=unit,
            exact=exact,
            source=f"NIST CODATA 2022 {DEFAULT_URL}",
        )

    return constants


def fetch_allascii(url: str = DEFAULT_URL, timeout: float = 15.0) -> str:
    """Fetch the raw table. Raises CodataError on any transport error (honest gap)."""
    try:
        req = Request(url, headers={"User-Agent": "GENESIS-research/0.1 (+https://github.com/genesis)"})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise CodataError(f"HTTP {resp.status} for {url}")
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise CodataError(f"failed to fetch CODATA table from {url}: {exc}") from exc


def load_codata_constants(
    *,
    raw_text: Optional[str] = None,
    use_cache: bool = True,
    refresh: bool = False,
) -> dict[str, PhysicalConstant]:
    """Load the 2022 CODATA set.

    Priority (for reproducibility):
      1. raw_text (tests / pinned gold data) — never touches network or disk.
      2. Existing cache (unless refresh).
      3. Fresh fetch + write to cache.

    The caller is responsible for recording the table as a source (see
    `codata_table_source_ref` and `content_hash_of`).

    Every factual use of these constants in a Claim **must** reference the
    table via SourceRef (url + content_hash) so that Ledger + gates can
    audit it.
    """
    if raw_text is not None:
        return parse_allascii(raw_text)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if use_cache and CACHE_FILE.exists() and not refresh:
        text = CACHE_FILE.read_text(encoding="utf-8")
        return parse_allascii(text)

    text = fetch_allascii()
    if use_cache:
        CACHE_FILE.write_text(text, encoding="utf-8")

    return parse_allascii(text)


def get_constant(name: str, constants: Optional[dict[str, PhysicalConstant]] = None) -> PhysicalConstant:
    """Convenience accessor. Raises KeyError on unknown (explicit, no silent default)."""
    if constants is None:
        constants = load_codata_constants()
    if name not in constants:
        raise KeyError(f"unknown CODATA constant {name!r} (available: {sorted(constants)[:5]}...)")
    return constants[name]


def content_hash_of(text: str) -> str:
    """Stable short hash of the *raw table text* for SourceRef.content_hash and reproducibility."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def codata_table_source_ref(table_text: str, *, retrieved: bool = True) -> SourceRef:
    """Build a SourceRef for the entire CODATA table.

    Use this when creating Claims that are backed by one or more constants from
    this table. The content_hash anchors the exact version of the data used.
    """
    return SourceRef(
        url_or_id=DEFAULT_URL,
        retrieved=retrieved,
        content_hash=content_hash_of(table_text),
        span="2022 CODATA complete listing",
        support="supports",  # type: ignore[arg-type]
    )


def make_codata_constant_claim(
    const: PhysicalConstant,
    table_text: str,
    *,
    claim_id: Optional[str] = None,
) -> "Claim":
    """Produce a ready-to-ledger Claim for a single CODATA constant.

    This ensures every use of a fundamental constant carries proper provenance
    back to the authoritative table + exact content hash.

    The claim text is the minimal atomic statement.
    """
    from ..core.state import Claim, ClaimStatus  # local to avoid top-level cycles

    table_hash = content_hash_of(table_text)
    text = (
        f"{const.quantity} = {const.value} {const.unit}"
        + (f" ± {const.uncertainty}" if const.uncertainty is not None else " (exact)")
    )
    source = codata_table_source_ref(table_text, retrieved=True)
    source = SourceRef(  # re-create to ensure support
        url_or_id=source.url_or_id,
        retrieved=source.retrieved,
        content_hash=table_hash,
        span=source.span,
        support=source.support,
    )

    cid = claim_id or f"codata2022:{const.name}"
    return Claim(
        id=cid,
        text=text,
        sources=[source],
        quote=f"{const.value} {const.unit}",
        status=ClaimStatus.UNVERIFIED,
        confidence=1.0 if const.exact else 0.99,  # exacts are definitions
        produced_by="codata_loader",
    )
