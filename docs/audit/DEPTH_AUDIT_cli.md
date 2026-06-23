# Depth-Audit: `src/gen/cli.py` — Rendering-Oberfläche

**Geprüfter Umfang:** die reinen, deterministischen Render-Funktionen
`format_report`, `format_solution`, `format_specification`, `render_spec`
(NICHT die Netzwerk-/Pipeline-`--mode`-Zweige).

**Verdikt: REAL.** Keine Quelländerung nötig — `cli.py` bleibt unverändert (per
„change nothing if correct").

## Was getestet wurde (Facade-Detektor)

Neuer Test: `tests/test_cli_characterization.py` (15 Tests, alle grün).

Jeder Renderer wurde gegen die Halluzinations-/Fassaden-Gefahr geprüft: Gibt er
ein eingebranntes Template aus, oder konsumiert er seinen Input?

1. **`format_specification` konsumiert Wert + Einheit.** Der `:g`-formatierte Wert
   einer `Quantity` (47.5) und ihre Einheit (`kg`) erscheinen wortwörtlich; ein
   anderer Wert (12.0) bzw. eine andere Einheit (`N`) erzeugt eine andere
   Ausgabe. Eine zusätzliche **Property-Based-Probe** (Hypothesis, 50 Beispiele)
   beweist für beliebige endliche Werte im Bereich, dass `f"{value:g}"` immer im
   gerenderten Text auftaucht — der Wert wird nie verschluckt.
2. **Ehrliche Abstention (L1/Negativfall).** `format_report` ohne
   `statement_to_claim` rendert die Zeile
   „keine — nichts konnte unabhängig verifiziert werden"; `format_solution` ohne
   Ansätze rendert „keine — nichts konnte verankert werden"; eine leere
   `Specification` (keine Bauteile/Schritte) rendert
   „keine behauptet — nichts konnte belegt werden". Mit verifizierten
   Befunden/verankerten Ansätzen kippt die Ausgabe auf die Aufzählung um. Das ist
   exakt das Kernprinzip 4 („‚Ich weiß es nicht' ist ein gültiger Output").
3. **`render_spec` dispatcht nach `fmt`.** `'text'` ist identisch mit
   `format_specification(spec)`; ein **unbekanntes** Format (`'totally-unknown'`)
   fällt korrekt auf den Text-Renderer durch (dokumentierter Default, kein
   Crash); `md`/`scad`/`b123d`/`text` liefern vier paarweise verschiedene,
   nicht-leere Strings mit ihren jeweiligen Exporter-Signaturen.

## Ehrliche Grenze (kein Defekt)

Die `scad`/`b123d`-Exporter rendern die **CSG-Geometrie**, nicht die lose
Größentabelle. Eine `Quantity`, die an keinen Geometrie-Parameter eines Bauteils
gebunden ist, taucht dort korrekterweise NICHT auf. Das ist richtiges Verhalten
(die Exporter erfinden keine Geometrie), keine Fassade — die
Wert-Propagations-Probe ist deshalb auf `text` + `md` (die die Größentabelle
rendern) beschränkt und im Test ausdrücklich kommentiert.

## 4 Linsen

- **L1 Wahrheit:** Renderer geben nur belegte/erklärte Werte aus; Abstention ist
  eine explizite Zeile, kein leeres Template. Bestätigt.
- **L2 Drift:** Wert-/Einheit-/Format-Änderung schlägt sich nachweisbar in der
  Ausgabe nieder — kein konstanter Output. Bestätigt.
- **L3 Vollständigkeit/Naht:** `render_spec` deckt alle dokumentierten Formate
  ab und der Unknown-Fall fällt definiert auf Text durch. Bestätigt.
- **L4 Realisierbarkeit:** Tests sind offline, deterministisch, ohne
  CAD/Netzwerk-Abhängigkeit (komponentenfreie Spec für die Nicht-Text-Pfade).
  Bestätigt.

**Abgleich GENESIS_PLATFORM_PLAN:** CLI/CAD-Renderer-Oberfläche als Konsument der
γ-Spezifikation; die ehrliche Abstention untermauert das Anti-Halluzinations-Ziel
der Plattform.
