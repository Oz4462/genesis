# GENESIS

*Generative Engine for Networked Ideation, Synthesis & Specification*

Ein Mensch liefert ein Problem oder eine Idee. GENESIS recherchiert, **verifiziert**, synthetisiert, detailliert und simuliert — und liefert eine umsetzbare Spezifikation. Domänenübergreifend. **Ohne Halluzination.**

> Open-Source-Infrastruktur, damit Menschen — privat wie Unternehmen — aus einer kleinen Idee etwas Vollständiges erschaffen können.

## Status

**Phase α + β abgeschlossen und beweisbar korrekt — jetzt auch live gegen echte Modelle lauffähig.**

Die vollständige α-Pipeline (Anti-Halluzination) und der β-Lösungsraum sind gebaut und getestet: Fakten-Ledger (Quellenzwang), Tool-Adapter (ehrliches Fetch), die Agenten (`scout`, `scholar`, `skeptic`, `conductor`, `synthesizer`), Cross-Model-Verifikation, die Gates α und β und die End-to-End-Verdrahtung mit CLI.

```
$ python -m pytest tests/ -q
154 passed
```

Alle Tests laufen **ohne einen einzigen LLM-Token und ohne Netzwerk**. Das heißt: Die Garantie „kein Fakt ohne Quelle, keine widerlegte Aussage als Tatsache, Lücken werden als Lücken markiert, im Zweifel Abstention" ist **bewiesen** — und von einem unabhängigen, adversarialen Audit bestätigt (Details: `docs/phases/PHASE_ALPHA_RESULT.md`).

```
$ python -m gen --demo        # deterministischer End-to-End-Lauf, offline
$ python -m gen "Frage..."     # Live-Lauf: lokale Ollama-Modelle + Wikipedia, keine Cloud-Keys
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

Phase α + β sind als Architektur vollständig bewiesen, und die ersten realen Adapter (Ollama, Wikipedia, Postgres) sind live angebunden und verifiziert. Der ehrliche nächste Schritt: die externen Discovery-Quellen produktionsreif machen (Semantic-Scholar-API-Key, höfliches Rate-Limiting), damit der Happy-Path — verifizierter Claim aus abrufbarer Quelle — auch unter Live-Last reproduzierbar grün wird, und dieselbe Akzeptanz-Suite gegen Live-Daten fahren. Danach: Phase γ (Spezifikation/CAD). Siehe `docs/phases/PHASE_ALPHA_RESULT.md` §Methodik und `docs/BUILD_LOG.md` (Live-Integrations-Sprint).

## Lizenz

Ziel: Apache-2.0 (Open Source).
