# PHASE δ — RESULT (ehrlich)

> Erste beweisbare δ-Schicht: deterministische Geometrie-Validierung. Format wie
> die α/β/γ-RESULT-Dateien. Keine Schönfärberei.

## Zusammenfassung

Phase δ (Validierung vor dem Bauen) hat ihre **erste beweisbare Schicht** als Code
erbracht: deterministische **geometrische Soundness** des CSG-Modells über die
achsenparallele Bounding-Box (AABB). δ liest die γ-validierte Spezifikation und
fügt nur Validierung hinzu — α/β/γ bleiben unberührt.

```
pytest -q  ->  311 passed (0.78s, ohne LLM-Token, ohne Netzwerk)
```

(290 vorherige + 21 δ: 13 AABB-Geometrie, 8 GATE-δ.)

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

## Phase δ: Fazit

Die erste δ-Schicht — *deterministische geometrische Soundness, validiert vor dem
Bauen, ohne ein Physik-Urteil zu erfinden* — ist als Code erbracht und getestet,
auf dem bewiesenen α/β/γ-Fundament. Der nächste ehrliche Schritt: weitere
δ-Schichten mit echten Modellen (Toleranz/Passung deterministisch; FEM/CFD hinter
Adaptern, sobald Modelle verfügbar sind), jede unter demselben Beweis-Standard.
