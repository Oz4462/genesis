# Depth-Audit — `src/gen/physics_selection.py` (spec→physics-check auto-selection)

**Verdikt: REAL** — keine Quelländerung nötig (`change nothing if correct`).

## Was geprüft wurde
`select_physics_checks` + `evaluate_spec_physics` bauen aus einer `Specification` (mit `Quantity`s die `measurand`-Tags tragen) die passenden `PhysicsCheck`s für GATE δ. Trigger-Measurand entscheidet Präsenz; alle Inputs müssen auflösbar sein (mit korrekter Unit-Konversion via `verification.units`). Fehlende/opake/inkompatible Inputs werden als explizite GAPs gemeldet — nie stiller Drop, nie falsche Einheit. Die neue `tests/test_physics_selection_depth.py` ist der Fassaden-Detektor.

## Belege, dass der Input wirklich konsumiert wird (kein Konstant-Pick)
- Trigger absent (z. B. nur "geometry.width") → checks==[] und gaps==[] (Silence korrekt).
- Trigger present + alle Inputs in passenden Einheiten → Check wird emittiert; Änderung des Werts (z. B. shaft.torque 4.2 N*m) ändert exakt das `inputs["torque"]` im Check.
- Unit-Konversion wird ausgeführt (N*m → N*mm ×1000; g→kg; cm²→m²); identischer physikalischer Wert in anderer Einheit liefert identische resolved Magnitude (siehe Property-Test).
- evaluate liefert `{"gate": GateResult, "checks": [...], "gaps": [...]}` konsistent zu direktem select.
- Property-basiert (Hypothesis): Determinismus (A5) über Variation der Werte; Konversions-Skala exakt (×1000) für jede positive Torque.

## Belege für ehrliches Fail-Loud / Gap-Pfad (`keine stillen Defaults`)
- Trigger vorhanden, aber ein required Input fehlt → genau 1 Gap-String, der Rezeptname + fehlenden Measurand nennt; checks bleibt leer.
- Dimension mismatch (z. B. "kg" für Länge) → Gap mit `"nicht dimensionsgleich"`.
- Unbekannte/opaque Einheit → Gap mit passender Reason (`"nicht dimensionsgleich"` für abweichende Dim; intern auch `"opake Einheit"` bei gleichem Opaque-Symbol + fehlender Scale).
- NEGATIVE Tests sind die Gap-Pfade (missing / incompatible / opaque) — "a gate without a test does not exist".
- GateFailure-Codes (PHYSICS_CHECK_FAILED etc.) werden bei ungültigen Checks durch die nachgelagerte gate_delta_physics korrekt emittiert.

## 4 Linsen
- **L1 (Wahrheit):** Konversionen + Gap-Reasons gegen units.py + Hand-Rechnung geprüft; Property-Tests über Werte-Raum; keine Behauptung ohne Beleg. Keine stillen Magnitude-Copies.
- **L2 (Drift):** Docstring-Versprechen (Trigger-Skipping, Unit-Conversion, Gap bei Missing/Dim/Opaque, evaluate-Struktur) decken sich exakt mit Code + Tests.
- **L3 (Vollständigkeit/Naht):** 4 Kernfälle (a/b/c/d) + evaluate-Konsistenz + Properties; Legacy `test_physics_selection.py` bleibt unberührt und grün. Naht zu physics_validation / units sauber (keine neue Math).
- **L4 (Realisierbarkeit):** Randfälle (fehlende Inputs, falsche Einheiten, absent Trigger, determinism) sind getestet; ehrliche Boundary (unrunnable check → Gap statt Crash oder Guess) ist implementiert und dokumentiert.

## Änderungen
- **Quelle:** keine (Modul ist korrekt und erfüllt den Vertrag).
- **Neu:** `tests/test_physics_selection_depth.py` (9 Tests: 7 Beispiel + 2 Hypothesis-Properties, inkl. expliziter NEGATIV-Pfade + evaluate-Consistency), dieses Audit-Dokument.
- File-Scope strikt eingehalten; nur neues Testfile + Audit; Isolation (Standalone in Worktree) erfüllt.

**Tests:** `python -m pytest tests/test_physics_selection_depth.py -q` → 9 passed.
