"""Offline tests for DLMF thin client + integration with FormulaRegistry."""

from __future__ import annotations

import pytest

from gen.tools.dlmf import (
    DlmfEntry,
    fetch_dlmf_tex,
    fetch_dlmf_entry,
    dlmf_source_ref,
    load_curated_dlmf,
    DlmfError,
)
from gen.formulas.registry import FormulaRegistry, FormulaRecord


_SAMPLE_TEX = r"\( J_{\nu}(z) = \left(\frac{z}{2}\right)^{\nu} \sum_{k=0}^{\infty} \frac{(-1)^{k} (z/2)^{2k}}{k! \Gamma(\nu+k+1)} \)"


def test_fetch_dlmf_tex_injected(monkeypatch):
    def fake_fetch(*a, **k):
        return _SAMPLE_TEX
    monkeypatch.setattr("gen.tools.dlmf.fetch_dlmf_tex", fake_fetch)

    tex = fetch_dlmf_tex("10.2.E2")
    assert "J" in tex and "Gamma" in tex


def test_dlmf_entry_and_source_ref():
    entry = DlmfEntry(
        identifier="10.2.E2",
        title="Bessel J",
        latex=_SAMPLE_TEX,
        url="https://dlmf.nist.gov/10.2.E2",
        chapter="10",
    )
    src = dlmf_source_ref(entry)
    assert src.url_or_id.endswith("10.2.E2")
    assert src.content_hash is not None


def test_load_curated_offline(monkeypatch):
    def fake_entry(ident, **kw):
        return DlmfEntry(
            identifier=ident,
            title=f"fake {ident}",
            latex=r"\sin z",
            url=f"https://dlmf.nist.gov/{ident}",
            chapter=ident.split(".")[0],
        )
    monkeypatch.setattr("gen.tools.dlmf.fetch_dlmf_entry", fake_entry)

    entries = load_curated_dlmf(use_cache=False)
    assert "10.2.E1" in entries or len(entries) > 0   # at least some curated succeeded via fake


def test_dlmf_registry_roundtrip(monkeypatch):
    def fake_entry(ident, **kw):
        return DlmfEntry(ident, f"title-{ident}", r"J_\nu(z)", f"https://dlmf/{ident}", "10")
    monkeypatch.setattr("gen.tools.dlmf.fetch_dlmf_entry", fake_entry)

    entries = load_curated_dlmf(use_cache=False)
    reg = FormulaRegistry()

    for ident, e in entries.items():
        rec = FormulaRecord(
            record_id=f"dlmf:{ident}",
            kind="identity",
            name=f"dlmf-{ident}",
            expr=e.latex,
            sources=(e.source,),
        )
        reg.register(rec)

    assert len(reg.list_names()) >= 1
    # Can be turned into Ledger sources later via dlmf_source_ref
