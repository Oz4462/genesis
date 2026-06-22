"""Unit tests for ``gen.config`` — defaults, hash determinism, round-trip.

These exercise the public reproducibility contract (PHASE_ALPHA §7, A5): the
config is a frozen dataclass tree whose canonical JSON SHA-256 is the anchor
that, together with run_id + ledger, makes a run reproducible. We test that
contract — stable defaults, deterministic hash, lossless serialization round-trip
— rather than any implementation detail.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path

from hypothesis import given, strategies as st

# Match the repo convention: each test file puts ``src`` on the path so the
# package imports as ``gen.*`` without an installed distribution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.config import (  # noqa: E402
    Config,
    Models,
    PhaseAlphaConfig,
    config_hash,
    default_config,
)

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")  # lowercase-hex SHA-256 digest shape


# --- (a) construction / defaults -------------------------------------------

def test_default_config_is_a_config():
    assert isinstance(default_config(), Config)
    # default_config() is just Config() — both must agree (frozen equality).
    assert default_config() == Config()


def test_phase_alpha_defaults():
    pa = default_config().phase_alpha
    assert pa.confidence_threshold == 0.7
    assert pa.max_refine_rounds == 3
    assert pa.require_independent_source is True
    assert pa.min_sources_for_verified == 2
    # A single declared backend, kept as a 1-tuple (never exploded to chars).
    assert pa.search_backends == ("semantic_scholar",)


def test_model_defaults_are_cross_family():
    models = default_config().phase_alpha.models
    assert models.generator == "claude-opus-4-8"
    assert models.verifier == "grok-composer-2.5-fast"
    assert models.judge is None
    # Core principle 3 (cross-model): the verifier must not be the generator.
    assert models.generator != models.verifier


def test_phase_beta_and_gamma_defaults():
    cfg = default_config()
    assert cfg.phase_beta.confidence_threshold == 0.7
    assert cfg.phase_beta.min_grounded_approaches == 2
    assert cfg.phase_beta.require_verified_grounding is True
    assert cfg.phase_gamma.confidence_threshold == 0.7
    assert cfg.phase_gamma.derivation_tolerance == 1e-9
    assert cfg.phase_gamma.require_grounded_approach is True


def test_default_factories_are_independent():
    # field(default_factory=...) must yield distinct (but equal) instances so a
    # frozen tree is never accidentally aliased across configs.
    a, b = Config(), Config()
    assert a.phase_alpha.models is not b.phase_alpha.models
    assert a.phase_alpha.models == b.phase_alpha.models


# --- (b) config_hash determinism -------------------------------------------

def test_hash_is_lowercase_hex_sha256():
    digest = config_hash(default_config())
    assert _HEX64.match(digest), digest
    assert len(digest) == 64


def test_hash_is_deterministic_across_independent_builds():
    # Two independently constructed defaults must hash identically — the whole
    # point of A5 reproducibility.
    assert config_hash(Config()) == config_hash(Config())
    assert config_hash(default_config()) == config_hash(default_config())


def test_hash_changes_when_a_field_changes():
    base = default_config()
    mutated = Config.from_dict(
        {"phase_alpha": {"confidence_threshold": 0.95}}
    )
    assert mutated.phase_alpha.confidence_threshold == 0.95
    assert config_hash(mutated) != config_hash(base)


def test_hash_independent_of_dict_key_order():
    # Canonical form sorts keys, so semantically-equal configs hash equal
    # regardless of how the source dict was ordered.
    d1 = {"phase_alpha": {"confidence_threshold": 0.42, "max_refine_rounds": 5}}
    d2 = {"phase_alpha": {"max_refine_rounds": 5, "confidence_threshold": 0.42}}
    assert config_hash(Config.from_dict(d1)) == config_hash(Config.from_dict(d2))


# --- (c) asdict / to_dict round-trip ---------------------------------------

def test_to_dict_from_dict_round_trip():
    original = default_config()
    restored = Config.from_dict(original.to_dict())
    assert restored == original  # frozen dataclass structural equality


def test_from_dict_empty_returns_default():
    assert Config.from_dict({}) == default_config()
    assert Config.from_dict(None) == default_config()  # documented: data or {}


def test_round_trip_preserves_hash():
    original = default_config()
    restored = Config.from_dict(original.to_dict())
    assert config_hash(restored) == config_hash(original)


def test_round_trip_of_mutated_config():
    # Round-trip must be lossless even for a non-default tree.
    mutated = replace(
        default_config(),
        phase_alpha=replace(
            default_config().phase_alpha,
            confidence_threshold=0.81,
            search_backends=("arxiv", "semantic_scholar"),
            models=Models(generator="g-x", verifier="v-y", judge="j-z"),
        ),
    )
    restored = Config.from_dict(mutated.to_dict())
    assert restored == mutated


# --- (d) search_backends coercion ------------------------------------------

def test_search_backends_string_becomes_singleton_tuple():
    # The documented contract: a plain string is a single backend name, so it
    # must wrap into a 1-tuple and NEVER explode into one entry per character.
    cfg = Config.from_dict({"phase_alpha": {"search_backends": "semantic_scholar"}})
    assert cfg.phase_alpha.search_backends == ("semantic_scholar",)


def test_search_backends_list_becomes_tuple():
    cfg = Config.from_dict(
        {"phase_alpha": {"search_backends": ["arxiv", "semantic_scholar"]}}
    )
    assert cfg.phase_alpha.search_backends == ("arxiv", "semantic_scholar")


def test_search_backends_none_becomes_empty_tuple():
    cfg = Config.from_dict({"phase_alpha": {"search_backends": None}})
    assert cfg.phase_alpha.search_backends == ()


# --- property-based invariants ---------------------------------------------

# A non-empty, non-whitespace backend name (avoid YAML/JSON-control noise is
# unnecessary here since we never serialize to YAML in these properties).
_backend_name = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=12,
)


@given(name=_backend_name)
def test_property_single_string_backend_never_explodes(name):
    # INVARIANT: for ANY single string, coercion yields exactly that 1-tuple —
    # the length is always 1, regardless of how many characters the name has.
    cfg = Config.from_dict({"phase_alpha": {"search_backends": name}})
    assert cfg.phase_alpha.search_backends == (name,)
    assert len(cfg.phase_alpha.search_backends) == 1


@given(
    threshold=st.floats(min_value=0.0, max_value=1.0),
    rounds=st.integers(min_value=0, max_value=10),
    backends=st.lists(_backend_name, max_size=5),
)
def test_property_round_trip_is_identity(threshold, rounds, backends):
    # INVARIANT: from_dict(to_dict(c)) == c for arbitrary phase_alpha values.
    cfg = replace(
        default_config(),
        phase_alpha=replace(
            default_config().phase_alpha,
            confidence_threshold=threshold,
            max_refine_rounds=rounds,
            search_backends=tuple(backends),
        ),
    )
    restored = Config.from_dict(cfg.to_dict())
    assert restored == cfg
    # And the hash, being a pure function of the canonical form, is preserved.
    assert config_hash(restored) == config_hash(cfg)


@given(
    a=st.floats(min_value=0.0, max_value=1.0),
    b=st.floats(min_value=0.0, max_value=1.0),
)
def test_property_hash_equal_iff_value_equal(a, b):
    # INVARIANT: equal configs hash equal; differing configs hash differently.
    # Normalize signed zero (-0.0 + 0.0 == +0.0 in IEEE-754): -0.0 is
    # dataclass-equal to 0.0 yet serializes to a different JSON literal, which
    # would spuriously break the "equal value -> equal hash" direction.
    a, b = a + 0.0, b + 0.0
    ca = Config.from_dict({"phase_alpha": {"confidence_threshold": a}})
    cb = Config.from_dict({"phase_alpha": {"confidence_threshold": b}})
    if a == b:
        assert config_hash(ca) == config_hash(cb)
    else:
        assert config_hash(ca) != config_hash(cb)
