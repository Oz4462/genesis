# Depth-Audit: `src/gen/grenzverschiebung/bench_test_runner.py`

**Verdict: FACADE (auf `main`) → REAL (nach diesem Fix).**

Das Modul beansprucht laut PLAN (GENESIS_PLATFORM_PLAN.md §3.3) "plant **UND bewertet**
den Messlauf für diesen Prototyp". Auf `main` war davon nichts wahr.

## Die Facade (auf `main` bewiesen)

`run_bench_test(prototype_plan, ...)` hatte drei harte Facade-Defekte:

1. **`prototype_plan.prototypes` wurde komplett ignoriert.** Konsumiert wurde nur
   `prototype_plan.source_traum`. Die eigentliche Eingabe (die Prototyp-Specs aus dem
   technology_builder) hatte **null** Einfluss auf den Output.
2. **Hartkodiertes 1-/2-Item-Ergebnis per Substring.** `if "jetpack" in traum.lower()`
   → fixe 2 Ergebnisse mit kanned Messdaten/Kriterien; sonst genau 1 fixes P0-Ergebnis.
   Drei Prototypen lieferten also 1 Ergebnis, fünf ebenso — die Kardinalität war von der
   Eingabe entkoppelt.
3. **`BenchTestResult.ergebnis_bewertung` war immer `None`.** Das Modul "bewertete" also
   nie irgendetwas — die Hälfte des Headline-Versprechens existierte nicht. Ein stilles
   `None` als faktischer Default verletzt CLAUDE.md-Kernprinzip "keine stillen Defaults".

Bewiesen mit einem Replikat der alten Logik: bei 3 Prototypen → `len(results) == 1`
(statt 3) und `ergebnis_bewertung == [None]`. Beide neuen Characterization-Assertions
(`test_one_result_per_prototype_proves_prototypes_are_consumed`,
`test_every_result_has_non_none_honest_bewertung`) fallen auf der Facade durch.

## Was jetzt REAL ist (der Fix)

Auf `src/gen/grenzverschiebung/bench_test_runner.py` beschränkt:

- **Eine `BenchTestResult` pro `TechnologyPrototypeSpec`** — die Output-Kardinalität folgt
  jetzt exakt `len(prototype_plan.prototypes)` (Reihenfolge erhalten). Die Prototyp-Liste
  ist damit nachweislich konsumiert.
- **Kriterien aus realen Feldern abgeleitet, nicht hartkodiert:**
  - `messdaten_anforderungen` und `erfolgskriterien` = je ein Eintrag pro
    `spec.anforderungen` (der Anforderungs-Text steckt im Messplan);
  - `abbruchkriterien` = je ein Eintrag pro `spec.risiken` **plus** ein universelles
    Sicherheits-Stopp (auch ein risiko-armer Prototyp wird nie ohne Stopp gefahren).
  Ändert man eine einzelne Anforderung, ändert sich der Messplan
  (`test_changing_an_input_anforderung_changes_the_output`) — kein Konstant-Stub.
- **`ergebnis_bewertung` ist nie `None`**, sondern ein expliziter, ehrlicher Status
  (single source of truth als Modul-Konstante):
  - `STATUS_GEPLANT_NICHT_AUSGEFUEHRT` ("geplant_nicht_ausgefuehrt") wenn der Plan
    vollständig ableitbar war — mit Begründung, dass noch **kein realer Messlauf**
    existiert (also bewusst kein erfundenes Pass/Fail);
  - `STATUS_GEPLANT_UNVOLLSTAENDIG` wenn der Prototyp keine Anforderungen trägt → kein
    Erfolgskriterium ableitbar; die Lücke wird ausgewiesen statt überspielt
    (neues Feld `bewertung_begruendung` trägt den Grund).
- **Ehrliche Abstention bei leerer Eingabe:** kein Prototyp → leere `results` + ehrliche
  `zusammenfassung`, statt — wie die Facade — einen P0-Prototyp zu fabrizieren.
- **Jetpack-Reichtum bleibt erhalten — jetzt input-derived:** die reichen
  Energiedichte-/Control-Anforderungen erscheinen weiter im Messplan, aber weil sie aus
  den (reichen) Prototyp-Specs des Builders abgeleitet werden, nicht weil ein Stringliteral
  sie einsetzt (`test_jetpack_rich_content_is_preserved_and_input_derived`).

Downstream sicher: `breakthrough_watch` und `safety_ladder` lesen keine `BenchTestResult`-
Felder direkt, daher ist das neue Feld `bewertung_begruendung` (Default am Listenende)
rückwärtskompatibel.

## Tests

`tests/test_bench_test_runner_characterization.py` (12 Tests, inkl. 2 Hypothesis-Properties):
Ein-Ergebnis-pro-Prototyp, Kardinalität folgt Input, Ableitung von Messdaten/Erfolg aus
`anforderungen` und Abbruch aus `risiken`, Input-Sensitivität, Bewertung nie `None`,
Unvollständig-Flag ohne Anforderungen, leere Abstention, Jetpack-Regression. Property:
`|results| == |prototypes|`, Reihenfolge erhalten, Bewertung nie `None`, Ableitung total.
Alle 12 grün; die fokussierte Grenzverschiebungs-Suite bleibt grün (52 passed / 14 skipped).

## 4 Linsen

- **L1 (Wahrheit/Provenance):** Jede `BenchTestResult.quelle` benennt die Ableitung
  (`bench_test_runner (abgeleitet aus Prototyp-Spec) + <spec.quelle> + §3.3`). Statt eines
  faktischen `None`-Defaults wird der Mess-Status explizit als Plan-/Lücken-Status mit
  Begründung deklariert — "Ich weiß es (noch) nicht" als gültiger Output (Kernprinzip 4).
- **L2 (Drift/Grounding):** Der Output ist jetzt eine reine Funktion der Eingabe; die
  Substring-Drift auf `source_traum` ist entfernt. Test beweist: Input-Änderung ⇒
  Output-Änderung; kein "war schon so".
- **L3 (Vollständigkeit/Naht):** Naht zum technology_builder geschlossen — alle Prototypen
  (nicht nur das Jetpack-Paar) werden bedient; Naht zum Konsumenten geprüft
  (`breakthrough_watch`/`safety_ladder` lesen keine BenchTestResult-Felder, kein Bruch).
  Universelles Sicherheits-Stopp deckt die Lücke "risiko-armer Prototyp ohne Stopp".
- **L4 (Realisierbarkeit):** Die ehrlichen Stati spiegeln den realen Reifegrad — es gibt in
  dieser Stufe keinen echten Messstand-Lauf, also wird kein Mess-Verdikt erfunden. Die
  Felder sind so geformt, dass ein späterer realer Lauf nur `ergebnis_bewertung` von
  `geplant_*` auf ein gemessenes "bestanden"/"nicht erreicht" hebt — ohne Strukturbruch.
