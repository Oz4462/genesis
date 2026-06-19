"""License-disciplined external-binding registry (external/registry.py).

Pins the hard license gate (CLAUDE.md §1 / INVENTOR §10¾ C): the core links only permissive licenses;
copyleft is a separate-process oracle ONLY; non-commercial is forbidden in the commercial core; an unknown
license is refused, never silently trusted. A valid binding is recorded into the ledger as a VERIFIED claim
carrying its provenance, so the dependency surface is auditable from the anti-hallucination ledger.
Offline, deterministic, async ledger.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from gen.external import (
    IntegrationMode, LicenseClass, LicenseViolation,
    classify_license, external_binding, record_binding,
)
from gen.ledger.store import InMemoryLedgerStore

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("spdx, cls", [
    ("Apache-2.0", LicenseClass.PERMISSIVE),
    ("MIT", LicenseClass.PERMISSIVE),
    ("BSD-3-Clause", LicenseClass.PERMISSIVE),
    ("CC0-1.0", LicenseClass.PERMISSIVE),
    ("CC-BY-4.0", LicenseClass.PERMISSIVE),
    ("GPL-3.0", LicenseClass.COPYLEFT),
    ("AGPL-3.0", LicenseClass.COPYLEFT),
    ("LGPL-3.0", LicenseClass.COPYLEFT),
    ("CC-BY-NC-4.0", LicenseClass.NONCOMMERCIAL),
    ("research-only", LicenseClass.NONCOMMERCIAL),
    ("Weird-Custom-1.0", LicenseClass.UNKNOWN),
])
def test_classify_license_maps_each_class(spdx, cls):
    assert classify_license(spdx) is cls


def test_nc_is_never_mistaken_for_plain_cc_by():
    # the dangerous confusion: CC-BY-NC must NOT classify as the permissive CC-BY
    assert classify_license("CC-BY-NC-4.0") is LicenseClass.NONCOMMERCIAL
    assert classify_license("CC-BY-4.0") is LicenseClass.PERMISSIVE


def test_permissive_library_binding_is_recorded_as_a_verified_claim_with_provenance():
    store = InMemoryLedgerStore()
    b = external_binding("numpy", "2.4.6", "BSD-3-Clause", provenance="pip:numpy==2.4.6")
    assert b.commercial_ok and b.license_class is LicenseClass.PERMISSIVE
    claim = run(record_binding(store, b, run_id="r1", created_at=_T0))
    assert claim.id == "extbind:numpy:2.4.6"
    assert claim.status.value == "verified"
    assert claim.sources[0].url_or_id == "pip:numpy==2.4.6" and claim.sources[0].retrieved
    # retrievable from the ledger, license recorded in the claim text
    stored = run(store.get_claims("r1"))
    assert stored[0].id == "extbind:numpy:2.4.6"
    assert "BSD-3-Clause" in stored[0].text and "commercial_ok=True" in stored[0].text


def test_noncommercial_in_core_raises():
    # THE acceptance check: an NC license (e.g. an AlphaFold3-style weights term) is forbidden in the core
    with pytest.raises(ValueError):
        external_binding("alphafold3", "1.0", "CC-BY-NC-4.0", provenance="weights")


def test_noncommercial_is_forbidden_even_as_a_separate_process():
    # NC restricts USE, not just linking — a process boundary does not rescue it in a commercial product
    with pytest.raises(LicenseViolation):
        external_binding("nc-tool", "1.0", "CC-BY-NC-4.0",
                         provenance="subprocess", integration_mode=IntegrationMode.PROCESS)


def test_copyleft_in_library_is_forbidden_but_a_process_oracle_is_allowed():
    with pytest.raises(LicenseViolation):
        external_binding("gpl-lib", "1.0", "GPL-3.0", provenance="import gpl_lib")  # linked into core: no
    proc = external_binding("gpl-oracle", "1.0", "GPL-3.0",
                            provenance="subprocess:gpl-oracle", integration_mode=IntegrationMode.PROCESS)
    assert proc.commercial_ok and proc.license_class is LicenseClass.COPYLEFT


def test_unknown_license_is_refused():
    with pytest.raises(LicenseViolation):
        external_binding("mystery", "1.0", "Weird-Custom-1.0", provenance="x")


def test_blank_fields_are_rejected():
    with pytest.raises(ValueError):
        external_binding("", "1.0", "MIT", provenance="x")
    with pytest.raises(ValueError):
        external_binding("name", "1.0", "MIT", provenance="")
