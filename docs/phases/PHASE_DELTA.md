# PHASE δ — Validierung vor dem Bauen (deterministische Geometrie-Soundness)

> **Zweck dieser Datei:** Operative Spezifikation der vierten Stufe, erste
> beweisbare Schicht. Aufbau wie `PHASE_GAMMA.md`. So detailliert, dass die
> Implementierung ohne Rückfragen erfolgt und jede Entscheidung gegen ein
> Akzeptanzkriterium prüfbar ist.
>
> **Warum diese Stufe jetzt:** γ liefert eine vollständige, belegte Bauanleitung.
> Bevor ein Mensch reale Zeit/Material investiert, soll das System die Lösung
> **validieren** — δ aus der Vision: *„Lösungen werden simuliert/validiert vor
> jedem realen Aufwand."* Aber GENESIS darf kein Physik-Urteil **erfinden**.
> Deshalb beweist δ — wie α das Anti-Halluzinations-Fundament zuerst und isoliert
> bewies — zuerst die **deterministisch beweisbare** Schicht der Validierung:
> **geometrische Soundness** des CSG-Modells. Keine FEM, keine Statik, keine
> Strömung — nur, was aus der Geometrie selbst mit Sicherheit folgt.

---

## 0. Die eine Einsicht (warum δ ehrlich bleibt)

Validierung klingt nach „simulieren". Simulation braucht Modelle, und Modelle
können falsch sein — ein erfundenes Festigkeitsurteil ist eine δ-Halluzination,
so gefährlich wie ein erfundener Fakt in α. Die Auflösung:

> **δ behauptet nur, was deterministisch aus der Geometrie folgt, und nutzt eine
> Schranke, die nie lügt: die achsenparallele Bounding-Box (AABB).**

Die zentrale, ehrlich-machende Asymmetrie (AABB ist eine *konservative* Schranke):

| Aussage | Gilt? | Konsequenz |
|---|---|---|
| Zwei AABBs sind **disjunkt** | ⟹ die Festkörper überlappen **beweisbar nicht** | δ darf eine tote/leere Operation **melden** (keine False Positives) |
| Zwei AABBs **überlappen** | ⟹ die Festkörper überlappen **vielleicht** | δ meldet **nichts** (kein Rateurteil) |

Daraus folgt die δ-Invariante, die die α→β→γ-Kette fortsetzt:

| Phase | Einheit | Invariante |
|---|---|---|
| α | Claim | kann nicht ohne Quelle existieren. |
| β | Approach | kann nicht ohne VERIFIED-Claim existieren. |
| γ | Wert/Schritt/Geometrie | kein Wert ohne Beleg, keine Rechnung ohne Nachrechnung, keine Referenz ins Nichts, keine Wahl ohne Deklaration, kein Schritt ohne Prüfung. |
| δ | **Geometrie-Operation** | **keine nachweislich tote oder leere Operation bleibt unbemerkt — und δ behauptet kein Urteil, das es nicht beweisen kann.** |

> **Folge (ehrlich, zentral):** Ein **bestandenes** δ heißt **nicht** „die Lösung
> ist physikalisch gültig/herstellbar/tragfähig". Es heißt: „kein
> **beweisbar** kaputter geometrischer Defekt." Ein **gescheitertes** δ heißt:
> „definitiv kaputt." Diese Asymmetrie ist der ganze Punkt — δ verkauft nie mehr
> als es beweist.

---

## 1. Was Phase δ leistet (Scope)

**Input:** Eine γ-`Specification` (validiert durch GATE γ) mit CSG-Geometrie.
**Output:** Ein `ValidationReport` (GateResult-artig): bestanden/gescheitert je
geometrischer Bedingung, plus die berechnete **Hüllbox** (Envelope) jeder
Komponente — eine nützliche, belegte Validierungs-Ausgabe für den Menschen
(„passt das in mein Druckbett / meinen Bauraum?").

**Geometrie-Konvention (festgelegt, konsistent mit build123d):** GENESIS-CSG-
Primitive sind am Ursprung **zentriert**; `translate` verschiebt das Zentrum.
- `box(size_x,size_y,size_z)`: AABB = ±size/2 je Achse.
- `cylinder(radius,height)`: Achse entlang Z; AABB = [±r, ±r, ±h/2].
- `sphere(radius)`: AABB = ±r je Achse.
- `translate(x,y,z) child`: AABB(child) um (x,y,z) verschoben.
- `union`: **Hüllbox** (min der Minima, max der Maxima) der Kinder.
- `difference(A,B,…)`: Subtraktion kann nur schrumpfen ⟹ sound = AABB(A).
- `intersection`: **Überlapp** (max der Minima, min der Maxima); auf einer Achse
  invertiert ⟹ **leer**.

**In Scope:**
- AABB-Algebra über den GeometryNode-Baum (`verification/geometry.py`).
- GATE δ: deterministische, LLM-freie Prüfung (s. §4).
- Envelope-Report je Komponente (Maße der Hüllbox).
- **Volumen-Eigenschaft** (`volume_of`, s. §3.1): exakt-wo-beweisbar, sonst sound
  obere Schranke — eine reale Materialmengen-Größe **vor** dem Bauen.
- Reproduzierbar, offline, ohne LLM-Token (wie α/β/γ).

**Explizit NICHT in Scope (spätere δ-Schichten / Live):**
- Festigkeit/Statik/FEM, Strömung/CFD, Thermik, Toleranz-/Passungs-Simulation.
- Exakte CSG-Volumen-/Masse-Berechnung (AABB ist eine Schranke, kein exaktes
  Volumen).
- Kollisions-/Interferenz-**Bestätigung** (δ beweist nur Nicht-Überlapp, nie
  Überlapp — s. §0).
- Material-/Kostenmodelle.

---

## 2. Datenfluss (Phase δ)

```
   γ-Specification (GATE γ bestanden)
            │  components[*].geometry + quantities
            ▼
   ┌─────────────────────────────┐
   │ verification/geometry.py     │  AABB je Knoten (sound bounds)
   │  aabb_of(node, quantities)   │
   └───────────┬─────────────────┘
               ▼
   ┌─────────────────────────────┐
   │ GATE δ  gate_delta(state)    │  §4-Bedingungen (deterministisch, LLM-frei)
   └───────────┬─────────────────┘
   bestanden ──┤── nicht bestanden
          ▼             ▼
   ValidationReport  benannte geometrische Defekte
   (Envelope +       (totes difference, leeres intersection,
    „keine bewiesenen degenerierte Geometrie) — nie ein
    Defekte")        erfundenes Physik-Urteil
```

δ berührt α/β/γ nicht; es liest die validierte Spezifikation und fügt nur die
Geometrie-Validierung hinzu.

---

## 3. AABB-Algebra (exakt, `verification/geometry.py`)

`Aabb` = `(min_x,min_y,min_z, max_x,max_y,max_z)` mit `min ≤ max` je Achse.
`aabb_of(node, quantities)` rechnet rekursiv nach §1-Konvention; nutzt die
Quantity-Werte (kein LLM). Fehlende/absente Param-Quantity ⟹ `GeometryError`
(laut, nie geraten). Eine leere `intersection` liefert eine als **leer**
markierte AABB (inverted), die das Gate als `EMPTY_INTERSECTION` meldet.

Zwei AABBs **überlappen** ⟺ sie überlappen auf **jeder** Achse
(`a.min ≤ b.max ∧ b.min ≤ a.max` je Achse). Das ist der einzige Geometrie-Test,
den δ braucht — und er ist exakt und sound.

---

## 3.1 Volumen als deterministische Eigenschaft (`volume_of`)

`volume_of(node, quantities) -> Volume(value, exact, note)`. `value` ist **immer
eine sound obere Schranke** der wahren Volumen (in der Längeneinheit hoch drei);
`exact=True` nur, wenn beweisbar exakt — sonst ehrliche Schranke + `note`. GENESIS
gibt nie eine geschätzte Volumen als exakt aus (dieselbe §0-Ehrlichkeit, auf eine
Eigenschaft angewandt).

- **Primitive (exakt):** box = x·y·z, cylinder = π·r²·h, sphere = 4/3·π·r³
  (Standardformeln). `translate` erhält das Volumen.
- **union:** exakt = Σ Teile, wenn die Kinder **paarweise disjunkt** sind
  (beweisbar via AABB); sonst ist Σ Teile eine sound obere Schranke (∪ ≤ Σ).
- **difference:** exakt = vol(A) − Σ vol(tool) **nur**, wenn A-Solid = seine AABB
  (eine Box), jedes Werkzeug in A **enthalten** und die Werkzeuge paarweise
  disjunkt sind; sonst ist vol(A) eine sound obere Schranke (Subtraktion
  schrumpft nur). *Schlüssel:* ein Box-Solid **ist** exakt seine AABB, also folgt
  Solid-Enthaltensein aus AABB-Enthaltensein — der häufige „Loch im Block" ist
  exakt.
- **intersection:** min(Teile) ist eine sound obere Schranke (∩ ≤ jedes Teil);
  Exaktheit wird nicht behauptet.

CLI: der δ-Abschnitt zeigt je Komponente `volume: <v> <unit>³ (exact)` oder
`volume: <= <v> (upper bound — <Grund>)`.

**Masse (`mass_of`, gebaut):** Trägt eine Komponente eine `material_density`
(quantity_id einer Dichte, GROUNDED oder DECISION), so ist `masse = volumen ×
dichte` deterministisch berechnet und **sound einheiten-konvertiert** via
`units.unit_scale` (Faktor zur SI-Basis; `g/cm³` → 1e3, `mm` → 1e-3), sodass
`mm³ × g/cm³` die korrekte Masse ergibt statt still falsch zu rechnen. Geprüft:
Dichte-Dimension = mass/length³, Geometrie-Längeneinheit eindeutig, alle Einheiten
bekannt — sonst `value=None` + Grund (nie eine geratene Zahl). Ausgabe in Gramm,
`exact` folgt der Volumen-Exaktheit. GATE γ löst `material_density` auf (C-8).
(Die Längeneinheit der Dichte muss zur Geometrie passen; eine Umrechnung wird als
DERIVED-Quantity deklariert — dimensions-geprüft.)

## 4. Das Verifikations-Gate (GATE δ)

Reine Funktion `gate_delta(state)` in `verification/gates.py`, testbar ohne LLM.
δ schwächt γ nicht ab; es liest nur die (bereits γ-validierte) Geometrie.

| # | Code | Bedingung |
|---|---|---|
| D-0 | `NO_SPECIFICATION` | Es existiert eine `Specification` (sonst nichts zu validieren). |
| D-1 | `DEGENERATE_GEOMETRY` | Keine Komponente hat eine degenerierte Hüllbox (Extent ≤ 0 auf einer Achse) — nichts „Baubares" mit Volumen null. |
| D-2 | `EMPTY_INTERSECTION` | Kein `intersection`-Knoten hat disjunkte Kinder-AABBs (Ergebnis wäre **beweisbar leer**). |
| D-3 | `DEAD_OPERATION` | Kein `difference`-Knoten hat ein Subtrahier-Kind, dessen AABB die AABB des Minuenden **nicht** schneidet (der Schnitt entfernt **beweisbar nichts** — z. B. ein Loch, das das Teil verfehlt). |
| D-4 | `EMPTY_GEOMETRY_TREE` | Eine fabrizierte Komponente (geometry ≠ None) liefert eine als leer markierte Gesamt-AABB. |

**Abstention/Leerlauf:** Eine Spezifikation ohne fabrizierte Geometrie (nur
zugekaufte Teile) passt δ trivial (nichts zu widerlegen) — ehrlich, kein
Sonderpfad.

**Bei Nicht-Bestehen:** δ ist ein **Validierungs-Gate**, kein Erzeuger. Es meldet
die Defekte; der Mensch (oder eine spätere γ-Re-Strukturierung) korrigiert die
Geometrie. δ erzeugt nie selbst Geometrie.

---

## 5. Akzeptanzkriterien Phase δ

| # | Kriterium | Messung | Zielwert |
|---|---|---|---|
| D1 | **Soundness (keine False Positives)** | δ meldet einen Defekt nur, wenn er aus disjunkten AABBs **beweisbar** folgt | 100 % |
| D2 | **Totes difference gefangen** | ein Loch/Schnitt, dessen Werkzeug den Körper verfehlt → `DEAD_OPERATION` | 100 % |
| D3 | **Leeres intersection gefangen** | nicht-berührende Teile geschnitten → `EMPTY_INTERSECTION` | 100 % |
| D4 | **Degenerierte Geometrie gefangen** | null/negative Hüllbox-Achse → `DEGENERATE_GEOMETRY` | 100 % |
| D5 | **Envelope korrekt** | berechnete Hüllbox = analytisch erwartete Maße (zentrierte Konvention) | exakt |
| D6 | **γ unberührt** | bestehende γ-Spezifikation validiert; keine Regression in α/β/γ | erfüllt |
| D7 | **Ehrliche Grenze** | δ behauptet **kein** Physik-/Tragfähigkeits-/Herstellbarkeitsurteil | dokumentiert + getestet |

> **D1 und D7 sind die wichtigsten** — sie sichern die GENESIS-Ehrlichkeit: δ
> beweist nur, was beweisbar ist, und verkauft nie mehr.

---

## 6. Test-Set (Klassen)

Deterministische Geometrie, kein LLM, kein Netz:

- **Klasse A — valide:** Wandhalterung (box ∖ zentrierter cylinder, Loch im Teil)
  → δ bestanden, Envelope = box-Maße.
- **Klasse B — totes Loch:** `difference(box, translate(weit_weg, cylinder))` —
  das Loch liegt außerhalb des Körpers → `DEAD_OPERATION`.
- **Klasse C — leeres intersection:** zwei disjunkt platzierte Boxen geschnitten →
  `EMPTY_INTERSECTION`.
- **Klasse D — degeneriert:** eine Box mit einer 0-Achse (über eine 0-Quantity) →
  `DEGENERATE_GEOMETRY`.
- **Klasse E — Envelope:** union zweier versetzter Boxen → Hüllbox = analytische
  Min/Max (D5).
- **Ehrlichkeits-Test:** überlappende, aber physikalisch fragwürdige Geometrie
  (dünne Wand) → δ **besteht** (kein Physik-Urteil; D7).

---

## 7. Was in Phase δ konkret gebaut wird (Reihenfolge, gate-first)

1. `verification/geometry.py` — `Aabb`, `aabb_of(node, quantities)`,
   `overlaps(a,b)`, `is_empty(aabb)`; `GeometryError` in `core/errors.py`.
2. `tests/test_geometry.py` — AABB je Primitiv/Operation/translate, overlap,
   Envelope-Mathematik (ohne Gate).
3. `verification/gates.py` — `gate_delta()` als reine Funktion (D-0..D-4).
4. `tests/test_gate_delta.py` — Gate-Tests **zuerst**, je Positiv-/Negativfall.
5. `tests/test_phase_delta_acceptance.py` — Klassen A–E + Ehrlichkeits-Test.
6. CLI: γ-Text-Ausgabe um einen Abschnitt „Geometric validation (δ)" +
   „Envelope" ergänzen (surfacing, kein neuer Pflicht-Lauf).
7. `docs/phases/PHASE_DELTA_RESULT.md` — ehrliches Ergebnis je Kriterium.

> **Reihenfolge wie α/β/γ:** AABB + Gate testbar OHNE LLM zuerst — δ ist
> beweisbar korrekt, bevor es irgendetwas behauptet.

---

## 8. Quellen + ehrliche Grenze

**Quellen (extern, am 2026-06-11 verifiziert):**
- Achsenparallele Bounding-Box (AABB), Hüllbox einer Vereinigung (min der Minima,
  max der Maxima), Überlapp-Region (max der Minima, min der Maxima), und der
  Achsen-Überlapp-Test (zwei AABBs überlappen nur, wenn sie auf **jeder** Achse
  überlappen) — Standard, *Minimum bounding box*
  (https://en.wikipedia.org/wiki/Minimum_bounding_box).
- CSG-Festkörper-Repräsentation: Requicha 1980 (s. `PHASE_GAMMA.md §10`).

**Ehrliche Grenze (nicht verhandelbar, wiederholt aus §0):** δ ist die
**deterministische Geometrie-Schicht** der Validierung. Es beweist Nicht-Überlapp
(tote/leere Operationen) und berechnet Hüllboxen exakt. Es trifft **kein** Urteil
über Festigkeit, Herstellbarkeit, Toleranzen, Material oder reale Funktion — das
sind spätere δ-Schichten mit echten Modellen (FEM/CFD/Toleranzanalyse), und sie
werden, wenn gebaut, denselben Beweis-Standard tragen: nur behaupten, was belegt
ist. Ein bestandenes δ ist eine **notwendige**, keine hinreichende Bedingung für
eine baubare Lösung.
