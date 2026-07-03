# Phase 4 — Governance / Run-Audit (abgeschlossen 2026-06-13)

> Gerechtfertigt durch PoV-4 (PASS): sign→verify ok, tamper erkannt, fremder Key
> abgelehnt, CCDD-Drift feuert bei Shift / schweigt bei No-Shift.

## Was integriert wurde

- **`src/gen/audit/run_audit.py`** (net-new, geführter Import über `verify`-Extra):
  - `audit_from_claims(...)` → `RunAuditRecord` (Status-Counts + reproduzierbarer
    `digest_claims` SHA-256 über id|status|text|sorted-sources).
  - `sign_audit` / `verify_audit` — DSSE-PAE-Envelope, signiert mit trust-core
    `KeyStore` (generischer Ed25519-Signer + Key-Rotation/Revocation). Verify schlägt
    bei Tampering loud fehl; unbekannter Key → `KeyError`.
- **Drift-Hälfte** der Governance liefert bereits `gen.verification.drift_monitor`
  (Phase 1, CCDD) — Modell-Output-Drift-Monitoring.

## Native statt VERIDEX-Import (bewusst)

VERIDEX' Audit-Schicht (Annex-IV-Generator, Article-12-Logging) ist eine
**Deployment-Fläche** (FastAPI + k8s/Helm + Multi-Tenant-Backend), keine schlanke
Library. Genesis bleibt lokale Library → ich baue nativ auf dem **gemeinsamen
trust-core-Primitiv** (Ed25519-`KeyStore`, das VERIDEX selbst nutzt), statt VERIDEX zu
importieren. Gleiche Krypto-Wurzel, kein Web/k8s-Ballast. Der volle Annex-IV/Art-12-
Report wäre ein späterer, separater Service-Adapter (owner-gated Deployment).

## Verifikation (Zahlen)

- `tests/test_run_audit.py` 4/4: Counts + deterministischer Digest; sign→verify-Roundtrip;
  **Tamper erkannt** (`BadSignatureError`); unbekannter Key abgelehnt.
- **Volle Suite: 856 passed, 19 skipped, 0 Fehler.** ruff: All checks passed.

## Nicht erledigt / deferred

- Verdrahtung an `runner`/`telemetry`: nach jedem Lauf automatisch ein signiertes
  Audit-Bündel + Persistenz (owner-gated Pipeline-Integration).
- Voller VERIDEX-Annex-IV/Art-12-Report als separater Service-Adapter (Deployment).
- DriftMonitor in die Phasen-Gates verdrahten (braucht Output-Embeddings in RunState).
