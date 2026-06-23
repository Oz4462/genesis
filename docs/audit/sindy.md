# Depth-Audit: discovery/sindy.py — VERDICT: REAL

**Modul:** `src/gen/discovery/sindy.py`
**Aufgabe (T01):** Tiefen-Audit der Headline-Behauptung *Sparse Identification of Nonlinear
Dynamics (SINDy)* — Entdeckung der Bewegungsgleichung eines Systems aus einer Zeitreihe per
**spärlicher** Regression über eine Kandidaten-Bibliothek (Brunton/Proctor/Kutz, PNAS 2016).
**Test:** `tests/discovery/test_sindy_characterization.py` (8 Tests, alle grün).

## Headline-Behauptung
> Recover the governing terms of a dynamical system via *sparse* regression over a candidate
> library — keep only the terms the dynamics need (echte Sparsity, kein dichter LSQ-Fit).

## Befund: REAL (keine Quellcode-Änderung nötig)
Das Modul implementiert **STLSQ** (sequentially-thresholded least squares) in reinem numpy:
LSQ-Fit → Koeffizienten unter Schwelle auf 0 → Refit auf Überlebenden → Fixpunkt. Das ist der
echte SINDy-Kern, keine Fassade. Charakterisiert und bewiesen:

1. **Echte Term-Wiederherstellung.** Aus Daten eines BEKANNTEN sparsen Polynomsystems
   `y = 3 + 2·x − 1.5·x³` (7-Term-Bibliothek, 4 echt inaktive Terme) findet STLSQ exakt die 3
   aktiven Terme mit korrekten Koeffizienten (±0.1) und setzt **jeden** Störterm auf **exakt 0** —
   auch unter Messrauschen.
2. **Sparsity ist real, kein dichter Fit.** Auf denselben verrauschten Daten lässt `np.linalg.lstsq`
   die Störterme von 0 verschieden; STLSQ nullt sie exakt. Wäre SINDy ein umetikettierter dichter
   Fit, würde dieser Test scheitern.
3. **End-to-End ODE-Entdeckung.** Aus einer per RK4 erzeugten Trajektorie der bekannten nichtlinearen
   ODE `θ̈ = −2·θ − 0.6·θ̇³` rekonstruiert `discover_ode` den kubischen Dämpfungsterm
   (Koeffizient ±0.02) bei R² > 0.999; irrelevante Default-Terme (1, sin, cos) werden ausgethresholdet.
4. **Sparse-Recovery-Invariante (Hypothesis).** Für beliebige gut-konditionierte zufällige sparse
   lineare Systeme wird der exakte Support + die Koeffizienten wiederhergestellt.

## Negativ-/Ehrlichkeits-Fälle (kein fabriziertes Gesetz)
- **Fehlende Daten:** zu kurze Trajektorie → `ValueError` (fail loud), nie ein erfundenes ODE.
- **Ungültige Schwelle:** `threshold < 0` → `ValueError`.
- **Keine sparse Repräsentation:** ein mit der Bibliothek unkorreliertes Rausch-Ziel → STLSQ liefert
  das **Null-Modell** (ehrliches „nichts gefunden"), keine erfundenen aktiven Terme.
- **Unzureichende Bibliothek:** dieselbe kubische ODE ohne den `θ̇³`-Term → ehrlich niedrigeres R²
  (< 0.99), der fehlende Term kann nicht erfunden werden — keine R²≈1-Fabrikation.

## 4 Linsen
- **L1 Wahrheit:** Behauptung gegen reale Numerik geprüft; Koeffizienten/Support stimmen mit der
  bekannten Ground-Truth überein. Kein faktischer Output ohne Beleg.
- **L2 Drift:** Docstring deckt sich mit dem Verhalten (STLSQ, Schwellen-Refit-Fixpunkt, R²-Report);
  ehrliche Grenzen (skalare ODE 2. Ordnung, FD-Bias) sind dokumentiert und werden nicht überschritten.
- **L3 Vollständigkeit/Naht:** Output ist ein **Vorschlag/Kandidat** (so dokumentiert), gepaart mit
  `srbench_hygiene` + Unsicherheits-Bändern (`ode_coefficient_bands`) — kein Ledger-Fakt, daher kein
  Ledger-Eintrag erforderlich; die Naht zu den Hygiene-/Uncertainty-Gates bleibt intakt.
- **L4 Realisierbarkeit:** rein numpy, deterministisch, offline; aus GENESIS-Simulatoren gespeist
  (saubere RK4-Daten entschärfen SINDys Rausch-Empfindlichkeit). Plan-Abgleich: deckt den
  „categorical jump beyond single power-law" (FORSCHUNG_AUTONOMES_ERFINDEN §A2) ab.

**Was real gemacht wurde:** Das Modul war bereits real; der Audit fügt den falsifizierbaren
Charakterisierungs-Beweis (inkl. dichter-vs-sparser Kontrast, Ehrlichkeits-Negativfälle und
Hypothesis-Invariante) hinzu und dokumentiert das Verdikt. Keine Verhaltensänderung am Quellcode.
