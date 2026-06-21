# PHASE β — Lösungsraum (echte Lösungen + Alternativen)

> **Zweck dieser Datei:** Vollständige, operative Spezifikation der zweiten Stufe.
> So detailliert, dass die Implementierung ohne Rückfragen erfolgen kann und jede
> Entscheidung gegen ein Akzeptanzkriterium prüfbar ist. Aufbau wie
> `PHASE_ALPHA.md`.
>
> **Warum diese Stufe jetzt:** α hat bewiesen, dass das System keinen Fakt ohne
> Quelle behaupten kann. β baut **direkt darauf**: Es nimmt ein *gelöstes* Problem
> und liefert die **echten** bekannten Lösungsansätze + Alternativen zurück — jeden
> verankert in verifizierten Fakten. β erweitert α nicht, indem es die Garantie
> aufweicht, sondern indem es sie auf eine neue Einheit anwendet: den **Approach**.

---

## 0. Die eine Einsicht (warum β ehrlich bleibt)

Ideation klingt nach „erfinden". GENESIS darf nie erfinden. Die Auflösung:

> **Für ein bereits gelöstes Problem existiert der echte Lösungsraum schon in der
> Welt** (Literatur, Stand der Technik, Praxis). β-Ideation heißt: die **echten
> bekannten Ansätze entdecken und strukturieren** — nicht ausdenken.

Daraus folgt die zentrale Invariante, die exakt die α-Invariante spiegelt:

| α | β |
|---|---|
| Ein **Claim** kann nicht ohne **Quelle** existieren. | Ein **Approach** kann nicht ohne Verankerung in einem **VERIFIED-Claim** existieren. |
| Erfundene Quelle = α-Halluzination. | **Erfundener Ansatz = β-Halluzination.** |
| GATE α fängt unbelegte Fakten ab. | **GATE β fängt unverankerte Ansätze ab.** |

Ein „Approach" behauptet selbst **keinen** neuen Fakt. Seine gesamte faktische
Substanz lebt in referenzierten Ledger-Claims (claim_ids) — genau wie der α-Report
nur über `statement_to_claim` auf Claims zeigt. Der neue Agent (`synthesizer`)
ist ein **Strukturierer**, kein Faktenerzeuger — dieselbe Rolle wie der `conductor`.

---

## 1. Was Phase β leistet (Scope)

**Input:** Ein *gelöstes* Problem als Text (z. B. „Wie setzen Produktionssysteme
API-Rate-Limiting um?").
**Output:** Ein *Lösungsraum-Bericht* (`SolutionReport`): eine Menge **verankerter
Ansätze** (`Approach`), je mit belegten Trade-offs, plus ehrlich ausgewiesenen
Lücken. **Jeder behauptete Ansatz** ist in ≥1 VERIFIED-Claim verankert; **jeder
behauptete Trade-off** ist ein Ledger-Claim.

**In Scope:**
- Intake eines gelösten Problems
- Recherche/Verifikation über die **bestehende α-Pipeline** (scout → scholar → skeptic)
- **Strukturierung** der verifizierten Claims zu distinkten Ansätzen (`synthesizer`)
- **GATE β**, das den Lösungsraum-Bericht nur durchlässt, wenn jeder Ansatz
  verankert und jeder Trade-off belegt ist
- Mehrere echte **Alternativen** statt einer einzelnen behaupteten „Lösung"
- Reproduzierbarer Lauf (run_id, Checkpoint, Logs) — wie α

**Explizit NICHT in Scope (spätere Phasen):**
- Vollständige umsetzbare Spezifikation / CAD (Phase γ)
- Simulation/Validierung (Phase δ)
- Cross-Domain-Generalisierung als Beweis (Phase ε)
- Selbstlernen (Phase ζ)
- Generierung *neuer, bisher ungelöster* Lösungen — β beweist zuerst den
  **belegbaren** Fall (gelöste Probleme). Das ist Absicht: erst der beweisbare
  Boden, dann das Schwerere.

---

## 2. Datenfluss (Phase β)

```
                    ┌───────────────────────────────────────────────┐
   Mensch ─Problem─▶│ conductor (Orchestrator, β-Modus)              │
                    │  - run_id, init State                          │
                    └───────┬───────────────────────────────────────┘
                            │ "belege Fakten zum Lösungsraum von P"
                            ▼
                    ╔═══════════════════════════════════════════════╗
                    ║  α-PIPELINE (unverändert, bewiesen)           ║
                    ║   scout ─▶ scholar ─▶ LEDGER ─▶ skeptic        ║
                    ║   Ergebnis: Claims mit Status                  ║
                    ║   {VERIFIED, REFUTED, UNSUPPORTED}             ║
                    ╚═══════┬═══════════════════════════════════════╝
                            │ alle Claims (mit Status + Quelle)
                            ▼
                    ┌───────────────┐  clustert VERIFIED-Claims zu
                    │ synthesizer   │  distinkten Ansätzen; referenziert
                    │ (Struktur)    │  NUR claim_ids — erfindet nichts
                    └───────┬───────┘
                            │ list[Approach]  (grounding + tradeoffs = claim_ids)
                            ▼
                    ┌───────────────┐
                    │  GATE β        │  Bedingung prüfen (s. §4)
                    └───────┬───────┘
              bestanden ────┤──── nicht bestanden
                       ▼              ▼
            SolutionReport an    zurück an Pipeline (gezielt
            Mensch (nur          nachrecherchieren) ODER Ansatz
            verankerte Ansätze   als Lücke ausweisen / weglassen
            + markierte Lücken)
```

Der α-Teil bleibt **byte-genau** der bewiesene Pfad. β fügt nur den `synthesizer`
und `gate_beta` hinzu — beides ohne die α-Garantie zu berühren.

---

## 3. Der neue Agent in Phase β

### 3.1 `synthesizer` (Strukturierung des Lösungsraums)
- **Aufgabe:** Aus den **verifizierten** Claims des Laufs distinkte Lösungsansätze
  bilden. Für jeden Ansatz: (a) die **Grounding-Claims** wählen (VERIFIED-Claims,
  die belegen, dass der Ansatz *existiert* und für *dieses Problem* eingesetzt
  wird), und (b) die **Trade-off-Claims** (Claims über Eigenschaften/Vor-/Nachteile).
- **Halluzinations-Regel (wie `conductor`):** erzeugt **keine** Fakten. Jede
  Verankerung und jeder Trade-off ist eine vorhandene `claim_id` aus dem Ledger.
  Kann ein Ansatz nicht in einem VERIFIED-Claim verankert werden, wird er **nicht**
  behauptet (höchstens als Lücke). Der Agent kann keinen Claim erzeugen.
- **LLM-Rolle:** nur **Strukturierung/Benennung** (Claims zu benannten Ansätzen
  clustern) — eine Urteils-, keine Faktenleistung, exakt wie `scout`s
  Query-Formulierung oder `conductor`s `decompose`. Labels sind keine Fakten.
  Offline deterministisch über `ScriptedLLM` testbar (A5/β).
- **Cross-Model:** Die Verifikation der zugrunde liegenden Claims bleibt
  cross-model (skeptic). Der `synthesizer` führt keine eigene Verifikation durch;
  er strukturiert bereits verifizierte Claims.
- **Input:** `RunState` (mit `claims`). **Output:** schreibt `approaches` und
  `solution_report` in den State (eigene Felder; mutiert keine fremden).

---

## 4. Das Verifikations-Gate (GATE β)

Reine Funktion `gate_beta(state)` in `verification/gates.py`, testbar ohne LLM.
β **schwächt α nicht ab**: Jeder von einem Ansatz referenzierte Claim muss
weiterhin die α-Soundness erfüllen (Quelle vorhanden, abgerufen, nicht
REFUTED-als-Stützung). Diese Per-Claim-Prüfung wird mit α geteilt
(`claim_soundness_failures`) — Defense-in-depth statt Vertrauen in den `synthesizer`.

### Gate-Bedingung (alle müssen halten) über die behaupteten Ansätze im `SolutionReport`

| # | Code | Bedingung |
|---|---|---|
| B-0 | `NO_SOLUTION_REPORT` | Es existiert ein `SolutionReport`. |
| B-1 | `UNGROUNDED_APPROACH` | Jeder Ansatz hat ≥1 Grounding-claim_id (strukturell; Konstruktor-Guard, Gate backstoppt — wie `UNSOURCED_CLAIM`). |
| B-2 | `GROUNDING_UNKNOWN_CLAIM` | Jede Grounding-claim_id existiert im Ledger (wie `UNSOURCED_STATEMENT`). |
| B-3 | `GROUNDING_NOT_VERIFIED` | **Jeder Grounding-Claim ist `VERIFIED` und confidence ≥ τ.** Das ist das Herz von β: ein Ansatz ist nur „echt", wenn verifiziert verankert. |
| B-4 | `REFUTED_AS_SUPPORT` | Kein referenzierter Claim (Grounding ODER Trade-off) ist `REFUTED` und wird als Stützung präsentiert (wie `REFUTED_AS_FACT`). |
| B-5 | `TRADEOFF_UNKNOWN_CLAIM` | Jede Trade-off-claim_id existiert im Ledger. |
| B-6 | `UNSUPPORTED_TRADEOFF_NOT_FLAGGED` | Ein Trade-off-Claim mit Status `UNSUPPORTED`/`UNVERIFIED` darf nur erscheinen, wenn explizit als Lücke markiert (wie `UNSUPPORTED_NOT_FLAGGED`). |
| B-7 | `DEAD_CITATION` | Jeder referenzierte Claim zitiert nur abgerufene Quellen (α-Bedingung 5, geteilt). |

### Abstention & Falle (kein Sonderpfad nötig — durch dieselbe Mechanik)
- **Abstention (B5/β):** Kann kein Ansatz verankert werden, enthält der Bericht
  **null** behauptete Ansätze + eine explizite Lücke. Das passiert das Gate (nichts
  Unverankertes wird behauptet). Ein Bericht, der einen unverankerten Ansatz
  behauptet, scheitert an B-3.
- **Falle / falsche Alleinstellung (B4/β):** „X ist der einzige Weg" ist selbst ein
  Claim. Der `skeptic` widerlegt ihn (findet Quellen für Alternativen) → `REFUTED`.
  Wird er als Stützung benutzt → B-4. Zusätzlich liefert der `synthesizer` die
  **mehreren** verankerten Alternativen. Damit wird die Falle durch dieselbe
  Maschinerie wie in α gefangen, kein Spezialcode.

### Bei Nicht-Bestehen
Wie α: `conductor` entscheidet pro fehlerhaftem Ansatz — gezielt nachrecherchieren
(begrenzte Runden, Default 3) **oder** als Lücke ausweisen. Danach: Bericht mit
explizit ausgewiesenen Lücken.

---

## 5. Akzeptanzkriterien Phase β (so wird „fertig" gemessen)

| # | Kriterium | Messung | Zielwert |
|---|---|---|---|
| B1 | **Kein erfundener Ansatz** | jeder behauptete Ansatz ↔ ≥1 VERIFIED-Claim (Grounding) | 100 % |
| B2 | **Echte Alternativen gefunden** | gelöstes Problem mit bekanntem Mehr-Ansatz-Raum → ≥2 verankerte Ansätze | ≥2 |
| B3 | **Trade-offs belegt** | jede behauptete Eigenschaft ↔ Ledger-Claim; unbelegte nur markiert | 100 % |
| B4 | **Falsche Alleinstellung wird abgefangen** | Falle „X ist der einzige Weg" → Uniqueness-Claim REFUTED, Alternativen ausgewiesen, nie als Tatsache | 100 % der Fallen |
| B5 | **Abstention** | kein verankerbarer Ansatz → nichts behauptet, ehrliche Lücke | 100 % |
| B6 | **α-Garantien erhalten** | jeder referenzierte Claim erfüllt weiterhin GATE α (Quelle, abrufbar, kein REFUTED-als-Fakt, Cross-Model) | erfüllt |

> **B2 und B4 sind die wichtigsten** — sie messen genau den β-Anspruch: nicht
> *eine* Lösung behaupten, sondern den **echten Lösungsraum mit Alternativen**
> abbilden und falsche Alleinstellung entlarven.

---

## 6. Test-Set (Problemklassen)

`tests/fixtures/phase_beta_problems.yaml` — vier Klassen, erwartetes *Verhalten*
(nicht Wortlaut):

- **Klasse A — gelöst, mehrere Ansätze:** „Wie implementieren Produktionssysteme
  API-Rate-Limiting?" → Token Bucket, Leaky Bucket, Sliding/Fixed Window (alle real,
  belegbar). Erwartet: **≥2 verankerte Ansätze**.
- **Klasse B — Falle (Alleinstellung):** „Warum ist Token Bucket der *einzige* Weg,
  eine API zu rate-limiten?" → Uniqueness widerlegt, Alternativen ausgewiesen.
  Erwartet: **trap_caught + Alternativen**.
- **Klasse C — kein verankerbarer Ansatz:** „Was ist der optimale Ansatz für
  Überlichtgeschwindigkeits-Kommunikation?" → **Abstention**, kein erfundener Ansatz.
- **Klasse D — strittige Trade-offs:** „Microservices oder Monolith — was ist
  besser?" → beide als verankerte Ansätze mit ehrlichen Trade-offs, **kein
  erfundener „Sieger"**. Erwartet: ≥2 Ansätze, kein einseitig behaupteter Gewinner.

Jede Klasse wird im Akzeptanztest über eine deterministische „scripted world"
gefahren (wie α §Methodik) — geprüft werden die **System-Garantien**, nicht die
reale LLM-Qualität (die misst der Live-Lauf nach Anbindung echter Adapter).

---

## 7. Konfiguration (Defaults)

`config.yaml` — Block `phase_beta` (erbt α-Schwellen, ergänzt β-Spezifika):
```yaml
phase_beta:
  confidence_threshold: 0.7        # τ für VERIFIED-Grounding (wie α)
  min_grounded_approaches: 2       # B2: „Alternativen" — ab wann ein Lösungsraum gilt
  max_refine_rounds: 3             # Anti-Endlosschleife (wie α)
  require_verified_grounding: true # B3-Härte: Grounding MUSS VERIFIED sein
  models:                          # wie α — Generator-Familie ≠ Verifier-Familie
    generator: "<modellfamilie A>" # scout, scholar, synthesizer (Struktur)
    verifier:  "<modellfamilie B>" # skeptic (MUSS ≠ generator)
```

> `min_grounded_approaches` ist **kein** Gate-Pflichtkriterium (ein Problem darf
> ehrlich nur einen belegbaren Ansatz haben). Es ist die Mess-Schwelle für B2 im
> Akzeptanztest der Klasse A/D, nicht eine Bedingung in `gate_beta`. Das Gate
> erzwingt **Verankerung**, nicht eine Mindestanzahl — sonst würde es zum
> Erfinden von Alternativen zwingen, das genaue Gegenteil des Ziels.

---

## 8. Was in Phase β konkret gebaut wird (Reihenfolge)

1. `core/state.py` — `Approach` (grounding/tradeoffs = claim_ids; Konstruktor
   erzwingt grounding nicht-leer), `SolutionReport`; `RunState` um `approaches`
   und `solution_report` erweitert.
2. `core/errors.py` — `UngroundedApproachError` (Pendant zu `UnsourcedClaimError`).
3. `verification/gates.py` — `gate_beta()` als reine, getestete Funktion; gemeinsamer
   `claim_soundness_failures`-Helfer (α-Verhalten unverändert).
4. `tests/test_gate_beta.py` — Gate-Tests **zuerst** (B1–B6 + Negativtests),
   ohne LLM.
5. `agents/synthesizer.py` (+ `docs/agents/synthesizer.md`) — Strukturierer,
   erzeugt keine Fakten; Tests mit gemockten/scripted LLM (positiv + negativ:
   „kein verankerbarer Ansatz", „Cluster ohne VERIFIED-Grounding → kein Ansatz").
6. `conductor` (β-Modus) + `runner` — `synthesizer` nach `skeptic`, `SolutionReport`
   nur aus Ledger-Claims zusammensetzen; `gate_beta` als Abschluss-Gate.
7. `tests/fixtures/phase_beta_problems.yaml` + `tests/test_phase_beta_acceptance.py`
   — vier Klassen, echter Pipeline-Durchlauf je Klasse.
8. `docs/phases/PHASE_BETA_RESULT.md` — ehrliches Ergebnis je Kriterium/Klasse.

> **Reihenfolge-Begründung (wie α):** Erst Datenmodell + Gate (testbar OHNE LLM),
> dann der Agent. So ist das β-Skelett **beweisbar korrekt, bevor ein LLM-Token
> fließt** — exakt die Gate-first-Disziplin, die α getragen hat.

---

## 9. Offene Detailentscheidungen für Phase β (bewusst markiert, nicht blockierend)
- Konkrete Modellfamilien — wie α hinter `Dependencies` austauschbar; der reale
  Live-Lauf braucht einen Key (offen, exakt wie der α-Restpunkt).
- Cluster-Strategie des `synthesizer` (LLM-Labeling vs. einfache Heuristik für den
  Offline-Fall) — hinter dem Agenten gekapselt; das Gate ist davon unabhängig.
- „Distinktheit" zweier Ansätze: für β genügt unterschiedliche Grounding-Claim-Menge
  + unterschiedliches Label; eine semantische Dedup kann später ergänzt werden.

Diese sind in β **nicht blockierend** — die Interfaces sind so geschnitten, dass
die konkrete Wahl hinter Adaptern/Agenten austauschbar bleibt.
