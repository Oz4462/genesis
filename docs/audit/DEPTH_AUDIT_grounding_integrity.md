# DEPTH AUDIT — `src/gen/grounding_integrity.py`

**Task:** T04 — Depth-audit + fix grounding_integrity.py (corroboration independence + report grounding)
**Datum:** 2026-06-23
**Verdikt:** **REAL** — beide Checks konsumieren ihre Eingaben echt und implementieren ihren dokumentierten Vertrag korrekt. **Kein Source-Edit nötig** (`change nothing if correct`).

## Umfang
Zwei deterministische, modellfreie Graph-Checks über die bestehenden Ledger-Typen:

1. `corroboration_independence(claims) -> CorroborationReport` (Headline #1)
2. `report_grounding(report, claims) -> GroundingCoverage` (Headline #2)

Neue Test-Datei: `tests/test_grounding_integrity_characterization.py` (Facade-Detektor + Property-Based; Legacy-Test `test_grounding_integrity.py` unangetastet).

## Befunde

### Headline #1 — Corroboration Independence: REAL
- `original = {s.url_or_id for s in c.sources}`, `corroborating = {s.url_or_id for s in c.verification}`; geflaggt wird bei **jeder** Überschneidung (`original & corroborating`). Das ist **strikte Disjunktheit** ("verification sources DISJOINT from original sources"), nicht nur "mindestens eine neue Quelle".
- Nur `VERIFIED`-Claims werden gezählt/auditiert (Vertrag: "verified" soll etwas bedeuten). `independent_rate = (n_verified − |circular|)/n_verified` bzw. `1.0` bei `n_verified == 0` (ehrliche Abstention).
- **Facade-Killer bestanden:** Bei identischen Claim-IDs und nur geändertem Verifikations-Quell-URL bewegt sich die Rate 0.5 → 1.0 und `ok` False → True — die Eingabe wird echt konsumiert, kein konstanter Wert.
- **Negativ/Abstention:** leere Liste / nur Nicht-VERIFIED → `n_verified == 0`, `ok True`, Rate `1.0`.

#### Beobachtung (bewusst NICHT geändert)
Ein `VERIFIED`-Claim mit **leerer** `verification`-Liste wird derzeit als unabhängig gewertet (leere Menge ist vakuös disjunkt). Das ist **außerhalb** der zwei spezifizierten Headlines (die ausdrücklich nur "REUSE any original source" verlangen) und upstream durch den `skeptic` ausgeschlossen: `VERIFIED` wird nur bei `len(supports) >= min_sources` gesetzt (`agents/skeptic.py:261`), und Verifikations-Quellen werden gegen die Scholar-URLs gefiltert (`skeptic.py:206`, Unabhängigkeitsregel). Eine Änderung würde die dokumentierte Disjunktheits-Semantik verschieben → bewusst als Scope-Grenze dokumentiert statt Feature-Creep einzubauen.

### Headline #2 — Report Grounding Coverage: REAL
- Jeder `statement -> claim_id`-Eintrag landet in **genau einem** Bucket: `dangling` (claim_id fehlt), `refuted_backed` (claim ist `REFUTED`), sonst `grounded` (jeder Nicht-REFUTED-Status, inkl. UNVERIFIED/UNSUPPORTED — exakt der dokumentierte "real, non-refuted claim"-Vertrag).
- `coverage = n_grounded/n_statements` bzw. `1.0` bei leerem Report (Abstention). `ok` ⇔ keine dangling/refuted-backed.
- **Facade-Killer bestanden:** 1/4 grounded → coverage 0.25; dieselben Sätze auf einen soliden Claim umgemappt → 1.0, `ok` True.
- **Negativ:** dangling- und refuted-backed-Sätze feuern exakt (mit korrektem `(sentence, claim_id)`-Tupel).

## Property-Based Invarianten (Hypothesis)
- **Partition/Conservation:** `n_grounded + |dangling| + |refuted_backed| == n_statements` für beliebige Bucket-Mischungen; `coverage` == Closed-Form-Verhältnis ∈ [0,1]; `ok` konsistent mit den Listen.
- **Circular-Count:** Anzahl geflaggter Claims == Anzahl konstruiert-wiederverwendender Claims; `independent_rate` == Closed-Form-Verhältnis ∈ [0,1]; `ok` ⇔ keine circular.

## 4 Linsen
- **L1 Wahrheits-Linse:** Beide Checks rechnen echte Mengen-/Verhältnis-Operationen über reale `Claim`/`Report`-Objekte; keine erfundenen/konstanten Werte. Cross-Korroboration ist als strikte Quell-Disjunktheit korrekt operationalisiert.
- **L2 Drift-Linse:** Headlines = Code = Tests. Die strikte-Disjunktheit-Semantik (jede Wiederverwendung flaggt) wird per dediziertem Test gegen die schwächere "hat eine neue Quelle"-Lesart gepinnt → kein stiller Drift.
- **L3 Vollständigkeits-/Naht-Linse:** Alle Status-Werte abgedeckt (VERIFIED/UNVERIFIED/REFUTED/UNSUPPORTED + fehlend); Partition-Property beweist, dass kein Statement durchfällt; Abstention (leere Eingaben) explizit getestet.
- **L4 Realisierbarkeits-Linse:** Rein offline, deterministisch, stdlib + bereits deklarierte Deps (`hypothesis` ist in `dev`). Keine neuen Abhängigkeiten, kein Netz/Subprozess.

## Abgleich GENESIS_PLATFORM_PLAN / Kernprinzipien
Erfüllt "Kein faktischer Output ohne Quelle" auf Graph-Ebene (Report-Grounding) und "Cross-Model / echte Verifikation zählt nur unabhängig" (Corroboration-Independence). "Ich weiß es nicht" als gültige Abstention ist über die vakuös-`ok`-1.0-Pfade respektiert und getestet.

## Ergebnis
21/21 Tests grün (19 neu charakterisierend inkl. 2 Property-Tests + 2 Dataclass-Smoke; Legacy 8 weiter grün). **Keine Quellcode-Änderung** — Modul ist REAL und vertragstreu.
