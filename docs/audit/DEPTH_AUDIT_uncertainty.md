# Depth-Audit: `src/gen/discovery/uncertainty.py`

**Modul:** `discovery/uncertainty.py` — Bootstrap-Konfidenzbänder über ein entdecktes Gesetz
**Datum:** 2026-06-23
**Aufgabe:** T04 — Beweisen, dass die Bänder auf EXAKTEN Daten degeneriert sind und mit Rauschen WEITER werden.
**Verdikt:** **REAL.** Quelltext der `bootstrap_law`-Logik unverändert — der Characterization-Test deckt
keinen Defekt in diesem Modul auf. Die Headline-Behauptung hält messbar.

## Headline-Behauptung (FORSCHUNG_AUTONOMES_ERFINDEN §A2/P2)
`bootstrap_law` resampled die Datenpunkte mit Zurücklegen, rediscovered je Resample das beste
Potenzgesetz und meldet pro Parameter ein Perzentil-Band statt einer scheinsicheren Einzelzahl:
- **Exakte Daten → degeneriertes Band (≈0 Breite).** Jedes Resample liefert denselben perfekten Fit,
  also keine Unsicherheit; `contains(true_value)` hält und `r2_mean == 1.0`.
- **Rauschen → Band wird WEITER** und `r2_mean < 1.0` — quantifiziert, wie stark die Daten den
  Parameter festnageln.
- **Deterministisch** für festen `seed`.
- **< 3 Punkte → laute `ValueError`** (Bootstrap braucht echte Stichproben) — keine stillen Defaults.

## Beweis (tests/test_uncertainty_characterization.py)
Getrieben durch die ECHTEN Engine-Konstruktoren (`DiscoveryProblem`/`Variable`) auf einem sauberen
Quadratgesetz `y = C·x²` ([m²]=[m]²): die Dimensionsanalyse fixiert den Exponenten exakt auf 2, der
Koeffizient `C` ist der einzige datengetriebene Parameter — der kanonische Fall, in dem das
Koeffizienten-Band das informative ist.

1. `test_exact_data_gives_degenerate_bands_that_contain_the_truth` — Koeffizient- UND Exponent-Band
   haben Breite ≈0, brackten ihren wahren Wert (`C`, `2.0`), `r2_mean == 1.0`.
2. `test_noise_widens_the_coefficient_band_and_drops_r2` — **der Facade-Killer:** dasselbe Problem mit
   10 % multiplikativem Rauschen liefert ein deutlich breiteres Koeffizienten-Band (gemessen
   ~0.76 vs. exakt 0) und `r2_mean < 1.0`. Beweist: der Bootstrap KONSUMIERT die Datenstreuung, echot
   kein gebackenes Intervall.
3. `test_deterministic_for_fixed_seed` — zwei Läufe, selber Seed → byte-identische Bänder + `r2_mean`
   (A5-Reproduzierbarkeit).
4. `test_fewer_than_three_points_raises` — 2 Punkte → `ValueError("…at least 3 data points…")`.
5. `test_property_exact_data_always_degenerate_and_brackets_truth` (Hypothesis) — für JEDEN positiven
   Koeffizienten und jede (≥3) Stichprobengröße bleibt das Koeffizienten-Band degeneriert und brackt
   `C`. Die Headline ist eine Eigenschaft der Methode, nicht eines handverlesenen Arrays.

## Ehrliche Nuance bei kleinem n (dokumentiert, nicht versteckt)
Bei sehr wenigen Punkten kann ein Resample mit Zurücklegen zufällig lauter identische Indizes ziehen;
dessen Ziel ist dann konstant, wo R² mathematisch unbestimmt ist (keine Varianz zu erklären). Die
Float-Rest-`ss_tot` in `engine._r_squared` rutscht dort knapp an der `<=0`-Konstanten-Falle vorbei und
liefert für genau dieses Resample einen R²-Ausreißer. **Folge für die Headline: keine.** Der
Koeffizient wird auch in diesem Resample EXAKT zurückgewonnen, das Band bleibt degeneriert — daher
prüft der Property-Test bewusst die Band-Invariante (die echte Headline), nicht `r2_mean==1.0` für
kleines n. `r2_mean==1.0` wird im gut bestichprobten Beispiel (6 Punkte) geprüft. Diese R²-Kante lebt
in `engine.py` (außerhalb des Datei-Scopes dieser Aufgabe) und ist kein Defekt von `bootstrap_law`.

## 4 Linsen
- **L1 Wahrheits-Linse:** Bänder sind aus Resamples berechnet (`np.percentile`/`np.mean`/`np.std`), nicht
  konstant — exakt=0, verrauscht>0, beides empirisch belegt. Kein faktischer Wert ohne Datenbasis.
- **L2 Drift-Linse:** Der Docstring verspricht „degeneriert auf exakt, weiter mit Rauschen" — exakt das
  testet der Charakterisierungs-Test; kein Versprechen ohne Deckung. Exponent-Band ist strukturell
  degeneriert (dimensions-fixiert), Koeffizient-Band ist das informative — wie im Docstring beschrieben.
- **L3 Vollständigkeits-/Naht-Linse:** Happy Path (exakt + verrauscht), Determinismus-Naht und der
  Fail-Loud-Pfad (<3 Punkte) sind abgedeckt; die Engine-Naht (`symbolic_regress`) wird real durchlaufen,
  nicht gemockt.
- **L4 Realisierbarkeits-Linse:** Reines numpy, offline, deterministisch; läuft in <4 s. Die kleine-n-
  R²-Kante ist als ehrliche Grenze dokumentiert statt kaschiert.

## Abgleich GENESIS_PLATFORM_PLAN.md
Erfüllt den Integritäts-/Unsicherheits-Anspruch („Distribution über Gesetze statt scheinsicherer Formel"):
das Modul liefert ehrliche, datengetriebene Bänder und sagt bei dünnen/verrauschten Daten laut „die Daten
bestimmen das nicht stark" statt eine Einzelzahl vorzutäuschen.
