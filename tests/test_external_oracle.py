"""External-oracle plugin type — gated claims, never raw truth (external/oracle.py, INVENTOR §10¾ D).

Pins the third plugin type's anti-hallucination invariant: an external oracle (foundation model / heavy
simulator / DB) emits an OracleClaim PROPOSAL that always carries a validated license binding, and the only
path into the ledger writes it UNVERIFIED — an oracle can never self-certify a VERIFIED fact, and a claim
without a license binding cannot be constructed. A non-commercial oracle could not even be bound (TC1).
Offline, deterministic, async ledger.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from gen.external import (
    ExternalOracle, IntegrationMode, OracleClaim,
    external_binding, oracle_claim_to_ledger, record_oracle_claim,
)
from gen.ledger.store import InMemoryLedgerStore

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


class _FakeFoldOracle:
    """An offline stand-in for a GPU foundation-model oracle (Boltz-2, MIT — the open replacement for the
    non-commercial AlphaFold3)."""

    name = "boltz2-fake"
    binding = external_binding("boltz2", "0.4", "MIT",
                               provenance="hf:boltz-community/boltz-2", integration_mode=IntegrationMode.LIBRARY)

    async def query(self, spec):
        return OracleClaim(subject=str(spec), statement="predicted fold pLDDT 82", binding=self.binding,
                           oracle_provenance="boltz2.predict(seq=...)", value=82.0, uncertainty=6.0,
                           confidence=0.7)


def test_fake_oracle_satisfies_the_protocol():
    assert isinstance(_FakeFoldOracle(), ExternalOracle)


def test_oracle_output_is_gated_into_the_ledger_as_unverified_with_provenance():
    store = InMemoryLedgerStore()
    oc = run(_FakeFoldOracle().query("protein X"))
    claim = run(record_oracle_claim(store, oc, run_id="r1", created_at=_T0))
    assert claim.status.value == "unverified"                 # an oracle never self-certifies
    # both the specific call AND the licensed-source provenance are recorded
    provs = {s.url_or_id for s in claim.sources}
    assert "boltz2.predict(seq=...)" in provs and "hf:boltz-community/boltz-2" in provs
    assert "MIT" in claim.text and "value=82" in claim.text
    assert run(store.get_claims("r1"))[0].id == "oracle:boltz2:protein X"


def test_uncertainty_is_recorded_not_hidden():
    oc = OracleClaim(subject="s", statement="answer", binding=_FakeFoldOracle.binding,
                     oracle_provenance="call", value=1.0, uncertainty=None)
    claim = oracle_claim_to_ledger(oc, created_at=_T0)
    assert "unknown" in claim.text                            # a missing uncertainty is stated, not faked as 0


def test_an_oracle_claim_without_a_binding_is_structurally_impossible():
    with pytest.raises(TypeError):
        OracleClaim(subject="x", statement="y", binding=None, oracle_provenance="z")  # type: ignore[arg-type]


def test_a_noncommercial_oracle_cannot_even_be_bound():
    # AlphaFold3-style non-commercial weights: the binding raises at construction, so no NC oracle exists
    with pytest.raises(ValueError):
        external_binding("alphafold3", "1.0", "CC-BY-NC-4.0", provenance="weights")


def test_blank_oracle_fields_are_rejected():
    with pytest.raises(ValueError):
        OracleClaim(subject="", statement="y", binding=_FakeFoldOracle.binding, oracle_provenance="z")
    with pytest.raises(ValueError):
        OracleClaim(subject="x", statement="y", binding=_FakeFoldOracle.binding, oracle_provenance="",
                    confidence=2.0)


def test_recording_is_the_only_path_and_stays_unverified_even_with_high_confidence():
    # even a confident oracle answer is UNVERIFIED in the ledger — promotion is a deterministic gate's job
    oc = OracleClaim(subject="s", statement="very sure", binding=_FakeFoldOracle.binding,
                     oracle_provenance="call", confidence=1.0)
    claim = oracle_claim_to_ledger(oc)
    assert claim.status.value == "unverified" and claim.confidence == 1.0
