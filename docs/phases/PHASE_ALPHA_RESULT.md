# PHASE α — RESULT (ehrlich)

> Was erfüllt ist, was nicht, und wo die Grenze der Sandbox liegt. Keine
> Schönfärberei (CLAUDE_CODE_AUFTRAG_001 §2, CONTRIBUTING „Ehrlichkeit").

## Zusammenfassung
Das Anti-Halluzinations-Fundament steht und ist **als Code beweisbar korrekt**:
**102/102 Tests grün, ohne einen einzigen LLM-Token und ohne Netzwerk.** Die
komplette Pipeline (Ledger → Tools → Agenten → Gate → Runner/CLI) ist verdrahtet
und läuft offline deterministisch end-to-end.

```
pytest -q  ->  102 passed
```

## Akzeptanzkriterien (PHASE_ALPHA §5)

| # | Kriterium | Status | Beleg |
|---|---|---|---|
| A1 | Null unbelegte Fakten im Bericht | **ERFÜLLT** | `gate_alpha` + `test_phase_alpha_acceptance` (jeder behauptete Satz → Ledger-Claim mit Quelle); Quellenzwang dreischichtig |
| A2 | Erfundene Quellen = 0 | **ERFÜLLT** | `test_A2_no_fabricated_sources…`; `WebFetchTool` ok-Flag real gegen Netz geprüft; DEAD_CITATION im Gate |
| A3 | Bekannte Falschaussage wird abgefangen | **ERFÜLLT** | Klasse B (`trap_caught`): falsche Prämisse nie behauptet, als Lücke ausgewiesen |
| A4 | Abstention funktioniert | **ERFÜLLT** | Klasse C (`abstain`): nichts behauptet, „No claim could be independently verified", als Lücke ausgewiesen |
| A5 | Reproduzierbarkeit | **ERFÜLLT** | `test_A5_reproducibility…`: gleicher run_id+Config → identischer Bericht; `config_hash`, deterministische Claim-IDs |
| A6 | Cross-Model aktiv | **ERFÜLLT (strukturell)** | `test_A6…`: Verifier-Familie ≠ Generator-Familie hart erzwungen (`ModelConflictError`); im Runner-Log auditierbar |

**A3 und A4 — die wichtigsten — bestehen.**

## Ergebnis je Frageklasse (PHASE_ALPHA §6)

| Klasse | Frage (Beispiel) | Verhalten | Erwartet | OK |
|---|---|---|---|---|
| A belegbar | „Welcher CAD-Kernel liegt build123d/CadQuery zugrunde?" | VERIFIED behauptet | verified | ✅ |
| B Falle | „Warum ist OCCT der *einzige* Python-CAD-Kernel?" | nicht behauptet, REFUTED→Lücke | trap_caught | ✅ |
| C unbelegbar | „Welcher Kernel dominiert 2100?" | nichts behauptet, Abstention | abstain | ✅ |
| D strittig | „Ist FreeCAD zuverlässiger als Fusion 360?" | nicht einseitig behauptet, →Lücke | dissent | ✅ |

## Methodik — und ihre ehrliche Grenze
Die Akzeptanzläufe nutzen pro Klasse eine **deterministische „scripted world"**
(gescriptete Modelle + konservierte Quellen), die die jeweilige Klasse modelliert.
Das ist **bewusst** so: Die Akzeptanzkriterien prüfen die **Garantien des Systems**
(kein unbelegter Fakt, Falle, Abstention, Reproduzierbarkeit, Cross-Model) — und
die sind Eigenschaften der Architektur, beweisbar ohne Modell. Das ist exakt die
Gate-first-Philosophie des Projekts: „Die Garantie ist bewiesen, bevor irgendein
Modell angebunden wird."

**Was damit NICHT bewiesen ist (offen, nicht blockierend für α, §9):**
- Die reale Retrieval-/Urteilsqualität echter LLMs an echten Quellen. Dafür fehlt
  in dieser Umgebung ein realer LLM-Adapter (kein Key/SDK). Das ist eine dünne
  Adapter-Schicht hinter `Dependencies` — Modellwahl ist laut §9 ausdrücklich
  offen und hinter Adaptern austauschbar.
- `PostgresLedgerStore` ist nicht gegen eine laufende Postgres-Instanz ausgeführt
  (keine DB in der Sandbox); Korrektheit ruht auf exakter Schema-Übereinstimmung
  mit `sql/001_ledger.sql` + InMemory als Verhaltensreferenz.

**Nächster ehrlicher Schritt zu „echtem" Betrieb:** reale `LLMClient`-Adapter
(Generator-Familie ≠ Verifier-Familie) + Live-Backends anbinden, dann dieselbe
Suite gegen Live-Daten fahren, um Modellqualität zu *messen* (nicht die
Architektur). Das Gerüst dafür steht vollständig.

## Phase α: Fazit
Das „Unmögliche" zuerst — Halluzination strukturell verhindern — ist als Code
erbracht und getestet. Phase α ist **abgeschlossen**. Bereit für GitHub (privat),
und nach Anbindung realer Modelle für den ersten Live-Beweis.


## Unabhängiges Audit (adversarial) + Härtung
Ein unabhängiger Verifikations-Subagent hat versucht, die vier Garantien zu
brechen. Ergebnis: alle halten im ausgelieferten Pfad, **kein Live-Exploit**.
Zwei Single-Layer-Schwachstellen wurden gefunden und behoben:
1. `gate_alpha` ist jetzt ein **unabhängiger Backstop** (prüft selbst: behaupteter
   Claim hat ≥1 Quelle; Satz == Claim-Text) — Codes `UNSOURCED_CLAIM`,
   `SENTENCE_CLAIM_MISMATCH`.
2. Der **Zweitgutachter** des `skeptic` ruft jetzt wirklich ein zweites Modell auf
   (vorher Relabel derselben Urteile) — Disagreement erzwingt UNSUPPORTED.
Beide Fixes wurden von einem zweiten, frischen Auditor bestätigt; Tests
nicht-vakuös. Endstand: **102 passed**.
