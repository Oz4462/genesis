# GENESIS INVENTOR — Architektur-Plan

> **Auftrag (Owner, 2026-06-19):** GENESIS soll *wirklich erfinden* — autonom, über alle
> Domänen, hochprofessionell. Nicht abspielen, nicht fabulieren: **kühn erfinden, hart erden.**
>
> **Entscheidungen:** (1) Erst dieser Plan, dann Bau. (2) General über alle Domänen.
> (3) Beide Einstiegspunkte: offene Themen-Erfindung *und* problem-getrieben. (4) Gehirn:
> Claude + Grok live (Cross-Model). Rückgrat bleibt das Anti-Halluzinations-Gate.
>
> Status: **PLAN — wartet auf Owner-Freigabe.** Keine Zeile Code, bis du freigibst.

---

## 1 · Das Prinzip in einem Satz

**Ein generatives Modell erfindet die Idee (das WAS); der deterministische GENESIS-Motor erdet,
prüft und bepreist sie (das WIE); eine Schleife mit Neuheits-Druck und Cross-Model-Kritik wirft
weg, was unwahr, unneu oder unbaubar ist — übrig bleibt das, was gleichzeitig neu UND verifiziert
ist.** Das ist der einzige Weg, der „erfinden" und „professionell" zugleich erfüllt: Der LLM liefert
die Sprünge, das Gate macht sie ehrlich.

Warum das der Hebel ist: Ein LLM allein erfindet *und* halluziniert in einem Atemzug — es kann nicht
unterscheiden, welche seiner Ideen real ist. GENESIS' Einzigartigkeit ist genau dieser Trenner. Erst
dadurch wird aus „eine KI fabuliert beeindruckend" ein **belastbares Erfindungs-System**.

---

## 2 · Das Kernproblem der Erfindung (sauber benannt)

Eine Erfindung muss drei Dinge gleichzeitig sein. Die meisten KI-„Ideengeneratoren" scheitern, weil
sie nur das erste liefern:

| Achse | Frage | Wer liefert sie in GENESIS |
|---|---|---|
| **Neuheit** | Gibt es das so noch nicht? Ist es nicht-naheliegend? | LLM erzeugt Breite → **gemessen** gegen echte Prior-Art (nicht behauptet) |
| **Wert** | Löst es ein echtes Bedürfnis / Ziel? | Aus dem Brief abgeleitete Fitness; Cross-Model-Bewertung |
| **Machbarkeit** | Geht es physikalisch/ökonomisch wirklich? | **Deterministischer Motor** (Physik-Gates, Kosten, DFM, Domänen-Verifier) |

Neuheit und Machbarkeit ziehen gegeneinander (das Kühnste ist am ehesten unmöglich). Genau diese
Spannung löst ein **Such-/Evolutions-Loop** mit getrennten, ehrlichen Druckkräften — kein Einzelschuss.

---

## 3 · Architektur-Überblick — der Erfindungs-Loop

```
            ┌──────────────────────────────────────────────────────────────────────┐
            │                      INVENTION BRIEF (geframt)                          │
   Eingabe →│  offen:  "Erfinde etwas im Feld X, das Y kann und es noch nicht gibt"  │
            │  Problem:"Löse P unter Randbedingungen R"                               │
            └───────────────┬──────────────────────────────────────────────────────┘
                            │  (Ziel, Constraints, Erfolgskriterien, Domäne)
                            ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❶ PRIOR-ART & FRONTIER (live)   → was existiert schon? wo ist die Kante?         │
   │     reuse: agents/scout+scholar + tools/* (arXiv, Patente, Web, Wikidata, +MCP)   │
   └───────────────┬─────────────────────────────────────────────────────────────────┘
                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❷ GENERATE (Breite, Cross-Model)  → Claude UND Grok schlagen je N kühne Konzepte │
   │     reuse: llm/claude_cli + grok_cli ; discovery/symbiosis (council-Muster)       │
   └───────────────┬─────────────────────────────────────────────────────────────────┘
                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❸ NOVELTY-/OBVIOUSNESS-GATE  → tötet Duplikate & bekannte Prior-Art (gemessen)   │
   └───────────────┬─────────────────────────────────────────────────────────────────┘
                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❹ GROUND (deterministisch)  → Konzept → Spec → δ-Physik/Kosten/DFM/Domänen-Gate  │
   │     reuse: agents/architect (γ) ; physics_validation ; cad/* ; bundle ; cost_model │
   └───────────────┬─────────────────────────────────────────────────────────────────┘
                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❺ SCORE (multi-objektiv)  → Neuheit × Wert × Machbarkeit × Kosten × Erdung       │
   │     → Pareto-Front, KEIN einzelner Score   reuse-Muster: inverse_design.py        │
   └───────────────┬─────────────────────────────────────────────────────────────────┘
                   ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❻ EVOLVE / REFINE  → Gate-Fehlergründe ZURÜCK an den LLM ("Moment > Stall ×2") →  │
   │     mutieren, rekombinieren, neu erden. Vielfalt halten (MAP-Elites-Archiv).      │
   │     reuse: discovery/tournament + campaign (MAP-Elites) + refinement.py           │
   └───────────────┬───────────────────────────────────────────────────  Schleife ↑   │
                   ▼  (Budget erschöpft / Konvergenz)
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  ❼ OUTPUT  → rangierte Pareto-Menge GEERDETER, NEUER Erfindungen, je mit:          │
   │     Quellen (Provenance) · Gate-Verdikte · ehrliche Lücken · Kosten · Artefakt     │
   │     (CAD/STL/BOM bzw. Code/Protokoll) · Neuheits-Beleg gegen Prior-Art            │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

Der Loop ist **domänen-agnostisch**. Was je Domäne wechselt, steckt in Plugins (§6).

---

## 4 · Der Loop im Detail (mit Datentypen)

Neue Kern-Typen (in `src/gen/inventor/`):

```python
@dataclass(frozen=True)
class InventionBrief:
    mode: Literal["open", "problem"]      # offene Themen-Erfindung | problem-getrieben
    goal: str                             # "ein Greifer, der zerbrechliche Objekte ohne Sensorik hält"
    domain: str                           # "mechatronics" | "software" | "chemistry" | ...
    constraints: tuple[Constraint, ...]   # harte Randbedingungen (Budget, Größe, Norm, ...)
    success_criteria: tuple[str, ...]     # woran Wert gemessen wird
    run_id: str; seed: int                # reproduzierbare Auswertung

@dataclass(frozen=True)
class Concept:                            # eine ROHE Erfindungs-Idee (vom LLM)
    title: str; principle: str           # der Kniff / Mechanismus
    key_claims: tuple[str, ...]           # prüfbare Behauptungen (gehen ins α-Gate)
    rough_params: dict[str, float]        # grobe Auslegung (geht in die δ-Erdung)
    source_model: str                     # claude / grok — für den Audit

@dataclass(frozen=True)
class GroundedInvention:                  # ein Konzept NACH Erdung
    concept: Concept
    spec: Specification                   # γ-Spec (architect)
    novelty: NoveltyVerdict               # gemessen gegen Prior-Art (§7)
    feasibility: GateReport               # δ-Physik/Domänen-Gate: pass/fail/gap + Margen
    cost: CostEstimate; artifact: BundlePath
    provenance: tuple[SourceRef, ...]     # ECHTE Quellen je Claim
    scores: ParetoScores; gaps: tuple[str, ...]
```

**❶ Prior-Art & Frontier.** Aus dem Brief werden Suchanfragen erzeugt; `scout`+`scholar` ziehen
**echte** Prior-Art über die Connectors (arXiv/Patente/Web/Wikidata; je nach Domäne dazu die
MCP-Connectors: PubMed/ChEMBL/ClinicalTrials für Bio, GitHub/Papers für Software). Ergebnis: eine
belegte Karte „das existiert schon" + „hier ist die offene Kante". Das ist die Referenz, gegen die
„neu" überhaupt erst messbar wird.

**❷ Generate (Cross-Model Breite).** Claude **und** Grok bekommen Brief + Frontier und schlagen je
N kühne `Concept`s vor — bewusst zwei Modellfamilien, damit kein blinder Fleck eines Modells die
Breite begrenzt. Das `council`-Muster (`discovery/symbiosis.py`) existiert bereits; es wird vom
Formel-Level auf das Konzept-Level gehoben.

**❸ Novelty-/Obviousness-Gate.** Jedes Konzept wird gegen die Prior-Art aus ❶ gemessen (§7). Bekanntes
oder Naheliegendes fällt hier — *bevor* teuer geerdet wird.

**❹ Ground (deterministisch).** Überlebende Konzepte werden vom `architect` (γ) in eine strukturierte
`Specification` gegossen und durch die **echten** Gates gefahren: δ-Physik-Validatoren (Auto-Select aus
measurand-Tags), Kosten, DFM, Druckbarkeit, Domänen-Verifier. **Hier stirbt halluzinierte
Machbarkeit.** Jeder Claim wird zudem via `skeptic` (Cross-Model) gegen seine Quelle geprüft.

**❺ Score (multi-objektiv).** Fünf Achsen → **Pareto-Front**, nie ein einzelner Score (das würde
Trade-offs verstecken — unprofessionell). Der Nutzer sieht die Front und wählt den Kompromiss. Muster
aus `inverse_design.build_pareto_front` wird wiederverwendet.

**❻ Evolve / Refine.** Der Kern, der aus „LLM-Schuss" eine *Erfindung* macht:
- **Gate-Feedback-Reparatur:** Der Fehlergrund des Gates wird strukturiert an den LLM zurückgegeben
  („Schultermoment 50 N·m > Stall·Getriebe 34 N·m → Getriebe oder Motor ändern") → der LLM mutiert
  das Konzept → neu erden. Geschlossener Regelkreis.
- **MAP-Elites-Archiv** (`discovery/campaign.py` existiert): hält das beste Konzept *je Nische*
  (z. B. Mechanismus-Typ × Größenklasse) → erzwingt Vielfalt, verhindert Kollaps auf eine Idee.
  Das ist die professionelle Antwort auf „erfinde VIELE Dinge, nicht eins".
- **Rekombination:** zwei Archiv-Elites werden vom LLM zu einem Hybrid verschmolzen → echte neue
  Kombinationen.
Schleife bis Budget/Konvergenz.

**❼ Output.** Eine rangierte Pareto-Menge geerdeter, neuer Erfindungen — jede mit Provenance,
Gate-Verdikten, ehrlichen Lücken, Kosten, baubarem Artefakt und Neuheits-Beleg.

---

## 5 · Die zwei Einstiegspunkte (beide, wie gewählt)

Beide nutzen *denselben* Loop; sie unterscheiden sich nur im Framing von ❶ und in der Fitness:

- **Offene Themen-Erfindung** (`gen invent --field "..."` / Web „Erfinde …"): Input ist ein Feld +
  Ziel-Eigenschaft. Frontier = der ganze Stand der Technik im Feld; Fitness belohnt *neue Funktion
  oder neuer Mechanismus*. Das ist der echte „Träumer" — und er träumt geerdet.
- **Problem-getrieben** (`gen solve --problem "..."` / Web „Löse …"): Input ist ein konkretes Problem
  + Randbedingungen. Frontier = bestehende Lösungen für dieses Problem; Fitness belohnt *bessere
  Erfüllung der Erfolgskriterien*. Näher am Ingenieurs-Copiloten, gleiche Maschine.

---

## 6 · General über alle Domänen — das Plugin-Modell

„General" professionell heißt **nicht** „ein generischer Brei für alles", sondern **eine
domänen-agnostische Schleife + austauschbare Domänen-Plugins**. Jedes Plugin liefert drei Dinge
hinter einer festen Schnittstelle (`inventor/domains/<name>.py`):

```python
class DomainPlugin(Protocol):
    name: str
    def prior_art_sources(self, brief) -> list[SearchBackend]:  # WO gesucht wird
    def verifiers(self, spec) -> list[Gate]:                    # WOMIT geerdet wird
    def emit_artifact(self, spec) -> BundlePath:                # WAS rauskommt
```

| Domäne | Verifier (Erdung) | Prior-Art | Artefakt | Reife heute |
|---|---|---|---|---|
| **Mechatronik/Robotik** | δ-Physik-Validatoren, FEM, DFM, Kosten | arXiv, Patente, Web | CAD/STL/BOM | **echt & stark** (Beachhead) |
| Energie/Material/Mechanik | Teilmenge der Physik-Gates | arXiv, Web, Wikidata | Spec/BOM | teils stark, Lücken |
| Software/Algorithmen | Tests + Property-Checks + (opt.) SMT-Beweise | GitHub, Papers | lauffähiges Repo | **neuer Gate-Typ** |
| Chemie/Bio | Stöchiometrie/Thermo + DB-Plausibilität | PubMed, ChEMBL, ClinicalTrials (MCP da!) | Protokoll | **neuer Gate-Typ** |

**Ehrliche Abstufung statt Fake-Sicherheit:** Eine Domäne mit tiefem Verifier liefert „erfunden +
hart geerdet". Eine ohne (noch) liefert „erfunden + LLM-plausibilisiert + **als ungegated
geflaggt**" — nie ein erfundenes Gütesiegel. So bleibt GENESIS überall ehrlich, auch wo der Motor
noch nicht tief ist. Mechatronik ist der erste, weil dort der Motor schon echt ist; weitere Plugins
kommen geordnet dazu.

---

## 7 · Neuheit rigoros gemacht (der professionelle Knackpunkt)

Die meisten „KI-Erfinder" *behaupten* Neuheit. GENESIS **misst** sie — das ist verteidigbar und der
Unterschied zwischen Spielzeug und Werkzeug:

1. **Gegen echte Prior-Art, nicht gegen die LLM-Fantasie.** Zu jedem Konzept werden reale Treffer
   geholt (Connectors). „Neu" = „neu gegenüber dem, was existiert".
2. **Drei-Stufen-Verdikt** (analog zur δ-Asymmetrie des Formel-Entdeckers):
   - gleiche Funktion + gleicher Mechanismus wie existierend → **nicht neu** (raus);
   - gleiche Funktion, **neuer Mechanismus** → neu;
   - **neue Funktion** → am neuesten.
3. **Nicht-Naheliegend, cross-model:** das *jeweils andere* Modell wird gefragt „ist das angesichts
   dieser Prior-Art naheliegend?". Sagen beide „naheliegend", wird es geflaggt.
4. **Beleg mitliefern:** Das Neuheits-Verdikt trägt die Prior-Art-Referenzen, gegen die es bewertet
   wurde — überprüfbar, nicht „glaub mir".

```python
@dataclass(frozen=True)
class NoveltyVerdict:
    level: Literal["nicht_neu", "neuer_mechanismus", "neue_funktion"]
    nearest_prior_art: tuple[SourceRef, ...]
    obvious_to_models: tuple[str, ...]   # welche Modelle es naheliegend fanden
    rationale: str
```

---

## 8 · Wiederverwendung vs. Neubau (konkret — wir starten nicht bei null)

**Wird wiederverwendet (existiert, echt):**
- `llm/claude_cli.py`, `grok_cli.py`, `factory.py` — das Cross-Model-Gehirn.
- `agents/scout`, `scholar`, `skeptic` + `tools/*` — Prior-Art-Recherche + Claim-Erdung (live).
- `agents/architect` (γ) — Konzept → strukturierte `Specification`.
- `physics_validation` + `physics_selection` + die ~27 Validatoren + FEM — die Machbarkeits-Erdung.
- `discovery/symbiosis` (council), `tournament`, `campaign` (MAP-Elites), `refinement` — die
  Evolutions-/Breite-Maschinerie. **Das ist der Keim des Loops — heute auf Formeln, wird auf Konzepte
  gehoben.**
- `cad/*`, `export/*`, `bundle`, `cad/cost_model` — die Artefakt-Kette.
- `inverse_design` — das Pareto-Front-Muster für ❺.
- `ledger`, die Gates, `verification/*` — Provenance + Anti-Halluzination.

**Wird neu gebaut (`src/gen/inventor/`):**
- `brief.py` — `InventionBrief`-Framing (beide Modi).
- `generate.py` — Konzept-Generierung (council aufs Konzept-Level gehoben).
- `novelty.py` — das gemessene Neuheits-Gate (§7). *Genuin neu, kein Vorbild im Code.*
- `score.py` — multi-objektive Pareto-Bewertung über die 5 Achsen.
- `loop.py` — der Erfindungs-Orchestrator (❶–❼, Budget, Checkpoint, Audit).
- `domains/` — das Plugin-Modell + `mechatronics.py` (erstes Plugin, wrappt den heutigen Motor).
- Entrypoints: `cli.py` `invent`/`solve` + Web-Routen, **live entsperrt**.

Grobschätzung: ~70 % der Bausteine existieren; der Neubau ist primär **die Verkabelung zum Loop +
das Neuheits-Gate + das Plugin-Interface**.

---

## 9 · Was „hochprofessionell" hier konkret heißt

- **Jede Erfindung ist belegt:** Provenance (echte Quellen) + Gate-Verdikte (was geprüft, was
  pass/fail/gap) + ehrliche Lücken + Kosten + baubares Artefakt. Keine nackte Behauptung.
- **Determinismus an der richtigen Stelle:** Die LLM-Erzeugung ist nicht-deterministisch (ehrlich so
  benannt) — aber **jede Bewertung, jedes Gate, jeder Neuheits-Check ist deterministisch, geseedet,
  geloggt**; die Auswertung eines gegebenen Konzepts ist reproduzierbar; voller Audit-Trail mit
  `run_id`.
- **Ingenieurs-Disziplin:** Tests zuerst für jedes Gate, die 4-Linsen-/Deep-Review-Routine, ruff/CI,
  Cross-Model-Drift-Check pro Baustein — die Standards, die das Projekt schon hat.
- **Echtes Produkt:** die Web-UI entsperrt, Idee rein → geerdete Erfindungen raus, für einen Menschen
  ohne CLI bedienbar.

---

## 10 · Der Entdeckungs-Modus — neue Gesetze finden (der Forschungs-Kern)

> Owner-Richtung 2026-06-19: GENESIS soll **echt forschen** — neue, potentielle Naturgesetze,
> neue mathematische/physikalische/geometrische/biologische Formeln; der Formel-Entdecker soll
> **neue empirische Gesetze aus Daten, Simulationen UND Prüfungen** finden. **Neue Physik UND
> Regression.** Live-Erfinden ist im KI+Daten-Zeitalter das Wichtigste überhaupt.

**Über das Verifizierbare hinaus liegt nicht „unmöglich" — dort liegt der geschlossene
Entdeckungs-Loop. Das ist die Forschungs-Magie, und sie ist baubar.** GENESIS bleibt nicht bei
Regression auf vom Nutzer gelieferte Daten stehen; es **erzeugt seine eigenen Daten** und entdeckt
damit Gesetze, die in keinem Trainingsdatensatz stehen:

```
   Hypothese (LLM/SR schlägt ein Gesetz/Mechanismus vor)
        │
        ▼
   Experiment / Simulation ENTWERFEN   ← experiment_designer.py, reality.py (δ⁺)
        │   (das diskriminierende Experiment, das zwei rivalisierende Gesetze trennt)
        ▼
   LAUFEN LASSEN  ← Simulatoren: PyBullet · Mehrkörper · FEM · Schaltungssim · MD ·
        │            ODER echte Messung (δ⁺/reality)  → erzeugt DATEN
        ▼
   FITTEN & FALSIFIZIEREN  ← discovery/engine (SR + δ-Asymmetrie + Out-of-Sample) +
        │                     active_resolution (der aktive Zug nach „unentschieden")
        ▼
   VERFEINERN → nächstes Experiment ───────────────────────────────── Schleife ↑
```

Das ist die **mechanisierte wissenschaftliche Methode** — autonom, in Maschinengeschwindigkeit.

**Drei Entdeckungs-Regime (was wirklich geht):**
- **Mathematik & Geometrie — entdecken UND BEWEISEN.** Hier kann GENESIS *zertifizieren*, nicht nur
  stützen: eine neue Identität/Formel wird per SymPy + Beweis-Kernel (`proof_kernels`,
  `identity_research`, `constraint_smt`) **bewiesen**. → echte neue, zertifizierte Sätze sind möglich.
- **Physik / empirisch / biologisch — Kandidaten-Gesetze aus Daten + Simulation + Test.** SR +
  δ-Asymmetrie + Out-of-Sample finden ein Gesetz, das *nicht* in den Trainingsdaten steckt (weil aus
  selbst-erzeugten Daten); GENESIS leitet die Konsequenzen ab und entwirft das Experiment, das es
  widerlegen würde. → echte Entdeckung; die Zertifizierung als Naturgesetz braucht die reale Welt.
- **Ingenieurwesen — neuartige machbare Konstruktionen, Mechanismen, Kombinationen,** hart geerdet
  (der Inventor-Loop §3).

**Vorhandene Bausteine zum Verdrahten (großteils assemblierbar, nicht von null):** `discovery/engine`
(SR; nimmt eine Sim-Funktion als Datenquelle, nicht nur statische Daten), `active_resolution`
(diskriminierende Messung), `surrogate`, `validation` (Out-of-Sample gegen p-hacking),
`first_principles` (Beweisbäume), `proof_kernels`, `reality`/δ⁺ (Falsifikations-Experiment + echte
Messung), `experiment_designer`, `simulation/*` (PyBullet/Mehrkörper), `fem*`, `electronics`
(Schaltungssim), `wissensbasis/bio_molecular` (MD).

---

**Belegter Stand (Tiefenrecherche 2026-06-19 → `FORSCHUNG_AUTONOMES_ERFINDEN_2026-06-19.md`):** Der
Stand der Technik **bestätigt GENESIS' Seele** — *jedes* vertrauenswürdige Entdeckungssystem
(FunSearch, AlphaEvolve, AlphaProof, Adam/Eve) schließt den Loop mit einem **externen, nicht-LLM
Verifizierer**; jedes, das sich selbst bewertet (Sakana-Auto-Reviewer, co-scientist-Elo), halluziniert.
Engine-als-Verifizierer ist also richtig. Konkrete, benannte Methoden, die den heutigen
Einzel-Potenzgesetz-Fitter auf Forscher-Niveau heben: **PySR** (Multi-Term-SR + Pareto/MDL),
**SINDy/WSINDy** (Differentialgleichungen aus Sim-Daten — der kategoriale Sprung), **Bayes-SR**
(Unsicherheit statt Scheinsicherheit), **SRBench-Hygiene** (Struktur-Recovery statt R², Dummy-Variablen
gegen Schein-Entdeckung), **Beweis-Kernel-Loop** (SymPy/SMT/Lean → zertifizierte Identitäten),
**T-Optimalität** (die rigorose Form von `active_resolution`). Voller Fahrplan P1–P4, Gap-Tabelle und
ehrliche Hype-Trennung (GNoME-„scant evidence", A-Lab-Korrektur „neu für die Plattform", „novelty
mirage", Ideation-Execution-Gap) im Recherche-Report.

## 10½ · Die ehrliche Linie: **Entdecken ≠ Zertifizieren** (Integrität, kein Deckel)

Das ist der einzige ehrliche Vorbehalt — und er ist *kein* Ambitions-Deckel, sondern das Fundament
der Glaubwürdigkeit: **GENESIS entdeckt kühn und labelt ehrlich.** Jedes neue Gesetz trägt seine
**Evidenz-Basis** (welche Daten / welche Simulation / welches Experiment) und seinen **Falsifikator**
(welches Experiment würde es kippen) — Status **„Kandidat"**, nie „bewiesene Wahrheit", solange die
reale Welt es nicht bestätigt hat. Ein bloßes LLM würde das neue Gesetz einfach *behaupten*; GENESIS
entdeckt es UND sagt ehrlich, wie sicher es ist und wie man es widerlegt. Genau das macht aus
„beeindruckendem Fabulieren" echte Forschung.

Die kleinen, klaren realen Grenzen (kein Ambitions-Deckel):
- Ein in Simulation X entdecktes Gesetz ist zunächst wahr *von X* — bis eine reale Messung es
  bestätigt (dafür δ⁺/`reality` + Sign-off). In der Mathematik entfällt das: dort wird bewiesen.
- Fundamentale Frontier-Physik (eine neue Kraft, eine GR-Korrektur) braucht reale Messdaten an
  Grenzen, die GENESIS vom Schreibtisch nicht selbst erheben kann — **aber GENESIS liefert den
  Kandidaten, seine quantitative Vorhersage und das entscheidende Experiment.** Das ist der ganze
  Weg bis an die letzte Tür.
- **Live-Entdeckung ist der Kern** und braucht Netz + Modelle (offline nur die Erdung). Im
  KI+Daten-Zeitalter ist genau dieser Live-Loop das Wichtigste — bestätigt (Owner).
- Die Erdung ist nur so gut wie der Domänen-Verifier; flach geerdetes wird ehrlich „leicht geerdet"
  geflaggt, nie als sicher verkauft. Ein bestandenes Gate ist notwendig, nicht hinreichend —
  bauen, messen, verantworten bleibt beim Menschen (Sign-off).

---

## 10¾ · Externe Modelle & Werkzeuge — der konkrete Bau-Stack (eingebaut, kommerziell)

> Owner-Entscheidung 2026-06-19: **alle relevanten offenen Modelle in GENESIS einbinden.** Voller
> Katalog mit ~80 Systemen + Lizenz-Check je Eintrag: `MODELL_KATALOG_EXTERN_2026-06-19.md`.

**Prinzip — anrufen vs. nachbauen:**
- **Foundation-Modelle** (Protein, Material, Wetter/Erde) werden **angerufen** — als Verifizierer/
  Orakel/Datenquelle hinter dem Domänen-Plugin-Interface (§6), NICHT nachgebaut (Millionen $ Training).
- **Agenten-/Methoden-Loops** (AlphaEvolve, Symbolic Regression, Beweiser, Bayes-Opt) werden
  **nachgebaut/eingebunden** (offener Code).
- **Nur kommerziell-permissive Lizenzen** (Apache/MIT/BSD) im Kern; Googles Nicht-Kommerziell-Modelle
  (AlphaFold 3, GraphCast-Gewichte, GNoME, AlphaGenome) werden durch offene Alternativen **ersetzt**.

**A · Der Erfindungs-/Entdeckungs-Loop (nachbauen / einbinden):**

| Loop-Stufe (§3/§10) | Werkzeug | Lizenz | Rolle in GENESIS |
|---|---|---|---|
| Erfindungs-Engine | **OpenEvolve** / **ShinkaEvolve** | Apache | AlphaEvolve-Muster: propose→evaluate→evolve; Claude/Grok = Generator, GENESIS-Engine = Evaluator |
| Formel-Entdeckung | **PySR** · **PhySO** (Einheiten) | Apache/MIT | Multi-Term-SR ersetzt Einzel-Potenzgesetz |
| Dynamik / DGL | **PySINDy** (+ weak-form) | MIT | Gesetze aus Sim-Trajektorien |
| Mathe-Zertifizierung | **Lean 4 + Mathlib** · **LeanDojo** · **Goedel-Prover-V2** | Apache/MIT | Kandidat → kernel-bewiesener Satz |
| Experiment-Wahl | **Ax / BoTorch** · **Atlas** | MIT | T-Optimalität/EIG-Upgrade von `active_resolution` |
| Prior-Art / Literatur | **STORM** · PatentsView / Google-Patents-Embeddings | MIT | echte Quellen + Neuheits-Messung |

**B · Domänen-Verifizierer (anrufen, als Orakel hinter §6-Plugins):**

| Domäne (Plugin) | Orakel-Modell(e) | Lizenz | Prüft / liefert |
|---|---|---|---|
| Bio / Protein | **Boltz-2** · Chai-1 · RFdiffusion · LigandMPNN · DiffDock | MIT/BSD/Apache | Struktur, Bindung, Design-Machbarkeit |
| Materialien / Chemie | **ORB** · MatterSim · CHGNet · **MatterGen** · Materials Project | Apache/MIT/BSD/CC-BY | Energie/Kraft/Stabilität, Generierung |
| Wetter / Klima / Erde | **MS Aurora** · ECMWF AIFS · Clay · Prithvi-EO | MIT/CC-BY/Apache | Vorhersage, Geo-Erdung |
| Mechatronik (M1) | **GENESIS-eigene δ-Physik** (schon echt) | — | Statik/Thermik/Flug/Kinematik … |
| Mathematik | Lean / Goedel (s. A) | Apache | Beweis |

**C · Lizenz-Disziplin (hart):**
- Pro Modell **Gewichts-/Daten-Lizenz separat** prüfen — *Code offen ≠ Gewichte kommerziell* (MACE, GraphCast, AlphaFold 3).
- Kern = Apache/MIT/BSD. GPL (SevenNet) nur intern. RAIL/FAIR (DeepSeek-Prover, Meta-OMat/UMA, Sakana **AI-Scientist**) nur nach Prüfung; FAIR-Lizenz schließt Länder aus (China/Russland/Belarus).
- Trainingsdaten-Lizenz der Wettermodelle (ERA5/Copernicus/MERRA-2) bei Output-Weitergabe beachten.
- **Jede Anbindung trägt im Ledger: Modell, Version, Lizenz, Aufruf-Provenance.**

**D · Architektur-Konsequenz:** Das Domänen-Plugin-Interface (§6) bekommt einen dritten Typ neben
`verifiers()` und `prior_art_sources()`: **`external_oracle()`** — ein angebundenes Modell (lokal
geladen oder via API/MCP), dessen Output als **gegateter Claim** ins Ledger geht, nie als nackte
Wahrheit. Das Orakel ist ein Verifizierer/Generator mit Provenance + Unsicherheit — so bleibt das
Anti-Halluzinations-Prinzip auch bei externen Modellen gewahrt (ein Orakel-Ergebnis ist Evidenz, kein
Freibrief). Das `external_oracle()` umfasst drei Quell-Typen: **Foundation-Modelle** (oben),
**Simulatoren** (E) und **Datenbanken** (F).

**E · Simulatoren-Orakel (anrufen — auch GPL als separater Prozess; voll: `WERKZEUGE_DATEN_SIMULATION_2026-06-19.md`):**
- Mechatronik/Mechanik: **MuJoCo · Drake · Kratos · Project Chrono** (ergänzen GENESIS' PyBullet); FEM **FEniCSx/SfePy**; CFD **SU2/PyFR**; EM **Meep**.
- Molekül/Material/Chemie: **OpenMM · LAMMPS** (MD) · **PySCF · xtb** (Quantenchemie) · **Cantera** (Reaktionskinetik) — alle hinter der **ASE**-Python-Klammer (LGPL) austauschbar.
- Elektronik **ngspice/Verilator** (ergänzt MNA-Sim) · Quantencomputer **Qiskit Aer/Cirq** · Systembiologie **Tellurium/COPASI/NEURON**.
- *GENESIS' eigene Simulatoren bleiben; externe Engines erweitern die Erdung pro Domäne.*

**F · Daten-Zugriff (Ground-Truth + Prior-Art — voll: `WERKZEUGE_DATEN_SIMULATION`):**
- **Schon via MCP erreichbar:** ChEMBL · PubMed · ClinicalTrials · bioRxiv · HuggingFace-Hub; plus GENESIS' eigene: Semantic Scholar · arXiv · Wikidata · CODATA · DLMF.
- **Leicht ergänzbar (freie APIs):** **OpenAlex** (250M Werke, CC0) · PubChem (119M) · RCSB PDB (CC0) · UniProt · AlphaFold-DB (214M) · Materials Project · OPTIMADE (NOMAD/OQMD) · Google Patents (BigQuery).
- **Milliarden-Skala:** ZINC-22 (54,9 Mrd. Moleküle) · GDB-17 (166 Mrd.) · OMat24 (110M DFT). Datensatz-Lizenz **separat** prüfen (CC0/CC-BY = sauber; NC-Records meiden).

**G · Dev-/Optimierungs-/Provenance-Werkzeuge:**
- Optimierung: **OR-Tools** (CP-SAT) · **pymoo** (Multi-Objektiv) · **Optuna** · BoTorch/Ax — alle Apache/MIT.
- Hypothesen-Reasoning: **PyKEEN** (KG-Embeddings) · txtai · RDFLib.
- CAD/Design: **CadQuery · build123d** (schon teils in GENESIS) · inverses Design **Modulus/DeepXDE** (PINNs).
- **⭐ AiiDA (MIT)** — provenance-getrackte automatisierte Simulations-Kampagnen; **Backbone-Kandidat** für den Entdeckungs-Loop, weil es Input→Output-Provenance querybar hält (deckungsgleich mit GENESIS' Ledger-Prinzip).

---

## 11 · Build-Plan in Phasen (jede mit Abnahme-Gate, kein Push ohne Owner)

| Phase | Inhalt | Abnahme-Gate (Definition of Done) |
|---|---|---|
| **M0 · Vorbereitung** | `claude`/`grok`-CLI-Verfügbarkeit verifizieren; Live-Pfad entsperren (kontrolliert); 3 korrupte Dateien reparieren (engine.py etc., siehe `REALITAETSCHECK`); CRLF normalisieren | beide CLIs antworten live (PONG); Suite wieder grün; sauberer Working Tree |
| **M1 · Erfindungs-Loop, vertikal (Mechatronik)** | `inventor/` Kern: brief→generate→ground→score, ein Durchlauf ohne Evolve; Mechatronik-Plugin wrappt den heutigen Motor; CLI `invent`/`solve` | Ein **frei eingegebenes** Feld/Problem erzeugt LIVE ≥1 geerdetes, neues Konzept mit Quellen+Gate+Artefakt — reproduzierbar im Gate; Tests grün |
| **M2 · Neuheit rigoros** | `novelty.py`: gemessen gegen echte Prior-Art + cross-model Obviousness; ins Gate vor der Erdung | bekannte Prior-Art wird nachweislich als „nicht_neu" gefiltert; Neuheits-Beleg liegt jedem Output bei (Negativtest grün) |
| **M3 · Evolve/Refine** | Gate-Feedback-Reparatur + MAP-Elites-Archiv + Rekombination; **Engine-Basis OpenEvolve/ShinkaEvolve (§10¾)**; Pareto-Front statt Einzel-Output | ein gescheitertes Konzept wird durch Gate-Feedback nachweislich repariert; Lauf liefert vielfältige Pareto-Menge, nicht eine Idee |
| **M3⁺ · Echte Formel-Entdeckung (Forschungs-Kern, §10, belegt)** | PySR (Multi-Term-SR + Pareto/MDL) ersetzt das Einzel-Potenzgesetz; SINDy/WSINDy-Pfad für DGLs aus **eigenen Simulatoren**; Bayes/Bootstrap-Unsicherheit; SRBench-Hygiene-Gate | GENESIS entdeckt aus Sim-Daten ein **Multi-Term-Gesetz UND eine Differentialgleichung**, mit Unsicherheitsband; Dummy-Variablen-Test grün (keine Schein-Entdeckung); kein best-of-N |
| **M3⁺⁺ · Zertifizieren & Diskriminieren** | Mathe-Loop propose→`mpmath`-Vorfilter→SymPy/SMT-Beweis (nur Kernel-geschlossen = „Satz"); `active_resolution` → echte T-Optimalität (innerer Rival-Refit, maximin-robust, Sim-zu-Real-Fidelity als Rauschboden) | eine **neue Identität wird kernel-bewiesen**; ein diskriminierendes Experiment trennt zwei Rivalen nachweislich — **auch nachdem der unterlegene Rival sich nachfittet** |
| **M4 · Domänen-Plugins** | `external_oracle()`-Anbindung (§10¾): Bio→**Boltz-2/Chai-1/RFdiffusion**, Materialien→**ORB/MatterSim/MatterGen**, Wetter→**Aurora/AIFS**; Software-Plugin (Tests/Property/SMT-Gate); ehrliche Reife-Flags | je Plugin: eine Erfindung end-to-end geerdet (über das externe Orakel) bzw. ehrlich „leicht geerdet" geflaggt; Orakel-Output gegated im Ledger; Plugin-Interface stabil |
| **M5 · Produkt** | Web-UI entsperrt + Erfinder-Flow (Idee→Pareto-Erfindungen→Artefakt-Download); Provenance/Gaps sichtbar | ein Laie erfindet über den Browser etwas Geerdetes, ohne CLI |
| **M6 · Pro-Härtung** | Deep-Review der neuen Module (Cross-Model), Eval-Harness für Erfindungs-Qualität, Doku/Relabel, CI | neue Module review-sauber; Erfindungs-Eval misst Neuheit/Erdung/Wert; Doku ehrlich |

Reihenfolge ist bewusst: **erst ein echter Erfindungs-Lauf in der starken Domäne (M1) — der ehrliche
Beweis, dass es wirklich erfindet** — dann Neuheit/Tiefe/Breite/Produkt. „Erst Plan" (deine Wahl) ist
dieses Dokument; M0 beginnt nach deiner Freigabe.

---

## 12 · Offene Entscheidungen für dich (blockieren M1 nicht)

1. **Reihenfolge der weiteren Domänen-Plugins** nach Mechatronik: Software zuerst (großer Markt,
   sauberer Gate-Typ) oder Bio/Chemie (MCP-Connectors liegen bereit)?
2. **Erfindungs-Budget pro Lauf** (Zeit/Modell-Calls) — bestimmt Tiefe vs. Kosten der Abo-CLIs.
3. **„Neu" Messlatte:** schon „neuer Mechanismus" als Erfindung akzeptieren, oder nur „neue Funktion"?
4. **Patent-Ambition:** Soll der Neuheits-Beleg perspektivisch patent-tauglich dokumentiert werden
   (strengere Prior-Art-Pflicht), oder reicht interne Neuheit?

---

## 13 · Wissens-Inventar — „Haben wir genug Daten zum Erfinden?" (geprüft 2026-06-19)

**Kern-Einsicht:** Es gibt drei Arten von „Daten zum Erfinden", und GENESIS steht bei jeder anders
da. Der Engpass ist **nicht** „zu wenig Formeln/Gesetze zum Erfinden" — das LLM trägt die Formeln der
Welt schon. Der Engpass ist die Zahl der **deterministischen Verifizierer**. Eine Formel in einer
Datenbank verifiziert nichts, bis sie als Gate (Einheiten + Annahmen + Check) verdrahtet ist.

| Art von Wissen | Wofür | Wo es in GENESIS sitzt | Stand |
|---|---|---|---|
| **① Erzeugen** (was könnte existieren) | Ideen vorschlagen | **LLM-Gewichte (Claude+Grok)** + Live-Recherche | **Überfluss** — praktisch die ganze veröffentlichte Wissenschaft |
| **② Erden** (ist es real) | Erfindung deterministisch prüfen | ~36 Closed-Form-Validatoren + FEM + CODATA | **endlich, mechatronik-lastig** — der echte Engpass |
| **③ Prior-Art** (gibt es das schon) | Neuheit messen | Live-Connectoren (arXiv, S2, Wikidata, Bio-MCPs) | da, aber netz-abhängig; **Patente fehlen** |

**Quantifiziertes Inventar (deterministische Erdung):**
- **~36 Prüfachsen** (`physics_selection.RECIPES`): Festigkeit/Struktur, Thermik, Ermüdung/Bruch,
  Modal, Flug/Aero, Akku/Leistungselektronik, Roboter-Kinematik/Dynamik/ZMP, Hydraulik,
  Compute/Inferenz, Datenbus, Krypto, 3D-Druck-DFM. Plus FEM 1D/3D/quadratisch.
- **~350 Fundamentalkonstanten** — komplette NIST-CODATA-2022-Tabelle (`out/codata/allascii_2022.txt`). Echt & vollständig.
- **Formel-Registry: fast leer** (`formulas/registry.py` = Skelett-Container) · **`mechanics_formulas.py`: 5 Formeln** · DLMF nur mit ~4 Anker-URLs verdrahtet.
- **Wissensbasis** (`wissensbasis/store.py`): ein Store mit einigen Seed-Funktionen (Elektronik-Komponenten, Subsysteme, Bio-molekular, Nano/Space) — Infrastruktur, **keine** umfassende Wissens-DB.
- **Live-Connectoren** (echt, HTTP): arXiv, Semantic Scholar, Wikipedia, Wikidata, DLMF, CODATA; dazu in dieser Umgebung MCP: PubMed, ChEMBL, ClinicalTrials, bioRxiv.

**Abdeckungs-Karte der Erdung:** stark in **Mechatronik/Hardware** (+ etwas Krypto); **dünn bis
nicht vorhanden** in Chemie, Biologie, Elektromagnetik/Optik, allgemeiner Strömung,
Software-Korrektheit, Wirtschaft.

**Implikationen für den Bau:**
- **M1 (Mechatronik) ist datenseitig voll versorgt** — die ~36 Achsen reichen zum echten Erden. Kein Daten-Sammeln nötig vor dem ersten Erfindungs-Lauf.
- **„Mehr Erdung" = Domänen-Plugins (M4)** — pro Domäne ein neuer Verifizierer-Satz, **kein** passiver Formel-Dump.
- **Zwei konkrete Ergänzungen:** (a) **Patent-Connector** für die Neuheitsprüfung (in M2 ziehen); (b) optional die Formel-Registry mit Ingenieurs-Standardformeln (Roark/Shigley) + tieferem DLMF füllen — **aber nur als gegatete Validatoren**, sonst wertlos.

---

## 14 · Laufendes Prüf-Log (die Untersuchung geht weiter)

> Dieses Dokument ist das **lebende Haupt-Dokument**. Hier sammeln wir alle Prüf-Ergebnisse.
> Owner-Hinweis 2026-06-19: „wir haben noch einiges mehr zu prüfen." Status je Punkt nachführen.

**Bereits geprüft (✓):**
- ✓ Dream/Ideas/Council-Modi = Replay hartcodierter, einst-LLM-erzeugter Inhalte (`REALITAETSCHECK_DREAM_2026-06-19.md`).
- ✓ LLM-Adapter (Claude/Grok/Ollama) echt; Agenten LLM-fähig; live α/β/γ in CLI verdrahtet, aber Web-UI hart gesperrt.
- ✓ Physik/CAD/Discovery = echte deterministische Berechnung (kein Stub); Discovery = dimensionale Regression, braucht Zahlen-Input.
- ✓ Quell-Connectoren = echte HTTP-Calls, netz-abhängig; Claims der Replay-Ideen tragen Fake-Quellen.
- ✓ Wissens-Inventar quantifiziert (§13): Erdung mechatronik-lastig, ~36 Achsen.
- ✓ **Tiefenrecherche SOTA autonomes Erfinden** (`FORSCHUNG_AUTONOMES_ERFINDEN_2026-06-19.md`, 5 belegte Digests): Kern-Architektur (Verifizierer-als-Wahrheit) **bestätigt**; konkreter P1–P4-Fahrplan + Gap-Tabelle; Hype ehrlich getrennt (GNoME/A-Lab walk-backs, „novelty mirage", Ideation-Execution-Gap). Discovery-Kern (§10) entsprechend re-fundiert.
- ✓ **Externer Modell-Katalog** (`MODELL_KATALOG_EXTERN_2026-06-19.md`, ~80 Systeme, 5 Teams): Download-/Lizenz-Status je System; für jedes Google-NC-Modell eine offene kommerzielle Alternative. **Owner-Entscheidung: alle relevanten offenen Modelle einbauen** → als §10¾ (Bau-Stack: anrufen vs. nachbauen, je Loop-Stufe + Domäne + Lizenz-Disziplin) in die Architektur eingetragen; Build-Plan M3/M4 darauf verdrahtet.
- ✓ **Simulatoren-, Daten- & Dev-Werkzeug-Katalog** (`WERKZEUGE_DATEN_SIMULATION_2026-06-19.md`, 4 Teams): offene Simulatoren je Domäne (MuJoCo/OpenMM/Cantera/ngspice/… via ASE-Klammer), große offene Datensätze + Zugriff (OpenAlex/PubChem/PDB/AlphaFold-DB/Materials Project; Milliarden-Skala ZINC-22/GDB-17/OMat24; mehrere schon via MCP erreichbar), Dev-Stack (OR-Tools/pymoo/Optuna/PyKEEN/CadQuery + **AiiDA** Provenance). In §10¾ E/F/G eingetragen. **`external_oracle()` = Foundation-Modell ∪ Simulator ∪ Datenbank.**

**M0-Bau-Abgleich (gemessen 2026-06-19, Bau-Session — Forschungs-Kern-zuerst-Bau gestartet):**
- ✓ **„3 korrupte Dateien" = FALSE.** AST-Parse über alle **233** `src/gen/**`-Dateien: 0 Fehler. `discovery/engine.py` u. a. kompilieren; der M0-Claim war stale. CRLF ok (Windows+autocrlf), keine Normalisierung nötig.
- ✓ **Live-CLI/Netz erreichbar (Bau-Bash):** `claude -p`→**PONG**; Ollama `/api/tags`→**200** (gemma4:12b u. a.); **Grok** auth-gated. **Netz offen** → freie APIs live-probebar: **OpenAlex (CC0)** liefert 138 513 Treffer für „symbolic regression" ✅ (der Prior-Art/Neuheits-Connector ist live baubar). arXiv/PatentsView-Probe leer (Format/Key — PatentsView braucht jetzt API-Key; in TC2 behandelt).
- ✓ **Deps offline da:** numpy 2.4.6 / scipy 1.17.1 / sympy 1.13.1 / z3 4.16.0 / mpmath 1.3.0 / pybullet / cadquery. **Fehlen (opt-in pip / extern):** pysindy, pysr, julia, Lean.
- ✓ **Web-Live-Lock** = gewollter `GENESIS_ALLOW_LIVE=1`-Flag (`web/app.py`), kein Bug. **safety_ladder.py** existiert, ist aber **nicht in einen Loop verdrahtet** (→ Phase S).
- → Bau-Reihenfolge (Owner): **Forschungs-Kern zuerst** (SINDy/Hygiene/Unsicherheit/Beweis/T-Opt), dann Erfindungs-Loop; externe Schicht (Lizenz-Ledger + freie-API-Connectoren + `external_oracle()` + Tool-/Sim-Seams) interface-first verwoben. Plan: `~/.claude/plans/steady-sleeping-pascal.md`.

**Noch zu prüfen (offen):**
- ☐ **Live-CLI-Verfügbarkeit:** Antworten `claude -p` und `grok -p` auf Ozans Rechner eingeloggt (PONG)? *(M0-Voraussetzung; Claude ✓ gemessen, Grok auth-gated)*
- ☐ **Validator-Tiefe:** Welche der ~36 Achsen sind wirklich gegen Anker verifiziert vs. nur vorhanden? (Deep-Review Schritt 7–9 lt. WORK_QUEUE offen.)
- ☐ **Connector-Robustheit live:** Rate-Limits, Ausfälle, Extraktionsqualität (`EXTRACTION_BOTTLENECK.md`).
- ☐ **measurand-Emission:** Setzt ein echtes Modell die `measurand`-Tags zuverlässig (entscheidet, ob δ-Auto-Select live greift)? — laut README ungetestet.
- ☐ **Novelty-Mechanik:** Gibt es schon Embedding/Ähnlichkeit? (Nein — neu in `novelty.py`.) Patent-Connector fehlt.
- ☐ **Safety-Gate fürs Erfinden:** Ein Allzweck-Erfinder braucht ein Missbrauchs-/Sicherheits-Gate (z. B. Waffen/Bio-Gefahr ablehnen). `grenzverschiebung/safety_ladder.py` prüfen + in den Loop verdrahten. **Pro-Pflicht.**
- ☐ **3 korrupte Dateien** (`discovery/engine.py` u. a., kompiliert nicht) — *(M0)*.
- ☐ **Determinismus/Repro** an den Gates bei live-LLM-Erzeugung sauber geloggt?
- ☐ **wissensbasis Seed-Inhalt:** Wie viel ist real geseedet vs. leer?
- ☐ **Entdeckungs-Bausteine live (Forschungs-Kern, §10 — höchste Priorität laut Owner):** Sind `experiment_designer`, `reality`/δ⁺, `active_resolution`, `first_principles`, `proof_kernels` und die Simulatoren (`pybullet`/`multibody`/`fem*`/`electronics`/`bio_molecular`) wirklich verdrahtet & lauffähig? Nimmt `discovery/engine` eine **Sim-Funktion als Datenquelle** (selbst-erzeugte Daten), nicht nur statische Zahlen? Trägt jeder entdeckte Kandidat Evidenz-Basis + Falsifikator?
- ☐ *(weitere Punkte hier eintragen, während wir prüfen)*

---

*Dies ist der Bauplan. Er nutzt ~70 % vorhandene, echte Bausteine und fügt die genuin neue Mitte
hinzu: den Erfindungs-Loop, das gemessene Neuheits-Gate und das Domänen-Plugin-Modell. Er hält
GENESIS' Versprechen — kühn erfinden, niemals lügen — und macht es zum ersten Mal zur Laufzeit wahr.*
