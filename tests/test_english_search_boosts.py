"""Skeptic DE→EN search boosts + evidence windowing — fact-free retrieval only."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.skeptic import (  # noqa: E402
    _english_search_boosts,
    _evidence_for_judge,
    _JUDGE_MAX_CHARS,
)


def test_steel_density_german_claim_boosts_english_keywords():
    boosts = _english_search_boosts(
        "Die Dichte von Stahl liegt typischerweise zwischen 7750 und 8050 kg/m3."
    )
    assert boosts
    joined = " ".join(boosts).lower()
    assert "steel" in joined and "density" in joined


def test_english_stainless_claim_boosts_steel_density():
    # Live bug: English "stainless steel" claim only boosted bare "density"
    boosts = _english_search_boosts(
        "Die Dichte von stainless steel liegt je nach Legierung im Bereich von 7.5 bis 8.0 g/cm3."
    )
    joined = " ".join(boosts).lower()
    assert "stainless" in joined or "steel" in joined
    assert "density" in joined


def test_no_boost_for_unrelated_claim():
    assert _english_search_boosts("Build123d uses the Open Cascade kernel.") == []


def test_evidence_window_keeps_density_sentence():
    # Large extract with density buried in the middle
    head = "Intro " * 2000
    mid = (
        "The density of steel varies based on the alloying constituents "
        "but usually ranges between 7,750 and 8,050 kg/m3."
    )
    tail = " Outro " * 2000
    content = head + mid + tail
    assert len(content) > _JUDGE_MAX_CHARS
    window = _evidence_for_judge(
        "Die Dichte von Stahl liegt zwischen 7750 und 8050 kg/m3.",
        content,
    )
    assert "7,750" in window or "density of steel" in window.lower()
    assert len(window) <= _JUDGE_MAX_CHARS
