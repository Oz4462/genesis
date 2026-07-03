# PHASE β — RESULT (ehrlich)

> Was erfüllt ist, was nicht, und wo die Grenze der Sandbox liegt. Keine
> Schönfärberei (CLAUDE_CODE_AUFTRAG_001 §2, CONTRIBUTING „Ehrlichkeit"). Format
> wie `PHASE_ALPHA_RESULT.md`.

## Zusammenfassung
Phase β (Lösungsraum) steht und ist **als Code beweisbar korrekt**: Die komplette
β-Pipeline (α-Recherche → `synthesizer` → `SolutionReport` → GATE β) ist verdrahtet
und läuft offline deterministisch end-to-end. Die α-Garantien bleiben **unverändert**.

```
pytest -q  ->  129 passed
```
(102 α + 1 α-Backstop-Test + 26 β: 14 GATE-β, 7 synthesizer, 5 Akzeptanz — die
α-Tests bleiben im Normalverhalten unverändert.)

Zentrale β-Invariante, gespiegelt zu α: **ein `Approach` kann nicht ohne Verankerung
in einem VERIFIED-Claim existieren.** Ein erfundener Ansatz ist das β-Äquivalent
eines halluzinierten Fakts — strukturell verhindert (Konstruktor-Guard im `Approach`,
Drop im `synthesizer`, Backstop in GATE β: dreischichtig wie der α-Quellenzwang).

## Akzeptanzkriterien (PHASE_BETA.md §5)

| # | Kriterium | Status | Beleg |
|---|---|---|---|
| B1 | Kein erfundener Ansatz | **ERFÜLLT** | jeder behauptete Ansatz ↔ ≥1 VERIFIED-Claim; `gate_beta` (`GROUNDING_NOT_VERIFIED`/`UNGROUNDED_APPROACH`) + `synthesizer` droppt unverankerte; `test_class_A`, `test_gate_beta` |
| B2 | Echte Alternativen gefunden | **ERFÜLLT** | Klasse A & D liefern je 2 verankerte Ansätze (`test_class_A_multiple_grounded_approaches`, `test_class_D…`) |
| B3 | Trade-offs belegt | **ERFÜLLT** | Trade-offs sind VERIFIED-Ledger-Claims; `gate_beta` (`TRADEOFF_UNKNOWN_CLAIM`/`UNSUPPORTED_…`); Token-Bucket trägt einen verifizierten Trade-off in `test_class_A` |
| B4 | Falsche Alleinstellung wird abgefangen | **ERFÜLLT** | Klasse B: Uniqueness-Claim REFUTED, nie als Ansatz verankert, Alternativen ausgewiesen (`test_class_B_false_uniqueness_trap_caught`) |
| B5 | Abstention | **ERFÜLLT** | Klasse C: kein verankerbarer Ansatz → null Ansätze + ehrliche Lücke (`test_class_C_abstention`) |
| B6 | α-Garantien erhalten | **ERFÜLLT** | jeder referenzierte Claim erfüllt weiterhin GATE α (geteilter `claim_soundness_failures`); 102 α-Tests grün nach dem Refactor |

**B2 und B4 — die wichtigsten — bestehen.**

## Ergebnis je Problemklasse (PHASE_BETA.md §6)

| Klasse | Problem (Beispiel) | Verhalten | Erwartet | OK |
|---|---|---|---|---|
| A gelöst | „Wie setzen Produktionssysteme API-Rate-Limiting um?" | 2 verankerte Ansätze (Token/Leaky Bucket), Trade-off belegt | multi_approach | ✅ |
| B Falle | „Warum ist Token Bucket der *einzige* Weg?" | Uniqueness REFUTED → Lücke; Alternativen verankert | trap_caught | ✅ |
| C unbelegbar | „Optimaler Ansatz für Überlicht-Kommunikation?" | nichts behauptet, Abstention | abstain | ✅ |
| D strittig | „Microservices oder Monolith — besser?" | beide Ansätze, kein erfundener „Sieger" | dissent | ✅ |

## Methodik — und ihre ehrliche Grenze
Die Akzeptanzläufe nutzen pro Klasse eine **deterministische „scripted world"**
(gescriptete Modelle + konservierte Quellen), die die jeweilige Klasse modelliert —
exakt die Gate-first-Methodik aus α. Geprüft werden die **System-Garantien**
(kein erfundener Ansatz, Alternativen, Falle, Abstention, α erhalten), nicht die
reale LLM-Qualität.

**Was damit NICHT bewiesen ist (offen, nicht blockierend für β):**
- Die reale Cluster-/Urteilsqualität echter LLMs an echten Quellen. Dafür fehlt in
  dieser Umgebung ein realer LLM-Adapter (kein Key/SDK) — exakt der offene α-Restpunkt.
  Der `synthesizer` ist hinter `LLMClient` austauschbar; der β-Beweis (Garantien)
  ist davon unabhängig.
- Die „Vollständigkeit" eines Lösungsraums wird **bewusst nicht** behauptet: β
  präsentiert die *verankerbaren* Ansätze, nie „alle". `min_grounded_approaches` ist
  eine Mess-Schwelle (B2), keine Gate-Bedingung — das Gate erzwingt Verankerung, nie
  eine Mindestzahl, sonst würde es zum Erfinden von Alternativen zwingen.

**Nächster ehrlicher Schritt zu „echtem" Betrieb:** reale `LLMClient`-Adapter
(Generator-Familie ≠ Verifier-Familie) + Live-Backends anbinden und dieselbe Suite
gegen Live-Daten fahren, um Modellqualität zu *messen* (nicht die Architektur).
Das Gerüst dafür steht — `run_solution(question, deps)` ist der Einstieg.

## Phase β: Fazit
Der β-Anspruch — echte Lösungen + Alternativen für gelöste Probleme, **ohne einen
Ansatz zu erfinden** — ist als Code erbracht und getestet, auf dem bewiesenen
α-Fundament und ohne es zu schwächen. Phase β ist **abgeschlossen**, bereit für die
Anbindung realer Modelle für den ersten Live-Beweis.

## Unabhängiges Audit (adversarial) + Härtung
Ein unabhängiger Verifikations-Subagent hat versucht, die β-Garantie zu brechen
(erfundener/ungeerdeter Ansatz, Gate-Soundness, α-Schwächung, Trade-off-Ehrlichkeit,
Cross-Model, „checked-but-not-enforced"). Ergebnis: die Garantie hält im
ausgelieferten Pfad, **kein End-to-End-Exploit.** Eine Single-Layer-Schwäche wurde
gefunden und behoben:

- **W1:** Das Gate (geteilter Helfer `claim_soundness_failures`) markierte nur
  `UNSUPPORTED`-Claims als flag-pflichtig, nicht `UNVERIFIED` — obwohl Spec B-6 beide
  nennt. End-to-end durch den `synthesizer`-Filter maskiert, aber das Gate soll der
  **unabhängige** Backstop sein. Behoben (Bedingung auf `UNSUPPORTED|UNVERIFIED`
  erweitert) — wirkt für **beide** Gates (α & β), keine β-Regression, α-Normalpfad
  unverändert. Zwei Regressionstests, **non-vakuös bewiesen** (scheitern ohne Fix).

Endstand: **129 passed.**
