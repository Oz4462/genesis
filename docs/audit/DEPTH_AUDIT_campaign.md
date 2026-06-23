# Depth-Audit: `src/gen/discovery/campaign.py`

**Datum:** 2026-06-23
**Auditor-Task:** T01 — Depth-audit + harden campaign.py (learned-prior + cross-domain composition)
**Verdikt: REAL** — `run_campaign` komponiert die Teile echt; keine Quellenänderung nötig.

## Was geprüft wurde
`run_campaign` behauptet, drei Bausteine im echten Fluss zu KOMPONIEREN statt sie zu faken:
die ledger-gelernte `ConceptUtility`-Prior, das MAP-Elites-`EliteArchive` und den SciAgents-
Cross-Domain-Vorschlag mit dimensionalem Typ-Filter. Der Audit testet jede Behauptung als
Facade-Detektor (`tests/test_campaign_characterization.py`, 10 Tests + 1 Property-Test), indem er
beweist, dass die Ausgabe sich mit den treibenden Eingaben ÄNDERT und die ehrlichen
Abstention-Pfade leer bleiben (kein erfundenes Ergebnis).

## Befunde (4 Linsen)

### L1 — Wahrheit / Korrektheit
- **Prior akkumuliert echt aus dem Gate-Ledger.** `prior = ConceptUtility.fit(ledger)` wird nach
  JEDEM Problem aus `result.all_records` (bestanden UND verworfen) neu gefittet und ins nächste
  `discover_new_formulas(..., prior=prior)` durchgereicht (campaign.py:69–73). Beweis:
  - Ein NUR-bestanden-Lauf (`[pendel, fläche]`) liefert die **neutrale, leere** Prior
    (`utility('var:L') == 0.0`, `score(best) == 0.0`) — eine kontrastive Utility braucht beide
    Verdikt-Seiten (concept_utility.py:72 `if n_pos and n_neg`).
  - Ein gemischter Lauf (`+` ein fail-Fall `v=g·t+v0`, `unentschieden`) liefert eine **nicht-neutrale**
    Prior: `utility('var:L') > 0` (ein nur auf der Pass-Seite gesehenes Konzept) und
    `score(best) > 0 != empty_prior.score(best)`. Entfernt man den fail-Fall, kollabiert die Prior
    wieder auf neutral — sie REAGIERT also auf das akkumulierte Ledger, ist nicht gecannt.
- **`validated_count` + `coverage` spiegeln echte bestätigte Gesetze.** Zwei strukturell distinkte
  Pass-Gesetze füllen genau 2 MAP-Elites-Zellen (`coverage == 2`, `len(elites) == coverage`),
  `validated_count >= 2`, `best().r_squared > 0.99`; der fail-Fall trägt zu beidem 0 bei
  (Archiv-Invariante: nur Gate-Pässe rein, archive.py:39–50).
- **Cross-Domain-Hypothesen sind echt dimensional gefiltert.** Mit erreichbarem Ziel (`"s"`) sind sie
  nicht-leer, und JEDE Gruppierung ist — unabhängig im Test über `dimensional_power_law` nachgerechnet
  — dimensional machbar (Residuum < `DIMENSION_TOLERANCE`). Property-Test: das gilt für jeden Seed.

### L2 — Drift (Doc vs. Code)
Kein Drift. Der Docstring verspricht „nur Ordnung, keine Korrektheit" für die Prior — der Code nutzt
sie ausschließlich als tertiären Tie-Breaker in `discover_new_formulas._key` (engine.py:449–452); das
Gate bleibt alleinige Autorität. Cross-Domain-Hypothesen werden korrekt als HYPOTHESEN (Gate-Inputs)
und nie als Findings ausgegeben.

### L3 — Vollständigkeit / Naht
- `cross_domain_target=None` → `cross_domain_hypotheses == ()` (Naht zum Default sauber).
- Leere `problems`-Sequenz → leeres Archiv, `coverage==0`, `validated_count==0`, neutrale Prior,
  und selbst mit angefordertem Ziel keine Hypothesen (leerer KG, `size=2 > len(names)=0`).
- Unerreichbare Zieldimension (`"mol"` — keine Variable trägt Stoffmenge) → `()`, kein Fabrikat.

### L4 — Realisierbarkeit / Edge-Cases
Determinismus bestätigt (gleiche Probleme + Seed → byte-identische Headline-Ausgaben, A5). Der
dimensionale Disposer kann keine unmögliche Gruppe durchlassen (Residuum-Gate), inkl. der SciAgents-
typischen Spurious-Path-Falle — im Property-Test über 25 Seeds geprüft.

## Ergebnis
Kein genuiner Defekt gefunden. Gemäß „change nothing if correct" / „keine stillen Defaults" wurden
**keine** Änderungen an `campaign.py` vorgenommen. Der frühere Test `test_campaign.py` prüfte die Prior
nur via `isinstance(...)` — diese Schein-Sicherheit wird durch die neuen Tests geschlossen, die die
ECHTE Akkumulation (non-neutral vs. neutral) und das ECHTE dimensionale Filtern beweisen.

**Abgleich GENESIS_PLATFORM_PLAN.md:** deckt den „Universe Explorer / Discovery-Campaign"-Strang
(Archiv-Diversität + gelernte Ordnung + SciAgents-KG mit dimensionalem Filter) als verifiziert-echt ab.
