"""Characterization test for ``model_family`` codex-vs-openai precedence.

This pins the headline contract of T03: an id that carries BOTH the ``gpt`` and
the ``codex`` substrings (the deselected ``gpt-5.5-codex`` case) must resolve to
the more-specific ``codex`` family, while every other known mapping — including
plain ``gpt-4o``/``gpt-4o-mini`` -> ``openai`` — is unchanged.

Before the fix, ``_FAMILY_KEYWORDS`` tested ``("gpt", ...) -> openai`` before
``("codex",) -> codex``; first-match-wins therefore mis-attributed
``gpt-5.5-codex`` to ``openai``. Mis-attribution is not cosmetic: the cross-model
audit (A6) relies on family equality to forbid same-family self-verification, so
a Codex judge masquerading as ``openai`` could be wrongly accepted or rejected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import ModelConflictError  # noqa: E402
from gen.verification.cross_model import (  # noqa: E402
    assert_different_families,
    model_family,
)


# --- The full known-family table, with the codex-precedence rows --------------

KNOWN_FAMILIES = [
    # Anthropic
    ("claude-opus-4-8", "claude"),
    ("anthropic.claude-v2", "claude"),
    # OpenAI base family — plain gpt ids must stay openai.
    ("gpt-4o", "openai"),
    ("gpt-4o-mini", "openai"),
    ("openai/o3-mini", "openai"),
    ("davinci-002", "openai"),
    # Codex — the narrower family must win even when 'gpt' is also present.
    ("codex", "codex"),
    ("gpt-5.5-codex", "codex"),
    ("openai-codex-latest", "codex"),
    # Other families (regression guard: reorder must not disturb these).
    ("gemini-1.5-pro", "google"),
    ("gemma2:9b", "google"),
    ("llama3.1:8b", "llama"),
    ("mixtral-8x7b", "mistral"),
    ("codestral-22b", "mistral"),
    ("qwen2.5:14b", "qwen"),
    ("deepseek-r1", "deepseek"),
    ("grok-build", "xai"),
    ("command-r-plus", "cohere"),
    ("phi-3-mini", "phi"),
]


@pytest.mark.parametrize("model,family", KNOWN_FAMILIES)
def test_known_family_table(model, family):
    assert model_family(model) == family


def test_codex_beats_openai_for_combined_id():
    """The deselected case: an id with both substrings resolves to codex."""
    assert "gpt" in "gpt-5.5-codex"
    assert "codex" in "gpt-5.5-codex"
    assert model_family("gpt-5.5-codex") == "codex"


def test_plain_gpt_still_openai():
    """Precedence change must not steal plain gpt ids from openai."""
    assert model_family("gpt-4o") == "openai"
    assert model_family("gpt-4o-mini") == "openai"


# --- Unknown-fallback and empty-raises contracts ------------------------------

def test_unknown_falls_back_to_leading_token():
    assert model_family("acme-supermodel-v2") == "acme"
    # Two distinct unknowns must not collide on a shared default.
    assert model_family("foo-1") != model_family("bar-1")


@pytest.mark.parametrize("empty", ["", "   ", "\t\n"])
def test_empty_id_raises(empty):
    with pytest.raises(ValueError):
        model_family(empty)


# --- assert_different_families: codex vs openai are genuinely different --------

def test_codex_and_openai_are_different_families():
    # gpt-5.5-codex (codex) vs gpt-4o (openai) must NOT collide — no raise.
    assert_different_families("gpt-5.5-codex", "gpt-4o")
    # And the reverse direction is symmetric.
    assert_different_families("gpt-4o", "gpt-5.5-codex")


def test_two_codex_ids_collide():
    # Both resolve to 'codex' -> same family -> self-verification is blocked.
    with pytest.raises(ModelConflictError):
        assert_different_families("codex", "gpt-5.5-codex")


# --- Property: appending '-codex' to any non-codex id forces the codex family --

# WHY property-based: the precedence rule must hold for ALL gpt/openai-shaped
# ids, not just the hand-picked ones. Any id with 'codex' as a substring is a
# codex id by contract, regardless of what other family keywords it also carries.
_PREFIXES = st.sampled_from(["gpt-5.5", "gpt-4o", "openai", "o3", "foo", "bar-7"])


@given(prefix=_PREFIXES)
def test_any_id_containing_codex_is_codex(prefix):
    assert model_family(f"{prefix}-codex") == "codex"
