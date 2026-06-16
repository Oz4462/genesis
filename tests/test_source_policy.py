"""Tests für SourcePolicy + fail-closed Storage-Gate (Bauwelle B3/A4).

Siehe docs/GENESIS_PLATFORM_BUILD_TODO.md §3 (B3 SourceConnectorRegistry, A4
Source Connector Contract) und §11 ("Discovery ja, Vollspeicher nein";
"Volltext nur speichern, wenn erlaubt/lizenziert").

Das Gate ist die harte Bedingung: ohne explizite Lizenz-Erlaubnis wird das
Persistieren von Volltext verweigert (fail-closed, GENESIS-Kernprinzip 2).
"""

import pytest

from gen.wissensbasis.store import (
    SourcePolicy,
    SourceConnector,
    StoragePolicyViolation,
    assert_may_store,
)


def test_default_policy_is_fail_closed_for_fulltext():
    """Default-Policy erlaubt keine Volltext-Speicherung (fail-closed)."""
    p = SourcePolicy()
    assert p.store_fulltext is False
    assert p.may_store("fulltext") is False
    # Snippets (Evidence-Auszüge) sind per Default erlaubt (PLAN B4: Evidence statt Datenhalde)
    assert p.may_store("snippet") is True


def test_assert_may_store_blocks_fulltext_without_license():
    """Das Gate wirft, wenn Volltext ohne Lizenz gespeichert werden soll."""
    proprietary = SourcePolicy(license="proprietary", store_fulltext=False)
    with pytest.raises(StoragePolicyViolation):
        assert_may_store(proprietary, "fulltext")
    # Snippet bleibt erlaubt
    assert_may_store(proprietary, "snippet")  # darf nicht werfen


def test_open_access_policy_allows_fulltext():
    """Open-Access-Quelle darf Volltext speichern."""
    oa = SourcePolicy(license="open-access", store_fulltext=True, ttl_days=30)
    assert oa.may_store("fulltext") is True
    assert_may_store(oa, "fulltext")  # darf nicht werfen


def test_missing_policy_is_deny_all():
    """Fehlende Policy (None) wird als deny-all behandelt — auch Snippets."""
    with pytest.raises(StoragePolicyViolation):
        assert_may_store(None, "fulltext")
    with pytest.raises(StoragePolicyViolation):
        assert_may_store(None, "snippet")


def test_unknown_content_kind_fails_closed():
    """Unbekannte content_kind wird verweigert (kein geratener Default)."""
    oa = SourcePolicy(license="open-access", store_fulltext=True)
    assert oa.may_store("raw_dump") is False
    with pytest.raises(StoragePolicyViolation):
        assert_may_store(oa, "raw_dump")


def test_connector_carries_policy():
    """Ein SourceConnector kann eine Policy tragen (rückwärtskompatibel: default None)."""
    plain = SourceConnector(name="x", kind="web")
    assert plain.policy is None  # backward compatible

    arxiv = SourceConnector(
        name="arxiv",
        kind="arxiv",
        policy=SourcePolicy(license="open-access", store_fulltext=True, store_snippets=True, ttl_days=90),
    )
    assert arxiv.policy is not None
    assert_may_store(arxiv.policy, "fulltext")


def test_default_registry_connectors_declare_policies():
    """Jeder seeded Connector der Default-Registry trägt eine SourcePolicy (PLAN B3 DoD:
    'Jeder Connector gibt ein SourcePolicy-Objekt zurück')."""
    from gen.wissensbasis.store import get_registry

    reg = get_registry()
    conns = reg.list()
    assert conns, "registry should seed at least one connector"
    for c in conns:
        assert c.policy is not None, f"connector {c.name} declares no SourcePolicy"

    arxiv = reg.get("arxiv")
    assert arxiv.policy.license == "open-access"
    assert arxiv.policy.store_fulltext is True

    # internal sources are Genesis' own output -> fully storable
    local = reg.get("local_out")
    assert local.policy.license == "internal"
    assert local.policy.may_store("fulltext")
