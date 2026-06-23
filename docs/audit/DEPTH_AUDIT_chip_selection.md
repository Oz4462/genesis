# Depth-Audit: `src/gen/chip_selection.py`

**Verdikt: REAL** — keine Quelländerung nötig (`change nothing if correct`).

## Was geprüft wurde
`select_chip` behauptet ein echter *Proposer/Gate*-Split zu sein: Katalog (`CHIPS`) = Kandidatenraum,
`compute.py`'s drei Closed-Form-Screens (Durchsatz / Leistung / Latenz) = Gate, `prefer` = Ordnung über
die durchgelassene Teilmenge. Die neue `tests/test_chip_selection_characterization.py` ist der
Fassaden-Detektor und beweist den Anspruch statt ihn zu glauben.

## Belege, dass der Input wirklich konsumiert wird (kein Konstant-Pick)
- **Requirement → Auswahl:** Eine winzige Last (0.2 TOPS) wählt einen kleinen, billigen Chip; eine große
  Last (50 TOPS) erzwingt einen leistungsstärkeren (höheres `peak_tops`) und teureren Chip. Verschiedene
  Anforderungen ⇒ verschiedene Selektion.
- **`prefer` ordnet wirklich um:** Bei einer Anforderung mit drei feasiblen Chips liefern
  `price`/`power`/`headroom` **drei verschiedene** Chips (Orin Nano / Orin NX / AGX Orin). Empirisch
  verifiziert; jeder Pick ist nachweislich das Minimum der feasiblen Menge unter dem dokumentierten
  Ordnungs-Key. Ein gecannter Konstant-Pick könnte das nicht.
- **Gate ist echt:** `compute.py` direkt auf den selektierten Chip angewandt reproduziert den Pass.
- **Property-based (Hypothesis, 200 Beispiele):** Für jede Anforderung gilt `selected is None ⇔ feasible
  leer`; ein nicht-`None` `selected` ist selbst feasible UND das Minimum der feasiblen Menge unter dem
  prefer-Key; `feasible` ist exakt die gate-passierende Teilmenge von `evaluated`. Determinismus
  (A5) ebenfalls property-geprüft.

## Belege für ehrliches Fail-Loud (`keine stillen Defaults`)
- Unbekanntes `prefer` → `ValueError` (`unknown prefer`).
- Leerer Katalog → `ValueError` (`empty`).
- Nicht-positive Anforderung (`workload_tops`/`power_budget_w`/`control_period_s`/`inference_ops` ≤ 0)
  → `ValueError`, propagiert aus `compute.py`'s eigenen Guards (jede Achse einzeln parametrisiert getestet).
- **Honest abstention:** Last über jede Katalog-Kapazität (usable max = 275·0.6 = 165 TOPS) → `selected is
  None`, `feasible == ()`, jeder Chip nennt seinen bindenden Grund (`limiting == "throughput"`). Kein
  fabrizierter Teil.

## 4 Linsen
- **L1 Wahrheit:** Auswahl-Verdikt ist gegen `compute.py` reproduzierbar; keine faktische Aussage ohne
  Gate-Beleg. Jeder Chip trägt `source`-Provenance (sonst der anonyme Konstant, den der Katalog ersetzt).
- **L2 Drift:** Doc-String-Versprechen (drei Guards, prefer-Semantik, None-bei-no-fit) decken sich 1:1 mit
  dem Verhalten — kein Doku/Code-Drift gefunden.
- **L3 Vollständigkeit/Naht:** Naht zu `compute.py` sauber — `select_chip` erfindet keine eigene Mathematik,
  sondern delegiert die drei Screens; `prefer`-Tie-Break per Name ist deterministisch.
- **L4 Realisierbarkeit:** Katalogwerte sind als *illustrativ-nominal* mit Provenance markiert (kein
  vorgetäuschtes Datenblatt); honest boundary von `compute.py` (Peak-TOPS statt gemessener Roofline) trägt
  bewusst weiter.

## Änderungen
- **Quelle:** keine (Modul ist korrekt).
- **Neu:** `tests/test_chip_selection_characterization.py` (16 Tests, inkl. 2 Hypothesis-Properties +
  Negativfälle), dieses Audit-Dokument.
