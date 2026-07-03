"""gen.external — the interface-first integration layer for outside models, tools, and data.

Every connection to something GENESIS did not build (a foundation model, a simulator, a free data API,
a third-party library) enters through here so that two invariants hold for ALL of them:

  1. LICENSE DISCIPLINE (``registry``): the core links only permissive (Apache/MIT/BSD/CC0/CC-BY) code;
     copyleft (GPL/AGPL) is allowed ONLY as a separate-process oracle; non-commercial is forbidden in the
     commercial core. Every binding is recorded into the ledger as a VERIFIED claim with its provenance.
  2. GATED ORACLES (planned ``oracle``): an external answer is a *claim with provenance and uncertainty*
     gated into the ledger, never raw truth — exactly like an LLM proposal.

Offline-first: the in-house deterministic default is always the test backbone; an external binding is an
opt-in seam, never a hard core dependency.
"""

from .oracle import (
    ExternalOracle,
    OracleClaim,
    oracle_claim_to_ledger,
    record_oracle_claim,
)
from .registry import (
    ExternalBinding,
    IntegrationMode,
    LicenseClass,
    LicenseViolation,
    binding_claim,
    classify_license,
    external_binding,
    record_binding,
)

__all__ = [
    "ExternalBinding",
    "IntegrationMode",
    "LicenseClass",
    "LicenseViolation",
    "binding_claim",
    "classify_license",
    "external_binding",
    "record_binding",
    "ExternalOracle",
    "OracleClaim",
    "oracle_claim_to_ledger",
    "record_oracle_claim",
]
