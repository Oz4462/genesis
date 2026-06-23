# Depth-Audit: `src/gen/discovery/transcendental.py`

**Task:** T02 — prove honest transcendental-vs-powerlaw verdicts (`discover_transcendental`, exercised `discover_rivals`/`evaluate_rival`/`refit_rival`).

**Verdict: REAL**

No source edits performed. The implementation already satisfies the headline contract exactly as specified.

## Was geprüft wurde

Charakterisierungs-Test `tests/test_discovery_transcendental_characterization.py` (10 Fälle inkl. 2 Property-Tests mit Hypothesis) der die drei zentralen Verdikte + die Rivalen-Maschinerie als *berechnet, nicht gefälscht* nachweist:

| Anspruch | Beweis im Test | Ergebnis |
|---|---|---|
| **Genuine transzendentale Gesetze über π-Gruppe → bestaetigt nur wenn exakt UND Power-Rivale nicht** | `_exp_decay_trans` + `_sine_trans` liefern `bestaetigt`, `r_squared>=0.999`, `powerlaw_r2<0.999`; `alpha`/`C` werden auf die erzeugenden Werte zurückgewonnen | REAL |
| **Power/Quadrat desselben π-Gruppe → unentschieden (Power-Rivale klärt die Bar ebenfalls)** | `_quadratic_power_of_group` → `unentschieden`, beide R² >=0.999, `powerlaw_r2` exakt ~1; der Power-Rivale ist der entscheidende Grund für die Weigerung | REAL |
| **Kein dimensionsloses Argument → widerlegt** | `_kepler_no_dimless` → `dimensionless_groups()==[]` und `verdict=="widerlegt"`; nie eine erfundene transzendentale Form | REAL |
| **Rivalen-API ist input-getrieben (discover/evaluate/refit)** | Für den unentschieden-Fall liefern `discover_rivals` beide Formen; `evaluate_rival` reproduziert die Daten (R²>0.999); `refit_rival` auf identischen Daten liefert äquivalente Qualität | REAL |
| **Input-Konsum nachweisbar (kein Canned)** | Unterschiedliche erzeugende Daten (exp vs. sine, mit-Gruppe vs. ohne) → unterschiedliche `verdict`/`form_name`/`expression`; Scaling der Zielwerte skaliert nur `C` | REAL |
| **Fail-loud Guard exakt** | Non-positive Input/Constant → exakter `ValueError` mit dokumentiertem Text (Negativtest) | REAL |

**Property-Invarianten (Hypothesis):**
- Für alle erzeugten (C, α≤-0.9) mit ausreichender Krümmung: exakte Rückgewinnung + `bestaetigt` + `powerlaw_r2<0.999`.
- Skalierung des Targets (k>0): `verdict` und `r_squared` bleiben identisch; nur der `C`-Parameter skaliert (Form der transzendentalen ist skalierungsinvariant im Modell).

## Gefundener Defekt
Keiner. Die Quell-Logik (r2 >= threshold AND powerlaw_r2 < threshold → bestaetigt; elif >= → unentschieden; sonst weiter oder widerlegt) ist exakt die im Docstring und in der Task-Spec beschriebene ehrliche Regel. Kein toter Branch, kein silent default, keine falsche Zuordnung.

## Bewusst NICHT geändert („change nothing if correct“)
- Keine NaN/Inf-Guards hinzugefügt (nicht im dokumentierten Vertrag; bei korrupten Daten wird konservativ `widerlegt`/`-inf` geliefert — kein falsches `bestaetigt`).
- Keine Änderung an Schwellen, Form-Bibliothek, Fit-Initialisierungen oder Formatierung.
- Legacy-Test `test_discovery_transcendental.py` unverändert gelassen (neue Datei ist die autoritative Charakterisierung).
- Modul-Docstring nicht angepasst — er beschreibt den Vertrag bereits präzise und stimmt mit dem implementierten Gate überein.

## 4 Linsen
- **L1 Wahrheit:** Alle Behauptungen (bestaetigt/unentschieden/widerlegt) sind durch konstruierte Probleme mit bekannten Ground-Truth-Funktionen bewiesen; die Power-Rivale-Vergleichslogik ist die zentrale Anti-Übertreibungsmaßnahme (δ-Asymmetrie). Keine unbelegten Claims.
- **L2 Drift:** Kein Drift — die Charakterisierung bestätigt exakt das, was Docstring + Task-Spec + GROK_BUILD... seit 2026-06-18 beschreiben. Kein stiller Default entdeckt (im Gegensatz zu flight.py oder multiterm).
- **L3 Vollständigkeit/Naht:** Die neue `_characterization.py` ist pfad-disjunkt zur Legacy-Testdatei und zu allen anderen Discovery-Modulen; verwendet nur reale Konstruktoren aus `engine.py` + bereits deklarierte Deps (numpy/scipy). Keine neuen Imports/Abhängigkeiten. Alle existierenden Tests (legacy + 9 weitere Discovery-Char-Tests) bleiben kompatibel.
- **L4 Realisierbarkeit:** Test ist deterministisch (bis auf Hypothesis-Generatoren, die auf positive physikalische Größen eingeschränkt sind), läuft offline, übt Happy-Path + Negativfälle + Invarianten. Keine Änderung am Produktionscode nötig; die ehrliche Verdikt-Logik war bereits vorhanden.

## Abgleich mit GENESIS_PLATFORM_PLAN / HORIZON
Erfüllt den Discovery-Frontier-Anspruch (transzendentale Gesetze hinter Power/π): ehrliche Gate-Bedingung (bestaetigt nur bei klarem Mehrwert gegenüber simplerem Rivalen) + Reproduzierbarkeit (A5) + „keine stillen Defaults“. Keine offene Lücke für dieses Modul hinterlassen; die offene Frontier (Produkte von Transzendenten, volle GP-Suche) ist im Modul-Docstring als solche deklariert.

## Dateien dieser Task (strikt disjunkt)
- `src/gen/discovery/transcendental.py` — nur gelesen, nicht editiert
- `tests/test_discovery_transcendental_characterization.py` — neu (autoritative Fassade-Detektion)
- `docs/audit/DEPTH_AUDIT_transcendental.md` — neu (per-Modul-Audit, BUILD_LOG bleibt unberührt)

Fazit: Das Modul ist **REAL** — die versprochene „honest transcendental-vs-powerlaw“-Unterscheidung wird durch die Tests nachweislich geleistet.