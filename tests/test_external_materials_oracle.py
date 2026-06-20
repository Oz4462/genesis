"""The materials-energy ExternalOracle (M4): a license-disciplined ORB binding, an offline twin whose answer
enters the ledger ONLY as an UNVERIFIED gated claim (never raw truth), and a real adapter that skips honestly
without the GPU dependency. Deterministic, offline, no GPU.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.state import ClaimStatus  # noqa: E402
from gen.external.materials_oracle import (  # noqa: E402
    ORB_BINDING,
    MaterialsOracleUnavailable,
    OfflineMaterialsTwin,
    RealMaterialsOracle,
    StructureSpec,
)
from gen.external.oracle import oracle_claim_to_ledger  # noqa: E402

_HAS_ORB = importlib.util.find_spec("orb_models") is not None


def test_orb_binding_is_permissive_and_commercial():
    assert ORB_BINDING.license_class.value == "permissive" and ORB_BINDING.commercial_ok


def test_offline_twin_answer_enters_the_ledger_only_as_unverified():
    oc = asyncio.run(OfflineMaterialsTwin().query(StructureSpec("SiO2", 6, mean_displacement=0.1)))
    assert oc.value is not None and "OFFLINE TWIN" in oc.statement      # labelled, never passes as ORB
    claim = oracle_claim_to_ledger(oc)
    assert claim.status == ClaimStatus.UNVERIFIED                       # an oracle never self-certifies
    assert any("orb-models" in s.url_or_id for s in claim.sources)      # license provenance carried
    assert any("offline-twin" in s.url_or_id for s in claim.sources)    # call provenance carried


def test_offline_twin_is_deterministic():
    s = StructureSpec("SiO2", 6, mean_displacement=0.1, stiffness_ev_per_a2=2.0)
    a = asyncio.run(OfflineMaterialsTwin().query(s)).value
    b = asyncio.run(OfflineMaterialsTwin().query(s)).value
    assert a == b == pytest.approx(0.5 * 2.0 * 0.1 ** 2 * 6)


@pytest.mark.skipif(_HAS_ORB, reason="orb-models installed; the unavailable-path test only applies offline")
def test_real_oracle_skips_honestly_without_the_gpu_dep():
    with pytest.raises(MaterialsOracleUnavailable):
        asyncio.run(RealMaterialsOracle().query(StructureSpec("SiO2", 6)))
