# Depth-Audit — `src/gen/pipeline.py` (assess_specification honest overall verdict)

**Verdikt: REAL** — keine Quelländerung nötig (`change nothing if correct`, per team decision 2026-06-22/23).

## Was geprüft wurde
`assess_specification` ist die Kompositionsstelle der Quality-Engine: sie verdrahtet clarification, physics_selection + gate_delta_physics, constraint_consistency und (optional) grounding_integrity zu einem einzelnen `Assessment`. Der zentrale Vertrag ist der ehrliche `overall`-Status (needs_clarification > inconsistent_constraints > grounding_failed > physics_incomplete > physics_failed > no_physics_indicated > physics_verified) plus die abgeleiteten Properties `physics_ok` / `physics_checked` / `physics_complete`.

Die neue `tests/test_pipeline_characterization.py` (10 Tests, davon 2 Hypothesis-Properties) ist der Fassaden-Detektor. Alle `Specification`-Objekte werden über die echten `core.state` Konstruktoren gebaut (keine Demo-Helfer in den primären Pfaden). Legacy `test_pipeline.py` blieb unberührt.

## Belege, dass der Input wirklich konsumiert wird (kein Konstant-Pick)
- Trigger + alle Inputs + Werte die den Margin clearen (shaft.torsion 1000 N*mm / d=10 mm / strength=10 MPa) → overall='physics_verified' + physics_ok=True + physics_checked=True + physics_complete=True + gate.passed=True.
- Dieselbe Geometrie, strength auf 1.0 MPa gesenkt → overall='physics_failed' + physics_ok=False + gate.passed=False (der numerische Wert wird konsumiert, nicht gecached).
- Trigger vorhanden, ein Input fehlt (z. B. shear_strength) → overall == 'needs_clarification' (questions have priority over gaps in _overall_status), physics_ok=False, gaps + Fragen nicht leer.
- Keine trigger-Measurands (z. B. nur geometry.*) → overall='no_physics_indicated', physics_checked=False, physics_ok=False, 0 checks.
- Widersprüchliche Constraints (ge + lt auf demselben Paar) → overall='inconsistent_constraints' vor jeder Physik.
- Änderung eines driving Inputs (Measurand hinzufügen/entfernen oder Margin-Wert flippen) ändert overall + Properties signifikant.

## Belege für ehrliches Fail-Loud / Gap-Pfad + Seam-Schutz (`keine stillen Defaults`)
- Gate auf leerer Check-Liste ist vacuous passed (`gate.passed is True`).
- Trotzdem: physics_ok ist False sobald gaps existieren **oder** zero checks liefen — exakt das Masking-Problem, das das Modul verhindert (explizit in 2 Tests bewiesen: gap case + vacuous case).
- physics_ok <=> (physics_checked and gate.passed and physics_complete) und nur dann ist overall=='physics_verified'.
- Negative Fälle feuern exakt die dokumentierten Status-Strings (keine Erfindungen).
- "a gate without a test does not exist": die Seam- und Prioritäts-Tests decken die dokumentierten Zustände ab.

## Property-basierte Invarianten (Hypothesis)
- `physics_ok ⇒ overall == "physics_verified"` (und umgekehrt) über einen Wertebereich der shear_strength (Grenzwert ~5.09 MPa für die Fix-Geometrie).
- Determinismus (A5): identische Specs (gleiche Measurands + Werte) liefern identische overall + Properties bei zwei unabhängigen Aufrufen.
- Keine NaN/Inf in den Property-Inputs (Projektkonvention).

## 4 Linsen
- **L1 (Wahrheit):** Alle Behauptungen über Status-Übergänge, Seam und Properties sind durch konkrete Konstruktionen + laufende Prüfung von gate.passed / gaps / n_checks belegt. Keine stillen Defaults. Quellen sind die echten Module (clarification, physics_selection, physics_validation, constraint_consistency).
- **L2 (Drift):** Docstring in pipeline.py, _overall_status-Priorität und Property-Dokumentation (physics_ok nur bei real gelaufenen + bestandenen Checks) decken sich 1:1 mit Code + Tests. Keine Abweichung zwischen Versprechen und Verhalten.
- **L3 (Vollständigkeit/Naht):** Die 5 Kernfälle der spec (verified, missing→clarify/incomplete, vacuous, contradictory, failed) + explizite Seam-Assertion + 2 Properties prüfen die Komposition vollständig. Naht zu physics_selection / gate / clarification ist sauber (keine neuen Abhängigkeiten). Legacy-Test unberührt.
- **L4 (Realisierbarkeit):** Randfälle (fehlende Inputs, Margin-Flip, leere Spec, widersprüchliche Constraints, zero-checks) sind deterministisch und mit echten Konstruktoren getestet. Ehrliche Boundary (vacuous/gap → nicht verified) ist implementiert und wird nicht umgangen.

## Änderungen
- **Quelle (src/gen/pipeline.py):** keine (Modul erfüllt den Vertrag; Test hat keinen Defekt in Priorität oder den drei Properties gefunden).
- **Neu:**
  - `tests/test_pipeline_characterization.py` (10 Tests: 8 Beispiel + 2 Hypothesis; echte core.state-Konstruktoren; Input-driven + Seam-Proof + NEGATIVE-Pfade; legacy untouched).
  - `docs/audit/DEPTH_AUDIT_pipeline.md` (dieses Dokument).
- File-Scope exakt eingehalten. Isolation (Standalone in Worktree mit nur eigenen Dateien + pre-existing repo) erfüllt.
- Keine Out-of-Scope-Änderungen.

**Tests:** `python -m pytest tests/test_pipeline_characterization.py -q` → 10 passed.

**4-Linsen-Selbstkontrolle (post-edit):** Die Charakterisierung beweist, dass assess_specification ein echtes Kompositions-Gate ist (L1), keine Drift zu Doc (L2), die kritische Naht gegen Masking schützt (L3) und alle dokumentierten Ränder realisierbar und ehrlich sind (L4). Kein Bedarf für Quell-Änderung. Abgleich mit GENESIS_PLATFORM_PLAN (Quality-Engine / GATE δ+ Zusammensetzung) abgeschlossen — der Backlog-Punkt "ehrliches overall" ist gedeckt.
