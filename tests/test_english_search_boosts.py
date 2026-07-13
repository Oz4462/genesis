"""Skeptic DE→EN search boosts — fact-free retrieval keywords only."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.skeptic import _english_search_boosts  # noqa: E402


def test_steel_density_german_claim_boosts_english_keywords():
    boosts = _english_search_boosts(
        "Die Dichte von Stahl liegt typischerweise zwischen 7750 und 8050 kg/m3."
    )
    assert boosts
    joined = " ".join(boosts).lower()
    assert "steel" in joined and "density" in joined


def test_no_boost_for_unrelated_claim():
    assert _english_search_boosts("Build123d uses the Open Cascade kernel.") == []
