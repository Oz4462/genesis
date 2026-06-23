# Depth-Audit: `src/gen/discovery/tournament.py`

**Verdikt: REAL.** Keine Quell-Änderung nötig (Kernprinzip „change nothing if correct").
Die Headline-Behauptung — *bei unterbestimmtem Dimensionssystem findet die evolutionäre
Suche eine messbar bessere Hypothese als der Single-Shot-Least-Norm-Pick; bei bestimmtem
System gibt sie den Single-Shot ehrlich unverändert zurück* — hält **bewiesen** auf
konstruierten Daten, die durch die echte `engine` laufen.

## Was geprüft wurde (Facade-Detektor)
Neue Datei `tests/test_discovery_tournament_characterization.py`. Das stärkere Gegenbeispiel
gegenüber dem Legacy-Test: das wahre Gesetz ist `y = C · x1^2 · x2^-1`, dessen **beide**
Exponenten scharf vom dimensionalen Least-Norm-Pick `(0.5, 0.5)` abweichen — kein
„x2 irrelevant"-Sonderfall. Eine Attrappe (Rückgabe des Single-Shot, oder „Verbesserung"
nur durch Rationalisierung) würde hier hart durchfallen, denn nur eine echte
daten­getriebene Suche über den **Null-Raum** reist von `(0.5, 0.5)` bis `(2, -1)`.

Belegte Messwerte (reproduzierbar, seed-fest):
- Single-Shot: Exponenten `(0.5, 0.5)`, **R² = 0.05** — der Least-Norm-Pick erklärt die
  Daten nachweislich nicht.
- Evolution (seed 1): Exponenten `(2.0000, -1.0000)`, **R² = 0.99999998**, Koeffizient
  `2.99997` ≈ 3 — das wahre Gesetz exakt zurückgewonnen, vollständig **innerhalb** der
  dimensionalen Familie (`dimension_ok`, Residuum < 1e-6).

Tests im Einzelnen: Null-Raum-Vorbedingung (1 freie π-Gruppe); Single-Shot ist hier
*wirklich* falsch (R² < 0.5); messbare Verbesserung + Gesetz-Rückgewinnung + nicht-fallende
Fitness-Trajektorie; ehrlicher No-Search-Zweig (Kepler: `generations=0`, `improved=False`,
`population_size=1`, `best is single_shot`); Determinismus (gleicher seed → byte-gleich);
verschiedene seeds konvergieren zum **gleichen** wahren Gesetz (Daten, nicht seed, treiben);
**Property-Test (Hypothesis, 25 Beispiele)** über die ganze 1-Parameter-Familie
`a_exp ∈ [1.4, 3.0]`, `coeff ∈ [0.5, 8.0]` — Evolution gewinnt das jeweilige Gesetz immer
zurück. Negativfall = der determinierte (Kepler-)Zweig, der ehrlich nichts sucht.

Ergebnis: **7 passed** (neuer Test), **3 passed** (Legacy-Test) — keine Kollision.

## 4 Linsen
- **L1 Wahrheit:** Der Verbesserungs-Claim ist falsifizierbar gemacht und gehalten — die
  Zahlen (R² 0.05 → 1.0, Exponenten `(2,-1)`) stammen aus der echten Engine, nicht aus einem
  Stub. Keine stillen Defaults: der No-Search-Zweig behauptet keine Suche, die er nicht tut.
- **L2 Drift:** Docstring und Verhalten stimmen überein (Null-Raum-Suche, `improved`-Semantik,
  Determinismus). Kein Doc-Code-Drift gefunden; Modul unverändert gelassen.
- **L3 Vollständigkeit/Naht:** Beide Pfade (unterbestimmt / bestimmt) getestet, plus die
  Naht zur `engine` (`symbolic_regress`, `dimensional_system`, `candidate_from_exponents`)
  wird durch echte Aufrufe abgedeckt. Property-Test schließt die „nur ein Beispiel"-Lücke.
- **L4 Realisierbarkeit:** Offline, numpy-only, deterministisch, seed-fest; Laufzeit der
  Suite akzeptabel (~40 s, dominiert vom Hypothesis-Sweep). Keine neue Abhängigkeit außer
  `hypothesis` (bereits als Test-Dep in `pyproject.toml [dev]` deklariert).

## Abgleich GENESIS_PLATFORM_PLAN
Tournament ist die deklarierte Erweiterung des Single-Shot-SR um freie π-Gruppen
(„der Tournament-Loop weitet den Kandidatenraum", `engine.py`-Doc). Der Audit bestätigt:
diese Erweiterung ist **echt gebaut**, nicht nur benannt — sie liefert auf einer
under-determined Aufgabe nachweislich das richtige Gesetz, das der Single-Shot verfehlt.
Offene Grenze (unverändert, ehrlich): volle symbolische/GP-Suche bleibt ein Phase-1+-Gap;
Tournament deckt die *lineare* π-Gruppen-Familie ab, nicht beliebige Funktionsformen.
