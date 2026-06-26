"""Tests for the professional deliverable finalizer.

The finalizer must (a) actually WRITE files (not print success over nothing), (b) NEVER fabricate a
goldset score or all-green gates when they are absent, (c) be domain-aware (no humanoid research forced
into a non-humanoid deliverable), and (d) honestly skip the PDF when no backend is installed. These pin
the anti-fabrication contract directly (the opposite of the pasted print()-only draft).
"""

from __future__ import annotations

from pathlib import Path

from gen.finalizer import finalize_pipeline


def test_forge_writes_real_files(tmp_path):
    res = finalize_pipeline(
        {"name": "Test", "idea": "x", "gates": {"alpha": True, "delta": False}, "gaps": ["g1"]},
        out_dir=tmp_path,
    )
    md = Path(res["markdown"])
    html = Path(res["html"])
    assert md.exists() and md.stat().st_size > 0
    assert html.exists() and html.stat().st_size > 0
    assert (tmp_path / "MANIFEST.json").exists()
    # real gate verdicts rendered (PASS/FAIL), not a fabricated all-green
    text = md.read_text(encoding="utf-8")
    assert "alpha" in text and ("PASS" in text or "✅" in text)
    assert "delta" in text and ("FAIL" in text or "❌" in text)


def test_never_fabricates_score_or_gates_when_absent(tmp_path):
    # No goldset_score, no gates → must say "not measured" / "no gate verdicts", never invent 97 or all-green.
    res = finalize_pipeline({"name": "Bare", "idea": "y"}, out_dir=tmp_path)
    text = Path(res["markdown"]).read_text(encoding="utf-8")
    assert "not measured" in text.lower()
    assert "97" not in text                      # the pasted draft's fabricated default
    assert "no gate verdicts" in text.lower()


def test_research_is_domain_aware(tmp_path):
    report = "PROPRIETARY HUMANOID RESEARCH REPORT BODY"
    cool = finalize_pipeline({"name": "Cooling system", "idea": "data-center cooling", "research": report},
                             out_dir=tmp_path / "cool")
    assert report not in Path(cool["markdown"]).read_text(encoding="utf-8")  # not forced into a cooling deliverable
    hum = finalize_pipeline({"name": "AETHON humanoid", "idea": "a humanoid robot", "research": report},
                            out_dir=tmp_path / "hum")
    assert report in Path(hum["markdown"]).read_text(encoding="utf-8")       # included where relevant


def test_pdf_is_honestly_skipped_without_backend(tmp_path):
    res = finalize_pipeline({"name": "NoPdf", "idea": "z"}, out_dir=tmp_path)
    # No weasyprint in the env → pdf is None with a reason, and no PDF file is fabricated.
    if res["pdf"] is None:
        assert res["pdf_skipped"]
        assert not (tmp_path / "DELIVERABLE.pdf").exists()
    else:  # if a backend IS present, the file must really exist
        assert Path(res["pdf"]).exists()
