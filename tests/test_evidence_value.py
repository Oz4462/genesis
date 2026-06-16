"""Tests für den Evidence Extractor (Bauwelle B4).

Siehe docs/GENESIS_PLATFORM_BUILD_TODO.md §3 (B4 Evidence Extractor):
"Aus einem Datenblattwert wird ein strukturierter EvidenceValue. Gate blockiert
Wert ohne Quelle, Einheit oder Gültigkeitsbereich."

EvidenceValue ist das quantitative Pendant zu Claim: ein Zahlenwert darf nur als
Beleg existieren, wenn er Quelle + Einheit + Gültigkeitsbereich trägt
(GENESIS-Kernprinzip 1; Mars-Climate-Orbiter-Fehlerklasse).
"""

import pytest

from gen.core.state import SourceRef, SourceSupport
from gen.core.errors import EvidenceIntegrityError
from gen.wissensbasis.evidence import EvidenceValue, extract_evidence_value
from gen.wissensbasis.store import SourcePolicy, assert_may_store


def _src() -> SourceRef:
    return SourceRef(url_or_id="datasheet://acme-cell-x/v2", retrieved=True,
                     content_hash="abc123", support=SourceSupport.SUPPORTS)


def test_happy_path_builds_structured_value():
    ev = EvidenceValue(
        claim_text="max continuous discharge current",
        value=30.0, unit="A", validity_range="25 °C, pack level",
        source=_src(), uncertainty="±2 A", quelle="extractor:test",
    )
    assert ev.value == 30.0 and ev.unit == "A"
    assert ev.source.url_or_id.startswith("datasheet://")


def test_value_without_source_is_rejected():
    with pytest.raises(EvidenceIntegrityError):
        EvidenceValue(claim_text="energy density", value=300.0, unit="Wh/kg",
                      validity_range="pack level", source=None)  # type: ignore[arg-type]


def test_value_without_unit_is_rejected():
    with pytest.raises(EvidenceIntegrityError):
        EvidenceValue(claim_text="energy density", value=300.0, unit="",
                      validity_range="pack level", source=_src())


def test_value_without_validity_range_is_rejected():
    with pytest.raises(EvidenceIntegrityError):
        EvidenceValue(claim_text="energy density", value=300.0, unit="Wh/kg",
                      validity_range="   ", source=_src())


def test_dimensionless_value_is_allowed():
    """Verhältnisse/Zählwerte sind erlaubt — Einheit 'dimensionless', nicht leer."""
    ev = EvidenceValue(claim_text="round-trip efficiency", value=0.92,
                       unit="dimensionless", validity_range="20 °C, 1C rate",
                       source=_src())
    assert ev.unit == "dimensionless"


def test_extract_builder_from_datasheet_value():
    """B4 DoD: aus einem rohen Datenblattwert wird ein strukturierter EvidenceValue."""
    ev = extract_evidence_value(
        claim_text="thermal resistance junction-to-case",
        value=1.5, unit="K/W", validity_range="TO-220, still air",
        source_url="datasheet://acme-fet/rev3", content_hash="deadbeef",
        retrieved=True, quelle="extractor:test",
    )
    assert isinstance(ev, EvidenceValue)
    assert ev.source.retrieved is True and ev.source.content_hash == "deadbeef"


def test_extract_builder_rejects_missing_source_url():
    with pytest.raises(EvidenceIntegrityError):
        extract_evidence_value(claim_text="x", value=1.0, unit="A",
                               validity_range="25 °C", source_url="")


def test_evidence_composes_with_snippet_storage_policy():
    """B3↔B4-Naht: ein EvidenceValue ist Snippet-Evidenz; das Storage-Gate erlaubt
    Snippets bei open-access, blockiert sie bei einer no-snippet-Policy."""
    ev = extract_evidence_value(claim_text="capacity", value=5.0, unit="Ah",
                                validity_range="0.2C, 25 °C", source_url="datasheet://x")
    assert ev is not None
    open_access = SourcePolicy(license="open-access", store_snippets=True)
    assert_may_store(open_access, "snippet")  # darf nicht werfen

    no_snippet = SourcePolicy(license="metadata-only", store_snippets=False)
    with pytest.raises(Exception):
        assert_may_store(no_snippet, "snippet")
