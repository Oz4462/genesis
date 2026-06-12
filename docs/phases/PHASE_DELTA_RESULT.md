# PHASE δ — RESULT (ehrlich)

> Erste beweisbare δ-Schicht: deterministische Geometrie-Validierung. Format wie
> die α/β/γ-RESULT-Dateien. Keine Schönfärberei.

> **Hinweis (historischer Snapshot):** Dieses RESULT dokumentiert die *erste*
> δ-Schicht (Stand damals: 318 Tests). δ wurde seitdem zur vollen deterministischen
> Physik-Engine ausgebaut — 13 Validatoren, δ-Physik-Gate, Auto-Select,
> Quality-Engine, Web-UI. Aktueller Stand und alle Schichten: `PHASE_DELTA.md`
> (§1–§51) und das README.

## Zusammenfassung

Phase δ (Validierung vor dem Bauen) hat ihre **erste beweisbare Schicht** als Code
erbracht: deterministische **geometrische Soundness** des CSG-Modells über die
achsenparallele Bounding-Box (AABB). δ liest die γ-validierte Spezifikation und
fügt nur Validierung hinzu — α/β/γ bleiben unberührt.

```
pytest -q  ->  318 passed (0.75s, ohne LLM-Token, ohne Netzwerk)
```

(290 vorherige + 28 δ: 20 AABB-Geometrie/Volumen, 8 GATE-δ.)

**Erweitert:** deterministische **Volumen-Eigenschaft** (`volume_of`) — exakt-wo-
beweisbar, sonst sound obere Schranke; im CLI-δ-Abschnitt sichtbar. Siehe Abschnitt
„Volumen" unten.

Zentrale δ-Invariante (α→β→γ→δ-Kette): **keine nachweislich tote oder leere
Geometrie-Operation bleibt unbemerkt — und δ behauptet kein Urteil, das es nicht
beweisen kann.** Die Ehrlichkeit kommt aus der AABB-Asymmetrie: disjunkte
Bounding-Boxes ⟹ Festkörper überlappen **beweisbar nicht** (δ darf melden,
**keine False Positives**); überlappende Boxes ⟹ vielleicht (δ meldet nichts).

Sichtbar: `python -m gen --demo --mode spec` zeigt jetzt einen Abschnitt
„Geometric validation (δ)" mit der Hüllbox (`c_bracket envelope: 60 x 80 x 6`) und
dem ehrlichen Status (`PASS — necessary, not sufficient`).

## Akzeptanzkriterien (PHASE_DELTA.md §5)

| # | Kriterium | Status | Beleg |
|---|---|---|---|
| D1 | Soundness (keine False Positives) | **ERFÜLLT** | δ meldet nur disjunkte AABBs; `overlaps` ist der exakte Achsentest; `test_thin_wall_still_passes…`, `test_valid_bracket_passes` |
| D2 | Totes difference gefangen | **ERFÜLLT** | `DEAD_OPERATION` bei Loch außerhalb des Körpers; `test_hole_that_misses_the_part_is_dead` |
| D3 | Leeres intersection gefangen | **ERFÜLLT** | `EMPTY_INTERSECTION`/`EMPTY_GEOMETRY_TREE` bei disjunkten Teilen; `test_intersection_of_disjoint_parts_is_empty` |
| D4 | Degenerierte Geometrie gefangen | **ERFÜLLT** | `DEGENERATE_GEOMETRY` bei 0-Achse; `test_zero_axis_is_degenerate` |
| D5 | Envelope korrekt | **ERFÜLLT** | Hüllbox = analytische Maße (zentrierte Konvention); `test_envelope_reports_extent`, `test_union_is_envelope` |
| D6 | γ unberührt | **ERFÜLLT** | δ liest nur `state.specification`; alle 290 vorherigen Tests grün |
| D7 | Ehrliche Grenze | **ERFÜLLT** | dünne Wand besteht δ (kein Festigkeitsurteil); CLI-Zeile „no physics judgement"; `test_thin_wall_still_passes_delta_makes_no_strength_claim` |

**D1 und D7 — die wichtigsten — bestehen.**

## Ergebnis je Klasse (PHASE_DELTA.md §6)

| Klasse | Geometrie | Verhalten | Erwartet | OK |
|---|---|---|---|---|
| A valide | box ∖ zentrierter cylinder | bestanden, Envelope = box | pass | ✅ |
| B totes Loch | difference(box, translate(weit, cyl)) | `DEAD_OPERATION` | flag | ✅ |
| C leeres ∩ | intersection disjunkter Boxen | `EMPTY_INTERSECTION`/`EMPTY_GEOMETRY_TREE` | flag | ✅ |
| D degeneriert | box mit 0-Achse | `DEGENERATE_GEOMETRY` | flag | ✅ |
| E Envelope | union versetzter Boxen | Hüllbox = analytische Min/Max | exakt | ✅ |
| Ehrlichkeit | dünne, aber valide Wand | **bestanden** (kein Physik-Urteil) | pass | ✅ |

## Drift-/Konsistenz-Fund (im Audit gefangen + behoben)

Beim Bau von δ aufgefallen: die AABB-Mathematik nutzt **zentrierte** Primitive
(wie build123d), während der OpenSCAD-Exporter Primitive mit Ecke/Basis am
Ursprung emittierte (OpenSCAD-Default). Für δs **relative** Überlapp-Checks und
für **Größen** war das folgenlos, aber für **absolute Platzierung** (translate)
wäre das gerenderte OpenSCAD-Modell vom δ-angenommenen abgewichen. **Root-Cause-Fix
(kein Workaround):** OpenSCAD emittiert jetzt `cube([...], center=true)` und
`cylinder(..., center=true)`. Damit teilen δ, build123d und OpenSCAD **eine**
zentrierte Konvention. Beide OpenSCAD-Erwartungs-Strings entsprechend aktualisiert,
alle Tests grün.

## Methodik + ehrliche Grenze

Deterministische Geometrie, kein LLM, kein Netz — die Gate-first-Methodik aus
α/β/γ. **Ehrliche Grenze (nicht verhandelbar):** δ ist die *geometrische* Schicht
der Validierung. Es beweist Nicht-Überlapp (tote/leere Operationen) und berechnet
Hüllboxen exakt. Es trifft **kein** Urteil über Festigkeit, Herstellbarkeit,
Toleranzen, Material oder reale Funktion — das sind spätere δ-Schichten mit echten
Modellen (FEM/CFD/Toleranzanalyse), die denselben Beweis-Standard tragen werden.
Ein **bestandenes** δ ist eine **notwendige**, keine hinreichende Bedingung für
eine baubare Lösung. Genau diese Asymmetrie macht δ GENESIS-konform: nur behaupten,
was beweisbar ist.

## Volumen (deterministische Eigenschaft, `volume_of`)

Eine reale Materialmengen-Größe, berechnet **vor** dem Bauen — mit derselben
Ehrlichkeit wie δ selbst: `value` ist **immer eine sound obere Schranke**,
`exact=True` nur wo beweisbar. Primitive exakt (box/cylinder/sphere,
Standardformeln); `translate` erhält; **union** exakt bei paarweise disjunkten
Kindern (sonst Σ als Schranke); **difference** exakt nur bei Box-Minuend +
enthaltenen, paarweise disjunkten Werkzeugen (sonst vol(Minuend) als Schranke);
**intersection** min(Teile) als Schranke. Der häufige „Loch im Block" ist exakt
(Box-Solid = AABB ⟹ AABB-Enthaltensein = Solid-Enthaltensein).

**Belege:** `test_geometry.py` (7 Volumen-Tests: exakte Primitive, translate-
erhält, exaktes Loch-im-Block, disjunkte-union-exakt, überlappende-union-Schranke,
unenthaltenes-difference-Schranke, Nicht-Box-Minuend-inexakt). Demo:
`c_bracket volume: 28704.6 mm³ (exact)`.

**Ehrliche Grenze:** Bei überlappender/unenthaltener/Schnitt-Geometrie nur eine
obere Schranke (nie als exakt ausgegeben). Einheit nur gezeigt, wenn eindeutig.

## Masse (`mass_of`) + sound Einheiten-Skalierung (`unit_scale`)

`Component.material_density` (quantity_id einer Dichte) ⟹ `masse = volumen ×
dichte`, **sound einheiten-konvertiert**. Neu in `units.py`: `unit_scale(unit)`
gibt den Faktor zur SI-Basis (compound-fähig: `g/cm³`→1e3, `mm`→1e-3; unbekanntes
Atom→None). Damit rechnet `mm³ × g/cm³` korrekt (`(mm/cm)³ = 1e-3`) statt still
falsch. `mass_of` prüft: Dichte-Dimension = mass/length³, Geometrie-Längeneinheit
eindeutig, alle Einheiten bekannt — sonst `value=None` + Grund (nie geraten).
Ausgabe in Gramm. **Belege:** `test_units.py` (unit_scale: Basis/Prefix/compound/
unknown/Ratio), `test_geometry.py` (Masse: konsistente Einheit, mm³×g/cm³-Konversion,
ohne Dichte→None, Nicht-Dichte-Einheit→None, unbekannte Einheit→None),
`test_gate_gamma.py` (material_density dangling + resolved). Demo:
`c_bracket mass: 35.5937 g (exact)` (PLA 0.00124 g/mm³ × 28704.6 mm³).

## Phase δ: Fazit

Die erste δ-Schicht — *deterministische geometrische Soundness, validiert vor dem
Bauen, ohne ein Physik-Urteil zu erfinden* — ist als Code erbracht und getestet,
auf dem bewiesenen α/β/γ-Fundament. Der nächste ehrliche Schritt: weitere
δ-Schichten mit echten Modellen (Toleranz/Passung deterministisch; FEM/CFD hinter
Adaptern, sobald Modelle verfügbar sind), jede unter demselben Beweis-Standard.
