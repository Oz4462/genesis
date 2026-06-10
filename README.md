# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

Ein Mensch liefert ein Problem oder eine Idee. GENESIS recherchiert, **verifiziert**, synthetisiert, detailliert und simuliert — und liefert eine umsetzbare Spezifikation. Domänenübergreifend. **Ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können.

## Status

**Phase α abgeschlossen — das Anti-Halluzinations-Fundament steht und ist beweisbar korrekt.**

Die vollständige Phase-α-Pipeline ist gebaut und getestet: Fakten-Ledger (Quellenzwang), Tool-Adapter (ehrliches Fetch), die vier Agenten (`scout`, `scholar`, `skeptic`, `conductor`), Cross-Model-Verifikation, das Verifikations-Gate und die End-to-End-Verdrahtung mit CLI.

```
$ python -m pytest tests/ -q
102 passed
```

Alle Tests laufen **ohne einen einzigen LLM-Token und ohne Netzwerk**. Das heißt: Die Garantie „kein Fakt ohne Quelle, keine widerlegte Aussage als Tatsache, Lücken werden als Lücken markiert, im Zweifel Abstention" ist **bewiesen** — und von einem unabhängigen, adversarialen Audit bestätigt (Details: `docs/phases/PHASE_ALPHA_RESULT.md`).

```
$ python -m gen --demo        # deterministischer End-to-End-Lauf, offline
```

## Warum diese Reihenfolge

Wenn ein System halluziniert, ist jede weitere Fähigkeit (Ideenfindung, CAD, Simulation) wertlos — sie baut auf Erfundenem auf. Deshalb wird Anti-Halluzination **zuerst** und **isoliert** bewiesen. Erst dann kommen Ideation (Phase β), Spezifikation/CAD (γ), Simulation (δ), weitere Domänen (ε), Selbstlernen (ζ).

## Struktur

```
CLAUDE.md                       Operative Arbeitsregeln (Quelle der Wahrheit für Claude Code)
config.yaml                     Phase-α-Konfiguration (τ, Cross-Model-Familien, Backends)
docs/
  VISION.md                     Vision, Stand der Technik, ehrliche Risiken
  BUILD_LOG.md                  Beweiskette des Baus (Selbstkontrolle je Aufgabe)
  phases/PHASE_ALPHA.md         Spezifikation der Stufe + Akzeptanztests
  phases/PHASE_ALPHA_RESULT.md  Ehrliches Ergebnis je Kriterium + Audit
  agents/*.md                   Pro Agent: Verantwortung, I/O, Tools, Fehler, Tests
src/gen/
  core/interfaces.py            Framework-freie Protocols (Agent, Tool, LedgerStore, Gate, SearchBackend)
  core/state.py                 Datenmodell — inkl. Claim mit Quellenzwang-Invariante
  core/errors.py                Typisierte Fehler (lautes Scheitern statt stiller Defaults)
  ledger/store.py               InMemory-Ledger (Quellenzwang, Unabhängigkeitsregel)
  ledger/postgres.py            Postgres-Adapter (3. Schicht Quellenzwang, lazy asyncpg)
  tools/fetch.py                WebFetchTool — toter Fetch wird NIE zur Quelle
  tools/search.py               Semantic Scholar + generischer Web-Search-Adapter
  llm/base.py                   LLM-Boundary (mockbar) + deterministischer ScriptedLLM
  agents/scout.py               Breite — nur Quellen-Kandidaten
  agents/scholar.py             Tiefe — atomare Claims, jedes Zitat gegen die Quelle geprüft
  agents/skeptic.py             Verifikator — Cross-Model, neue unabhängige Quellen
  agents/conductor.py           Orchestrator — Report nur aus Ledger-Claims
  verification/gates.py         GATE α — reine, getestete Verifikationslogik (+ Backstops)
  verification/cross_model.py   Cross-Model-Pflicht + Confidence-Folding
  config.py / runner.py / cli.py  Konfiguration, run(question)->Report, `python -m gen`
sql/001_ledger.sql              Fakten-Ledger; Quellenzwang als DB-Constraint
tests/                          102 Tests, inkl. Gate-Akzeptanz & 4 Frageklassen
```

## Die zentrale Idee in einer Datenstruktur

Alles dreht sich um den `Claim` (`src/gen/core/state.py`): eine einzelne, prüfbare Aussage, die **nicht ohne Quelle existieren kann** (erzwungen im Konstruktor, im Ledger UND als DB-Constraint — drei Schichten). Der `scholar` erzeugt einen Claim nur, wenn sein Stützzitat **wörtlich in der abgerufenen Quelle** steht. Der `skeptic` prüft jeden Claim mit **neuen, unabhängigen Quellen** und einem **anderen Modell** als der Erzeuger. Das `gate_alpha` lässt nur Berichte durch, in denen jede Tatsache so belegt ist — und prüft die Quellen-/Zuordnungs-Invarianten selbst nach, statt dem Assembler zu vertrauen.

## Nächster Schritt

Phase α ist als Architektur vollständig bewiesen. Der ehrliche nächste Schritt zum Live-Betrieb: reale `LLMClient`-Adapter (Generator-Familie ≠ Verifier-Familie) und Live-Such-Backends hinter `Dependencies` anbinden und dieselbe Akzeptanz-Suite gegen Live-Daten fahren — dann beginnt **Phase β** (Ideation). Siehe `docs/phases/PHASE_ALPHA_RESULT.md` §Methodik.

## Lizenz

Ziel: Apache-2.0 (Open Source).
