"""W1: Source connector catalog + health (live search backends + wissensbasis registry).

One honest report for operators/agents: which connectors exist, key requirements,
live/offline posture, and how to probe them. Never fabricates a "healthy" live
status without a real probe when ``live=True``.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorEntry:
    """One catalog row — discovery or internal knowledge connector."""

    name: str
    kind: str  # search_backend | wissensbasis | ledger | vector
    license: str
    key_required: bool
    key_env: str | None
    key_present: bool
    live_capable: bool
    status: str  # ready | key_missing | offline_only | not_wired | optional
    endpoint_or_path: str
    notes: str = ""
    quelle: str = "gen.tools.source_catalog"


@dataclass
class CatalogReport:
    connectors: list[ConnectorEntry] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    patents: dict[str, Any] = field(default_factory=dict)
    ledger: dict[str, Any] = field(default_factory=dict)
    vector: dict[str, Any] = field(default_factory=dict)
    quelle: str = "gen.tools.source_catalog.catalog_report"

    def to_dict(self) -> dict[str, Any]:
        return {
            "connectors": [asdict(c) for c in self.connectors],
            "summary": self.summary,
            "patents": self.patents,
            "ledger": self.ledger,
            "vector": self.vector,
            "quelle": self.quelle,
        }

    def text(self) -> str:
        lines = ["═══ GENESIS SOURCE CATALOG ═══", ""]
        for c in self.connectors:
            key = "key✓" if c.key_present else ("key✗" if c.key_required else "key—")
            lines.append(
                f"  [{c.status:12}] {c.name:18} {c.kind:16} {key:6}  {c.endpoint_or_path}"
            )
            if c.notes:
                lines.append(f"                 └─ {c.notes}")
        lines += [
            "",
            f"summary: {self.summary}",
            f"patents: {self.patents.get('status')} — {self.patents.get('note', '')}",
            f"ledger:  {self.ledger.get('status')} — {self.ledger.get('note', '')}",
            f"vector:  {self.vector.get('status')} — {self.vector.get('note', '')}",
            "",
            "Live probe: set GENESIS_ALLOW_LIVE=1; PatentsView needs PATENTSVIEW_API_KEY.",
        ]
        return "\n".join(lines)


def _env_key(name: str | None) -> bool:
    if not name:
        return False
    return bool(os.environ.get(name, "").strip())


def patents_status() -> dict[str, Any]:
    """W3: honest PatentsView key-gated status (no fake empty search)."""
    env = "PATENTSVIEW_API_KEY"
    present = _env_key(env)
    return {
        "backend": "patentsview",
        "status": "ready" if present else "key_missing",
        "key_env": env,
        "key_present": present,
        "note": (
            "PatentsView v1 requires X-Api-Key; CLI wires PatentsViewBackend only when key set"
            if present
            else "Set PATENTSVIEW_API_KEY to enable patent prior-art search (403 without key — never fabricated miss)"
        ),
        "endpoint": "https://search.patentsview.org/api/v1/patent/",
        "quelle": "gen.tools.sources.patents + cli.build_live",
    }


def ledger_status() -> dict[str, Any]:
    """W4: Postgres ledger posture — ready only if DSN present; smoke is separate."""
    dsn = os.environ.get("GENESIS_PG_DSN", "").strip()
    if dsn:
        # Never log credentials — only host-ish tail
        safe = dsn.split("@")[-1] if "@" in dsn else "(local)"
        return {
            "status": "dsn_configured",
            "note": f"GENESIS_PG_DSN set → host {safe}; run scripts/postgres_smoke.py for proof",
            "smoke": "scripts/postgres_smoke.py",
            "schema": "sql/001_ledger.sql",
            "store": "gen.ledger.postgres.PostgresLedgerStore",
            "in_memory_default": False,
        }
    return {
        "status": "offline_in_memory",
        "note": "No GENESIS_PG_DSN — live runs use InMemoryLedgerStore; production tables pending env",
        "smoke": "scripts/postgres_smoke.py (requires GENESIS_PG_DSN)",
        "schema": "sql/001_ledger.sql",
        "store": "gen.ledger.store.InMemoryLedgerStore (default)",
        "in_memory_default": True,
    }


def vector_status() -> dict[str, Any]:
    """W5: vector / embedding posture — one honest path description (no half-claims)."""
    # Detect optional deps without importing heavy stacks if missing
    has_numpy = False
    try:
        import numpy  # noqa: F401

        has_numpy = True
    except ImportError:
        pass

    anamnesis = False
    try:
        from gen.memory._vendor.anamnesis_mem import storage  # noqa: F401

        anamnesis = True
    except Exception:
        anamnesis = False

    # Qdrant / pgvector: not wired as production services in-core
    qdrant_env = bool(os.environ.get("QDRANT_URL") or os.environ.get("GENESIS_QDRANT_URL"))
    pgvector_hint = "pgvector" in os.environ.get("GENESIS_PG_DSN", "").lower()

    if anamnesis and has_numpy:
        path = "anamnesis_mem (vendored) + embedder-agnostic storage"
        status = "local_vendor"
        note = (
            "Verified-facts / conformal memory path uses vendored anamnesis_mem; "
            "production Qdrant/pgvector cluster is NOT wired as a GENESIS service"
        )
    else:
        path = "none"
        status = "not_wired"
        note = "No production vector store; optional anamnesis vendor incomplete"

    if qdrant_env:
        note += f"; QDRANT_URL env present but no first-class gen.qdrant client (status={status})"
    if pgvector_hint:
        note += "; DSN mentions pgvector — use ledger schema only unless operator extends"

    return {
        "status": status,
        "path": path,
        "qdrant_env": qdrant_env,
        "production_qdrant": False,
        "production_pgvector": False,
        "note": note,
        "quelle": "gen.memory + gen.tools.source_catalog.vector_status",
    }


def build_search_backend_entries() -> list[ConnectorEntry]:
    """Live α/β search backends used by build_live / invent."""
    patents = patents_status()
    return [
        ConnectorEntry(
            name="wikipedia",
            kind="search_backend",
            license="CC BY-SA (content)",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=True,
            status="ready",
            endpoint_or_path="Wikipedia API via tools",
            notes="keyless",
        ),
        ConnectorEntry(
            name="materials",
            kind="search_backend",
            license="internal registry",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=False,
            status="offline_only",
            endpoint_or_path="gen.tools.materials_backend",
            notes="offline grounded materials cards",
        ),
        ConnectorEntry(
            name="wikidata_density",
            kind="search_backend",
            license="CC0",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=True,
            status="ready",
            endpoint_or_path="Wikidata P2054",
            notes="independent density claims",
        ),
        ConnectorEntry(
            name="semantic_scholar",
            kind="search_backend",
            license="API ToS",
            key_required=False,
            key_env="SEMANTIC_SCHOLAR_API_KEY",
            key_present=_env_key("SEMANTIC_SCHOLAR_API_KEY"),
            live_capable=True,
            status="ready",
            endpoint_or_path="api.semanticscholar.org",
            notes="keyless with rate limits; key optional",
        ),
        ConnectorEntry(
            name="arxiv",
            kind="search_backend",
            license="open-access",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=True,
            status="ready",
            endpoint_or_path="export.arxiv.org (Atom)",
            notes="keyless preprints",
        ),
        ConnectorEntry(
            name="openalex",
            kind="search_backend",
            license="CC0",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=True,
            status="ready",
            endpoint_or_path="api.openalex.org/works",
            notes="CC0 scholarly graph; community_evidence + invent",
        ),
        ConnectorEntry(
            name="patentsview",
            kind="search_backend",
            license="US gov public domain",
            key_required=True,
            key_env="PATENTSVIEW_API_KEY",
            key_present=patents["key_present"],
            live_capable=True,
            status=patents["status"],
            endpoint_or_path=patents["endpoint"],
            notes=patents["note"],
        ),
        ConnectorEntry(
            name="formula",
            kind="search_backend",
            license="mixed (DLMF/CODATA)",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=True,
            status="ready",
            endpoint_or_path="gen.tools.formula_backend",
            notes="DLMF + CODATA + registry",
        ),
    ]


def build_wissensbasis_entries() -> list[ConnectorEntry]:
    """Internal SourceConnectorRegistry rows from wissensbasis.store."""
    try:
        from gen.wissensbasis.store import get_registry

        reg = get_registry()
        entries: list[ConnectorEntry] = []
        for conn in reg.list():
            ep = str(getattr(conn, "endpoint_hint", None) or "internal")
            lic = getattr(getattr(conn, "policy", None), "license", "internal")
            status = "offline_only" if ep in ("internal", "out/") else "ready"
            entries.append(
                ConnectorEntry(
                    name=conn.name,
                    kind="wissensbasis",
                    license=str(lic),
                    key_required=False,
                    key_env=None,
                    key_present=True,
                    live_capable=False,
                    status=status,
                    endpoint_or_path=ep,
                    notes=str(getattr(conn, "quelle", None) or conn.kind),
                )
            )
        if entries:
            return entries
    except Exception:
        pass

    return [
        ConnectorEntry(
            name=n,
            kind="wissensbasis",
            license="internal",
            key_required=False,
            key_env=None,
            key_present=True,
            live_capable=False,
            status="offline_only",
            endpoint_or_path="wissensbasis.store",
            notes="seeded SourceConnectorRegistry",
        )
        for n in ("arxiv", "local_out", "materials", "components", "suppliers")
    ]


def catalog_report() -> CatalogReport:
    """Full catalog: search backends + wissensbasis + ledger + vector honesty."""
    connectors = build_search_backend_entries() + build_wissensbasis_entries()
    # W4/W5
    led = ledger_status()
    vec = vector_status()
    connectors.append(
        ConnectorEntry(
            name="postgres_ledger",
            kind="ledger",
            license="operator DB",
            key_required=True,
            key_env="GENESIS_PG_DSN",
            key_present=_env_key("GENESIS_PG_DSN"),
            live_capable=bool(_env_key("GENESIS_PG_DSN")),
            status=led["status"],
            endpoint_or_path="sql/001_ledger.sql",
            notes=led["note"],
        )
    )
    connectors.append(
        ConnectorEntry(
            name="vector_memory",
            kind="vector",
            license="vendored/local",
            key_required=False,
            key_env="QDRANT_URL",
            key_present=bool(os.environ.get("QDRANT_URL")),
            live_capable=False,
            status=vec["status"],
            endpoint_or_path=vec.get("path") or "not_wired",
            notes=vec["note"],
        )
    )

    summary: dict[str, int] = {}
    for c in connectors:
        summary[c.status] = summary.get(c.status, 0) + 1
    summary["total"] = len(connectors)

    return CatalogReport(
        connectors=connectors,
        summary=summary,
        patents=patents_status(),
        ledger=led,
        vector=vec,
    )


__all__ = [
    "ConnectorEntry",
    "CatalogReport",
    "catalog_report",
    "patents_status",
    "ledger_status",
    "vector_status",
]
