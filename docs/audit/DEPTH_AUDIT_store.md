# DEPTH_AUDIT — `src/gen/ledger/store.py` (`InMemoryLedgerStore`)

**Verdikt: REAL.** Keine Quell-Änderung nötig. Jede dokumentierte Invariante hält
unter dem neuen Charakterisierungstest (`tests/test_store_characterization.py`,
20 Tests, alle grün). Der Store ist kein Fassaden-Stub: jeder Input wird
tatsächlich konsumiert, jede Mutation ist beobachtbar, jeder dokumentierte Guard
feuert laut.

## Was geprüft wurde (geerdet an `store.py`-Docstrings)

| Invariante | Beleg im Test |
|---|---|
| **Insertion-Order / A5-Determinismus** | `get_claims` echot exakt die Add-Reihenfolge (unsortierte ids `c3,c1,c2`); identische Op-Sequenz → identischer Snapshot; **Property-Test** über beliebige unique-id-Listen inkl. leerer Batch. |
| **Mandatory Provenance (Layer 2)** | nachträglich geleerte `sources` (Konstruktor-Layer-1 kann das nicht fangen, da `sources` mutierbar) → `UnsourcedClaimError`. |
| **Batch-Atomarität (kein Teil-Write)** | guter + unsourced Claim → ganze Batch verworfen, Ledger unverändert; frischer + Duplikat-id → frischer Claim NICHT persistiert (Validierung vor jeder Mutation). |
| **Append-only Creation** | doppelte id → `ValueError`. |
| **`update_claim`-Guards** | unbekannte id → `UnknownClaimError` (laut, kein stiller Insert); sourceless-Update → `UnsourcedClaimError`; gültiges Update ersetzt Status/Confidence in place. |
| **Fetch-Idempotenz** | späteres `record_fetch` pro `(run_id,url)` überschreibt; `get_fetch` liefert den `FetchRecord`; unbekannt → `None`; gleicher url unter anderem `run_id` ist eigener Record. |
| **Unabhängigkeitsregel** | Skeptic-Quelle die eine Scholar-Quelle wiederverwendet → genau `[(claim_id,url)]`; unabhängige Skeptic-Quelle → `[]`; keine Verifikation → `[]`. |
| **Snapshot-Deep-Copy** | Snapshot ist gegen spätere Store-Mutation immun; Vandalismus am Snapshot erreicht den Live-Store nicht. |

## 4 Linsen

- **L1 Wahrheits-Linse.** Keine geratenen Defaults: jeder fehlende/ungültige Fall
  wirft (UnsourcedClaim/UnknownClaim/ValueError) statt einen Wert zu erfinden.
  Provenienz ist hart erzwungen — deckungsgleich mit Kernprinzip 1.
- **L2 Drift-Linse.** Docstrings vs. Verhalten geprüft: „validates *before* any
  mutation", „idempotent per (run_id,url)", „insertion order", „deep copy" — alle
  exakt erfüllt; kein Versprechen ohne Code-Deckung gefunden.
- **L3 Vollständigkeits-/Naht-Linse.** Negativpfade (leerer/unbekannter Run,
  fehlender Fetch, keine Verifikation) ebenso getestet wie Happy-Path. Naht zur
  SQL-Schicht (`sql/001_ledger.sql`, Postgres-Adapter) ist als gespiegelte
  Invariante dokumentiert; dieser Test deckt die Referenz-Implementierung.
- **L4 Realisierbarkeits-Linse.** Reiner In-Process-Code, keine Deps über stdlib
  hinaus (+ Hypothesis als Test-Dep, bereits im `dev`-Extra deklariert). Test
  nutzt `asyncio.run` statt eines Plugins → in jedem Worktree lauffähig.

## Offene Punkte / bewusst nicht geändert

- **Within-Batch-Duplikat (zwei gleiche ids in *einer* `add_claims`-Liste):** der
  Validierungs-Loop prüft gegen den bereits persistierten Bestand, nicht gegen die
  Batch selbst. Das ist außerhalb der dokumentierten Invarianten und außerhalb des
  T03-Scopes; „change nothing if correct" → nicht angefasst, hier nur notiert.
- Keine Änderung an `store.py` — der Test bestätigt die bestehende Implementierung.
