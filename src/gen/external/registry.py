"""registry — the license-disciplined gateway for every external binding (INVENTOR §10¾ C, Katalog Teil D).

The hard rule (CLAUDE.md §1 license discipline): the GENESIS core links only PERMISSIVE licenses
(Apache/MIT/BSD/CC0/CC-BY/ISC/MPL); COPYLEFT (GPL/AGPL/LGPL) is allowed ONLY as a separate-process oracle
(a license firewall — never statically linked into the core process); NON-COMMERCIAL (CC-BY-NC, research-
only) is forbidden in the commercial core entirely; an UNKNOWN license is refused rather than silently
trusted (CLAUDE.md "keine stillen Defaults bei faktischen Dingen"). Google-NC foundation models are
replaced by open commercial alternatives in the catalog, not bound here.

The enforcement is a CONSTRUCTOR invariant: an offending ``ExternalBinding`` cannot be built (``__post_init__``
raises ``LicenseViolation``), mirroring how the ledger refuses a sourceless ``Claim``. A valid binding is then
recorded into the ledger as a VERIFIED ``Claim`` carrying its provenance — so the project's dependency surface
is auditable from the same anti-hallucination ledger as every other fact. Deterministic, offline, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ..core.state import Claim, ClaimStatus, SourceRef, SourceSupport, now_utc


class LicenseClass(Enum):
    """How a license may be used relative to the commercial GENESIS core."""

    PERMISSIVE = "permissive"        # linkable into the core process
    COPYLEFT = "copyleft"            # GPL/AGPL/LGPL — separate-process oracle ONLY
    NONCOMMERCIAL = "noncommercial"  # CC-BY-NC / research-only — forbidden in a commercial product
    UNKNOWN = "unknown"              # unclassifiable — refused, never silently trusted


class IntegrationMode(Enum):
    """How the dependency is wired in — this is what makes copyleft safe or not."""

    LIBRARY = "library"   # imported into the GENESIS process (static/dynamic link)
    PROCESS = "process"   # invoked as a separate subprocess — a license firewall
    DATA = "data"         # a dataset, not executable code


class LicenseViolation(ValueError):
    """A binding whose license/integration combination breaks the core license discipline. A ValueError
    subclass so callers can catch it as either."""


# Canonical SPDX-ish identifiers per class. Lowercased keys; ``classify_license`` also applies prefix
# fallbacks but NEVER falls through to a permissive default — an unrecognized id is UNKNOWN (refused).
_PERMISSIVE = {
    "apache-2.0", "apache2", "mit", "bsd", "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0",
    "cc0-1.0", "cc0", "cc-by-4.0", "cc-by-3.0", "cc-by", "unlicense", "psf-2.0", "python-2.0", "zlib",
}
_COPYLEFT = {
    "gpl-2.0", "gpl-3.0", "gpl", "gplv2", "gplv3", "agpl-3.0", "agpl", "lgpl-2.1", "lgpl-3.0", "lgpl",
}
_NONCOMMERCIAL = {
    "cc-by-nc-4.0", "cc-by-nc", "cc-by-nc-sa-4.0", "cc-by-nc-sa", "cc-by-nc-nd", "cc-by-nc-nd-4.0",
    "research-only", "non-commercial", "noncommercial", "proprietary-research", "cc-by-nc-3.0",
}


def classify_license(spdx: str) -> LicenseClass:
    """Map a license id to its usage class. Non-commercial is checked FIRST (an ``nc`` variant must never be
    mistaken for plain CC-BY). Recognized prefixes (gpl/agpl/lgpl, apache/bsd/mit) resolve their class; an
    unrecognized id returns ``UNKNOWN`` — the caller then refuses it rather than guessing."""
    key = spdx.strip().lower().replace(" ", "")
    if key in _NONCOMMERCIAL:
        return LicenseClass.NONCOMMERCIAL
    if "nc" in key.split("-") or "-nc-" in key or key.endswith("-nc"):
        return LicenseClass.NONCOMMERCIAL
    if key in _PERMISSIVE:
        return LicenseClass.PERMISSIVE
    if key in _COPYLEFT:
        return LicenseClass.COPYLEFT
    if key.startswith(("agpl", "lgpl", "gpl")):
        return LicenseClass.COPYLEFT
    if key.startswith(("apache", "bsd", "mit", "isc", "mpl", "cc0", "unlicense")):
        return LicenseClass.PERMISSIVE
    return LicenseClass.UNKNOWN


def _validate(license_class: LicenseClass, mode: IntegrationMode) -> None:
    """The license gate. Raises ``LicenseViolation`` on any forbidden combination."""
    if license_class is LicenseClass.UNKNOWN:
        raise LicenseViolation(
            "unknown license: refusing to bind a dependency whose license cannot be classified "
            "(declare the SPDX id; no silent default to permissive)")
    if license_class is LicenseClass.NONCOMMERCIAL:
        raise LicenseViolation(
            "non-commercial license forbidden in the GENESIS core: a non-commercial term restricts USE, not "
            "just linking, so even a separate process is disallowed in a commercial product — pick the open "
            "alternative from the catalog (Boltz-2/Aurora/ORB/OpenEvolve/Goedel)")
    if license_class is LicenseClass.COPYLEFT and mode is IntegrationMode.LIBRARY:
        raise LicenseViolation(
            "copyleft (GPL/AGPL/LGPL) may NOT be linked into the core: bind it as a separate-process oracle "
            "(IntegrationMode.PROCESS) so the copyleft boundary is a process boundary")


@dataclass(frozen=True)
class ExternalBinding:
    """One audited connection to an outside model/tool/dataset. The license discipline is enforced at
    CONSTRUCTION — an offending binding raises ``LicenseViolation`` in ``__post_init__`` and never exists.

    ``license_class`` and ``commercial_ok`` are derived (use the :func:`external_binding` factory); they are
    fields so the recorded ledger claim is self-describing. ``provenance`` is how/where it is invoked (a URL,
    a pip name+version, a call signature) — it becomes the claim's source."""

    name: str
    version: str
    license: str
    integration_mode: IntegrationMode
    provenance: str
    license_class: LicenseClass
    commercial_ok: bool

    def __post_init__(self) -> None:
        if not (self.name and self.version and self.provenance):
            raise ValueError("external binding needs a non-empty name, version, and provenance")
        _validate(self.license_class, self.integration_mode)


def external_binding(
    name: str,
    version: str,
    license: str,
    *,
    provenance: str,
    integration_mode: IntegrationMode = IntegrationMode.LIBRARY,
) -> ExternalBinding:
    """Classify ``license``, derive ``commercial_ok``, and build a validated :class:`ExternalBinding`.

    ``commercial_ok`` is True for permissive code, and for copyleft ONLY when bound as a separate process
    (the firewall preserved). A non-commercial / unknown license, or copyleft linked into the core, raises
    ``LicenseViolation`` here — the binding cannot be constructed."""
    lc = classify_license(license)
    commercial_ok = lc is LicenseClass.PERMISSIVE or (
        lc is LicenseClass.COPYLEFT and integration_mode is IntegrationMode.PROCESS)
    return ExternalBinding(
        name=name, version=version, license=license, integration_mode=integration_mode,
        provenance=provenance, license_class=lc, commercial_ok=commercial_ok)


def binding_claim(binding: ExternalBinding, *, created_at: Optional[datetime] = None) -> Claim:
    """Build the VERIFIED ledger ``Claim`` for a validated binding (its provenance becomes the source). Pure;
    no I/O — :func:`record_binding` is the async path that persists it. ``created_at`` defaults to now (UTC)."""
    src = SourceRef(url_or_id=binding.provenance, retrieved=True, support=SourceSupport.SUPPORTS)
    text = (f"External binding: {binding.name} v{binding.version} — license {binding.license} "
            f"({binding.license_class.value}), integration {binding.integration_mode.value}, "
            f"commercial_ok={binding.commercial_ok}")
    return Claim(
        id=f"extbind:{binding.name}:{binding.version}",
        text=text,
        sources=[src],
        quote=None,
        status=ClaimStatus.VERIFIED,
        confidence=1.0,
        verification=[],
        produced_by="external.registry",
        model="external-registry",
        created_at=created_at or now_utc(),
    )


async def record_binding(
    store,
    binding: ExternalBinding,
    *,
    run_id: str,
    created_at: Optional[datetime] = None,
) -> Claim:
    """Record a validated binding into the (async) ledger as a VERIFIED ``Claim`` carrying its provenance, so
    the project's external-dependency surface is auditable from the anti-hallucination ledger. Returns the
    claim. The license fact is VERIFIED — a checkable property of the named artifact (retrieved=True against
    the provenance). ``created_at`` is accepted for deterministic tests; it defaults to now (UTC)."""
    claim = binding_claim(binding, created_at=created_at)
    await store.add_claims(run_id, [claim])
    return claim
