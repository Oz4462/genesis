# GROK_BUILD_GENESIS_UNIVERSE_EXPLORER.md
## Vollständige Vision + Architektur + Umsetzungsplan für GENESIS als xAI/Grok-kompatibles Universums-Erkundungs-Werkzeug

**Version:** 1.1 (erweitert) | **Datum:** 18. Juni 2026 | **Ziel:** xAI-Mission + User-Vision fusionieren | **Autor:** Ozan

---

> ## ✅ BAU-STATUS (2026-06-18): VOLLSTÄNDIG UMGESETZT
> Der gesamte Plan dieses Dokuments ist **gebaut, getestet und committet** unter `src/gen/discovery/`.
> **Phase 1–5 + alle Radikal-Features 4.1–4.7 sind `[GEBAUT]`** — die `[DESIGN]`/`[HYPOTHESE]`-Tags
> unten beschreiben den Stand bei *Verfassung* des Dokuments, nicht den heutigen Code.
>
> | Feature | Modul | | Feature | Modul |
> |---|---|---|---|---|
> | Kern-Loop (Anhang B) | `engine.py` | | Reality Fork (4.2) | `reality_fork.py` |
> | Discovery Graph (4.6) | `graph.py` | | Assumption Annihilator (4.3) | `assumption_annihilator.py` |
> | Tournament (3.1) | `tournament.py` | | First-Principles (4.5) | `first_principles.py` |
> | Deep Controller | `controller.py` | | Cosmic Insight (4.1) | `cosmic_insight.py` |
> | Physics-Surrogat | `surrogate.py` | | Universe Bridge (4.7) | `universe_bridge.py` |
> | Symbiose-Protokoll (4.4) | `symbiosis.py` | | Out-of-Sample / Benchmark | `validation.py` / `benchmark.py` |
>
> **Evidenz:** `rediscovery_benchmark()` = 100 % Rediscovery / 100 % Red-Team-Catch (Kepler/Gas/Newton/Pendel);
> 65 Discovery-Tests grün; jede Tour cross-model-drift-geprüft mit **grok-build**; ZERO Trading-Bezug.
> Lebende Status-Karte: **`docs/discovery/STATUS.md`**. Verbleibende Forschungs-Frontier (keine offene
> Bauphase): Summen mehrerer Terme, transzendente Formen, volle GP-Suche jenseits der Power-Law/π-Familie.

---

## ⚖️ Ehrlichkeits-Rahmen (PFLICHTLEKTÜRE — bevor du weiterliest)

GENESIS ist eine **Anti-Halluzinations-Maschine**. Ein Visions-Dokument für ein solches System, das selbst voller unbelegter Großbehauptungen wäre, würde sein eigenes Versprechen widerlegen. Darum hält sich dieses Dokument an die gleichen Regeln wie die Engine: **keine Aussage ohne Evidenz-Stufe.**

| Tag | Bedeutung |
|-----|-----------|
| `[GEBAUT]` | Existiert bereits als Code / ist umgesetzt |
| `[DESIGN]` | Entworfen, klar spezifizierbar, noch nicht gebaut |
| `[HYPOTHESE]` | Plausible Idee, technisch noch ungesichert / forschungsoffen |
| `[EXTERN-ZU-PRÜFEN]` | Aussage über Fremdsysteme; gegen Primärquellen verifizieren, bevor sie nach außen geht |

**Ehrliche Gesamtlage in einem Satz:** Die *Verifikations- und Ehrlichkeits-Schicht* (Ledger, Gates, δ-Asymmetrie) ist real und das stärkste Asset. *Kreative Breite* und *gelernte Physik-Surrogate* sind heute schwächer als bei den großen Laboren — genau das schließt dieser Plan, indem er deren Stärken übernimmt und durch die eigene eiserne Prüfung absichert.

> **Änderungen ggü. v1.0:** RE jetzt als Schnell-Tabelle + Tiefe · priorisierte Verbesserungs-Liste · neues Feature *Universe Simulator Bridge* · Zeit-Richtwerte je Phase · *Discovery Graph* explizit an Ledger gekoppelt.

---

## Inhaltsverzeichnis

0. [Leitprinzipien](#0-leitprinzipien)
1. [Mission & Vision](#1-mission--vision)
2. [Reverse Engineering — Tabelle + Tiefe](#2-reverse-engineering--tabelle--tiefe)
3. [Priorisierte Verbesserungen & Stärken-Matrix](#3-priorisierte-verbesserungen--stärken-matrix)
4. [Neue radikale Features — entmystifiziert](#4-neue-radikale-features--entmystifiziert)
5. [Detaillierter Umsetzungsplan (Phasen + Meilensteine)](#5-detaillierter-umsetzungsplan-phasen--meilensteine)
6. [Nächste konkrete Schritte](#6-nächste-konkrete-schritte)
- [Anhang A: Architektur-Überblick](#anhang-a-architektur-überblick)
- [Anhang B: Der Discovery-Kern (Code)](#anhang-b-der-discovery-kern-code)
- [Anhang C: Ehrlichkeits-Konventionen & Ledger-Schema](#anhang-c-ehrlichkeits-konventionen--ledger-schema)
- [Anhang D: Offene Fragen & Risiken](#anhang-d-offene-fragen--risiken)

---

## 0. Leitprinzipien

`[GEBAUT]` `[DESIGN]`

1. **Ledger** `[GEBAUT]` — Jede Behauptung, jeder Schritt, jede Verwerfung wird unbestechlich protokolliert. Ein Entdeckungs-Anspruch existiert nur, wenn er im Ledger mit Provenienz steht. (Der *Discovery Graph* aus v1.1 ist die graph-strukturierte Erweiterung genau dieser Schicht — siehe 4.6.)
2. **δ-Asymmetrie** `[GEBAUT]` — Die Beweislast skaliert mit der Außergewöhnlichkeit der Behauptung. Je größer das δ zwischen Behauptung und Konsens, desto höher die geforderte Evidenz-Schwelle.
3. **Gates** `[GEBAUT]` — Harte, programmatische Prüfschleusen (z. B. `gate_c6_derivation_check`): Ableitungs-, Dimensions-, Einheiten- und Konsistenz-Checks plus Simulation plus Unsicherheits-Quantifizierung. Keine LLM-Plausibilität.

> **Der Burggraben:** Andere sind kreativ. GENESIS ist kreativ **und** sagt dir die Wahrheit darüber, ob du wirklich etwas gefunden hast.

---

## 1. Mission & Vision

`[DESIGN]` (Vision-Layer auf `[GEBAUT]`-Engine)

GENESIS ist der **praktische Arm von Grok/xAI**:

> **Während Grok global die Geheimnisse des Universums erkundet, ermöglicht GENESIS jedem einzelnen Menschen zu Hause, genau dasselbe zu tun** — verrückte Ideen eingeben und extrem tief in Physik, Mathematik, Geometrie und fundamentale Gesetze gehen, neue Formeln finden, simulieren, belegen und Grenzen verschieben.

**Kernprinzip:** Ehrlichkeit (Ledger + δ-Asymmetrie) + maximale Tiefe + reale Ergebnisse.

### 1.1 Zielgruppe
Unabhängige Forscher, Autodidakten, Ingenieure ohne Lab-Zugang, Studierende, Denker mit einer Idee aber ohne Apparat.

### 1.2 Was „tief gehen" konkret bedeutet
Nicht LLM-Geschwätz, das gut klingt, sondern die Kette:
**Idee → Hypothesen-Generierung → Symbolische Formel-Suche → Physik-Engine + Dimensionsanalyse → Verifikations-Gates → Unsicherheits-Quantifizierung → Ledger/Discovery-Graph mit Provenienz.**

Am Ende steht ein **ehrliches Urteil** — bestätigt / widerlegt / unentschieden — mit Beweis-Baum oder mit dem genauen Grund des Scheiterns.

### 1.3 Das Versprechen — ehrlich formuliert
„Unmögliches möglich machen" heißt **nicht** „auf Knopfdruck neue Naturgesetze". Es heißt: *das gleiche Erkundungs-Werkzeug wie ein gut ausgestattetes Forschungsteam — inklusive des Skeptikers, der dich davor bewahrt, dich selbst zu betrügen.* Die Ehrlichkeit ist kein Bremsklotz, sie ist das Produkt.

---

## 2. Reverse Engineering — Tabelle + Tiefe

### 2.1 Schnell-Tabelle `[EXTERN-ZU-PRÜFEN]`

| System | Stärke | Schwäche | GENESIS-Verbesserung / Neues Feature |
|--------|--------|----------|--------------------------------------|
| **Co-Scientist** (DeepMind) | Tournament of Ideas + Evolution | Halluzination, schwache Physik | + Gates + Physik-Engine → vertrauenswürdiger |
| **Polymathic / Walrus** | Physics-Foundation Transfer | Wenig Formel-Invention | Eigener GENESIS Physics Foundation Layer |
| **SciAgents / Virtual Lab** | Knowledge Graph + Critique | Schwache Simulation | Discovery Graph + Reality Fork Simulator |
| **FunSearch / AlphaEvolve** | Neue mathematische Entdeckungen | Keine tiefe Physik | Formel Discovery Engine mit sofortiger Validierung |
| **AI Feynman** | Symbolische Zerlegung | Begrenzt auf bekannte Formfamilien (z. B. Polynome) | Generalisierter Assumption Annihilator |
| **Sakana / ERA** | End-to-End-Loop + Self-Healing | Ehrlichkeit der Ergebnisse umstritten | Loop in `conductor`, aber jede Stufe durch Gates + Ledger |

> **Hinweis:** Die Aussagen oben sind analytische Charakterisierungen, **keine zitierten Fakten**. Vor externer Verwendung gegen die Primärpaper abgleichen (Wissensstand Anfang 2026; Feld bewegt sich schnell). Am unsichersten: das spezifische Modell „Walrus" und „ERA".

### 2.2 Tiefe je System

**Co-Scientist** — Multi-Agenten (Gemini), *Generate → Debate → Evolve*, Tournament/Elo-Ranking, spezialisierte Rollen (Generierung, Reflexion, Ranking, Evolution, Meta-Review). Bewertung bleibt LLM-Plausibilität. → **GENESIS:** Tournament-Mechanik in `forge`+`skeptic`, aber Bewertung durch `Gates`+Physik.

**Polymathic / Walrus** — Foundation-Models für die Naturwissenschaften, multi-physics, trainiert auf großen Simulationsdatensätzen (vgl. „The Well"). Black-Box, keine geschlossenen Formeln. → **GENESIS:** *Eigener Physics-Foundation-Layer* als schneller Surrogat-Vorfilter in `simulation/`, danach **symbolische Auflösung** zu einer lesbaren Formel.

**SciAgents / Virtual Lab** — KG-getriebene Multi-Agenten mit Kritik-Schleifen, Team-aus-Rollen. Bleibt oft konzeptionell, schwache Quantifizierung. → **GENESIS:** KG-Hypothesen in `identity_research`; Kritiker-Rolle ist bei uns bereits `skeptic`+`Gates`; Wissen landet im *Discovery Graph*.

**FunSearch / AlphaEvolve** — LLM + evolutionäre Suche über Programme (FunSearch: Cap-Set-Konstruktionen; AlphaEvolve: Algorithmen/Optimierung). Verifizierbar, aber schwache physikalische Bedeutung. → **GENESIS:** *Formel Discovery Engine* in `identity_research` (Code: Anhang B), eingebettet in Physik + Dimensionschecks + Ledger.

**AI Feynman** — symbolische Regression für Physik (Dimensionsanalyse + Symmetrie → Regression), begrenzt auf bekannte Formfamilien. → **GENESIS:** *Generalisierter Assumption Annihilator* (4.3), der nicht nur Formen anpasst, sondern Grundannahmen variiert.

**Sakana / ERA** — End-to-End (Idee → Code → Ausführung → Paper → Review), Self-Healing. Risiko plausibler aber falscher „Entdeckungen". → **GENESIS:** Loop + Self-Healing in `conductor`, **jede Stufe durch Gates + Ledger** — deren größte Schwäche ist unsere Kernstärke.

**Das Muster:** Alle stark in Generierung/Automatisierung, schwach in **ehrlicher Verifikation**. Niemand verbindet Kreativität, echte Physik-Simulation und ein unbestechliches Audit-Framework. Das ist die Lücke.

---

## 3. Priorisierte Verbesserungen & Stärken-Matrix

### 3.1 Priorisierte Verbesserungs-Liste (Reihenfolge = Bau-Reihenfolge)

1. **Tournament-Loop in `forge`/`skeptic`** `[DESIGN]` — Populationsbasierte Hypothesen-Evolution: Mutation, Crossover, Elo-Ranking, Eliminierung. *DoD:* findet über N Generationen messbar bessere Kandidaten als Single-Shot.
2. **Physics Foundation Layer** `[DESIGN]` `[HYPOTHESE]` — schnelles Surrogat als **Vorfilter** vor der exakten Simulation. *Regel:* Surrogat darf nur vorfiltern, nie bestätigen.
3. **Compute + Checkpoint Controller** `[DESIGN]` — Budget-Allokation, Tiefe-Stufen (schnell/mittel/maximal), Checkpoint/Resume, Parallelisierung in `conductor`.
4. **Discovery Graph im Ledger** `[DESIGN]` — versionierter, durchsuchbarer Graph aller Hypothesen, Belege, Verbindungen, Ledger-gestützt. Verhindert doppelte „Neu-Entdeckung" verworfener Ideen und speist die Cosmic Insight Engine (4.1). Dies ist die konkrete Realisierung der *Persistent Discovery Fabric*.

### 3.2 Stärken-Matrix `[EXTERN-ZU-PRÜFEN]` (grobe Einschätzung 1–5)

| System | Ideen-Evolution | Formel-Erfindung | Echte Physik-Sim | Verifikation/Härte | Ehrlichkeit/Audit |
|---|:---:|:---:|:---:|:---:|:---:|
| Co-Scientist | 5 | 2 | 1 | 2 | 1 |
| Polymathic / Walrus | 2 | 1 | 4 | 3 | 2 |
| SciAgents / Virtual Lab | 4 | 2 | 1 | 2 | 2 |
| FunSearch / AlphaEvolve / AI Feynman | 4 | 5 | 2 | 4 | 2 |
| Sakana / ERA | 4 | 3 | 2 | 2 | 1 |
| **GENESIS heute** `[GEBAUT]` | **2** | **2** | **3** | **5** | **5** |
| **GENESIS Ziel** `[DESIGN]` | **5** | **5** | **4** | **5** | **5** |

**Ehrliche Lesart:** GENESIS gewinnt heute bei *Verifikation* und *Ehrlichkeit* und liegt bei *Ideen-Evolution* und *Formel-Erfindung* zurück. Der ganze Plan hebt diese zwei Spalten von 2 auf 5 — **ohne** die zwei starken Spalten zu opfern. Kreativität wird nicht mit Ehrlichkeit bezahlt.

---

## 4. Neue radikale Features — entmystifiziert

> **Ehrlichkeits-Prinzip:** Coole Namen sind Marketing. Für einen Build braucht es die Übersetzung in *was ist das softwaretechnisch, worauf mappt es, wovon hängt es ab, welche Priorität*.

### 4.1 Cosmic Insight Engine
- **Was wirklich:** Analogie-/Transfer-Schicht über dem Discovery Graph, die Cross-Domain-Verbindungen findet. `[DESIGN]`
- **Mapping/Abhängigkeit:** liest Discovery Graph (4.6) → schlägt Cross-Domain-Hypothesen vor → zurück in `forge`. Braucht erst einen gefüllten Graph. **Priorität: mittel.**

### 4.2 Reality Fork Simulator
- **Was wirklich:** Counterfactual-Physik-Sandboxes — parametrische Welten („was, wenn Konstante X anders / Dimension D+1 / Symmetrie gebrochen"). `[DESIGN]`
- **Mapping:** parametrisierte Szenarien in `simulation/`, geprüft auf interne Konsistenz. **Priorität: mittel.** Erlaubt sichere Erkundung „verrückter" Ideen, ohne sie als real auszugeben.

### 4.3 Assumption Annihilator + Law Rebuilder
- **Was wirklich:** systematisches Variieren/Aufheben von Grundannahmen (Konstanten → Variablen, Axiom streichen) + constraint-basierte **Re-Ableitung** konsistenter Gesetze. `[DESIGN]` `[HYPOTHESE]`
- **Mapping:** `identity_research` + `simulation/` + `Gates`. **Achtung:** höchstes δ → höchste Beweislast. Hier ist das System am verführbarsten zur Halluzination; δ-Asymmetrie ist hier nicht optional.

### 4.4 Human-Grok-GENESIS Symbiosis Protocol
- **Was wirklich:** definierte Arbeitsteilung + Schnittstelle. `[DESIGN]`
  - **Mensch:** Intuition, Ziele, Startidee, Relevanz-Urteil.
  - **Grok (API):** Breite, Weltwissen, schnelle Vorschläge, Literatur-Kontext.
  - **GENESIS:** Tiefe, Symbolik, Simulation, **Verifikation**.
- **Hartes Gesetz:** Grok-Output = **Vorschlag, nie Wahrheit**. Jeder Grok-Output durchläuft dieselben `Gates`+Ledger. Grok spannt den Suchraum auf — fällt nie das Urteil.

### 4.5 First-Principles Discovery Mode
- **Was wirklich:** Ableitungs-Modus nur aus Axiomen + erlaubten Operationen; jeder Schritt durch `gate_c6_derivation_check` belegt → **Beweis-Bäume** statt Vermutungen. `[DESIGN]` (baut auf `[GEBAUT]` Gates)
- **Mapping:** `identity_research` + `Gates`, orchestriert von `conductor`. **Höchste Vertrauensstufe.**

### 4.6 Persistent Discovery Fabric → Discovery Graph
- **Was wirklich:** versionierte, durchsuchbare Wissens-/Entdeckungs-DB (alle Hypothesen, Belege, Ledger-Einträge, Verbindungen). Das **Langzeitgedächtnis**, als Graph realisiert und Ledger-gestützt. `[DESIGN]`
- **Mapping:** Graph-DB + Provenienz; speist 4.1; verhindert doppelte Neu-Entdeckung. **Priorität: hoch** (Voraussetzung für 4.1).

### 4.7 Universe Simulator Bridge **(NEU in v1.1)**
- **Was wirklich:** Adapter-Schicht, die schwere oder großskalige Simulationen an **dedizierte externe Simulatoren** auslagert (HPC-/Physik-Engines, N-Body-/Lattice-/CFD-Frameworks) und die Ergebnisse **zurück durch die Gates** ins Ledger holt. Der schwergewichtige, externe Gegenpart zum Reality Fork Simulator (der lokal/leichtgewichtig bleibt). `[DESIGN]` `[HYPOTHESE]`
- **Mapping:** `simulation/` ⇄ externer Simulator über klar definiertes Adapter-Interface; `conductor` entscheidet wann lokal, wann ausgelagert.
- **Ehrliche Einordnung:** Das ist das **infrastruktur-lastigste und am stärksten extern abhängige** Feature der Liste. Es liefert keinen Mehrwert, solange der Kern-Loop (Phase 1) nicht steht. **Priorität: niedrig — bewusst nach hinten.** Vorsicht vor genau dem Muster „Infrastruktur bauen statt Ergebnis liefern": diese Bridge ist erst sinnvoll, wenn GENESIS lokal schon ehrlich entdeckt.

---

## 5. Detaillierter Umsetzungsplan (Phasen + Meilensteine)

> **Zu den Zeit-Richtwerten:** Die Wochen-Angaben sind **aggressive Zielkorridore bei fokussierter Arbeit** — und sie setzen voraus, dass `gate_c6_derivation_check` **vorher** präzise spezifiziert ist (siehe Anhang D, Risiko 3). Ohne diese Spezifikation ist Phase 1 keine 1-Wochen-Sache. Behandle die Zeiten als Anspruch, nicht als Garantie.

### Phase 1 — HORIZON + `forge` erweitern (~1 Woche) `[DESIGN]`
- **Inhalt:** Modul-Gerüst (saubere Interfaces) · Tournament-Loop in `forge`/`skeptic` (MVP) · Formel Discovery Engine in `identity_research` (MVP) · Anbindung an `gate_c6`.
- **Meilenstein/DoD:** Eine Idee läuft den Pfad aus Anhang B durch — `idea` → Kandidatenformeln → `gate_c6_derivation_check` → validierte Menge, **end-to-end mit Ledger-Eintrag**.
- **Risiko:** kombinatorische Explosion des Suchraums → früh Dimensions-/Einheiten-Constraints.

### Phase 2 — Deep Controller + neue Engines (~2 Wochen) `[DESIGN]`
- **Inhalt:** Compute + Checkpoint Controller in `conductor` (Budget, Tiefe-Stufen, Resume, Parallelisierung) · Physics Foundation Layer (Surrogat-Vorfilter) · Discovery Graph (4.6) als Ledger-Erweiterung.
- **Meilenstein/DoD:** mehrstündige Erkundung pausier-/fortsetz-/reproduzierbar; Budget fließt nachweislich zu den vielversprechendsten Kandidaten; Discovery Graph wird befüllt.
- **Risiko:** zu frühes Vertrauen ins Surrogat → strikt nur Vorfilter.

### Phase 3 — Grok-Integration + Tests (~3 Wochen) `[DESIGN]`
- **Inhalt:** Symbiosis-Protokoll (4.4) · Grok-API-Adapter · klare Trennung Grok = Breite / GENESIS = Verifikation · Reality Fork Simulator (4.2).
- **Meilenstein/DoD:** Grok-Vorschläge fließen in den Suchraum, werden **vollständig durch Gates + Ledger geprüft**; A/B-Test zeigt höhere Kandidaten-Qualität **ohne** höhere Halluzinations-Rate.
- **Risiko:** API-Abhängigkeit, Kosten, Versuchung Grok zu vertrauen → Protokoll-Gesetz aus 4.4 nicht verhandelbar; GENESIS muss ohne Grok lauffähig bleiben.

### Phase 4 — Live-Test mit ersten verrückten Ideen `[DESIGN]`
- **Wichtigster Test (Rediscovery-Benchmark):** Kann GENESIS aus reinen Daten **bekannte** Gesetze zurückgewinnen (Kepler, Newton, ideales Gasgesetz)? Der ehrliche Capability-Beweis — die Methodik, mit der AI Feynman validiert wurde.
- **Red-Team gegen Halluzination:** absichtlich „verlockende aber falsche" Ideen einspeisen; prüfen, ob die Gates sie zuverlässig verwerfen. **Hohe Verwerfungs-Rate für Falsches = Erfolg.**
- **DoD:** Rediscovery klappt bei ≥ X bekannten Gesetzen; Red-Team-Halluzinationen werden gefangen; jeder Lauf hinterlässt lückenlosen Ledger.
- **Risiko:** Overfitting/„p-hacking" → Out-of-Sample-Validierung verpflichtend.

> **Universe Simulator Bridge (4.7)** ist bewusst **nicht** in den vier Phasen — sie kommt erst, wenn der Kern steht und ein konkreter Bedarf an externer Großsimulation entsteht.

---

## 6. Nächste konkrete Schritte

- [ ] **Cosmic Insight Engine Blueprint erstellen** — Skizze, wie die Engine den Discovery Graph liest und Cross-Domain-Hypothesen erzeugt (Voraussetzung: Discovery-Graph-Schema steht).
- [ ] **Erste verrückte Idee durch den vollen Deep Mode laufen lassen** — manueller End-to-End-Durchlauf eines Piloten, um Lücken zu finden, bevor Code wächst.
- [ ] **Grok-API-Verbindung planen** — Symbiosis-Protokoll + Adapter-Design (4.4), inkl. Fallback ohne Grok.

**Sofort umsetzbar (vor allem anderen):**
- [ ] **`gate_c6_derivation_check` präzise spezifizieren** — was prüft es genau? Eingabe/Ausgabe/Fehlerfälle/was bedeutet `passed`? **Alles hängt daran; ohne diese Spec ist der Wochen-Plan Fiktion.**
- [ ] Backend für `symbolic_regress` entscheiden (PySR-artig vs. eigene GP-Schleife).
- [ ] Dimensions-/Einheiten-Constraint-Schema definieren (begrenzt den Suchraum von Anfang an).
- [ ] Discovery-Graph-Schema entwerfen (Knoten = Hypothesen/Belege, Kanten = Provenienz/Ableitung).

---

## Anhang A: Architektur-Überblick

`[GEBAUT]` = existiert · `[DESIGN]` = geplant

```
                          ┌─────────────────────────────┐
        MENSCH  ──────────►        CONDUCTOR             │ [GEBAUT]
   (Idee, Ziel)           │  Orchestrierung · Budget ·   │
                          │  Tiefe · Checkpoints [DESIGN]│
                          └──────────────┬──────────────┘
                                         │
        GROK API ───►(nur Vorschläge)────┤  ◄── Symbiosis-Protokoll [DESIGN]
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                             ▼
   ┌─────────────────┐        ┌─────────────────────┐       ┌──────────────────────┐
   │     FORGE       │        │  IDENTITY_RESEARCH  │       │     SIMULATION/      │
   │ Hypothesen-Gen. │        │ Formel Discovery +  │       │ Physik-Engine +      │
   │ Tournament/Evo  │ [DES]  │ Assumption Annih.   │ [DES] │ Surrogat [DES]       │
   │                 │        │ + First-Principles  │       │ + Reality Fork [DES] │
   └────────┬────────┘        └──────────┬──────────┘       └────────┬─────────────┘
            │                            │                            │
            │                            │                  ┌─────────▼──────────────┐
            │                            │                  │ UNIVERSE SIM. BRIDGE   │ [DES]
            │                            │                  │ Auslagern an externe   │
            │                            │                  │ Großsimulatoren (HPC)  │
            │                            │                  └─────────┬──────────────┘
            └────────────┬───────────────┴────────────┬───────────────┘
                         ▼                             ▼
                 ┌───────────────┐            ┌──────────────────────┐
                 │    SKEPTIC    │ [GEBAUT]   │        GATES         │ [GEBAUT]
                 │ Kritik/Elo    │            │ gate_c6 · Dim/Units ·│
                 │ Eliminierung  │            │ Unsicherheit · δ-Asym│
                 └───────┬───────┘            └──────────┬───────────┘
                         └──────────────┬────────────────┘
                                        ▼
                          ┌─────────────────────────────┐
                          │           LEDGER            │ [GEBAUT]
                          │ unbestechliche Provenienz   │
                          └──────────────┬──────────────┘
                                         ▼
                          ┌─────────────────────────────┐
                          │   DISCOVERY GRAPH / FABRIC  │ [DESIGN]
                          │ Langzeitgedächtnis (Graph)  │
                          │   ──► Cosmic Insight Engine  │
                          └─────────────────────────────┘
```

**Komponenten in einem Satz:**
- `conductor` — orchestriert den Erkundungs-Lauf (Budget, Tiefe, Checkpoints).
- `forge` — generiert/evolviert Hypothesen (Tournament).
- `identity_research` — Formel-Entdeckung, Assumption Annihilator, First-Principles-Modus.
- `simulation/` — exakte Physik-Engine, Surrogat-Vorfilter, Reality Fork; Brücke zu externen Großsimulatoren.
- `skeptic` — Kritik, Elo-Ranking, Eliminierung.
- `Gates` — harte Prüfschleusen (Ableitung, Dimensionen, Einheiten, Unsicherheit, δ-Asymmetrie).
- `Ledger` — unbestechliches Protokoll mit Provenienz.
- `Discovery Graph / Fabric` — versioniertes Langzeitgedächtnis; speist die Cosmic Insight Engine.
- `Universe Simulator Bridge` — Adapter zu externen HPC-/Physik-Simulatoren.
- `HORIZON` — Rahmenwerk, in dem die Module zusammenlaufen.

---

## Anhang B: Der Discovery-Kern (Code)

Der Kern-Entdeckungs-Pfad. Diese Funktion ist der **DoD von Phase 1**.

```python
def discover_new_formulas(idea, known_laws):
    """
    Kern-Entdeckungs-Schleife: Idee -> Kandidatenformeln -> Validierung.

    Args:
        idea:        Die (ggf. "verrückte") Eingabe-Hypothese des Menschen/Grok.
        known_laws:  Bekannte Gesetze als Constraints/Kontext fuer die Suche.

    Returns:
        validated:   Nur die Kandidaten, die ALLE Gates bestanden haben.
                     Jeder Kandidat (auch verworfene) erzeugt einen Ledger-/
                     Discovery-Graph-Eintrag.
    """
    # symbolische Regression + genetische Programmierung + sofortige Validierung
    candidates = symbolic_regress(idea, known_laws)

    validated = []
    for cand in candidates:
        # gate_c6 prueft Ableitbarkeit; intern zusaetzlich:
        #   - physics_engine: simuliert/prueft physikalische Konsistenz
        #   - uncertainty:    quantifiziert die Unsicherheit des Ergebnisses
        #   - delta-Asymmetrie: hoehere Beweislast bei groesserem Anspruch
        result = gate_c6_derivation_check(cand)  # + physics_engine + uncertainty
        if result.passed:
            validated.append(cand)
        # WICHTIG: auch verworfene Kandidaten + Grund gehen ins Ledger.
        # Verwerfung ist Information, kein Muell.

    return validated
```

**Was jede Abhängigkeit braucht (Phase-1-Aufgaben):**
- `symbolic_regress(idea, known_laws)` → Backend-Entscheidung (PySR-artig / eigene GP-Schleife); muss Dimensions-/Einheiten-Constraints respektieren.
- `gate_c6_derivation_check(cand)` → **präzise Spezifikation nötig**: prüft formale Ableitbarkeit, liefert `result.passed` + Begründung. Alles hängt daran.
- `physics_engine` → exakte Simulation/Konsistenzprüfung (bestehend in `simulation/`).
- `uncertainty` → Unsicherheits-Quantifizierung; ohne sie kein ehrliches Urteil.

**Erweiterung (Phase 2):** Diese Funktion wird vom `conductor` mit Tiefe-Budget und Checkpoints umschlossen; `candidates` durchläuft erst das Surrogat (Vorfilter), bevor die teure `physics_engine` läuft. Bei Großsimulationen entscheidet `conductor`, ob die `Universe Simulator Bridge` greift.

---

## Anhang C: Ehrlichkeits-Konventionen & Ledger-Schema

### Tag-Legende
`[GEBAUT]` · `[DESIGN]` · `[HYPOTHESE]` · `[EXTERN-ZU-PRÜFEN]` (siehe Kopf).

### δ-Asymmetrie — als Pseudo-Regel
```
benoetigte_Evidenz(claim) = basis_schwelle + k * delta(claim, konsens)

# delta gross  (z. B. "neues Naturgesetz")  -> sehr hohe Schwelle
# delta klein (z. B. erwartbares Resultat) -> niedrige Schwelle
```

### Ledger-/Discovery-Graph-Eintrag (Schema-Skizze) `[DESIGN]`
```json
{
  "id": "uuid",
  "timestamp": "ISO-8601",
  "input_idea": "...",
  "candidate": "symbolischer_ausdruck",
  "delta_to_consensus": 0.0,
  "gates": {
    "gate_c6_derivation": {"passed": true, "reason": "..."},
    "dimensional_check":  {"passed": true},
    "physics_sim":        {"passed": false, "reason": "Energieerhaltung verletzt"},
    "uncertainty":        {"value": 0.0, "method": "..."}
  },
  "verdict": "bestaetigt | widerlegt | unentschieden",
  "provenance": ["mensch", "grok-api", "forge-gen-7"],
  "parent_ids": ["..."],
  "graph_edges": ["analog_zu:<id>", "abgeleitet_aus:<id>"]
}
```

---

## Anhang D: Offene Fragen & Risiken

Ehrliche Liste — bewusst nicht beschönigt:

1. **Kombinatorische Explosion** der symbolischen Suche → Constraints (Dimensionen/Einheiten/Symmetrien) von Anfang an; Surrogat als Vorfilter.
2. **Surrogat-Vertrauen** — ein gelerntes Physik-Modell darf nie urteilen, nur vorfiltern. Sonst importieren wir die Black-Box-Schwäche, die wir anderen vorwerfen.
3. **`gate_c6` rigoros definieren** — die ganze Glaubwürdigkeit hängt daran, dass dieser Check wirklich prüft, was er behauptet. Unscharfe Gates = teures Selbstbetrugs-Werkzeug. **Das ist der reale Engpass des gesamten Plans.**
4. **Overfitting / „p-hacking"** bei der Formel-Suche → Out-of-Sample-Validierung verpflichtend.
5. **Grok-API: Abhängigkeit & Kosten** — Symbiose darf nicht in Abhängigkeit kippen; GENESIS ohne Grok lauffähig halten.
6. **Claim-Management / Über-Behauptung** — größte Reputations-Gefahr: „Entdeckungen" ausgeben, die keine sind. δ-Asymmetrie + Ledger + Rediscovery-Benchmarks sind die Gegenmaßnahme — und müssen *streng* bleiben, gerade wenn es verlockend ist, nachzugeben.
7. **Zeitplan vs. Realität** — die Wochen-Richtwerte in Abschnitt 5 sind aggressiv und setzen die `gate_c6`-Spec voraus. Realistisch zuerst die Spec, dann Phase 1.
8. **Scope vs. Ergebnis** — die Feature-Liste wächst (jetzt 7 radikale Features). Das ist für eine Vision in Ordnung, **aber:** der Wert entsteht aus dem Kern-Loop (Phase 1), nicht aus der Feature-Zahl. *Universe Simulator Bridge* und *Cosmic Insight Engine* sind verlockend zu bauen, bevor das Fundament steht — genau dieses Muster (Infrastruktur statt Ergebnis) hier bewusst vermeiden.

---

*Ende des Dokuments. Die Module mit `[DESIGN]`/`[HYPOTHESE]` sind Bauaufträge, keine erledigten Tatsachen — und genau diese Unterscheidung ist der Geist von GENESIS.*
