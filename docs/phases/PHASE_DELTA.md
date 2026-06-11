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

**Constraints am Worst-Case-Rand (C-13, jetzt aktiv):** Trägt eine in einem
Constraint referenzierte Größe eine Unsicherheit, prüft C-13 die Bedingung am
**GUM-erweiterten 95-%-Rand** (k=2), nicht nur am Punktwert — eine deklarierte
Unsicherheit **gated** also tatsächlich. Ohne Unsicherheit ist jedes `U=0` und es
reduziert sich exakt auf den Punktvergleich (voll rückwärtskompatibel). Der Rand
wird je Vergleichsrichtung adversarial genommen: `le` prüft `(lv+U_l) ≤ (rv−U_r)`.
Beispiel: `a = 9 ± 1` gegen `a ≤ 10` besteht nominal (9 ≤ 10), scheitert aber am
Rand (9 + 2·1 = 11 > 10) → `CONSTRAINT_VIOLATION`. Capstone: `σ_peak + U₉₅ =
24,3 ≤ 50` → robust bestanden.

**Ehrliche Grenze:** Dies ist die **First-Order**-GUM (lineares Taylor) für
unkorrelierte Eingänge — exakt für Summen/Produkte, sehr gute Näherung sonst.
Starke Nichtlinearität deckt jetzt **Monte-Carlo (JCGM 101, §18)** ab; korrelierte
Eingänge bleiben eine weitere Erweiterung.

---

## 13. ε-Elektronik — deterministischer Electrical Rule Check (ERC), OHNE SPICE

Das elektronische Pendant zu GATE δ: `gate_erc` validiert die **Konnektivität**
der Netzliste mit Sicherheit — **reine Logik, keine Simulation, keine externe
Engine** (ngspice/KiCad sind **nicht** nötig; eine Schaltungssimulation wäre eine
separate, Engine-gestützte Schicht). Datenmodell: `Pin` (typisiert: POWER_OUT /
POWER_IN / GROUND / PASSIVE), `Net` (verbindet Pins), `Netlist` (optional an der
Spec). Regeln:

| Code | Defekt |
|---|---|
| `DANGLING_PIN_REF` | ein Netz verbindet einen nie deklarierten Pin |
| `DANGLING_PART` | ein Pin gehört zu einem Teil, das nicht in der BOM ist |
| `DUPLICATE_PIN` | derselbe `part.pin` doppelt deklariert |
| `FLOATING_NET` | ein Netz verdrahtet < 2 Pins (verbindet nichts) |
| `UNCONNECTED_PIN` | ein deklarierter Pin taucht in keinem Netz auf |
| `PIN_MULTIPLE_NETS` | ein Pin in mehr als einem Netz (ein Pin = ein Knoten) |
| `POWER_CONFLICT` | zwei POWER_OUT-Treiber auf ein Netz kurzgeschlossen |
| `UNDRIVEN_INPUT` | ein Netz mit POWER_IN-Last ohne POWER_OUT-Treiber |

**Capstone:** das Netzteil (POWER_OUT) treibt den LED-Streifen (POWER_IN) über
`VCC_12V` + `GND` → ERC bestanden. **Zähne** (je ein Test): undriven Last → 
`UNDRIVEN_INPUT`; zwei Treiber → `POWER_CONFLICT`; Ein-Pin-Netz → `FLOATING_NET`;
undeklarierter/fremder/doppelter Pin → die jeweiligen Codes.

**Ehrliche Asymmetrie (wie δ):** ein **bestandener** ERC heißt „keine beweisbar
kaputte Verdrahtung", **nicht** „die Schaltung funktioniert" (kein SPICE-/Timing-/
Thermik-Urteil). Ein **gescheiterter** ERC heißt „definitiv kaputt verdrahtet".
Eine Spec ohne Netzliste besteht trivial (rein mechanischer Fall). Modul in
`verification/gates.py` (`gate_erc`), getestet in `tests/test_erc.py`.

**Quelle (extern, am 2026-06-11 verifiziert):** ERC als eigenständige, simulations-
freie Konnektivitätsprüfung (offene/fehlende Verbindungen) ist Standard in EDA-
Toolchains (KiCad ERC/DRC, ngspice für die *Simulation*); GENESIS implementiert die
deterministische ERC-Hälfte ohne Engine.

---

## 14. δ-FEM — eigenständiger Balken-Solver (Direkte Steifigkeitsmethode, numpy)

Die δ-2-Statik beantwortet den Kragträger mit einer **Formel**. Die echte
Verallgemeinerung ist die **Finite-Elemente-Methode**: Element-Steifigkeits-
matrizen assemblieren, Randbedingungen + Lasten anlegen, `K·u = F` lösen. `fem.py`
ist ein echter FEM-Solver (direkte Steifigkeitsmethode, 2-Knoten-Euler-Bernoulli-
Balkenelement) — in **reinem numpy**, also **ohne externen Solver** (CalculiX/
FreeCAD), voll offline und deterministisch.

**Verifiziert statt behauptet:** Für eine Tip-belastete Kragträger ist das
Balkenelement **exakt**, also muss das FEM-Ergebnis die geschlossene Form bis auf
Maschinengenauigkeit treffen — Spitzendurchbiegung `δ = F·L³/(3·E·I)` und
Wurzel-Biegespannung `σ = M·c/I = 6·F·L/(b·h²)`. Der entscheidende Test prüft das
FEM gegen **beides**: die geschlossene Form **und** die unabhängige δ-2-Analytik
(`structural.py`), die der Capstone nutzt — zwei verschiedene Methoden, die
übereinstimmen (`σ = 7,355 MPa` mesh-unabhängig für n=1…64), sind Defense-in-Depth
gegen einen Codefehler in einer der beiden.

**Ehrliche Grenze:** Dies ist **1-D-Euler-Bernoulli** per Matrixmethode (dieselbe
Modellklasse wie die Formel) — verallgemeinert auf Mehrsegment-/Mehrlast-Balken,
die eine Einzelformel nicht kann, ist aber **kein 3-D-Kontinuums-FEM** (kein
Spannungskonzentrationsfeld, keine Platten/Schalen). Das bleibt eine externe-Solver-
Schicht unter demselben Beweis-Standard. Modul `fem.py` (braucht numpy), getestet
in `tests/test_fem.py`.

**Quelle:** Direkte Steifigkeitsmethode, Hermite-kubisches Balkenelement
(Standard-FEM, z. B. Cook, *Concepts and Applications of Finite Element Analysis*);
Kragträger-Durchbiegung `δ = F·L³/(3EI)` (Euler-Bernoulli).

---

## 15. ε-Elektronik δ — DC-Arbeitspunkt per Modified Nodal Analysis (numpy)

ERC beweist die **Verdrahtung**; die nächste Schicht ist der echte **DC-Arbeits-
punkt**: welche Spannung liegt an jedem Knoten, welchen Strom liefert jede Quelle?
`circuit.py` ist genau dieser Löser — **Modified Nodal Analysis (MNA)**, der
lineare DC-Kern jeder SPICE-Engine — in **reinem numpy**, also **ohne externen
Simulator** (ngspice war nicht installiert), voll offline und deterministisch. MNA
assembliert `[[G,B],[C,D]]·[v;j] = [i;e]` und löst direkt.

**Verifiziert statt behauptet:** der Test prüft den Löser gegen Ohm (Quelle über
Widerstand → `I=V/R`), einen Spannungsteiler (bekannter Knoten), eine Stromquelle
und gegen die **Capstone-Zahlen selbst** — das 12-V-Netzteil über den Arbeitspunkt-
Widerstand des LED-Streifens (`R=V/I=8 Ω`) liefert **exakt** die Nennlast 1,5 A,
genau den Strom, den der Elektronik-Constraint (PSU 2 A ≥ LED 1,5 A) annimmt. Damit
wird der Constraint nicht nur deklariert, sondern **gerechnet**.

**AC-Erweiterung (komplexe MNA):** `solve_ac(components, omega)` löst den
Frequenzbereich — reaktive Admittanzen `Y_C=jωC`, `Y_L=1/(jωL)`, komplexe Knoten-
Phasoren (Betrag + Phase). **Verifiziert** gegen die analytische RC-Tiefpass-
Übertragungsfunktion `H(jω)=1/(1+jωRC)`: am Cutoff `ω=1/RC` exakt `|H|=1/√2`,
Phase −45°; über das ganze Band deckungsgleich. (DC ist der ω→0-Spezialfall.)

**Nichtlinear (Diode, Newton-Raphson):** `solve_dc_nonlinear` löst Arbeitspunkte
mit Shockley-Dioden über das **Companion-Modell + Newton-Raphson** (die klassische
SPICE-Innenschleife) mit SPICE-Spannungsbegrenzung (`pnjlim`, gegen Exponential-
Überlauf). **Verifiziert** gegen den analytischen Load-Line-Schnitt: über 4
Schaltungen exakt (`Vd` bis 1e-7), Sperrrichtung blockiert. Konvergiert nicht →
`RuntimeError` (nie ein still-falscher Arbeitspunkt).

**Transienten-Erweiterung (Zeitbereich):** `solve_transient` integriert per
**Backward-Euler-Companion-Modellen** (Kondensator → Leitwert C/dt + Memory-
Stromquelle; Spule → dt/L + Vorstrom-Quelle), je Zeitschritt via `solve_dc` gelöst
(unbedingt stabil). **Verifiziert** gegen die analytische RC-Ladekurve
`V_C=V(1−e^{−t/RC})` (auf <2 % bei dt=τ/200, **konvergiert** mit kleinerem Schritt)
und RL-Sättigung. 

**Ehrliche Grenze:** DC (linear + **nichtlinear/Diode**) + **linearer AC** +
**Transient** (linear, Backward-Euler). Nichtlineare Transienten (Diode im
Zeitschritt) wären die Kombination beider Companion-Schleifen — eine weitere Schicht.
Modul `circuit.py` (braucht numpy), getestet in `tests/test_circuit.py`.

**Quelle:** Modified Nodal Analysis (Standard-Schaltungsanalyse, Ho/Ruehli/Brennan
1975; der DC-Kern von SPICE); Ohmsches Gesetz, Kirchhoff.

---

## 16. δ-BREP — exakte Geometrie über den OpenCASCADE-Kernel (optional)

Die δ-1-Schicht (`verification/geometry.py`) rechnet über **achsenparallele
Bounding-Boxes**: sound, aber **konservativ** — sie beweist Nicht-Überlapp
(disjunkte AABBs) und exaktes Volumen nur in einfachen Fällen, **nie** ein False
Positive, aber oft „keine Aussage". `brep.py` hebt das auf **exakte** Geometrie:
die GENESIS-CSG wird in echte **OpenCASCADE-B-Rep-Festkörper** übersetzt (via
cadquery/OCP) und der Kernel direkt gefragt — exaktes Volumen, Solid-Validität
(`BRepCheck`), und **exakte Interferenz** (Volumen des echten Schnitts, nicht der
Hüllboxen).

**Der exakte-schlägt-konservativ-Gewinn:** Zwei Kugeln r=2 bei (0,0,0) und (3,3,0)
— Mittelpunktabstand √18 = 4,24 > 4, die **Festkörper sind disjunkt** — aber ihre
**AABBs überlappen** ([-2,2]³ vs [1,5]×[1,5]×[-2,2]). Die AABB-Schicht kann das
nicht entscheiden; exaktes BREP beweist **keine** Interferenz. Genau die Lücke, die
δ-1 ehrlich offenließ, schließt diese Schicht.

**Verifiziert:** exaktes Volumen des Capstone-Halters = **57409,148 mm³** =
unabhängig die analytische `geometry.volume_of` (zwei Methoden stimmen überein) und
≤ AABB-Schranke (exakt überschreitet nie die sound Schranke); Halter ist valider
Solid.

**cadquery/OCP ist OPTIONAL:** lazy import, klare Fehlermeldung wenn fehlend — der
Kern-Install (und CI) braucht **keinen** CAD-Kernel; der Test **skippt** ohne
cadquery (`pytest.importorskip`). Geometrie-Konvention zentriert (wie §1 / OpenSCAD
/ build123d). Modul `brep.py`, getestet in `tests/test_brep.py`.

**Ehrliche Grenze:** exakt für die modellierte CSG starrer Körper — weiterhin
**kein** physikalisches Urteil (Festigkeit/Herstellbarkeit; das ist Statik/DFM/FEM).
Ein bestandener Geometrie-Check bleibt notwendig, nicht hinreichend.

**Quelle:** OpenCASCADE Technology (B-Rep-Festkörperkernel) via cadquery; Boolesche
CSG-Operationen (Requicha 1980, s. PHASE_GAMMA §10).

---

## 20. Orientierungsabhängiges DFM — Überhang/Stützen-Erkennung über das BREP

§11 prüft Wandstärke/Loch aus den Größen; die **orientierungsabhängige** Regel
(„eine Fläche steiler als 45° aus der Senkrechten braucht Stützen") braucht die
echte Geometrie **und** eine **Baurichtung**, die die CSG allein nicht trägt.
`orientation.py` ergänzt sie über den OCCT-Kernel: Solid bauen, **tessellieren**,
und jedes Dreieck prüfen — eine nach unten weisende Fläche, deren Normale innerhalb
`max_overhang_deg` der Senkrecht-nach-unten liegt, braucht Stützen (außer dem
Bauplatten-Kontakt am z-Minimum). Tessellierung = der Standard-Slicer-Ansatz;
Dreieck-Winding für einen validen Solid ist konsistent auswärts.

**Der orientierungsabhängige Beweis:** **dasselbe** Capstone-Teil braucht **flach**
gedruckt (+Z) **keine** Stützen (das Durchgangsloch ist senkrecht), **auf der Seite**
gedruckt (+X) aber **schon** (das Loch wird waagerecht → Überhang; Fläche ~1003).
Kugel → Stützen (untere Kappe); Box / vertikaler Zylinder → keine.

**Bug im Verify-Loop gefangen+gefixt:** dabei fiel auf, dass `Solid.makeSphere(r)`
per Default nur eine **Halbkugel** baut (Vol = halb, nicht zentriert) — die
BREP-Kugel-Übersetzung (§16) war falsch; jetzt voll & zentriert
(`makeSphere(r, origin, +Z, -90, 90, 360)`), Vol = 4/3·π·r³.

**Stützvolumen-Schätzung:** `overhang_check` liefert zusätzlich eine **Obere-
Schranke** des Stützmaterials — die Säule unter jedem Überhang-Dreieck bis zur Platte
(projizierte Fläche × Höhe) mal `support_density` (Sparse-Infill-Anteil). **Verifiziert
gegen Handrechnung:** eine 20×20-Platte auf einer 4×4-Säule → Überhangfläche 384, Säule
20 mm → `Volumen = 384·20·0,2 = 1536`; linear in der Dichte. (Obere Schranke, weil die
Säule auch dort bis zur Platte zählt, wo Material darunter sitzt.)

**Ehrliche Grenze:** Standard-45°-Regel, exakt für die modellierte Geometrie, eine
Baurichtung (Default +Z); **keine** Orientierungs-Optimierung; Stützvolumen ist eine
Schätzung (obere Schranke). cadquery/OCP optional (Test skippt ohne). Modul
`orientation.py`, getestet in `tests/test_orientation.py`.

**Quelle:** 45°-Überhangregel für FDM (UltiMaker/Slicer-Standard, s. §11);
Tessellierungs-basierte Überhang-Erkennung (Standard im Slicing).

---

## 21. 3-D-Kontinuums-FEM — tetraedrische Linear-Elastizität (numpy)

§14 ist 1-D-Balken-FEM. Das echte **Kontinuums-Spannungsfeld** — das an einer
Bohrung auf die Kirsch-Konzentration steigt, die die Statik-Schicht nur konservativ
schrankt (Kt=3) — braucht ein **3-D-Kontinuums-FEM**. `fem3d.py` ist eines: das
**konstant-Dehnungs-4-Knoten-Tetraeder** der linearen isotropen Elastizität,
assembliert und gelöst in **reinem numpy**, mit eingebautem strukturiertem Box-
Mesher (jede Hex-Zelle → 6 Tets) — **kein externer Solver (CalculiX/FreeCAD), kein
Mesher (gmsh)**.

**Exakt verifiziert:** das konstant-Dehnungs-Tetraeder reproduziert einen
**gleichförmigen** Spannungszustand **exakt** — ein verschiebungsgesteuerter Stab
liefert `σ = E·δ/L` bis Maschinengenauigkeit (std 4,5e-13), perfekt gleichförmig,
mit `σ_yy=σ_zz=0` und der **korrekten Poisson-Querkontraktion** `u_y=−ν·ε·L_y`;
ein kraftgesteuerter Stab liefert `mean σ_xx = F/A` exakt (Gleichgewicht). Von-Mises
geprüft.

**Ehrliche Grenze:** lineare (Klein-Dehnungs-) isotrope Elastizität, statisch — keine
Plastizität/Kontakt/Großverformung. Ein **konformes Netz eines gelochten Teils**
(um das Kt-Feld selbst zu **rechnen** statt zu schranken) braucht einen
unstrukturierten Mesher (gmsh) — die nächste Schicht; **dieser Solver liefert die
Maschine, die sie speisen würde.** Modul `fem3d.py` (braucht numpy), getestet in
`tests/test_fem3d.py`.

**Quelle:** Konstant-Dehnungs-Tetraeder / lineare FEM-Elastizität (Standard, z. B.
Zienkiewicz/Cook); isotrope Elastizitätsmatrix (Lamé λ, μ).

---

## 22. Berechnetes Loch-Spannungsfeld — das FEM ersetzt die Kt=3-Schranke

§9 nutzt den Kirsch-Faktor **Kt=3** als **konservative Schranke** für den
Spannungs­überhöher an der Bohrung. §22 **rechnet** ihn: `plate_hole.py` vernetzt
das klassische **Platte-mit-Loch**-Benchmark mit **gmsh** (unstrukturiertes Tet-
Netz, am Loch verfeinert), speist es in den 3-D-Solver (§21, `fem3d`), zieht die
Platte und liest die **echte** Spitzenspannung am Lochrand — der Kreis, für den der
§21-Solver gebaut wurde, schließt sich.

Viertel-Symmetrie-Modell (x≥0, y≥0), dünne Platte ≈ ebener Spannungszustand;
Spitzen-`σ_xx` am Lochrand auf der y-Achse (θ=90° zur Last), wo Kirsch für die
**unendliche** Platte `σ_θθ = 3·σ_far` gibt.

**Verifiziert:** der berechnete Brutto-Kt **konvergiert monoton nach oben** unter
Netzverfeinerung (`3.086 → 3.168 → 3.311`) gegen **~3,1–3,3** — der Kirsch-Wert
**3,0** angehoben durch die **Endbreiten-Korrektur** (Peterson, hier d/W=0,2 →
~3,14). Das Fernfeld trifft die aufgeprägte `E·δ/L = 210` (Brutto). **Damit wird aus
der konservativen Konstante Kt=3 eine gerechnete Größe** — der Solver bestätigt und
schärft die Schranke, die die Statik-Schicht annahm.

**Ehrliche Grenze:** lineare Elastizität, konstant-Dehnungs-Tets (konvergieren an
einer Konzentration langsam → Verfeinerung), **endliche** Platte (Kt also der
Endbreiten-Wert, nicht exakt 3). Es rechnet die **Zug**-Konzentration (Kirsch); der
Biege+Loch-Fall des Halters ist eine direkte Erweiterung **desselben** Solvers. gmsh
optional (Test skippt ohne). Modul `plate_hole.py`, getestet in
`tests/test_plate_hole.py`.

**Quelle:** Kirsch (1898) Kt=3 (s. §9); Endbreiten-Korrektur Peterson's *Stress
Concentration Factors*; Platte-mit-Loch ist das kanonische FEM-Konzentrations-
Benchmark.

---

## 23. FEM des konkreten Halters in Biegung — die konservative Schranke geprüft

§22 rechnet die kanonische **Zug**-Kt; §23 schließt es für das **echte Teil**:
`bracket_fem.py` vernetzt die **tatsächliche Halter-Geometrie** (Box mit Durchgangs-
loch) mit gmsh — verfeinert **sowohl** am eingespannten Wurzelquerschnitt (max.
Biegung) **als auch** am Loch — speist sie in den 3-D-Solver (`fem3d`), belastet sie
als **Kragträger** (feste Wandfläche, transversale Spitzenlast) und liest die echte
Spitzenspannung.

**Ehrlicher Befund (verifiziert):** das 3-D-Feld **bestätigt** die Handrechnung —
die Wurzel-Oberflächenspannung konvergiert (von unten, CST-Tets) gegen die
analytische `σ_nom = 6FL/(bh²) = 7,355 MPa` — und zeigt, dass die Schranke
**konservativ** war: das Loch sitzt **mittig** (halbes Wurzelmoment), also ist es
selbst mit Konzentration **nicht** die kritische Stelle (`σ_hole < σ_root`), und der
reale Peak (~6,5 MPa) liegt **weit unter** der Kt=3-Schranke (22 MPa) und **weit
unter** der Festigkeit (50 MPa). **Eine konservative Handrechnung, vom FEM bestätigt
und quantifiziert.**

**Ehrliche Grenze:** lineare Elastizität, konstant-Dehnungs-Tets (Peak auf grobem
Netz unterschätzt → Verfeinerung, „konvergiert nach oben"), statische Spitzenlast,
PLA `E≈3500 MPa`, `ν≈0,35` deklariert. gmsh optional (Test skippt ohne). Modul
`bracket_fem.py`, getestet in `tests/test_bracket_fem.py`.

---

## 24. Quadratische Tets (T10) — der Konzentrations-Peak auf grobem Netz

§22/§23 lesen den Peak mit dem **4-Knoten-Tet** (CST, **konstante** Dehnung): jedes
Element trägt nur einen Spannungswert, also unterschätzt ein grobes Netz den Gradient
an einer Kerbe und konvergiert langsam. Der **10-Knoten-Tet** (T10: 4 Ecken + 6
Kantenmitten, `fem3d_quadratic.py`) hat **quadratische** Formfunktionen und damit
**lineare** Dehnung — er erfasst dasselbe Konzentrationsfeld mit weit weniger
Elementen. Reines numpy, 4-Punkt-Gauß-Integration (exakt für dieses Element).

**Verifiziert, nicht behauptet — zwei Ebenen:**
- **Element (ohne Mesher):** der **lineare Patch-Test** — ein lineares Verschiebungs-
  feld liefert an **jedem** Gauß-Punkt **exakt** die aufgeprägte konstante Dehnung
  (`atol 1e-12`); die Steifigkeit hat den **Starrkörper-Nullraum** (eine
  Translation trägt keine Kraft) und ist symmetrisch. Das pinnt die Element-Mathematik
  ohne jede externe Abhängigkeit.
- **Netz (gmsh order-2):** auf einer Box reproduziert das Element **Zug exakt**
  (`σ_xx = 210` MPa, `std < 1e-6`, Maschinengenauigkeit); auf der Platte-mit-Loch
  erreicht T10 auf einem **groben** Netz (503 Tets) den analytischen Howland/Heywood-
  **Brutto-Kt ≈ 3,14** (für `d/W = 0,2`) — `Kt_T10 = 3,15` —, während der **gleiche**
  grobe Netz mit dem linearen T4 noch **unterschätzt** (`Kt_T4 = 3,07`). Genau die
  „schnellere Konvergenz", um die es geht: weniger Elemente für denselben Peak.

**Schlüsseldetail (ehrlich):** der Peak wird bei T10 an den **Element-Knoten**
zurückgewonnen (`t10_nodal_stresses`), nicht im Element-Schwerpunkt — eine
Spannungskonzentration sitzt auf einem **Rand**knoten, der Schwerpunkt-Wert unter-
liest sie. Erst die **lineare** Dehnung des T10 macht diese Knoten-Rückgewinnung
sinnvoll (T4 ist konstant, Knoten = Schwerpunkt). So wird der Vorteil sauber sichtbar
und nicht durch die Abtast-Methode verdeckt.

**Mesher-Detail:** der strukturierte 6-Tet-Hex-Split ist für quadratische Elemente
**degeneriert** (seine kreuzenden inneren Diagonalen legen zwei verschiedene Knoten
auf dieselbe Kantenmitte → das Netz ist nicht konform), daher kommt das T10-Netz aus
gmsh `setOrder(2)`, dessen 6 Kantenknoten **geometrisch** (Mittelpunkt-Match) in die
lokale Reihenfolge dieses Moduls sortiert werden — unabhängig von gmshs eigener
Kantennummerierung.

**T10-Massenmatrix (für §26-Dynamik):** `t10_mass(coords, ρ)` ergänzt die
Konsistenz-Masse `ρ·V·(Ĉ⊗I₃)`. Da `N_a·N_b` Grad 4 ist (jenseits der 4-Punkt-Gauß-
Regel der Steifigkeit), wird `Ĉ` **exakt** aus der baryzentrischen Integralformel
`∫L1^aL2^bL3^cL4^d dV = 6V·a!b!c!d!/(a+b+c+d+3)!` berechnet (für gerade/affine
Elemente, wie die Box-Netze — Hohlkant-Elemente bräuchten Jacobi-Quadratur). `Ĉ`
summiert sich zu 1 (Element-Masse = `ρV`) und stimmt mit der tabellierten
T10-Konsistenzmasse `ρV/420·[…]` überein. **Wirkung:** dieselbe Modal-Lösung (§26) auf
einem T10-Netz trifft die Biegefrequenz auf **~0,2 %** auf grobem Netz, wo der lineare
Tet um **zig Prozent** danebenliegt.

**Ehrliche Grenze:** lineare isotrope Elastizität; der gmsh-Mesher ist optional (Test
skippt ohne). Die Knoten-Rückgewinnung ist eine **ungemittelte** obere Peak-Schätzung
(Standard-FEM-Praxis), kein gemittelter Knotenwert; die T10-Masse ist exakt für
**gerade** Elemente. Module `fem3d_quadratic.py` + die T10-Variante in `plate_hole.py`
+ T10-Dispatch in `modal.py`, getestet in `tests/test_fem3d_quadratic.py` und
`tests/test_modal.py`.

**Quelle:** Zienkiewicz & Taylor, *The Finite Element Method* (quadratische
Tetraeder, lineare Dehnung, schnellere Konvergenz); Howland (1930) / Heywood-
Endbreiten-Korrektur für den Brutto-Kt der gelochten Streifenplatte (`d/W = 0,2 →
Kt ≈ 3,14`).

---

## 25. Stationäre Wärmeleitung — die Thermik-Achse (`thermal.py`)

Die Elektronik-Schichten (`circuit.py`/ERC) rechnen die **Verlustleistung** eines
Bauteils; die Statik rechnet **Spannung**. Die fehlende Physik, die beide verbindet,
ist **Wärme**: eine dissipierte Leistung hebt die Bauteiltemperatur, und ein
Polymerteil (PLA-Glasübergang `~60 °C`) versagt **thermisch** lange bevor es
**mechanisch** versagt. Dieses Modul ist das stationäre Wärmeleitungs-Analogon zum
Elastizitäts-FEM: Skalarfeld = Temperatur, Element = 4-Knoten-Tet, Elementmatrix
`k·V·(∇N)ᵀ(∇N)` — Fourier-Leitung. Reines numpy, dieselbe strukturierte Vernetzung
wie der Elastizitäts-Solver, **keine** externe Abhängigkeit (läuft also auch ohne
gmsh/cadquery).

**Verifiziert, nicht behauptet:** der lineare Tet reproduziert ein **lineares**
Temperaturfeld **exakt** — das thermische Zwilling zum „Zug ist exakt"-Test. Damit
liefert 1-D-Leitung durch einen prismatischen Stab das **Fourier-Gesetz**
`Q = k·A·ΔT/L` auf **jedem** Netz maschinengenau: das Feld ist linear (`max|T−linear|
< 1e-9`), und die aus den FEM-**Reaktionen** gelesene geleitete Wärme **gleicht die
geschlossene Form exakt** (`rtol 1e-9`). Der Test pinnt beides; die geschlossenen
Helfer (`fourier_heat`, `conductive_temperature_rise`) sind damit als exakt
validiert (Hin-/Rück-Identität `Q ↔ ΔT`).

**Der echte Check (Thermal-DFM):** `overtemperature_check(power, k, A, L, ambient,
max_service_temp)` rechnet `ΔT = P·L/(k·A)`, addiert die Umgebung und meldet, ob der
Peak die **Service-Temperatur** des Materials reißt. Konkreter Befund (im Test): eine
LED mit `0,5 W` durch einen `5 mm`-PLA-Standoff (`A=20 mm²`) ergibt `ΔT ≈ 960 K` →
**FAIL** — PLA leitet `~1800×` schlechter als Aluminium, der Pfad ist **nicht**
kühlbar; derselbe Pfad in Aluminium: `ΔT ≈ 0,5 K` → **PASS**. Eine echte
„validiere-vor-dem-Bauen"-Aussage, die das geschlossene Loch zur **gerechneten**
Elektronik-Leistung schließt.

**Beliebige Geometrie:** `peak_temperature(...)` gibt den Peak des Leitungsfeldes auf
**jedem** vernetzten Teil — z. B. eine Platte, die eine **Punktquelle** zu gekühlten
Rändern spreizt (kein geschlossener Ausdruck): der Peak sitzt an der Quelle, das Feld
fällt monoton zum Senke-Rand, Energie ist exakt erhalten (`Σ Reaktionen + Quelle ≈ 0`).

**Ehrliche Grenze:** lineare, isotrope, **stationäre** Leitung — kein
Konvektions-/Strahlungs-Film, kein temperaturabhängiges `k`, **nicht** transient. Ein
sauberer PASS **schrankt** die rein konduktive Erwärmung: eine real konvektierende
Fläche senkt sie nur, also ist die Leitungs-Erwärmung **konservativ** für ein
wärme-gesenktes Teil und **optimistisch** für ein Stillluft-Teil (deklariert, nicht
versteckt). `solve_heat` braucht **mindestens eine** feste Temperatur (reines Neumann
ist singulär → klarer Fehler). Modul `thermal.py`, getestet in `tests/test_thermal.py`.

**Quelle:** Fourier-Wärmeleitung `q = −k∇T` (Fourier 1822); die FEM-Diskretisierung
des skalaren Laplace-Operators `∫(∇N)ᵀk(∇N)dV` ist Standard (Zienkiewicz & Taylor,
*The Finite Element Method*, Feldprobleme).

### 25b. Transiente Leitung — die Zeit-Achse (`solve_transient_heat`)

Stationär beantwortet „**wie heiß**?"; transient beantwortet „**wie lange** bis es
heiß ist?". Ergänzt die **Wärmekapazitäts**-Matrix `C·Ṫ + K·T = q` und marschiert sie
per **Backward-Euler** (unbedingt stabil) in der Zeit. **Verifiziert:** (1) die
Konsistenz-Kapazität summiert sich **exakt** zu `ρc·V`; (2) der Transient läuft im
`t→∞`-Limit **maschinengenau** in die stationäre Lösung (`max diff 1,6e-13`) — das
Backward-Euler-Pendant zum Steady-Check; (3) die **langsamste thermische Zeitkonstante**
`τ₁ = 1/λ₁` (kleinster Eigenwert von `K φ = λ C φ`, das thermische Pendant zur
Grundfrequenz) konvergiert gegen die analytische erste Stab-Eigenmode
`τ₁ = 4ρcL²/(π²k)` von **unten** mit Netzverfeinerung (`−4,4 % → −2,2 % → −1,1 %`).
`time_to_threshold(history, dt, T_grenz)` liefert direkt „Zeit bis zur Glasübergangs-
Temperatur". **Ehrliche Grenze:** Backward-Euler ist erster Ordnung in `Δt` (stabil,
aber genauigkeitslimitiert); der `τ₁`-Restfehler ist die räumliche Diskretisierung
(konsistent leicht zu steif → `τ` etwas niedrig). Getestet in `tests/test_thermal.py`.

---

## 26. Modalanalyse — Eigenfrequenzen, das Resonanz-Versagen (`modal.py`)

Das Statik-FEM beantwortet „hält es die Last?"; es kann **nicht** „**schwingt** es?"
beantworten — eine nahe einer Eigenfrequenz erregte Struktur verstärkt enorm und
versagt durch **Ermüdung** bei einer Last **weit unter** ihrer statischen Festigkeit.
Dieses Versagen ist für einen Spannungs-Check **unsichtbar**. Dieses Modul fügt es
hinzu: das Konsistenzmassen-Eigenproblem `K·φ = ω²·M·φ`, dessen kleinste Wurzeln die
Eigenfrequenzen sind. Es **wiederverwendet** die exakte Steifigkeit des 4-Knoten-Tets
(§21) und ergänzt die einzige fehlende Zutat — die Element-**Massenmatrix** — und löst
das verallgemeinerte Eigenproblem in reinem numpy (Cholesky-Transform, `M` SPD).

**Verifiziert, nicht behauptet — drei Ebenen:**
- **EXAKT:** die Konsistenzmassenmatrix summiert sich maschinengenau zur Körpermasse
  `ρ·V` (Konsistenzmasse pro Richtung `(ρV/20)(1+δ_ij)`, geschlossene Form, keine
  Quadratur).
- **EXAKT:** ein **frei-freier** Körper liefert **genau sechs** Null-Frequenz-
  Starrkörpermoden (3 Translationen + 3 Rotationen) — die strukturelle Signatur, die
  das Eigenproblem zeigen **muss** (Test: 6 Moden `< 1 Hz`, Modus 7 `≈ 3539 Hz`).
- **QUANTITATIV:** die **longitudinale** Eigenfrequenz eines Stabs konvergiert gegen
  die geschlossene Form `f₁ = c/(4L)`, `c = √(E/ρ)`, auf **~1 %** (`nx=16`) — den
  Axialmodus erfasst der lineare Tet **genau** (uniforme Axialdehnung ist CST-exakt).

**Ehrlicher Befund (Biegung):** die Kragträger-**Biege**frequenz konvergiert gegen
den Euler-Bernoulli-Wert `f₁ = (1,875²/2π)·√(EI/(ρA L⁴))` **von OBEN** — der
konstant-Dehnungs-Tet ist **biege-zu-steif** (`725 → 643 → 599 Hz` gegen analytisch
`418 Hz`, monoton fallend). Das ist **dieselbe** CST-Grenze, die §23 für Spannung
dokumentiert, hier mit umgekehrtem Vorzeichen: die Frequenz ist **zu hoch** verzerrt —
ein **nicht-konservativer** Bias (deklariert, nicht versteckt). Für eine belastbare
Biegemode: verfeinern oder **quadratische Tets** (§24) nehmen. Der **Axialmodus** ist
der saubere quantitative Anker; der Biege-Test prüft nur den **Konvergenz-Trend**.

**Der echte Check (Resonanz-Design):** `resonance_check(f_natural, f_excitation,
min_separation_factor=2.0)` meldet, ob die erste Eigenfrequenz die Erregerfrequenz um
einen sicheren Faktor übersteigt (steifes Mount-Design: `f₁ ≥ 2·f_erreger`, damit die
Erregung im flachen, schwach-verstärkten Antwortbereich sitzt). `120 Hz` über `100 Hz`
(nur `1,2×`) → **FAIL**; `300 Hz` (`3×`) → **PASS**.

**Ehrliche Grenze:** lineare, **ungedämpfte**, kleinverschiebungs-Modalanalyse;
konsistente (nicht gelumpte) Masse; SI-Einheiten **zwingend konsistent** (E in Pa, `ρ`
in kg/m³, Längen in m → Hz). Der lineare Tet überschätzt **Biege**frequenzen (Bias
hoch = nicht-konservativ). `natural_frequencies` braucht **mindestens einen** freien
Freiheitsgrad (sonst klarer Fehler). Modul `modal.py`, getestet in
`tests/test_modal.py`.

**Quelle:** verallgemeinertes Eigenwertproblem der Strukturdynamik `K φ = ω² M φ` +
Konsistenzmassenmatrix (Zienkiewicz & Taylor, *The Finite Element Method*, Bd. 2,
Dynamik); Kragträger-Grundmode `βL = 1,8751` (Blevins, *Formulas for Natural
Frequency and Mode Shape*); Stab-Longitudinalmode `f_n = (2n−1)c/4L`.

---

## 27. Euler-Knickung — das elastische Stabilitäts-Versagen (`buckling.py`)

Die Statik prüft, ob die Spannung unter der Festigkeit bleibt; §26 prüft Resonanz.
**Keine** sieht das dritte klassische Versagen: ein schlanker **Druck**stab **knickt**
— biegt seitlich aus und kollabiert — bei einer Last **weit unter** der, die ihn
fließen ließe. Eine Halter-Strebe, eine lange Schraube auf Druck, ein dünnes Bein:
spannungsseitig sicher, aber durch elastische **Instabilität** versagend. Dieses Modul
ergänzt es — mit **zwei** kreuz-geprüften Methoden:
- **Geschlossen:** Eulers `P_cr = π²·E·I / (K·L)²`, `K` der Lagerungs-Längenfaktor
  (gelenkig-gelenkig 1, fest-frei 2, fest-fest 0,5, fest-gelenkig ≈0,699).
- **Gerechnet:** ein Balken-Element-Knick-Eigenproblem `K_e·φ = P·K_g·φ` aus der
  Euler-Bernoulli-Elastizitäts-Steifigkeit (§ `fem.py`) **plus** der konsistenten
  **geometrischen** Steifigkeit; der kleinste Eigenwert ist `P_cr`. Wiederverwendet
  **dasselbe** Balkenelement, auf dem der Durchbiegungs-Solver verifiziert ist.

**Verifiziert, nicht behauptet:** die gerechnete `P_cr` konvergiert für **alle vier**
Lagerungen gegen die Euler-Form auf **deutlich unter 1 %** mit 8 Elementen
(gelenkig-gelenkig `0,003 %`, fest-frei `0,000 %`, fest-fest `0,05 %`, fest-gelenkig
`−0,03 %`) — zwei unabhängige Methoden, die übereinstimmen, sind der Schutz gegen einen
Fehler in einer von beiden. Das Lagerungs-Physik-Gesetz fällt direkt heraus: fest-frei
(`K=2`) ist **exakt ¼** so stark wie gelenkig-gelenkig (`P_cr ∝ 1/K²`).

**Der echte Check (ehrlich über Eulers Grenze):** `buckling_check(...)` ist ehrlich,
**wann** Euler gilt: ein **gedrungener** Stab (kleine Schlankheit `KL/r`) **staucht/
fließt** bevor er knicken kann, also ist das maßgebende Versagen das **kleinere** aus
Euler-Last und Stauchlast `σ_y·A`. Der Übergang liegt bei `λ_c = π·√(E/σ_y)`. Befund
(im Test, 10×10-Stahl `σ_y=250`): `L=350 mm` → `λ≈121 > λ_c≈91` → **„buckling"** (Euler
maßgebend); `L=100 mm` → `λ≈35 < 91` → **„yield"** (Stauchlast maßgebend, Euler würde
hier `σ_cr≈1727 MPa ≫ σ_y` **über**schätzen). Der Check meldet, **welcher** Modus
greift — statt Euler blind zu trauen.

**Ehrliche Grenze:** lineare elastische Euler-Knickung eines prismatischen Stabs,
**ideal** — keine Vorkrümmung/Lastexzentrizität (die die reale Tragfähigkeit senken),
also eine **obere** Schranke; ein realer Nachweis nutzt einen Sicherheitsfaktor bzw.
die Perry-Robertson-/Johnson-Abminderung für Imperfektion und Inelastizität.
N-mm-MPa-konsistent (wie `fem.py`). Modul `buckling.py`, getestet in
`tests/test_buckling.py`.

**Quelle:** Euler (1744) Knicklast `P_cr = π²EI/(KL)²`; geometrische
Steifigkeitsmatrix des Balkenelements (Cook, *Concepts and Applications of FEA*;
Przemieniecki, *Theory of Matrix Structural Analysis*); Schlankheits-/Kurzstab-Übergang
(Mechanik-Standard, Euler-vs-Johnson).

---

## 28. Ermüdung — zyklisches Versagen unter der Festigkeit (`fatigue.py`)

Der Spannungs-Check (§9) vergleicht eine Spitzenspannung mit der **statischen**
Festigkeit; er sieht **nicht**, dass ein oft genug zyklisch belastetes Teil bei einer
Spannung **weit unter** dieser Festigkeit bricht. Eine Welle, eine Feder, ein
schwingender Halter: alle bestehen jeden statischen Check und reißen trotzdem durch
**Ermüdung**. Dieses Modul ergänzt die Standard-High-Cycle-Checks — die dritte
mechanische Lebensdauer-Achse neben Spannung (statisch) und Resonanz (§26).

Drei Lehrbuch-Closed-Forms, **kein** FEM:
- **Dauerfestigkeit** `S_e ≈ 0,5·UTS` (Stahl, gekappt ~700 MPa), optional per
  Marin-Faktoren (Oberfläche/Größe/Zuverlässigkeit) reduziert;
- **Basquin-S-N** `σ_a = σ'_f·(2N)^b` — endliche Lebensdauer bei gegebener Amplitude;
- **Mittelspannungs-Korrektur** — eine reale Last hat Mittelspannung `σ_m` **und**
  Amplitude `σ_a`; ein **zugiger** Mittelwert senkt die zulässige Amplitude. **Goodman**
  (Gerade zu UTS) = Standard/konservativ; **Soderberg** (zu Streckgrenze) strenger;
  **Gerber** (Parabel) am wenigsten konservativ. Plus **Miner**-Schadensakkumulation
  `D = Σ nᵢ/Nᵢ`.

**Verifiziert, nicht behauptet:** die Linien reduzieren auf ihre **exakten** Endpunkte
(rein wechselnd → Bruch bei `S_e`; rein mittel → bei `UTS`/`S_y`); **Soderberg ≤ Goodman
≤ Gerber** in zulässiger Last (im Test `1,92 < 2,27 < 2,78` für `σ_a=80, σ_m=60,
UTS=500, S_y=300, S_e=250`); **Basquin invertiert exakt** (`σ→N→σ`, bei `2N=1` ist
`σ_a=σ'_f`); **Miner summiert zu 1 bei Bruch** (zwei Blöcke je halbes Leben → `D=1,0`).

**Der echte Check:** `goodman_check(σ_a, σ_m, UTS, S_e)` → Sicherheitsfaktor
`n = 1/(σ_a/S_e + σ_m/UTS)`, `infinite_life` wenn `n ≥ 1`. Beispiel `σ_a=80, σ_m=60,
UTS=500, S_e=250` → `Goodman-Wert 0,44`, `n=2,27` → unendliche Lebensdauer.

**Ehrliche Grenze:** High-Cycle-(spannungsbasierte) Ermüdung nominell elastischen
Materials; **nicht** Low-Cycle-Plastik (Coffin-Manson), **nicht** Risswachstum (Paris),
keine Umgebungs-/Korrosionseffekte. Ein **druck**iger Mittelwert ist nicht schädlich und
wird **konservativ ignoriert** (nicht gutgeschrieben). MPa-konsistent. Modul
`fatigue.py`, getestet in `tests/test_fatigue.py`.

**Quelle:** Wöhler-S-N-Kurve; Basquin (1910) `σ_a = σ'_f(2N)^b`; modifiziertes Goodman
`σ_a/S_e + σ_m/UTS = 1`, Soderberg, Gerber; Palmgren-Miner-Regel; Dauerfestigkeit
`0,5·UTS` für Stahl ≤ ~1400 MPa (Shigley, *Mechanical Engineering Design*, Kap. 6).

---

## 29. Wärmeausdehnungs-Mismatch — Thermospannung ohne äußere Last (`thermal_stress.py`)

Die Leitungs-Schicht (§25) findet die **Temperatur**; die Statik findet die
**Last**-Spannung. Dazwischen liegt ein Versagen, das **keine** allein sieht: eine
Temperaturänderung will Material verformen, und wenn das **behindert** ist — ein Teil
zwischen starren Lagern, oder zwei verbundene Materialien mit verschiedenen
Ausdehnungskoeffizienten — baut sich Spannung **ohne jede äußere Last** auf. Ein
Messing-Insert im PLA-Halter, eine Metallspur auf Polymer, jeder erwärmte Presssitz:
kann allein durch einen Temperaturhub reißen. Drei Standard-Closed-Forms:
- **Eingespannt:** `σ = −E·α·ΔT` (Druck beim Heizen, Zug beim Kühlen, längenunabhängig).
- **Verbundene Parallel-Stäbe:** zwei auf gemeinsame Länge gezwungene Materialien teilen
  eine innere Kraft — Kompatibilität (gleiche Dehnung) + Gleichgewicht (keine Nettokraft)
  geben jede Spannung exakt.
- **Bimetall-Krümmung:** zwei verbundene Schichten verschiedener `α` biegen beim Heizen;
  Timoshenkos Closed-Form (1925) liefert die Krümmung.

**Verifiziert, nicht behauptet:** der eingespannte Wert ist exakt `−EαΔT` (Stahl,
`ΔT=100` → `−252 MPa`); die Zwei-Stab-Lösung erfüllt **Gleichgewicht maschinengenau**
(`A₁σ₁+A₂σ₂ ≈ 0`, Stahl/Al `±57,75 MPa`), **verschwindet** bei gleichen Koeffizienten,
und geht für einen **starren** Partner in den eingespannten Grenzwert `E₁(α₂−α₁)ΔT=231`
über; die Bimetall-Krümmung verschwindet bei gleichem `α` und reduziert sich für
gleiches Modul/Dicke auf das Lehrbuch-`1,5·Δα·ΔT/h`. Alles im Test gepinnt.

**Der echte Check:** `thermal_mismatch_check(...)` vergleicht die größere
|Mismatch-Spannung| mit der Festigkeit jedes Materials → Sicherheitsfaktor + welches
Material maßgebt. Ein `ΔT=300`-Hub auf eine Stahl/Al-Verbindung sprengt `100 MPa` → FAIL.

**Ehrliche Grenze:** linear elastisch, gleichförmiges `ΔT`, 1-D (Stäbe) bzw.
Timoshenko-Balken (Bimetall) — kein Dickengradient, **kein** Fließen, **keine**
viskoelastische Relaxation (die die Spannung in einem Polymer über Zeit abbaut). MPa-mm.
Modul `thermal_stress.py`, getestet in `tests/test_thermal_stress.py`.

**Quelle:** lineare Thermoelastizität `σ = E(ε − αΔT)`; Timoshenko (1925) *Analysis of
Bi-Metal Thermostats* (J. Opt. Soc. Am.) für die Bimetall-Krümmung.

---

## 30. Torsion — Scherversagen einer tordierten Kreiswelle (`torsion.py`)

Die Spannungs-/Biege-/Axialprüfung (`structural.py`), `buckling.py` (Instabilität) und
`fatigue.py` (zyklische Lebensdauer) sehen die **Torsion** nicht: ein Drehmoment verdreht
die Welle und erzeugt eine **Schubspannung**, die an der Außenfläche maximal ist und das
Material abscheren kann, bevor irgendeine Biege-/Axialreserve erschöpft ist. Antriebswelle,
Achse, Drehstab: jede besteht alle Biege-/Axialchecks und versagt doch durch Torsionsschub.
Diese Schicht ergänzt die vierte Achse — geschlossene Form, kein FEM.

Vier Lehrbuchformeln für den Kreisquerschnitt: polares Flächenträgheitsmoment
`J = pi*d^4/32` (Vollwelle) bzw. `pi*(D^4-d^4)/32` (Hohlwelle); Schubspannung
`tau = T*r/J` (linear von Null auf der Achse bis Maximum an der Oberfläche);
Oberflächenspannung der Vollwelle `tau_max = 16*T/(pi*d^3)`; Verdrehwinkel
`phi = T*L/(G*J)` [rad]. Plus `shaft_torsion_check` (DFM): Schub, Verdrehwinkel,
Sicherheitsfaktor `shear_strength/max_shear`, `ok`-Bool. Einheiten N·mm, mm, MPa, rad.

**Verifiziert, nicht behauptet:** die Oberflächenspannung ist `16T/(pi d^3)` UND zugleich
`T*(d/2)/J` bis auf Maschinengenauigkeit (Identität, Differenz `7.1e-15`); Anker
`T=100000 N·mm, d=20 mm → tau=63.6620 MPa`, `J_solid(20)=15707.9633 mm^4`; die Hohl-`J`
reduziert sich exakt auf die Voll-`J` bei Bohrung 0 (`J_hollow(40,20)=235619.4490`); der
Verdrehwinkel skaliert exakt linear mit `L` und `1/G` (Anker `0.0795775 rad = 4.5595°`) —
10 Tests grün auf py-3.11 **und** py-3.13.

**Ehrliche Grenze:** linear-elastische St-Venant-Torsion einer **prismatischen Kreiswelle**
(voll oder hohl). Nicht abgedeckt: nichtkreisförmige Querschnitte (Verwölbung → Torsions-
konstante statt `J`), Kerbwirkung an Absätzen/Passfedernuten/Bohrungen (separat `K_t`),
plastische Torsion, kombinierte Biegung+Torsion (dafür von-Mises-/Maximalschub-Kriterium).
**Quelle:** R. C. Hibbeler, *Mechanics of Materials*, 10. Aufl. (2017), Kap. 5; Timoshenko & Gere — elementar `tau = T*rho/J`, `phi = T*L/(G*J)`.

---

## 31. Hertzscher Kontakt — die hohe lokale Pressung wo gekrümmte Körper sich berühren (`contact.py`)

Die Spannungsprüfung sieht nur die nominale Querschnittsspannung, die FEM-Schichten die
globale Verformung. Keine sieht das Versagen dort, wo zwei gekrümmte Körper sich BERÜHREN:
Kugellager auf Laufbahn, Pressbolzen, Zahnflanken, Nocken. Der Kontaktfleck ist winzig, also
erzeugt schon eine mäßige Kraft eine enorme LOKALE Pressung weit über der Nennspannung — der
Keim von Pitting, Spalling und unterirdischer Wälzkontakt-Ermüdung. Dieses Modul ergänzt
Hertz' Schließformeln von 1882.

- `effective_modulus` reduzierter Modul `1/E* = (1-nu1^2)/E1 + (1-nu2^2)/E2`; Stahl-Stahl
  (E=210000, nu=0.3) → `E*=115384.6 MPa`.
- `sphere_sphere_contact` Punktkontakt: `a=(3FR/(4E*))^(1/3)`, `p0=3F/(2 pi a^2)=1.5*p_mean`.
- `sphere_on_flat` der Grenzfall r2 → unendlich (R = Kugelradius).
- `cylinder_cylinder_contact` Linienkontakt: `b=sqrt(4F'R/(pi E*))`, `p0=2F'/(pi b)=(4/pi)*p_mean`.
- `contact_check` liefert `safety_factor = allowable/max_pressure` und `ok`.

**Verifizierter Anker:** zwei 10-mm-Stahlkugeln, F=100 N → `a=0.14812 mm`, `p0=2176.13 MPa`,
`p_mean=1450.76 MPa`, Verhältnis `3/2` exakt. `sphere_on_flat` == `sphere_sphere(r2=1e12)`
(rtol 1e-6); Linien-`p0=857.07 MPa` == unabhängige Identität `sqrt(F'E*/(pi R))`
maschinengenau, Verhältnis `4/pi` exakt. 11/11 Tests grün (py 3.11 + 3.13).

**Ehrliche Grenze:** reibungsfreier, nicht-adhäsiver, nicht-konformer elastischer Kontakt
glatter Körper, klein gegenüber den Körperradien (Hertz-Annahmen); keine JKR-Adhäsion, keine
Rauheit, keine Tangentiallast, kein Fließen ab `p0 ~ 1.6*sigma_y`, nicht die unterirdische
Schubspannung die Wälzermüdung tatsächlich auslöst.
**Quelle:** H. Hertz (1882), *Über die Berührung fester elastischer Körper*, J. reine angew. Math. 92; K. L. Johnson, *Contact Mechanics* (1985), Kap. 3-4.

---

## 32. Druckbehälter-Wandspannung — die Umfangsspannung, die einen Tank/ein Rohr aufreißt (`pressure_vessel.py`)

Ein Punktlast-Spannungscheck sieht den Versagensfall eines Bauteils ganz ohne äußere
Einzelkraft nicht: einen geschlossenen Tank, ein Rohr, eine Gasflasche unter **Innendruck**.
Der Druck drückt die Wand überall nach außen; die dabei entstehende Umfangs- (Hoop-) Spannung
spaltet die Wand längs — typisch doppelt so groß wie die Längsspannung. Diese Schicht ergänzt
die Druck-Achse, deterministisch und LLM-frei.

Drei Lehrbuch-Geschlossenformen, je an ihrem exakten Grenzfall verankert: **Dünnwand-
Membrantheorie** (Zylinder `hoop=p*r/t`, `axial=p*r/(2*t)` ⇒ `hoop=2*axial`; Kugel `p*r/(2*t)`,
die optimale Druckform) und **Lamé (1833)** für dicke Wände (`A=p_i*r_i²/(r_o²-r_i²)`,
`B=p_i*r_i²*r_o²/(r_o²-r_i²)`, `sigma_r=A-B/r²`, `sigma_theta=A+B/r²`, Hoop maximal an der
Innenwand).

**Verifiziert statt behauptet:** Anker `p=10 MPa, r=500 mm, t=10 mm` ⇒ `hoop=500 MPa`,
`axial=250 MPa` exakt; Lamé-Randbedingungen `sigma_r(r_i)=-p_i` und `sigma_r(r_o)=0` exakt; die
Dickwand-Hoop an der Innenwand ist HÖHER als die Dünnwand-Schätzung und beide konvergieren mit
`t/r→0` (`1.0099 %` Lücke bei `t/r=0.02`, `66.667 %` bei `t/r=1.0`, `0.05 %` bei `t/r=0.001`).
`pressure_vessel_check` liefert `max_hoop`, `safety_factor=yield/max_hoop`, `ok` (Modell
`thin`/`thick`). 15 Tests grün.

**Ehrliche Grenze:** linear-elastischer, statischer Innendruck eines axialsymmetrischen
prismatischen Zylinders/einer Kugel fern von Enden und Öffnungen — kein Endkappen-/
Diskontinuitätsbiegen, keine Stutzen-Kerbwirkung, keine Außendruck-Beulkollaps-Instabilität
(eigener Modus, `buckling.py`), keine Autofrettage; die Dünnwand-Form unterschätzt die wahre
Innenwand-Hoop (bei nicht kleinem `t/r` `model='thick'` nutzen).
**Quelle:** Dünnwand-Membrantheorie (Shigley, *Mechanical Engineering Design*); Lamé, G. & Clapeyron, B. (1833), Dickwand-Zylinder-Lösung.

---

## 33. Kriechen & Kriechbruch — der langsame Hochtemperatur-Tod (`creep.py`)

Der Spannungs-Check (`structural.py`) prüft gegen die Festigkeit bei Raumtemperatur;
`fatigue.py` ergänzt zyklisches Versagen. Beide übersehen eine dritte, langsame Lebensdauer-
Achse: ein Bauteil unter ruhender Last weit unter der Streckgrenze, aber heiß, verformt sich
stetig (Kriechen) und bricht nach genügend Zeit bei Temperatur — unsichtbar für jeden
isothermen Raumtemperatur-Check. Eine Turbinenschaufel, ein Kesselrohr, ein Bolzen im heißen
Flansch.

Drei geschlossene Formen: der **Larson-Miller-Parameter** `LMP = T·(C + log10(t_r))` (Zeit-
Temperatur-Äquivalenz, T in Kelvin, t_r in Stunden), seine **exakte Inverse**
`t_r = 10^(LMP/T − C)`, und das **Norton-Potenzgesetz** `ε̇ = A·σ^n·exp(−Q/RT)` für die
sekundäre (stationäre) Kriechrate. Plus ein DFM-Check `creep_life_check` mit
`safety_factor = rupture_time / design_life`.

**Verifiziert, nicht behauptet:** LMP und Inverse runden EXAKT zurück (`t_r → LMP → t_r`,
rel. Fehler 0..2e-16); Anker `T=811 K (~1000 °F), t_r=1e5 h, C=20 → LMP = 811·25 = 20275`;
Norton skaliert exakt als `(σ2/σ1)^n` (100→200 MPa, n=5 → Faktor `32.0 = 2^5`) und folgt dem
exakten Arrhenius-Verhältnis in T; `creep_life_check` liefert für `LMP=20275@811K` Bruchzeit
`1e5 h`, bei Auslegungsleben `1e4 h` → `safety_factor=10.0, ok=True`. 12 Tests grün (py 3.11 + 3.13).

**Ehrliche Grenze:** klassische Korrelationen für SEKUNDÄRES (stationäres) Kriechen und
Bruchzeit-Extrapolation; KEIN primäres/tertiäres Kriechen, keine Mehrachsigkeit, keine
Oxidation/Umgebung — und die Konstante C sowie die Master-Kurve LMP(σ) stammen aus echten
Werkstoff-Bruchdaten (das Modul rechnet damit, es erfindet sie nicht).
**Quelle:** Larson & Miller (1952), *A Time-Temperature Relationship for Rupture and Creep
Stresses*, Trans. ASME 74:765; Norton (1929), *The Creep of Steel at High Temperatures*.

---

## 34. Kerbermüdung — vom statischen Kerbfaktor zur Dauerfestigkeit (`notch_fatigue.py`)

Ein geometrischer Spannungssammler (`K_t` aus Bohrung, Hohlkehle, Nut, Gewinde) erhöht
statisch die Spitzenspannung — aber unter **zyklischer** Last wird die Dauerfestigkeit
**nicht** um den vollen `K_t` reduziert. Reale Werkstoffe zeigen **Kerbempfindlichkeit**
`q ∈ [0, 1]`: der steile Spannungsgradient an einer scharfen Kerbe lässt das Material die
Spitze teilweise „ausmitteln". Diese Schicht schlägt die Brücke von der statischen
Kerbgeometrie (§9 `K_t`) zur Hochzyklen-Lebensdauer (§28).

Drei geschlossene Formen (Peterson/Neuber): **Kerbempfindlichkeit** `q = 1/(1 + a/r)`
(`a` Werkstoffkonstante, `r` Kerbradius); **Kerbermüdungsfaktor** `K_f = 1 + q·(K_t − 1)`;
**kerbreduzierte Dauerfestigkeit** `Se_notched = Se/K_f`.

**Verifiziert, nicht behauptet:** Anker `K_t=3, r=1 mm, a=0.25 mm → q=0.8, K_f=2.6,
Se_notched=Se/2.6 = 76.92 MPa` (bei `Se=200`); stumpfe Kerbe `a/r→0 → q→1 → K_f→K_t`;
scharfe winzige Kerbe `a/r→∞ → q→0 → K_f→1`; `1 < K_f < K_t` für jedes endliche `r`.
10 Tests grün auf py 3.11 **und** 3.13.

**Ehrliche Grenze:** empirische Peterson-Kerbempfindlichkeit für stress-basierte
Hochzyklen-Ermüdung von Metallen; `q` ist ein **empirischer Fit**, und die Konstante `a`
(≈ 0,01..0,02 mm für Stähle) hängt vom Werkstoff ab und **muss geliefert werden** — das
Modul erfindet `a` nicht. `K_t` wird als bekannt vorausgesetzt (Diagramm/FEA). Keine
Niedrigzyklen-Plastizität, keine Bruchmechanik (§35), kein mehrachsiger Kerbzustand.
**Quelle:** R. E. Peterson, *Stress Concentration Factors* (Wiley 1974); Shigley & Budynas,
*Mechanical Engineering Design*, Kap. 6.

---

## 35. Bruchmechanik — der rissgetriebene Versagensfall (`fracture.py`)

Spannungscheck, `fatigue.py`, `buckling.py` und `torsion.py` sehen **keinen Riss**. Ein
Bauteil mit Fehler der Länge `a` versagt, wenn die Spannungsintensität `K = Y·σ·√(π·a)`
die Bruchzähigkeit `K_IC` erreicht (Sprödbruch weit unter Fließen); ein unterkritischer
Riss **wächst** pro Lastzyklus (Paris).

- Spannungsintensität `K = Y·σ·√(π·a)` (Irwin); Anker `Y=1, σ=100, a=1 → K=100√π =
  177.245 MPa·√mm`.
- Kritische Risslänge `a_c = (1/π)·(K_IC/(Y·σ))²` invertiert `K` exakt (`a_c` zurück →
  `K==K_IC` maschinengenau); Anker `K_IC=2000, Y=1, σ=100 → a_c=400/π = 127.324 mm`.
- `fracture_check` liefert `{stress_intensity, critical_crack_size, safety_factor=K_IC/K,
  ok}`.
- **Paris-Lebensdauer** (geschlossenes Integral, `m≠2`): `paris_life(C=1e-11, m=3, Δσ=100,
  a_i=1, a_f=10, Y=1.12) = 17480.85 Zyklen`, stimmt mit unabhängiger Trapez-Integration auf
  `2.96e-11`; größerer Anfangsriss → weniger Zyklen (`a_i=4 → 4698`). `m==2` wirft
  `NotImplementedError` statt eines falschen Werts. 14 Tests grün (py 3.11 + 3.13).

**Ehrliche Grenze:** Small-Scale-Yielding-LEFM eines idealen Durchrisses mit konstantem
Geometriefaktor `Y`. Kein elastisch-plastischer Bruch (J-Integral/CTOD), kein variierendes
`Y(a/W)`, kein `ΔK_th`-Schwellwert, keine Rissschließung/R-Verhältnis, nur Mode I.
`K`/`K_IC` in `MPa·√mm` (Handbuch meist `MPa·√m`; `1 MPa·√m ≈ 31.62 MPa·√mm`).
**Quelle:** G. R. Irwin, J. Appl. Mech. 24 (1957) — Spannungsintensität; P. C. Paris &
F. Erdogan, J. Basic Eng. 85 (1963) — `da/dN = C·(ΔK)^m`.

---

## 36. Plattenbiegung — die 2-D-Druckdurchbiegung eines flachen Panels (`plate_bending.py`)

Die Balken-/Stab-Schichten tragen Last entlang EINER Achse, die Druckbehälter-Schicht
(§32) eine Membranspannung in einer gekrümmten Schale. Keine sieht das Versagen einer
flachen Platte: ein Panel, ein Gehäusedeckel, eine Fensterscheibe, eine Leiterplatte, ein
Tankboden — am Rand eingespannt oder gelenkig gelagert und von gleichförmigem Druck `q`
belastet. Die Platte hat keine Achse zum Abtragen; sie muss in zwei Richtungen zugleich
BIEGEN und baut eine Biegespannung auf, die ein sprödes Fenster reißt oder einen dünnen
Deckel fließen lässt, lange bevor ein 1-D-Check warnt.

Geschlossene Kirchhoff-Formen für die KREISPLATTE (Radius R, Dicke t, Druck q):
Biegesteifigkeit `D = E·t³/(12(1−ν²))` (2-D-Analogon zu `E·I`, kubisch in t); EINGESPANNT
`w_max = q·R⁴/(64·D)` (Mitte), max. Spannung am RAND `σ = 3·q·R²/(4·t²)`; GELENKIG (weicher,
biegt MEHR) `w_max = (5+ν)·q·R⁴/(64·(1+ν)·D)`, max. Spannung in der MITTE
`σ = 3·(3+ν)·q·R²/(8·t²)`.

**Verifiziert** (py 3.11 + 3.13, 13 Tests): gelenkig biegt mehr als eingespannt, Verhältnis
`w_ss/w_clamped = (5+ν)/(1+ν) = 4.077` (ν=0,3); `D ∝ t³`, Durchbiegung `∝ R⁴` und `∝ 1/t³`;
Stahl-Anker `q=0.1 MPa, R=100 mm, t=5 mm → eingespannt w_max=0.065 mm, σ_max=30.0 MPa`
(gelenkig `0.265 mm`/`49.5 MPa`).

**Ehrliche Grenze:** linear-elastische KLEIN-Durchbiegungs-Theorie (Kirchhoff) einer dünnen,
flachen, isotropen KREISPLATTE unter GLEICHFÖRMIGEM Druck; keine großen Durchbiegungen (bei
`w ≈ t` versteift Membranwirkung → diese Formen ÜBERschätzen), keine rechteckigen Formen
(Roark-Seitenverhältnis), keine Punkt-/Teillasten, keine Lochspitzen.
**Quelle:** Timoshenko & Woinowsky-Krieger (1959), *Theory of Plates and Shells*, Kap. 3;
Young & Budynas, *Roark's Formulas for Stress and Strain* (flache Kreisplatte).

---

## 37. Schraubenvorspannung & Lastaufteilung — das Versagen, das die Nennspannung übersieht (`bolted_joint.py`)

Die Spannungsprüfung und der Schraubenschub-Check (§9) bemessen den Bolzen gegen die
**äußere** Last allein. Beide übersehen, was eine angezogene Schraube real tut: das
Drehmoment **spannt** sie auf Zug **vor** und klemmt die Fügeteile auf Druck. Unter dieser
Vorspannung **addiert** sich eine äußere Zuglast P nicht einfach — sie wird zwischen Schraube
und Fügeteilen nach ihren **Steifigkeiten** aufgeteilt: die Schraube sieht nur den Bruchteil
`C` von P, während die Klemmkraft sinkt. Zwei Dinge gehen schief, die `P/A_t` verfehlt: die
vorgespannte Schraube ist viel näher an der Streckgrenze (`F_i + C·P ≫ P`), und die
Verbindung kann sich **öffnen** (Separation) — die Teile verlieren jede Klemmung.

Fünf Geschlossenformen (Shigley/VDI 2230): Vorspannung `F_i = T/(K·d)` (Nut-Faktor `K≈0.2`);
Steifigkeitsfaktor `C = k_b/(k_b+k_m)` (Schrauben-Lastanteil, in `[0,1]`); Schraubenlast
`F_bolt = F_i + C·P`; Separationslast `P_sep = F_i/(1−C)` (wo `F_m = F_i − (1−C)·P` Null
erreicht). Plus `bolted_joint_check`: `bolt_stress`, `separation_margin`, `yield_safety`,
`ok` nur wenn **weder** Separation **noch** Fließen.

**Verifiziert:** Anker `T=10000 N·mm, d=10, K=0.2 → F_i=5000 N`; `k_b=k_m → C=0.5`,
`F_i=5000 → P_sep=10000 N`; `F_m=0` exakt bei `P=P_sep`. Beispiel `T=50000 N·mm, A_t=58 mm²,
P=10000 N, k_b=1, k_m=2, S_p=640 MPa → F_i=25000 N, C=1/3, σ_bolt=488.5 MPa, P_sep=37500 N,
ok`. **Eingebaute Einsicht:** naive `P/A_t=172.4 MPa` unterschlägt die Vorspannung, die wahre
`(F_i+C·P)/A_t=488.5 MPa` ist `2.83×` höher; `P=40000>P_sep → ok=False`. 20 Tests grün
(py 3.11 + 3.13).

**Ehrliche Grenze:** statische, linear-elastische Lastaufteilung einer **konzentrisch**
belasteten, vorgespannten Verbindung (Standard-Federmodell). NICHT: Drehmoment-Streuung (`K`
schwankt ~±25 % → `F_i` ist eine Schätzung), exzentrische/abhebelnde Lasten, Setzen/Kriechen
(Vorspannverlust), Schraubenermüdung (dafür `fatigue.py` auf `C·P/2`), Lochleibung; `k_m`
(Rotscher/VDI-Kegel) wird als Eingabe genommen.
**Quelle:** Shigley & Budynas, *Mechanical Engineering Design* (`C = k_b/(k_b+k_m)`,
`F_b = F_i + C·P`, `P_0 = F_i/(1−C)`); VDI 2230; `T = K·F_i·d`.

---

## 38. GATE δ-Physik — die Validatoren werden zur Engine (`physics_validation.py`)

Die §§9–37 liefern je **einen** Validator für **einen** Versagensmodus, isoliert. Diese
Schicht ist das **Gate**, das sie in die Pipeline verdrahtet: eine **Validator-Registry**
(`VALIDATORS`, aktuell **13** — Torsion, Knicken, Ermüdung, Kontakt, Druckbehälter, Kriechen,
Übertemperatur, Thermo-Mismatch, Resonanz, Kerbermüdung, Bruch, Platte, Schraube) plus
`gate_delta_physics(checks)`, das eine Liste deklarierter `PhysicsCheck`s (Validator-Name +
aufgelöste numerische Inputs) ausführt und **ein** `GateResult` zurückgibt.

Es trägt die Anti-Halluzinations-Disziplin in die Physik-Schicht — drei **harte**
Fehlermodi, **nie** ein stiller Pass:
- `PHYSICS_UNKNOWN_VALIDATOR` — ein Check nennt einen Validator, für den **kein Code**
  existiert: das Gate zertifiziert nichts, was es nicht rechnen kann.
- `PHYSICS_CHECK_ERROR` — der Validator **wirft** auf seinen Inputs (widersprüchliche
  Geometrie/Material): die nicht-rechenbare Prüfung wird **gemeldet**, nicht verschluckt.
- `PHYSICS_CHECK_FAILED` — der Validator rechnet, aber die Marge ist nicht erfüllt
  (mit Sicherheitsfaktor als Evidenz).

Das Verdikt ist damit **konstruktiv ehrlich**: das Gate besteht ein Design nur, wenn jeder
deklarierte Check **wirklich gerechnet** wurde und seine eigene Marge hielt. Eine leere Liste
besteht vakuös (nichts deklariert → nichts kann versagen) — das Pendant dazu, dass die
Spec-Gates eine leere Spezifikation bestehen. Der `PhysicsCheck` trägt **aufgelöste** Werte,
genau wie die Spec-Gates auf deklarierten `Quantity`s operieren: in der vollen Pipeline emittiert
ein Agent die Checks aus der Spezifikation (quantity_ids → Werte, wie Derivations aufgelöst
werden), und dieses Gate ist der deterministische, LLM-freie Backstop, der sie nachrechnet.

**Verifiziert** (8 Tests, py 3.11 + 3.13): alle-ok → `passed`; ein versagender Check → `not
passed` + `PHYSICS_CHECK_FAILED`; unbekannter Validator → `PHYSICS_UNKNOWN_VALIDATOR`; ein
werfender Validator (Durchmesser 0) → `PHYSICS_CHECK_ERROR` (kein stiller Pass); gemischter
Batch meldet **jeden** distinkten Fehlercode; leere Liste besteht vakuös; `run_physics_checks`
liefert die Evidenz (gerechnete Sicherheitsfaktoren) pro Check.

**Ehrliche Grenze:** das Gate rechnet die deklarierten Checks nach; die **autonome Auswahl**
aus der Spezifikation liefert §39. Modul `physics_validation.py`, getestet in
`tests/test_physics_validation.py`.

---

## 39. Auto-Select — die Spec wählt ihre Checks selbst (`physics_selection.py`)

§38 rechnet eine Liste deklarierter `PhysicsCheck`s nach — aber jemand muss die Liste
**bauen**. Diese Schicht baut sie **aus der Spezifikation**, sodass das Gate seine Checks
**selbst** wählt. Es ist das deterministische, LLM-freie Pendant zum Derivation-System: wo
eine `Derivation` Quantities per `quantity_id` referenziert, referenziert ein `CheckRecipe`
sie per deklariertem **`measurand`**-Tag — genau die explizite, **nicht** geratene Verknüpfung,
die GATE γ C-17 schon nutzt, um zu beweisen, dass zwei Quantities sich nicht widersprechen.

Jedes Rezept deklariert einen **Trigger**-Measurand (dessen Anwesenheit bedeutet, dass das
Design diese Physik hat — `"shaft.torque"` ⇒ es gibt eine Welle in Torsion) und den
Measurand+Einheit jeder Validator-Eingabe. `select_physics_checks(spec)`:
- **überspringt** ein Rezept ohne Trigger — das Design hat diese Physik schlicht nicht (kein
  Check, **keine Lücke**: Stille ist hier korrekt);
- **emittiert** einen fertigen `PhysicsCheck`, wenn der Trigger da ist und **jede** Eingabe
  auflöst — wobei jede Quantity **einheiten-korrekt konvertiert** wird (saubere Konversion via
  `units.py`, kein stilles Magnituden-Raten);
- **meldet eine Lücke**, wenn der Trigger da ist, aber eine Eingabe fehlt, dimensional
  unverträglich oder in opaker Einheit ist — ein **indizierter-aber-nicht-rechenbarer** Check
  wird gemeldet, nie still verworfen und nie mit falscher Einheit gefüttert.

So ist die Auswahl **konstruktiv ehrlich**: eine vom Spec deklarierte Physik-Sorge wird
entweder ein echter, einheiten-korrekter Check **oder** eine explizite Lücke.
`evaluate_spec_physics(spec)` macht den ganzen Fluss: selektieren → GATE δ-Physik laufen →
`{gate, checks, gaps}`.

**Verifiziert** (7 Tests, py 3.11 + 3.13): eine Welle+Ermüdungs-Spec liefert genau die
`{torsion, fatigue}`-Checks und das Gate besteht; ein in **`N·m`** deklariertes Drehmoment
erreicht den Validator **einheiten-korrekt als `5000 N·mm`** (×1000); fehlende
`material.shear_strength` bei vorhandenem `shaft.torque` → **Lücke** (kein stiller Drop);
ein Durchmesser in `kg` → **Lücke** („not dimensionally mm"); kein Trigger → **nichts**;
ein selektierter aber **versagender** Check (Schub 3,18 MPa > Festigkeit 2 MPa) lässt das
Gate **scheitern** (`PHYSICS_CHECK_FAILED`).

**Ehrliche Grenze:** das Rezept-Katalog (`RECIPES`, aktuell 6: Torsion, Ermüdung, Knicken,
Druckbehälter, Resonanz, Kerbermüdung) ist **erweiterbar** — ein neuer Validator wird
auto-wählbar durch ein neues Rezept. Nicht-Quantity-Konfiguration (Lagerungsfall, Wandmodell)
nutzt vorerst deklarierte Defaults im Rezept (`extra`); ihre Herleitung aus Spec-`Decision`s
ist der nächste Schliff. Modul `physics_selection.py`, getestet in
`tests/test_physics_selection.py`.

---

## 40. End-to-End auf einer echten Spec — die Antriebswelle (`demo.drive_shaft_spec`)

Der Capstone-Halter ist ein **statisches** Flachteil, dessen Spannung/Schub bereits die
γ-Constraints prüfen — die δ-Physik-Validatoren (Torsion/Knicken/Resonanz…) passen darauf
**nicht**; sie ihm aufzuzwingen wäre unehrlich. Der ehrliche End-to-End-Beweis läuft daher
auf einer **zweiten realen Spec** (wie `protocol_spec` die Bio-Domäne zeigt): eine
**rotierende Antriebswelle**, deren `Quantity`s mit `measurand`-Tags versehen sind, sodass
die ganze Kette von §39→§38 ohne Handarbeit greift.

`evaluate_spec_physics(drive_shaft_spec())` **wählt aus der Spec genau die drei zutreffenden
Checks** — Torsion (`shaft.torque`), Rotationsbiege-**Ermüdung** (`fatigue.stress_amplitude`),
Whirl-**Resonanz** (`vibration.excitation_frequency`) — und **keine** unpassenden (kein
`column.axial_load` → kein Knicken, kein `vessel.pressure` → kein Druckbehälter, kein
`notch.kt` → keine Kerbermüdung). Das in `N·m` deklarierte Drehmoment erreicht den Validator
**einheiten-korrekt als `150000 N·mm`**. Verdikt **bestanden, 0 Lücken**, mit gerechneten
Sicherheitsfaktoren als Evidenz: Torsion `5.32` (`τ_max=16T/(πd³)≈48.9 MPa` vs `260 MPa`),
Ermüdung `3.23` (Goodman `1/(80/290+20/585)`), Resonanz `3.00` (`150 Hz` über `50 Hz`
Betriebsdrehzahl). Material-Eigenschaften sind in Claims **gegroundet** (wie beim Halter), die
Auslegungs-Eingaben deklarierte Entscheidungen; deklarierte `gaps` (Passfedernut-Kerbe,
Lagerlebensdauer, Kupplung) bleiben ehrlich offen.

Damit ist die δ-Physik-Engine **durchverdrahtet bewiesen**: von measurand-getaggten
Spec-Quantities über die autonome Check-Auswahl und das ehrliche Gate bis zum Verdikt mit
Beweiskette — deterministisch, LLM-frei, gegen Closed-Form verifiziert.

**Verifiziert:** 5 Tests (py 3.11 + 3.13), `demo.py`-Ergänzung rein additiv (kein
Bestands-Gate-Test berührt). Spec `demo.drive_shaft_spec`/`drive_shaft_state`, getestet in
`tests/test_drive_shaft_physics.py`.

---

## 41. Eval-Harness Multi-Gate — die Garantie wird gemessen, auch für δ-Physik (`evaluation.py`)

Die VISION verlangt, dass die Anti-Halluzinations-Garantie **gemessen** wird, nicht behauptet
— und SOTA-Faktualität (FActScore, HalluLens, ACL 2025) misst Diskriminierung über kuratierte
**sound/unsound**-Sätze. `evaluation.py` aggregiert die Gates zu **einer** Metrik über solche
Fälle: passt das Gate **jeden** soliden Fall (inkl. ehrlicher Abstention) und failt es **jeden**
unsoliden? Die nicht-verhandelbare Zahl ist **`leaks == 0`** (kein Halluzinations-Leck rutscht
durch); dazu die `false_alarms` (Über-Blockieren).

**Erweiterung (dieser Schritt):** das Harness ist jetzt **Multi-Gate**. Neben dem γ-Gate
(7 Fälle, je eine Halluzinations-Klasse: C-4 erfundener Preis, C-6 gebrochene Derivation, C-2
Wert in fehlendem Claim, C-17 Faktenwiderspruch, C-15 Dimensionsunsinn, + Capstone + Abstention)
misst es nun auch das **δ-Physik-Gate** (§38): eine **solide** Antriebswelle besteht; eine
**überbeanspruchte** Welle (`d=5 mm` → `τ ≈ 6112 MPa ≫ 260`) **muss gefangen** werden
(`PHYSICS_CHECK_FAILED`); eine **widersprüchliche** Geometrie (`d=0`) **muss aufgedeckt** werden
(`PHYSICS_CHECK_ERROR`), nie still bestanden. Plus **Raten-Metriken**: `leak_rate` (False-Accept
der Garantie, Nenner = Anzahl unsolider Fälle) und `false_alarm_rate`.

**Verifiziert** (10 Fälle über beide Gates, py 3.11 + 3.13): `10/10 correct`, **`leaks = 0`
(rate 0 %)**, `false_alarms = 0`. Jeder unsolide δ-Physik-Fall failt das Gate, jeder solide
besteht. Offline, LLM-frei — gemessen wird die **deterministische Diskriminierung** der Gates,
nicht Live-Modell-Qualität (das braucht die aufgeschobenen, gemessenen Modell-Läufe).

**Ehrliche Grenze:** dies ist die **Offline-Gate-Diskriminierungs-Schicht** der Eval-Achse.
Die FActScore-artige atomare Claim-Bewertung gegen ein Gold-Set und die HalluLens-Nonsense→
Abstention-Prüfung auf **Live**-Pipeline-Läufen sind der nächste Teil — sie brauchen gemessene
Modell-Läufe (per Owner-Direktive bis „real-use ready" aufgeschoben). Modul `evaluation.py`,
getestet in `tests/test_evaluation.py`; CLI `python -m gen --mode eval`.

**Quelle:** FActScore (Min et al. 2023, atomare Claim-Zerlegung); HalluLens (ACL 2025,
LongWiki/PreciseQA/Nonsense); *Trust but Verify — Survey on Verification Design* (arXiv
2508.16665): „combine multiple verification signals", „integrate symbolic/formal methods".

---

## 17. ε-Software — Korrektheit per AUSFÜHRUNG (`gate_code`)

Jede andere Schicht **rechnet einen deklarierten Wert nach** (Formel, AABB, Netz).
Software hat den **stärksten** deterministischen Validator überhaupt: **ausführen.**
Ein `CodeArtifact` ist `source` + ein `check`; `gate_code` führt beides in einem
**isolierten Subprozess** (`python -I`) mit hartem Timeout aus und besteht nur,
wenn der Prozess mit 0 endet — **kein Modell-Urteil, die Maschine entscheidet.**
Das ist die reinste Form von „validieren vor dem Bauen": hier **ist** Bauen
Ausführen, und Validierung ist empirische Ausführung. Deterministisch, offline,
kein LLM.

| Code | Defekt |
|---|---|
| `UNSUPPORTED_LANGUAGE` | Sprache ohne lokale Runtime (nur Python läuft deterministisch hier) — **gemeldet, nicht gefaked** |
| `CODE_TIMEOUT` | der Check überschritt das Zeitlimit |
| `CODE_CHECK_FAILED` | Prozess ≠ 0 (fehlgeschlagene Assertion, Syntaxfehler, Exception) → Deliverable kaputt |

**Capstone:** ein echter Software-Baustein — `led_resistance(v,a)=v/a`, der genau
den Arbeitspunkt-Widerstand berechnet, den die DC-Analyse (§15) nutzt — wird **real
ausgeführt** (3 Assertions inkl. Guard für i≤0) und besteht. **Zähne** (je ein
Test): fehlschlagende Assertion → `CODE_CHECK_FAILED`; Syntaxfehler → dito; C statt
Python → `UNSUPPORTED_LANGUAGE`. Der Capstone läuft jetzt durch **vier** Gates:
γ + δ + ERC + CODE.

**Ehrliche Grenze:** ein **bestandener** CODE-Check heißt „kompiliert + die
deklarierten Checks bestehen" — für das geprüfte Verhalten **hinreichend**, beweist
aber nicht, dass die Checks selbst vollständig sind. Nur Python hat hier eine
garantierte Runtime; andere Sprachen brauchen ihre Toolchain. **Sicherheit:** spec-
gelieferten Code auszuführen ist ein Sandbox-Thema; isolierter Subprozess + Timeout
ist eine pragmatische Grenze, **keine** gehärtete Sandbox — ein Produktions-Deploy
gehört in eine echte Sandbox (`rules/95`). Modul `software.py` + `gate_code`,
getestet in `tests/test_software.py`.

**Quelle:** Test-/Ausführungs-getriebene Validierung ist der Goldstandard
deterministischer Software-Verifikation (CI/CD; „the build is green"); GENESIS
hebt sie auf Spec-Ebene.

---

## 18. Monte-Carlo-Unsicherheit (GUM-Supplement 1, JCGM 101)

Die First-Order-GUM (§12) linearisiert — exakt für Summen/Produkte, **Näherung**
sonst. JCGM 101 ersetzt die Linearisierung durch eine **Monte-Carlo-Simulation**:
jeden Eingang aus seiner Verteilung ziehen, jeden Sample durch das Modell schieben,
die Ausgangsverteilung direkt ablesen (Mittel, Standardunsicherheit, Überdeckungs-
intervall). Erfasst **Nichtlinearität** (inkl. der Mittelwert-Verschiebung, die
First-Order übersieht) und nicht-gaußsche Ausgänge. `montecarlo.py` (numpy).

**Deterministisch:** der Sampler ist **geseedet** (fester Default-Seed) → gleiche
Eingänge, gleiches Intervall (Reproduzierbarkeit, CLAUDE.md §5). Offline, kein LLM.

**Verifiziert gegen First-Order:** wo das Modell **linear** ist, **stimmt** MC mit
der First-Order-GUM überein (`F=m·g`: MC-Std 4,894 ≈ GUM 4,903 — der Kreuz-Check).
Wo es **nichtlinear** ist, zeigt MC was First-Order nicht kann: `y=x²` mit
`x=10±1` hat wahren Mittelwert `E[x²]=100+Var=101`, nicht 100 — **MC findet die
+1-Verschiebung**, die lineare Methode lässt den Wert bei 100.

**Korrelierte Eingänge (`montecarlo_correlated`):** gemeinsames Sampling aus
`N(values, Σ)` mit Kovarianz `Σ_ij = u_i·u_j·ρ_ij`. **Verifiziert:** für `a+b` mit
ρ=1 addieren sich die Varianzen **linear** (std = u_a+u_b = 7, **nicht** Quadratur
5); für `a−b` mit ρ=1 **heben** sie sich teilweise auf (std = |u_a−u_b| = 1). Das
ist real wichtig — z. B. ein Spiel `Loch−Welle`, wenn beide vom selben Prozess
korreliert sind.

**Ehrliche Grenze:** gaußsche Eingänge (jetzt auch **korreliert**), feste Sample-
Zahl (Intervall trägt MC-Fehler ~1/√N); nicht-gaußsche Priors sind eine weitere
Erweiterung. Modul `montecarlo.py`, getestet in `tests/test_montecarlo.py`.

**Quelle:** GUM Supplement 1 / JCGM 101:2008 (Monte-Carlo-Fortpflanzung von
Verteilungen).

---

## 19. ε-Bio — Protokoll mit Reproduzierbarkeits-Design + Sicherheitsgrenzen

Die zweite ε-Domäne realisiert das **VISION-Beispiel** („wie lassen sich Pflanzen
nachweislich gesünder wachsen?") — über die **gleiche γ-Maschinerie** wie der
Halter, nur in einer völlig anderen Domäne: belegte Werte, eine **Sicherheits-
grenze als Constraint** (C-13), Einheiten (C-15). Der **neue** bio-spezifische
Beitrag ist `gate_protocol`: der **Reproduzierbarkeits-Design-Check**, der genau
die Lücke adressiert, die die Reproduzierbarkeitskrise treibt (unvollständige
Designs ohne Kontrolle/Replikate).

| Code | Defekt |
|---|---|
| `MEASURE_WITHOUT_CONTROL` | misst ein Ergebnis, hat aber **keine Kontrollgruppe** (keine Baseline) |
| `CONTROL_NOT_IN_GROUPS` | die benannte Kontrolle ist nicht unter den Gruppen |
| `TOO_FEW_GROUPS` | ein gemessenes Ergebnis braucht ≥ 2 Gruppen (Treatment + Kontrolle) |
| `INSUFFICIENT_REPLICATES` | < `MIN_REPLICATES` (3) Replikate — kein reproduzierbarer Schluss |

**Demo (`python -m gen --mode protocol`):** Pflanzenwachstum, Nährlösung 150 g/m³
**unter** der belegten phytotoxischen Schwelle 200 g/m³ (Sicherheits-Constraint
`k_safe`, C-13), Treatment+Kontrolle, 5 Replikate, blind gemessen → γ + PROTOCOL
bestanden. **Zähne** (je ein Test): keine Kontrolle → `MEASURE_WITHOUT_CONTROL`;
2 Replikate → `INSUFFICIENT_REPLICATES`; Überdosis 250 g/m³ → `CONSTRAINT_VIOLATION`
(über die bestehende C-13, **kein** neuer Code).

**Ehrliche Asymmetrie:** ein **bestandener** PROTOCOL-Check heißt „das Design
**kann** prinzipiell einen reproduzierbaren quantitativen Schluss tragen", nicht
dass das Experiment gelingt — GENESIS **spezifiziert** das Experiment, führt es
nicht durch (als Gap deklariert). `MIN_REPLICATES=3` ist eine deklarierte,
dokumentierte Schwelle (Minimum für elementare Statistik). Modul `gate_protocol` +
`ExperimentDesign`, getestet in `tests/test_protocol.py`.

**Quelle:** Reproduzierbarkeits-Krise + Kontroll-/Replikat-Design (Standard-
Experimentalmethodik); maschinenlesbare Protokolle mit Parameter-Sicherheitsgrenzen
(Autoprotocol/BioCoder; formal-semantische Protokolle, arXiv 1710.08016).
