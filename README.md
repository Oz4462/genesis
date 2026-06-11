# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

Ein Mensch liefert ein Problem oder eine Idee. GENESIS recherchiert, **verifiziert**, synthetisiert, detailliert und simuliert — und liefert eine umsetzbare Spezifikation. Domänenübergreifend. **Ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können.

## Status

**Phase α + β + γ abgeschlossen und beweisbar korrekt — α/β auch live gegen echte Modelle bewiesen.**

Die vollständige α-Pipeline (Anti-Halluzination), der β-Lösungsraum und die γ-Spezifikation sind gebaut und getestet: Fakten-Ledger (Quellenzwang), Tool-Adapter (ehrliches Fetch), die Agenten (`scout`, `scholar`, `skeptic`, `conductor`, `synthesizer`, `architect`), Cross-Model-Verifikation, die Gates α, β und γ und die End-to-End-Verdrahtung mit CLI (`--mode report|solution|spec`).

**Neu (Phase γ):** Eine Idee wird zu einer **vollständigen, umsetzbaren Bauanleitung** — Größen mit deklarierter Herkunft, parametrische 3D-Geometrie (CSG), Stückliste, Schritte mit Prüfkriterien, numerisch geprüfte Constraints, Entscheidungsblatt. Die fünf γ-Halluzinationsklassen sind strukturell verhindert (PHASE_GAMMA.md §0): kein Wert ohne wörtlichen Beleg im VERIFIED-Claim, keine LLM-Arithmetik (Code rechnet, GATE γ rechnet unabhängig nach), keine Referenz ins Nichts, keine versteckte Entscheidung, kein Schritt ohne Check — und lieber ehrliche Abstention als eine teilweise/gedriftete Anleitung.

```
$ python -m pytest tests/ -q
232 passed
```

Alle Tests laufen **ohne einen einzigen LLM-Token und ohne Netzwerk**. Das heißt: Die Garantie „kein Fakt ohne Quelle, keine widerlegte Aussage als Tatsache, Lücken werden als Lücken markiert, im Zweifel Abstention" ist **bewiesen** — und von einem unabhängigen, adversarialen Audit bestätigt (Details: `docs/phases/PHASE_ALPHA_RESULT.md`).

```
$ python -m gen --demo                 # deterministischer α-Lauf, offline
$ python -m gen --demo --mode spec     # deterministische γ-Bauanleitung, offline
$ python -m gen "Frage..."             # Live-α: lokale Ollama-Modelle + Wikipedia
$ python -m gen --mode spec "Idee..."  # Live-γ: Idee -> belegte Spezifikation
```

**Live-Betrieb (neu):** Ein realer `OllamaLLM`-Adapter (Generator- und Verifier-Familie getrennt, vor jedem Aufruf erzwungen), ein keyloses `WikipediaBackend` als Discovery-Workhorse und der `PostgresLedgerStore` sind angebunden. Der Postgres-Ledger ist gegen eine echte PostgreSQL-Instanz verifiziert — alle drei Provenance-Schichten greifen, inklusive des DB-Triggers (`scripts/postgres_smoke.py`). Reale End-to-End-Läufe gegen lokale Ollama-Modelle (Generator ≠ Verifier-Familie) belegen beide Seiten der Garantie empirisch, ohne Cloud-Key (`scripts/live_smoke.py`):

- **Abstention statt Halluzination:** Sind Quellen nicht abrufbar oder ein Zitat nicht wörtlich belegbar, abstrahiert das System (Gate bestanden, null Claims). In einem Lauf fing der Wörtlich-Zitat-Guard live eine echte Modell-Paraphrase ab — manuell gegengeprüft, korrekt verworfen.
- **Autonomes VERIFIED:** Existiert echte, abrufbare Korroboration, erreicht GENESIS einen verifizierten Befund vollautomatisch — z. B. „Python is a programming language." mit `confidence 1.0`, gestützt durch zwei unabhängige Quellen, cross-model verifiziert, Gate bestanden.

Reales Testen mit kleinen lokalen Modellen deckte auch ehrliche Qualitätsgrenzen auf (Über-Fragmentierung, oberflächliches Verifier-Urteil) — root-cause-gefixt bzw. dokumentiert in `docs/BUILD_LOG.md` (LI-8). **Keine erfundene Tatsache gelangte je in einen Bericht.**

## Warum diese Reihenfolge

Wenn ein System halluziniert, ist jede weitere Fähigkeit (Ideenfindung, CAD, Simulation) wertlos — sie baut auf Erfundenem auf. Deshalb wird Anti-Halluzination **zuerst** und **isoliert** bewiesen. Erst dann kommen Ideation (Phase β), Spezifikation/CAD (γ), Simulation (δ), weitere Domänen (ε), Selbstlernen (ζ).

## Struktur

```
CLAUDE.md                       Operative Arbeitsregeln (Quelle der Wahrheit für Claude Code)
config.yaml                     Phase-α-Konfiguration (τ, Cross-Model-Familien, Backends)
docs/
  VISION.md                     Vision, Stand der Technik, ehrliche Risiken
  BUILD_LOG.md                  Beweiskette des Baus (Selbstkontrolle je Aufgabe)
  phases/PHASE_*.md             Spezifikation je Stufe (α, β, γ) + Akzeptanztests
  phases/PHASE_*_RESULT.md      Ehrliches Ergebnis je Kriterium + Audit
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
  agents/conductor.py           Orchestrator — Report/Spec nur aus Ledger-Claims
  agents/synthesizer.py         Phase β — verankerte Lösungsansätze, erfindet nichts
  agents/architect.py           Phase γ — Spezifikation; Wertzwang, Code rechnet, Self-Gate
  verification/gates.py         GATEs α, β, γ — reine, getestete Verifikationslogik (+ Backstops)
  verification/derivation.py    Safe-Evaluator — DERIVED-Werte: Code rechnet, Gate rechnet nach
  verification/cross_model.py   Cross-Model-Pflicht + Confidence-Folding
  config.py / runner.py / cli.py  Konfiguration, run(question)->Report, `python -m gen`
sql/001_ledger.sql              Fakten-Ledger; Quellenzwang als DB-Constraint
tests/                          102 Tests, inkl. Gate-Akzeptanz & 4 Frageklassen
```

## Die zentrale Idee in einer Datenstruktur

Alles dreht sich um den `Claim` (`src/gen/core/state.py`): eine einzelne, prüfbare Aussage, die **nicht ohne Quelle existieren kann** (erzwungen im Konstruktor, im Ledger UND als DB-Constraint — drei Schichten). Der `scholar` erzeugt einen Claim nur, wenn sein Stützzitat **wörtlich in der abgerufenen Quelle** steht. Der `skeptic` prüft jeden Claim mit **neuen, unabhängigen Quellen** und einem **anderen Modell** als der Erzeuger. Das `gate_alpha` lässt nur Berichte durch, in denen jede Tatsache so belegt ist — und prüft die Quellen-/Zuordnungs-Invarianten selbst nach, statt dem Assembler zu vertrauen.

## Nächster Schritt

Phase α + β + γ sind als Architektur vollständig bewiesen; α/β sind zusätzlich live (Ollama, Wikipedia, Postgres) verifiziert. Die ehrlichen nächsten Schritte: (1) der γ-Live-Beweis — `--mode spec` gegen lokale Ollama-Modelle fahren und die reale Struktur-/Formulierungsqualität messen (die Garantien gelten unabhängig davon); (2) CAD-Export-Adapter (CSG → OpenSCAD/build123d, PHASE_GAMMA.md §10); (3) externe Discovery-Quellen produktionsreif machen (Semantic-Scholar-API-Key, höfliches Rate-Limiting). Danach: Phase δ (Simulation/Validierung). Siehe `docs/phases/PHASE_GAMMA_RESULT.md` §Methodik.

## Lizenz

Ziel: Apache-2.0 (Open Source).
