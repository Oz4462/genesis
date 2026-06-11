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

---

## 9. δ-Schicht 2 — deterministische Statik (Biegung + Kerbe + Verbindung), OHNE neuen Gate-Code

Die zweite δ-Schicht beantwortet die erste echte **Physik**-Frage des Capstones —
*„Hält der Halter die belegte Last?"* — ohne ein erfundenes Festigkeitsurteil und
**ohne eine einzige neue Gate-Zeile**. Der ganze Check lebt in der **bestehenden
γ-Maschinerie**; das ist der Beweis, dass GENESIS' Anti-Halluzinations-Fundament
schon trägt, was nach „Simulation" aussieht.

**Vier deterministische Checks (jeder belegt oder nachgerechnet):**

| Element der Rechnung | Wie es in GENESIS lebt | Quelle | Wächter |
|---|---|---|---|
| `g` = 9.80665 m/s² | **GROUNDED** (Zahl wörtlich aus `c_gravity`) | 3. CGPM 1901 | C-1..C-4 |
| Bemessungslast `F = (m·SF)·g` | **DERIVED** über die schon deklarierte Sicherheit `SF=2` (`q_design`) | — | C-6 |
| `σ_nom = 6·F·L/(b·h²)` | **DERIVED** (`h²`=`h*h`, kein Potenz-Op) | Euler-Bernoulli, `I=b·h³/12` | C-6 |
| Kerbfaktor `Kt = 3` (Bohrung) | **GROUNDED** (wörtlich aus `c_kirsch`) | Kirsch 1898 | C-1..C-4 |
| `σ_peak = Kt·σ_nom` | **DERIVED**, bleibt Druck (Kt dimensionslos) | — | C-6/C-15 |
| in-plane-Festigkeit `σ_zul` = 50 MPa | **GROUNDED** (`c_pla`) + Druckorientierungs-**Entscheidung** | FDM-Anisotropie-Literatur | C-1..C-4 |
| Schraubenschub-Kapazität `αv·f_ub·A_s` | **DERIVED** aus 3 GROUNDED-Werten (αv=0.6, f_ub=800 MPa, A_s=8.78 mm²) | EN 1993-1-8, ISO 898-1 | C-6/C-15 |
| Schraubenschub-Bedarf `F/n` | **DERIVED** | — | C-6 |
| Urteile `σ_peak ≤ σ_zul`, `F/n ≤ Kapazität` | numerische **Constraints** | — | **C-13** |

Kein neues Gate, keine neue Halluzinationsfläche: die fünf γ-Wächter erzwingen die
Statik schon. Ein **erfundener** Festigkeits-/Kerb-/Schraubenwert scheitert an C-4
(`VALUE_NOT_IN_GROUNDING`), eine **dimensional falsche** Formel (kg+mm, oder
MPa·mm² ≠ N) an C-15, eine **Überlast** an C-13 (`CONSTRAINT_VIOLATION`). Alles
offline, kein LLM. Reine Formel-Strings in `structural.py` (eine Quelle für Demo
**und** Test — kein Drift), getestet in `tests/test_structural.py`.

**Der Check hatte Zähne — der Capstone wurde dadurch ehrlich umkonstruiert.** Mit
der Bemessungslast (24 kg) und dem Kerbfaktor Kt=3 ergab der ursprüngliche 6-mm-
Halter `σ_peak ≈ 88 MPa > 50 MPa` → **FAIL**. Das ist die wahre Antwort: ein
flacher 6-mm-PLA-Halter mit Bohrung trägt 12 kg (bemessen 24 kg) **nicht**
sicher. Die Lösung ist keine Zahlenkosmetik, sondern eine echte Konstruktions-
korrektur: Querschnittstiefe `h` 6 → 12 mm → `σ_peak ≈ 22 MPa` (56 % Reserve),
Schraubenschub 118 N vs 4214 N (36×). Genau dafür ist δ da — **vor** dem realen
Aufwand die Untauglichkeit fangen.

**Quellen (extern, am 2026-06-11 verifiziert):**
- Biegespannung `σ = M·c/I`, `M=F·L`, Rechteck `I=b·h³/12`, `c=h/2` ⟹
  `σ=6·F·L/(b·h²)` — Euler-Bernoulli, *Bending*
  (https://en.wikipedia.org/wiki/Bending).
- Kerbformzahl `Kt = 3` für eine Kreisbohrung in einer Platte unter Zug (exakt,
  größen- und materialunabhängig) — Kirsch (1898); Peterson's Stress Concentration
  Factors; fracturemechanics.org/hole.html. Hier als **konservative** Schranke
  benutzt (Biege-/Endbreiten-Wert ≤ 3).
- Schraubenschub `F_v = αv·f_ub·A_s`, `αv=0.6` für Klasse 8.8 — EN 1993-1-8;
  `f_ub=800 MPa` (Klasse 8.8) und `A_s=8.78 mm²` (M4, Steigung 0.70) — ISO 898-1.
- FDM-PLA-Anisotropie: in-plane (on-edge) ~47–55 MPa, Interlayer 30–50 % schwächer
  → Druckorientierungs-Entscheidung kontrolliert die geladene Richtung.
- Normfallbeschleunigung `g = 9,80665 m/s²` — 3. CGPM (1901).

**Ehrliche Grenze (δ-Asymmetrie, jetzt eng gefasst).** Ein **bestandener** Check
ist **notwendig, nicht hinreichend** — aber die Residuen sind keine Pauschal-
Disclaimer mehr, sondern **präzise** als Gaps benannt und je an eine deklarierte
Entscheidung oder eine wirklich externe Größe gebunden:
1. **Schrauben-Auszug aus der Wand** — hängt vom Wand-/Dübel-Substrat ab (Gipskarton
   vs Beton vs Holz), das die Spec nicht festlegt; nur der bracket-seitige
   Schraubenschub wird geprüft.
2. **Exaktes FEM-Feld** — Kt=3 ist die konservative Kirsch-Schranke; der genaue
   Biege-/Endbreiten-Peak (≤3) braucht FEM oder Peterson-Tabellen.
3. **Ermüdung + Stoß/Dynamik** — durch die deklarierte statische Innen-Last-
   Entscheidung außerhalb des Geltungsbereichs; nur die statische Bemessungslast
   (SF 2) wird geprüft.
4. **Druckprozess-Streuung** — die 50-MPa-in-plane-Festigkeit setzt einen guten
   Druck (hohes Infill, korrekte Temperatur) in der deklarierten on-edge-
   Orientierung voraus; ein schlechter/falsch orientierter Druck ist schwächer.

Ein **gescheiterter** Check heißt weiterhin: schon der modellierte Fall überlastet
das Teil — **definitiv zu schwach**. Echte FEM/Ermüdung bleiben spätere δ-Schichten
hinter Adaptern, unter demselben Beweis-Standard.

---

## 10. δ-Toleranz — deterministischer Worst-Case-Fit-Stack-up, OHNE neuen Gate-Code

Ein realer Sitz ist nicht seine Nennmaße. Der Capstone-Fit „Bohrung 4,5 ≥ Schraube
4,0" sieht nominal sauber aus — doch sobald jedes Maß eine **Fertigungstoleranz**
trägt, kann er klemmen. Die Toleranz-Schicht beantwortet die deterministische
Hälfte: **im schlechtesten Extrem (größte Schraube, kleinste Bohrung) — geht es
noch zusammen?** Wieder komplett in der bestehenden γ-Maschinerie:

| Element | Wie es in GENESIS lebt | Quelle | Wächter |
|---|---|---|---|
| Allgemeintoleranz `±t` je Maß | **GROUNDED** (Zahl wörtlich aus `c_iso2768`) | ISO 2768-1 m | C-1..C-4 |
| Worst-Case-Mindestspiel `(D−t_D)−(d+t_d)` | **DERIVED** (Code rechnet, Gate rechnet nach) | Worst-Case-Stack-up | C-6/C-15 |
| Urteil `Mindestspiel ≥ 0` | numerischer **Constraint** | — | **C-13** |

**Worst-Case vs. statistisch:** GENESIS implementiert die **Worst-Case**-Methode
(Summe der Toleranzen am Extrem ⟹ 100 % Fügbarkeit) — die, die mit Sicherheit
folgt und nie eine Wahrscheinlichkeit behauptet, die sie nicht beweisen kann
(dieselbe Ehrlichkeits-Asymmetrie wie die Geometrie-Schicht). Monte-Carlo (Yield-
Vorhersage) bleibt eine spätere Schicht.

**Der Check hat Zähne:** Bohrung 4,1 ±0,1 über Schraube 4,0 ±0,1 ist nominal in
Ordnung (4,1 ≥ 4,0), aber Worst-Case-Spiel = (4,1−0,1)−(4,0+0,1) = **−0,1 mm < 0**
→ `CONSTRAINT_VIOLATION`. Der Capstone (4,5/4,0) hat +0,3 mm Spiel → fügbar.

**Ehrliche Tabellen-Grenze:** Es ist **nur der verifizierte Teil** der ISO-2768-1-m-
Tabelle codiert (0,5–120 mm). Außerhalb **wirft** `iso2768_medium_linear_tolerance`
(`ToleranceError`) statt einen ungeprüften Normwert zu raten — ein geratener
Toleranzwert wäre eine erfundene Ingenieur-Tatsache. Modul `tolerance.py` (eine
Quelle für Demo + Test), getestet in `tests/test_tolerance.py`.

**Quelle (extern, am 2026-06-11 verifiziert):** ISO 2768-1 Allgemeintoleranzen für
Längenmaße, Klasse m (medium): 0,5–3 → ±0,1; >3–6 → ±0,1; >6–30 → ±0,2; >30–120 →
±0,3 (amesweb.info ISO-2768-Linear-Tabelle; Xometry ISO 2768/286). Stack-up-
Methodik: Standard-Toleranzanalyse (Worst-Case vs. Monte-Carlo).

---

## 11. δ-DFM — deterministische Herstellbarkeits-Regeln, OHNE neuen Gate-Code

Eine Spec kann Geometrie **und** Statik **und** Toleranz bestehen und trotzdem
**un-druckbar** sein: eine Wand dünner als die Düse legen kann, ein Loch zu klein
zum Überleben. Reale DFM-Tools fahren Dutzende solcher deterministischen
Geometrie-Regeln. GENESIS fügt die hinzu, die es aus den vorhandenen Größen
**beweisen** kann — wieder ganz in der γ-Maschinerie:

| Regel | Wie es in GENESIS lebt | Quelle | Wächter |
|---|---|---|---|
| Mindestwand `2 · Düse` | **DERIVED** aus GROUNDED Düse (0,4 mm) + Perimeter-Zahl (2) | FDM 2 Perimeter | C-6/C-15 |
| `Querschnitt ≥ Mindestwand` | numerischer **Constraint** | — | **C-13** |
| Mindest-Lochdurchmesser 2,0 mm | **GROUNDED** | FDM horizontales Loch | C-1..C-4 |
| `Loch ≥ Mindest-Loch` | numerischer **Constraint** | — | **C-13** |

**Zähne:** eine 0,3-mm-Wand < 0,8 mm → `CONSTRAINT_VIOLATION`; ein 1,0-mm-Loch <
2,0 mm → `CONSTRAINT_VIOLATION`. Der Capstone (12 mm Wand, 4,5 mm Loch) besteht.
Die ad-hoc-Regel `q_t ≥ max(2, 0,05·Breite)` wurde **vollständig ersetzt** durch
die belegte FDM-Regel (keine Code-Überlappung).

**Ehrliche Scope-Grenze:** Nur Regeln, die aus den vorhandenen Größen folgen, sind
codiert (Wandstärke, Loch-Druckbarkeit). **Orientierungsabhängige** Regeln —
Überhang > 45°, Brückenspannweite, Stützen — sind **nicht** still „bestanden",
sondern als **Gap** deklariert: sie brauchen ein Bau-Orientierungs-Modell, das die
CSG (zentrierte Primitive, ohne Druckrichtung) noch nicht trägt. Ein bestandener
DFM-Check ist notwendig, nicht hinreichend.

**Quelle (FDM/FFF, am 2026-06-11 verifiziert):** Mindestwand ≈ 0,8 mm = 2 Perimeter
einer 0,4-mm-Düse; Mindest-Loch 2,0 mm horizontal (1,0 mm vertikal); Überhang > 45°
braucht Stützen (UltiMaker „Design for FFF"; Hydra Research; Xometry FDM-Tipps;
Stanford Lab64). Modul `dfm.py`, getestet in `tests/test_dfm.py`.

---

## 12. Unsicherheits-Propagation (GUM / JCGM 100) — C-18, „Gate rechnet nach"

GENESIS behandelt Werte sonst als exakte Punkte. Doch ein realer gemessener/
bezogener Eingang trägt eine **Unsicherheit** (12 kg Regallast sind 12 ± etwas).
Damit „jeder Wert belegt" unter realen Eingaben **rigoros** bleibt, muss sich diese
Unsicherheit **fortpflanzen**: ein DERIVED-Wert trägt eine kombinierte
Standardunsicherheit, und GATE γ **C-18** rechnet sie unabhängig nach — exakt die
Defense-in-Depth von C-6 (Wert), nun auf die Unsicherheit angewandt.

**Methode (recherchiert):** GUM-Fortpflanzungsgesetz für **unkorrelierte** Eingänge
(JCGM 100:2008, Gl. 10): `u_c(y)² = Σ (∂f/∂x_i)² · u(x_i)²`. Die Partiellen werden
**numerisch** (zentrale Differenzen) über denselben sicheren Evaluator gebildet —
exakt für Summen/Produkte der Eingänge, kein symbolisches Differenzieren. Erweiterte
Unsicherheit `U = k·u_c` (k=2 ≈ 95 %). Modul `uncertainty.py` (eine Quelle für Demo
+ Test), getestet in `tests/test_uncertainty.py`.

**Capstone-Demonstration:** Die deklarierte Last-Unsicherheit (Typ B, ~5 %)
`12 ± 0,6 kg` propagiert deterministisch durch die ganze Kette:
`24 ± 1,2 kg → 235,4 ± 11,8 N → σ_nom 7,4 ± 0,37 → σ_peak 22,1 ± 1,1 MPa`
(U₉₅ = ±2,2). Selbst der Worst-Case `σ_peak + U₉₅ = 24,3 MPa` bleibt unter 50 MPa.
Jede abgeleitete Unsicherheit wird mit **demselben** Kombinierer gesetzt, den C-18
zum Nachrechnen nutzt — Übereinstimmung per Konstruktion; ein falsch deklarierter
Wert (`u` zu klein) → `BROKEN_UNCERTAINTY`.

**Ehrliche Grenze:** Dies ist die **First-Order**-GUM (lineares Taylor) für
unkorrelierte Eingänge — exakt für Summen/Produkte, sehr gute Näherung sonst.
Starke Nichtlinearität oder korrelierte Eingänge brauchen Monte-Carlo (JCGM 101) —
eine spätere Schicht. Die **Auswertung der Constraints am Worst-Case-Rand**
(`Wert ± U` statt Punktwert in C-13) ist die nächste Verfeinerung; aktuell prüft
C-13 den Punktwert, die Unsicherheit wird propagiert, verifiziert und ausgewiesen.
