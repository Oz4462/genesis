# PHASE γ — Spezifikation (Idee → umsetzbare Anleitung, inkl. 3D)

> **Zweck dieser Datei:** Vollständige, operative Spezifikation der dritten Stufe.
> So detailliert, dass die Implementierung ohne Rückfragen erfolgen kann und jede
> Entscheidung gegen ein Akzeptanzkriterium prüfbar ist. Aufbau wie
> `PHASE_ALPHA.md` / `PHASE_BETA.md`.
>
> **Warum diese Stufe jetzt:** α hat bewiesen, dass kein Fakt ohne Quelle existieren
> kann. β hat bewiesen, dass kein Lösungsansatz ohne VERIFIED-Verankerung existieren
> kann. γ baut **direkt darauf**: Es nimmt eine Idee + einen verankerten Ansatz und
> liefert eine **vollständige, detaillierte, umsetzbare Spezifikation** — Bauteile,
> parametrische 3D-Geometrie, Stückliste, Schritt-für-Schritt-Anleitung — in der
> **jeder Wert belegt, jede Rechnung nachgerechnet, jede Wahl deklariert und jede
> Referenz auflösbar** ist. Der VISION-Anspruch: *„Eine Idee wird zu einer
> Spezifikation, die ein Mensch ohne Rückfrage umsetzt."*

---

## 0. Die eine Einsicht (warum γ ehrlich bleibt)

In α/β hatte Halluzination je **ein** Gesicht (erfundener Fakt, erfundener Ansatz).
In einer Spezifikation hat sie **fünf** — und jedes bekommt einen eigenen,
deterministischen Wächter:

| # | γ-Halluzination | Beispiel | Wächter (LLM-frei) |
|---|---|---|---|
| 1 | **Erfundener Wert** | „Zugfestigkeit 70 MPa" ohne Beleg | Wertzwang: GROUNDED-Wert braucht VERIFIED-Claim **und** muss numerisch wörtlich im Claim-Text stehen (`VALUE_NOT_IN_GROUNDING`) — das γ-Pendant zu `scholar`s Wörtlich-Zitat-Guard |
| 2 | **Rechen-Halluzination** | „12 kg × 2 = 25 kg" | Rechenzwang: DERIVED-Werte berechnet **Code**, nie das LLM; das Gate rechnet deterministisch nach (`BROKEN_DERIVATION`) |
| 3 | **Drift** | Schritt 7 nutzt „Halterung B", die nirgends definiert ist | Referenzzwang: jede Referenz (Geometrie→Quantity, Step→BOM, Constraint→Quantity, …) muss auflösen (`DANGLING_REFERENCE`) |
| 4 | **Versteckte Entscheidung** | „Material ist PLA" als Tatsache statt als Wahl | Entscheidungszwang: jede Wahl ist eine deklarierte `Decision` mit Begründung, nie ein Fakt (`UNDECLARED_DECISION`) |
| 5 | **Unvollständigkeit** | Schritt ohne Prüfkriterium; Eingabe, die nie erzeugt wird | Vollständigkeitszwang: Aktion+Check pro Schritt, topologische Baubarkeit, BOM-Deckung (`INCOMPLETE_STEP`, `UNBUILDABLE_ORDER`) |

Daraus folgt die zentrale Invariante, die die α/β-Kette exakt fortsetzt:

| Phase | Einheit | Invariante |
|---|---|---|
| α | **Claim** | kann nicht ohne **Quelle** existieren. |
| β | **Approach** | kann nicht ohne **VERIFIED-Claim**-Verankerung existieren. |
| γ | **Quantity / Step / Geometrie** | **Kein Wert ohne Verankerung. Keine Rechnung ohne Nachrechnung. Keine Referenz ins Nichts. Keine Wahl ohne Deklaration. Kein Schritt ohne Prüfung.** |

Eine Spezifikation behauptet selbst **keinen** neuen Fakt: Ihre gesamte faktische
Substanz lebt in referenzierten Ledger-Claims (Wertzwang) oder ist deterministisch
daraus berechnet (Rechenzwang) oder ist eine explizit deklarierte menschen-
ratifizierbare Entscheidung (Entscheidungszwang). Der neue Agent (`architect`)
ist — wie `conductor` und `synthesizer` — ein **Strukturierer, kein Faktenerzeuger**.

**Die wichtigste neue Disziplin (Wertzwang im Wortlaut):** Ein GROUNDED-Wert muss
in der Einheit der Quelle wörtlich belegbar sein. Steht in der Quelle „5 cm" und
die Spezifikation braucht „50 mm", dann ist 50 mm **kein** GROUNDED-Wert, sondern
ein DERIVED-Wert mit Formel `q_source * 10` — nachrechenbar. Einheiten-Umrechnung
wird damit von einer stillen Fehlerquelle zu einer geprüften Rechnung.

---

## 1. Was Phase γ leistet (Scope)

**Input:** Eine Idee als Text (z. B. „Eine Wandhalterung, die ein Regalbrett mit
der belegten Last trägt") — plus der von β gelieferte, verankerte Lösungsraum.
**Output:** Eine `Specification`: Komponenten mit **parametrischer 3D-Geometrie
(CSG)**, Größen (`Quantity`) mit Herkunft (GROUNDED/DERIVED/DECISION), Stückliste
(`BomItem`), nummerierte Schritte (`Step`) mit Prüfkriterium, numerisch geprüfte
`Constraint`s, ein Entscheidungsblatt (`Decision`) und ehrlich ausgewiesene Lücken.

**In Scope:**
- Intake Idee + verankerter Ansatz (β-Kette: γ baut auf `Approach`, nie freischwebend)
- Recherche/Verifikation über die **bestehende α-Pipeline** (scout → scholar → skeptic)
- Lösungsraum über den **bestehenden β-Schritt** (synthesizer)
- **Strukturierung** zu einer vollständigen Spezifikation (`architect`)
- **GATE γ**: deterministisches, LLM-freies Abschluss-Gate über alle fünf Zwänge
- Parametrische 3D-Geometrie als **CSG-Baum**, dessen Parameter ausschließlich
  `Quantity`-Referenzen sind (kein roher Zahlenwert im Modell)
- Reproduzierbarer Lauf (run_id, Checkpoint, Logs) — wie α/β

**Explizit NICHT in Scope (spätere Phasen / Live-Betrieb):**
- Export in ein konkretes CAD-Format (OpenSCAD/build123d-Adapter: Live-Schritt;
  die Geometrie-Datenstruktur ist dafür geschnitten, s. §10 Quellen)
- Physikalische Simulation/Validierung (Phase δ) — γ prüft strukturell + numerisch
  deklarierte Constraints, **nicht** Festigkeit/Statik
- Semantische „Ohne-Rückfrage"-Qualität realer LLM-Outputs (Live-Messung; γ beweist
  die **strukturelle** Vollständigkeit und die Garantien)
- Cross-Domain-Generalisierung (ε), Selbstlernen (ζ)

---

## 2. Datenfluss (Phase γ)

```
                    ┌────────────────────────────────────────────────┐
   Mensch ──Idee───▶│ conductor (Orchestrator, γ-Modus)              │
                    └───────┬────────────────────────────────────────┘
                            ▼
                    ╔════════════════════════════════════════════════╗
                    ║  α-PIPELINE (unverändert, bewiesen)            ║
                    ║   scout ─▶ scholar ─▶ LEDGER ─▶ skeptic        ║
                    ╚═══════┬════════════════════════════════════════╝
                            ▼
                    ┌───────────────┐   β-Schritt (unverändert, bewiesen)
                    │ synthesizer   │   verankerte Approaches
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐  strukturiert Claims + Approach zu
                    │ architect     │  Specification; LLM liefert NUR Struktur;
                    │ (Struktur)    │  CODE validiert Referenzen, berechnet
                    └───────┬───────┘  DERIVED-Werte, droppt Unverankertes
                            ▼
                    ┌───────────────┐
                    │  GATE γ       │  fünf Zwänge prüfen (s. §5)
                    └───────┬───────┘
              bestanden ────┤──── nicht bestanden
                       ▼              ▼
            Specification an     zurück an Pipeline (gezielt, begrenzt)
            Mensch (Anleitung    ODER ehrliche Abstention: leere Spec
            + Entscheidungsblatt + benannte Lücke — nie eine gedriftete
            + Quellen + Lücken)  oder teilweise erfundene Spezifikation
```

α- und β-Teil bleiben **byte-genau** die bewiesenen Pfade. γ fügt nur den
`architect` und `gate_gamma` hinzu — ohne eine bestehende Garantie zu berühren.

---

## 3. Das γ-Datenmodell (exakt)

Alle Typen in `src/gen/core/state.py`, Konstruktor-Guards in `core/errors.py`.
Ids sind identifier-sicher (`[A-Za-z_][A-Za-z0-9_]*`), damit sie in Formeln
referenzierbar sind.

### 3.1 `Quantity` — das Herz von γ

Eine benannte, typisierte Größe mit Einheit und **deklarierter Herkunft**:

| `origin` | Bedeutung | Pflichtfelder | Konstruktor-Guard |
|---|---|---|---|
| `GROUNDED` | wörtlich aus einer verifizierten Quelle | `grounding` (claim_ids, ≥1) | `UngroundedValueError` |
| `DERIVED` | deterministisch berechnet | `derivation` (Formel + Inputs) | `InvalidDerivationError` |
| `DECISION` | explizite Design-Wahl | `rationale` (nicht leer) | `UndeclaredDecisionError` |

Strikte Trennung: `grounding` nur bei GROUNDED, `derivation` nur bei DERIVED,
`rationale` nur bei DECISION — alles andere ist ein Guard-Fehler (laut, nicht still).
`value` ist numerisch (`float|int`); nicht-numerische Wahlen sind `Decision`s,
nicht-numerische Fakten bleiben Claims.

### 3.2 `Derivation` — nachrechenbare Formel

`formula` (arithmetischer Ausdruck über Input-Ids: `+ - * /`, unäres `-`,
Klammern, Zahlen) + `inputs` (quantity_ids). Evaluation durch den **Safe-Evaluator**
(`verification/derivation.py`): AST-basiert, keine dynamische Code-Ausführung,
alles außerhalb der Grammatik → `FormulaError`. Division durch null →
`FormulaError`. DERIVED-Ketten werden topologisch aufgelöst; Zyklen sind ein Fehler.

### 3.3 `GeometryNode` — parametrische 3D-Geometrie (CSG)

CSG (Constructive Solid Geometry) ist die etablierte, kanonische Repräsentation
für garantiert valide Festkörper (Requicha 1980, s. §10) und die Repräsentation
hinter Script-CAD wie OpenSCAD — exakt das richtige Ziel für eine **belegbare**
Geometrie, weil jeder Parameter eine nachvollziehbare Größe ist.

| `kind` | `params` (Pflicht, exakt) | `children` |
|---|---|---|
| `box` | `size_x, size_y, size_z` | 0 |
| `cylinder` | `radius, height` | 0 |
| `sphere` | `radius` | 0 |
| `union`, `difference`, `intersection` | — | ≥ 2 (Reihenfolge signifikant bei `difference`) |
| `translate` | `x, y, z` | genau 1 |

**Jeder Parameterwert ist eine `quantity_id`** — niemals eine rohe Zahl. Damit ist
jede Abmessung im 3D-Modell rückverfolgbar bis zu Quelle, Rechnung oder
deklarierter Entscheidung. Primitiv-Dimensionen müssen > 0 sein; `translate`
darf negative Offsets tragen. Param-Menge muss **exakt** stimmen (Tippfehler =
Drift = Fehler).

### 3.4 `Component`, `BomItem`, `Step`, `Constraint`, `Decision`

- **`Component`**: `id, name, geometry (GeometryNode|None), quantity_ids` —
  gefertigtes Teil mit Geometrie oder abstraktes/zugekauftes Teil ohne.
- **`BomItem`**: `id, name, role (PART|MATERIAL|TOOL), count ≥ 1,
  component_id|None, grounding (claim_ids, optional)` — die Stückliste; `PART`
  mit `component_id` = Eigenfertigung.
- **`Step`**: `id, index, action (nicht leer), uses (BomItem-Ids),
  inputs (Artefakt-Ids), outputs (neue Artefakt-Ids), check (nicht leer),
  quantity_refs (Quantity-Ids)` — die Anleitung. Artefakt-Namensraum: initial
  alle BomItem-Ids; jeder Schritt darf neue Artefakte erzeugen; doppelte
  Artefakt-Definition ist ein Fehler.
- **`Constraint`**: `id, kind (le|lt|ge|gt|eq), left, right (Quantity-Ids),
  reason` — numerisch geprüfte Verträglichkeit (z. B. Lochdurchmesser ≥
  Schraubendurchmesser). Einheiten müssen übereinstimmen.
- **`Decision`**: `id, title, choice, rationale (nicht leer),
  informed_by (claim_ids, optional)` — nicht-numerische Wahlen
  (z. B. Material, Fertigungsverfahren). Erscheint im Entscheidungsblatt.

### 3.5 `Specification`

`run_id, idea, approach_id, quantities, components, bom, steps, constraints,
decisions, gaps, claim_ids_used, produced_by, model`. Eine Spezifikation, die
Inhalt behauptet (Komponenten/Schritte), muss über `approach_id` in einem
verankerten `Approach` des Laufs hängen (β-Kette). `RunState` erhält
`specification: Specification | None`; der `architect` besitzt dieses Feld
exklusiv (Agent-Ownership wie bisher).

---

## 4. Der neue Agent in Phase γ

### 4.1 `architect` (Strukturierung der Spezifikation)

- **Aufgabe:** Aus Idee + verankertem `Approach` + VERIFIED-Claims eine
  vollständige `Specification` strukturieren: Größen mit Herkunft, Komponenten
  mit CSG-Geometrie, Stückliste, Schritte mit Prüfkriterien, Constraints,
  Entscheidungsblatt.
- **Halluzinations-Regel (wie `conductor`/`synthesizer`):** erzeugt **keine**
  Fakten. Jeder GROUNDED-Wert referenziert existierende VERIFIED-claim_ids und
  muss numerisch im Claim-Text stehen; sonst wird die Größe **gedroppt** (Log).
- **Rechen-Regel (neu, hart):** Für DERIVED-Größen liefert das LLM nur
  `formula` + `inputs`. **Der Wert wird vom Code berechnet** (Safe-Evaluator,
  topologische Reihenfolge). Ein vom LLM mitgelieferter Wert wird ignoriert und
  überschrieben — das LLM rechnet in GENESIS grundsätzlich nie selbst.
- **Abstention-Regel:** Existiert kein verankerter Ansatz, oder ist der
  strukturelle Vorschlag nach den Drop-/Validierungs-Schichten nicht vollständig
  konsistent (dangling Referenz, unvollständiger Schritt, unbaubare Reihenfolge,
  kaputte Geometrie, Constraint-Verletzung), dann emittiert der `architect`
  **keine Teil-Spezifikation**, sondern eine leere Spezifikation mit benannter
  Lücke. Lieber ehrliche Abstention als eine gedriftete Anleitung — eine halbe
  Bauanleitung ist gefährlicher als keine.
- **LLM-Rolle:** nur Strukturierung/Benennung/Formel-Vorschlag — Urteils-, keine
  Faktenleistung (wie `scout`-Queries, `synthesizer`-Cluster). Offline
  deterministisch über `ScriptedLLM` testbar.
- **Cross-Model:** Die faktische Substanz (Claims) ist bereits cross-model
  verifiziert (skeptic). Der `architect` verifiziert nicht selbst; er
  strukturiert Verifiziertes. Generator-Familie, wie `synthesizer`.
- **Input:** `RunState` (claims + approaches). **Output:** schreibt
  `state.specification` (eigenes Feld; mutiert keine fremden).

### 4.2 LLM-Protokoll (JSON, eine Antwort)

```json
{
  "approach_id": "<id aus dem Prompt>",
  "quantities": [
    {"id":"q_load","name":"verified shelf load","unit":"kg","origin":"grounded",
     "value":12,"grounding":["<claim_id>"]},
    {"id":"q_sf","name":"safety factor","unit":"1","origin":"decision",
     "value":2,"rationale":"konservativ; Alternativen 1.5/3 erwogen"},
    {"id":"q_design","name":"design load","unit":"kg","origin":"derived",
     "formula":"q_load * q_sf","inputs":["q_load","q_sf"]}
  ],
  "components": [{"id":"c_bracket","name":"bracket","quantity_ids":["..."],
                  "geometry":{"kind":"difference","children":[...]}}],
  "bom":   [{"id":"b_bracket","name":"bracket","role":"part","count":1,
             "component_id":"c_bracket"}],
  "steps": [{"id":"s1","index":1,"action":"...","uses":["b_..."],
             "inputs":["b_..."],"outputs":["a_..."],"check":"...",
             "quantity_refs":["q_..."]}],
  "constraints": [{"id":"k1","kind":"ge","left":"q_hole_d","right":"q_screw_d",
                   "reason":"Schraube muss durch das Loch passen"}],
  "decisions": [{"id":"d_mat","title":"Material","choice":"PLA, 3D-Druck",
                 "rationale":"...","informed_by":["<claim_id>"]}]
}
```

---

## 5. Das Verifikations-Gate (GATE γ)

Reine Funktion `gate_gamma(state)` in `verification/gates.py`, testbar ohne LLM.
γ **schwächt α/β nicht ab**: Jeder referenzierte Claim durchläuft weiterhin den
geteilten `claim_soundness_failures`-Helfer; der Anker-Approach muss im Lauf
existieren und verankert sein. Defense-in-depth: Das Gate vertraut dem
`architect` nicht — es prüft alles selbst nach.

### Gate-Bedingungen (alle müssen halten)

| # | Code | Bedingung | Zwang |
|---|---|---|---|
| C-0 | `NO_SPECIFICATION` | Es existiert eine `Specification`. | — |
| C-1 | `UNGROUNDED_VALUE` | Jede GROUNDED-Quantity hat ≥1 grounding-claim_id (Konstruktor-Guard, Gate backstoppt). | Wert |
| C-2 | `VALUE_UNKNOWN_CLAIM` | Jede referenzierte claim_id (Quantity.grounding, BomItem.grounding, Decision.informed_by) existiert im Ledger. | Wert |
| C-3 | `VALUE_NOT_VERIFIED` | Jeder Grounding-Claim einer GROUNDED-Quantity ist `VERIFIED` mit confidence ≥ τ. | Wert |
| C-4 | `VALUE_NOT_IN_GROUNDING` | Der numerische Wert jeder GROUNDED-Quantity steht wörtlich (normalisiert: Ganzzahl- oder Dezimalform) im Text ≥1 ihrer Grounding-Claims. | Wert |
| C-5 | *(geteilt)* | `UNSOURCED_CLAIM` / `REFUTED_AS_FACT` / `UNSUPPORTED_NOT_FLAGGED` / `LOW_CONFIDENCE` / `DEAD_CITATION` auf jedem referenzierten Claim (α-Soundness, geteilter Helfer). | Wert |
| C-6 | `BROKEN_DERIVATION` | Jede DERIVED-Quantity rechnet exakt nach (Safe-Evaluator, topologisch; rel. Toleranz `derivation_tolerance`); Formelfehler, unbekannte Inputs, Zyklen, Division durch null scheitern hier. | Rechnung |
| C-7 | `UNDECLARED_DECISION` | Jede DECISION-Quantity hat eine nicht-leere `rationale`; jede `Decision` hat nicht-leere `choice` + `rationale`. | Entscheidung |
| C-8 | `DANGLING_REFERENCE` | Jede Referenz löst auf: Component.quantity_ids, GeometryNode.params→Quantity, Step.uses→BomItem, Step.quantity_refs→Quantity, BomItem.component_id→Component, Constraint.left/right→Quantity. | Drift |
| C-9 | `INVALID_GEOMETRY` | Bekannter `kind`, exakte Param-Menge, korrekte Kinderzahl, Primitiv-Dimensionen > 0. | Drift |
| C-10 | `INCOMPLETE_STEP` | Jeder Schritt hat nicht-leere `action` und nicht-leeren `check`; Schritt-Indizes eindeutig; BOM-`count` ≥ 1. | Vollständigkeit |
| C-11 | `UNBUILDABLE_ORDER` | Jede Step-`input` ist zum Schrittzeitpunkt verfügbar (BomItem oder Output eines früheren Schritts); kein Artefakt doppelt definiert. | Vollständigkeit |
| C-12 | `UNIT_MISMATCH` | Jede Quantity trägt eine nicht-leere Einheit (`"1"` für dimensionslos); Constraints vergleichen nur gleiche Einheiten. | Maß |
| C-13 | `CONSTRAINT_VIOLATION` | Jede deklarierte Constraint hält numerisch (le/lt/ge/gt/eq; eq mit `derivation_tolerance`). | Maß |
| C-15 | `DIMENSION_MISMATCH` | Jede DERIVED-Quantity ist **dimensional homogen**: ihre Formel addiert/subtrahiert nur dimensionsgleiche Größen, und die aus den Input-Einheiten errechnete Dimension stimmt mit der deklarierten Einheit überein. Einheiten als abelsche Gruppe (`verification/units.py`); unabhängig vom Zahlen-Nachrechnen (C-6). Fängt die Mars-Climate-Orbiter-Klasse (kg + mm; Fläche als Länge deklariert). | Maß |
| C-14 | `SPEC_NOT_ANCHORED` | Behauptet die Spezifikation Inhalt (Komponenten ODER Schritte), muss `approach_id` auf einen existierenden, verankerten Approach des Laufs zeigen. | β-Kette |

### Abstention & Fallen (durch dieselbe Mechanik, kein Sonderpfad)

- **Abstention:** Kann nichts verankert werden, enthält die Spezifikation null
  Komponenten/Schritte + explizite Lücken. Das passiert das Gate (nichts
  Unbelegtes wird behauptet) — exakt das α/β-Muster.
- **Falle „erfundener Wert":** Wert ohne Claim → C-1/C-3; Wert ≠ Quellen-Wortlaut
  → C-4. Beides nie im Output.
- **Falle „falsche Rechnung":** Das LLM kann gar nicht rechnen (Code rechnet);
  ein dennoch kaputter Pfad scheitert an C-6.
- **Falle „Drift/Unvollständigkeit":** C-8 bis C-11 fangen strukturell, was eine
  Anleitung „mit Rückfragen" machen würde.

### Bei Nicht-Bestehen

Wie α/β: `conductor` entscheidet — gezielt nachrecherchieren/neu strukturieren
(begrenzte Runden, Default 3) **oder** ehrliche Abstention mit benannter Lücke.

---

## 6. Akzeptanzkriterien Phase γ (so wird „fertig" gemessen)

| # | Kriterium | Messung | Zielwert |
|---|---|---|---|
| G1 | **Kein erfundener Wert** | jeder GROUNDED-Wert ↔ VERIFIED-Claim + numerisch im Claim-Text | 100 % |
| G2 | **Keine Rechen-Halluzination** | jeder DERIVED-Wert deterministisch nachgerechnet; LLM-gelieferte Werte nachweislich ignoriert | 100 % |
| G3 | **Keine versteckte Entscheidung** | jede Wahl als DECISION/Decision mit Begründung im Entscheidungsblatt | 100 % |
| G4 | **Kein Drift** | null dangling references über die gesamte Spezifikation | 100 % |
| G5 | **Strukturell ohne Rückfrage umsetzbar** | jeder Schritt Aktion+Check; topologisch baubar; BOM gedeckt; Geometrie vollständig parametrisiert; Einheiten vollständig | 100 % |
| G6 | **Fallen werden abgefangen** | erfundener Wert / Referenz ins Nichts / unvollständiger Schritt → nie als Inhalt behauptet | 100 % der Fallen |
| G7 | **Abstention** | nichts Verankerbares → leere Spezifikation + ehrliche Lücke | 100 % |
| G8 | **α+β-Garantien erhalten** | geteilte Soundness auf jedem referenzierten Claim; Anker nur verankerte Approaches; alle bestehenden Tests unverändert grün | erfüllt |

> **G1, G2 und G6 sind die wichtigsten** — sie messen genau den γ-Anspruch:
> eine *detaillierte* Anleitung, in der trotzdem **kein einziger Wert erfunden,
> errechnet-falsch oder ins Nichts referenziert** ist.
>
> **Ehrliche Grenze, von Anfang an benannt:** G5 ist die **strukturelle**
> Approximation von „ohne Rückfrage umsetzbar". Ob die Aktionstexte realer LLMs
> semantisch gut genug sind, misst erst der Live-Lauf (wie bei α/β: Architektur-
> Garantie ≠ Modell-Qualität). γ behauptet die Garantie, nicht die Modellgüte.

---

## 7. Test-Set (Problemklassen)

Vier Klassen, deterministische „scripted world" (wie α §Methodik, β §6) —
geprüft werden **System-Garantien**, nicht LLM-Qualität:

- **Klasse A — baubar:** Idee mit verankertem Ansatz + verifizierten Wert-Claims
  (z. B. Regalwandhalterung; Last und Schraubendurchmesser als VERIFIED-Claims).
  Erwartet: vollständige Spezifikation, GATE γ bestanden, ≥1 Komponente mit
  CSG-Geometrie, jeder Wert GROUNDED (numerisch im Claim) / DERIVED
  (nachgerechnet) / DECISION (begründet), Schritte topologisch baubar.
- **Klasse B — Falle (erfundener Wert / falsche Rechnung):** Der gescriptete
  `architect`-Vorschlag enthält (a) einen GROUNDED-Wert, der NICHT im Claim-Text
  steht, und (b) eine DERIVED-Größe mit falsch „vorgerechnetem" LLM-Wert.
  Erwartet: (a) wird gedroppt und nie behauptet; (b) der Wert im Output ist der
  **code-berechnete**, nicht der LLM-Wert. Gate besteht nur ohne die Falle.
- **Klasse C — unbelegbar:** Keine verifizierbaren Claims (wie β-Klasse C).
  Erwartet: **Abstention** — leere Spezifikation, ehrliche Lücke, Gate bestanden.
- **Klasse D — Unvollständigkeits-Falle:** Vorschlag mit dangling Referenz,
  Schritt ohne `check` und Eingabe, die nie erzeugt wird. Erwartet: keine
  Teil-Spezifikation; Abstention mit benannten Defekten. Zusätzlich beweisen
  Gate-Unit-Tests, dass GATE γ jede dieser Konstruktionen **unabhängig**
  abfängt (Defense-in-depth: Gate vertraut dem architect nicht).

---

## 8. Konfiguration (Defaults)

`config.yaml` — Block `phase_gamma` (erbt α/β-Schwellen, ergänzt γ-Spezifika):
```yaml
phase_gamma:
  confidence_threshold: 0.7        # τ für VERIFIED-Grounding (wie α/β)
  max_refine_rounds: 3             # Anti-Endlosschleife (wie α/β)
  derivation_tolerance: 1.0e-9     # rel. Toleranz fürs Nachrechnen (C-6, eq in C-13)
  require_grounded_approach: true  # β-Kette: Spec nur auf verankertem Approach
  models:                          # wie α/β — Generator-Familie ≠ Verifier-Familie
    generator: "<modellfamilie A>" # scout, scholar, synthesizer, architect
    verifier:  "<modellfamilie B>" # skeptic (MUSS ≠ generator)
```

---

## 9. Was in Phase γ konkret gebaut wird (Reihenfolge)

1. `core/state.py` — `ValueOrigin`, `Derivation`, `Quantity`, `GeometryNode`,
   `Component`, `BomRole`, `BomItem`, `Step`, `Constraint`, `Decision`,
   `Specification`; `RunState.specification`. Konstruktor-Guards.
2. `core/errors.py` — `UngroundedValueError`, `InvalidDerivationError`,
   `UndeclaredDecisionError`, `FormulaError`.
3. `verification/derivation.py` — Safe-Evaluator (AST-basiert, keine dynamische
   Code-Ausführung), topologische Auflösung, geteilt von `architect` (rechnen)
   und GATE γ (nachrechnen).
4. `verification/gates.py` — `gate_gamma()` als reine, getestete Funktion;
   `claim_soundness_failures` unverändert geteilt (α/β-Verhalten unverändert).
5. `tests/test_gate_gamma.py` — Gate-Tests **zuerst** (C-0–C-14, je Positiv- und
   Negativtest), ohne LLM. `tests/test_derivation.py` für den Evaluator.
6. `agents/architect.py` (+ `docs/agents/architect.md`) — Strukturierer; Tests
   mit ScriptedLLM (positiv + negativ: erfundener Wert, kaputte Referenz,
   kein Ansatz → Abstention).
7. `conductor.run_specification` + `runner.run_specification` + Checkpoint +
   `config.py` (`PhaseGammaConfig`) + CLI `--mode spec` inkl. deterministischem
   Offline-Demo (`--demo --mode spec` druckt die komplette Anleitung).
8. `tests/test_phase_gamma_acceptance.py` — vier Klassen, echter
   Pipeline-Durchlauf je Klasse.
9. `docs/phases/PHASE_GAMMA_RESULT.md` — ehrliches Ergebnis je Kriterium.

> **Reihenfolge-Begründung (wie α/β):** Erst Datenmodell + Evaluator + Gate
> (testbar OHNE LLM), dann der Agent. So ist das γ-Skelett **beweisbar korrekt,
> bevor ein LLM-Token fließt** — dieselbe Gate-first-Disziplin.

---

## 10. Offene Detailentscheidungen + Quellen

**Erledigt (war zuvor offen):**
- **Dimensionsanalyse von Formeln (Einheiten-Algebra) — GEBAUT (C-15).**
  `verification/units.py` implementiert Dimensionen als abelsche Gruppe (sieben
  SI-Basisdimensionen + Prefix-Parsing + gängige derived Units; unbekannte
  Einheiten werden *opaque*, nie geraten). GATE γ C-15 prüft jede DERIVED-Formel
  auf dimensionale Homogenität (add/sub nur dimensionsgleich; */ kombiniert
  Exponenten) und vergleicht die errechnete Dimension mit der deklarierten
  Einheit. Der `architect` droppt dimensional inkonsistente Größen vorab. Fängt
  die Mars-Climate-Orbiter-Klasse. Quellen unten.

**Bewusst offen (nicht blockierend):**
- Konkreter CAD-Export (OpenSCAD-Text vs. build123d-Python) — hinter einem
  Adapter; die CSG-Struktur (§3.3) ist auf beide abbildbar. Live-Schritt.
- **Magnitude/Skalen-Korrektheit innerhalb einer Dimension.** C-15 fängt
  *Dimensions*-Fehler (kg + mm, Fläche-als-Länge), **nicht** falsche Skalenfaktoren
  derselben Dimension (cm→mm via `*100` statt `*10` bleibt dimensional valide).
  Das ist die bekannte, ehrliche Grenze der Dimensionsanalyse — Magnitude prüft
  das Zahlen-Nachrechnen (C-6) und der Wortlaut-Anker (C-4), nicht C-15.
- Semantische Wert-Claim-Bindung über C-4 hinaus (z. B. ein Live-`skeptic` für
  Wert-Extraktionen) — C-4 ist der deterministische Wortlaut-Anker, das
  Live-Pendant folgt mit echten Modellen.

**Quellen (extern, am 2026-06-11 verifiziert):**
- CSG als kanonische Festkörper-Repräsentation: A. A. G. Requicha,
  *Representations for Rigid Solids: Theory, Methods, and Systems*, ACM
  Computing Surveys 12(4), 1980, S. 437–464. DOI: 10.1145/356827.356833
  (https://dl.acm.org/doi/10.1145/356827.356833).
- Script-basiertes CSG-CAD als etablierte Praxis: OpenSCAD — „The Programmers
  Solid 3D CAD Modeller" (https://openscad.org/;
  https://github.com/openscad/openscad).
- Parametrisches B-rep-CAD in Python auf OCCT: build123d — GENESIS-intern
  verifizierter Claim („build123d is built on the Open Cascade (OCCT) kernel…",
  confidence 1.0, zwei unabhängige Quellen, cross-model; siehe
  `runs/live-smoke/checkpoint.json` und CLI-Demo).
- **Dimensionsanalyse (C-15) — Theoriegrundlage:** Dimensionale Homogenität
  („only commensurable quantities … may be compared, equated, added, or
  subtracted"; Dimensionen bilden eine abelsche Gruppe unter Multiplikation;
  sieben SI-Basisdimensionen L, M, T, I, Θ, N, J) — Standard-Dimensionsanalyse
  (https://en.wikipedia.org/wiki/Dimensional_analysis).
- **Einheiten-Typsysteme als statische Prüfung:** A. Kennedy, *Types for
  Units-of-Measure: Theory and Practice*, CEFP 2009, LNCS 6299, S. 268–305,
  Springer. DOI: 10.1007/978-3-642-17685-2_8
  (https://link.springer.com/chapter/10.1007/978-3-642-17685-2_8). Kernidee:
  Unifikation über die Gleichungstheorie abelscher Gruppen; „dimensional
  consistency provides a first check on the correctness of an equation."
- **Motivierender realer Fehlerfall:** Mars Climate Orbiter (NASA, 1999) —
  Verlust durch Einheiten-Mismatch (pound-force·s vs. newton·s, Faktor 4.45;
  Lockheed-Martin-Bodensoftware ↔ JPL-Trajektorie)
  (https://en.wikipedia.org/wiki/Mars_Climate_Orbiter).

**Interne Verweise:** `PHASE_ALPHA.md` (Methodik, Gate-first),
`PHASE_BETA.md` §0 (Ehrlichkeits-Auflösung der Ideation), `CLAUDE.md`
(Kernprinzipien — gewinnen bei jedem Konflikt).
