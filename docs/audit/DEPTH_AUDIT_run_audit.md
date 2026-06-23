# Depth-Audit: `src/gen/audit/run_audit.py`

**Verdikt: REAL.** Kein Quell-Edit nötig — alle dokumentierten Garantien (Determinismus,
Tamper-Evidenz, die drei dokumentierten Ausnahmen) halten in der Charakterisierung stand.

Modul: tamper-evidenter, unabhängig verifizierbarer Run-Audit (Phase 4 / Governance).
Signiert eine Ledger-Zusammenfassung mit trust-core Ed25519 (DSSE-PAE-Umschlag).
Neuer Test: `tests/test_run_audit_characterization.py`. Die Krypto-Tests tragen einen
`skipif`-Mark auf den optionalen `verify`-Extra (trust-core); ein modulweiter
`importorskip` wäre falsch, weil er NULL Tests sammelt → pytest-Exit 5 ("no tests
collected"). Der immer laufende `test_import_contract` pinnt das dokumentierte
Lade-Verhalten in BEIDEN Umgebungen (saubere `ImportError` ohne Extra, echter Import mit),
sodass die Datei stets ≥1 bestandenen Test sammelt und das Gate grün bleibt — mit oder ohne Extra.

## Belegte Garantien (Facade-Killer)

| Behauptung | Wie der Test sie zwingt | Ergebnis |
|---|---|---|
| `digest_claims` deterministisch | zweimaliger Aufruf gleich; 64-Hex-SHA-256 (kein leerer/kanned Wert) | hält |
| quellen-reihenfolge-unabhängig | Quellen vorwärts vs. rückwärts → gleicher Digest; **Property-Test** (Hypothesis) über beliebige Quell-Permutationen | hält (Quellen werden sortiert) |
| inhalts-sensitiv | Ändern von `id` / `status` / `text` / Claim-Reihenfolge ändert je den Digest | hält (jedes Feld speist den Hash) |
| `audit_from_claims` zählt echt | exakte Status-Counts + `n_claims`; Summe der Counts == `n_claims`; Felder spiegeln Inputs | hält |
| `ledger_digest == digest_claims(claims)` | direkter Vergleich | hält (Input wird konsumiert, kein kanned Record) |
| `sign → verify` Round-Trip | Rückgabe `== rec`, ist `RunAuditRecord` | hält |
| Tamper → `BadSignatureError` | Payload dekodiert, **Status-Count (`n_verified`) verfälscht**, neu kodiert → verify wirft; zusätzlich Signatur-Byte-Flip → wirft | hält (Negativtest) |
| anderer Schlüssel → `BadSignatureError` | zweiter Key im selben Keystore, `key_id` umgebogen → bekannter Key, falsche verify-Key | hält (Negativtest) |
| unbekannte `key_id` → `KeyError` | Verify gegen leeren Keystore | hält (Negativtest) |
| falscher `payload_type` → `ValueError` | `payload_type="application/json"` | hält (Negativtest) |

## 4 Linsen

- **L1 Wahrheit:** Der Digest ist eine echte SHA-256-Funktion über `(id|status|text|sorted(sources))`;
  keine faktische Behauptung ohne Quelle — `Claim.__post_init__` erzwingt ≥1 `SourceRef`. Die
  Signatur bindet exakt diese kanonischen Bytes via DSSE-PAE; jede Verfälschung scheitert laut.
- **L2 Drift:** Die drei dokumentierten Ausnahmen (`ValueError`/`BadSignatureError`/`KeyError`)
  entsprechen exakt dem Docstring von `verify_audit`; kein stiller Default — falscher Payload-Typ,
  Tamper, falscher/unbekannter Key werfen je den richtigen Typ. Kein Self-Check: signiert wird
  über eine externe Krypto-Primitive (trust-core), verifiziert wird unabhängig.
- **L3 Vollständigkeit/Naht:** Counts decken *alle* vier `ClaimStatus`-Werte ab (Summe == `n_claims`);
  `ledger_digest` ist mit `digest_claims` verdrahtet (eine Quelle der Wahrheit). Naht zum Ledger:
  Claim-Reihenfolge ist Teil der Kanonik (A5, Insertion-Order deterministisch).
- **L4 Realisierbarkeit:** Reines lokales Bibliotheks-Verhalten, kein Netz/Subprozess. Der optionale
  `verify`-Extra (trust-core) ist via `skipif`-Mark + immer-laufendem Import-Contract-Test sauber
  gegated (kein modulweiter `importorskip` → kein Exit-5-„0 Tests gesammelt"); das volle pytest-Gate
  bleibt mit UND ohne den Extra grün (lokal verifiziert: 1 passed, 15 skipped, exit 0, sowohl mit
  als auch ohne `gen` auf dem Pfad). Property-Test (Hypothesis) deckt den Permutations-Invarianten-
  Raum ab, nicht nur Einzelbeispiele.

## Abgleich GENESIS_PLATFORM_PLAN

Governance/Tamper-Evidenz-Baustein (Phase 4): erfüllt die „signierter, reproduzierbarer Run-Audit"-
Anforderung. VERIDEX' Annex-IV/Article-12-Webservice bleibt bewusst außerhalb (Deployment-Fläche);
GENESIS bleibt lokale Bibliothek — kein Facade, da der Kern (sign→verify→tamper→wrong-key) hier real
und gegen eine echte Krypto-Primitive bewiesen ist.
