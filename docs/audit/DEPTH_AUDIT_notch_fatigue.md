# Depth-Audit: `src/gen/notch_fatigue.py` (Peterson notch-sensitivity closed forms)

**Verdikt: REAL.** Keine Quell-Änderung nötig — die drei Peterson/Neuber-Closed-Forms
rechnen exakt (q, K_f, Se_notched) und jeder dokumentierte Guard feuert mit der
exakten Message. T02 (notch_fatigue_depth) fügt nur `tests/test_notch_fatigue_depth.py`
(17 Tests, alle grün) + dieses Audit hinzu. Legacy `tests/test_notch_fatigue.py` (10 Tests)
bleibt unberührt und grün — keine Regression, keine Churn.

## Abgedeckte Oberfläche
- `notch_sensitivity`, `fatigue_notch_factor`, `notch_endurance_limit`, `notch_fatigue_check`
- Neu: `tests/test_notch_fatigue_depth.py` (Property-Tests + exakte Negative + Komposition)
- Kein Edit an `src/gen/notch_fatigue.py`

## Anker + Closed-Form-Nachweis (unabhängig, kein geteiltes Algebra)
- **Anchor (docstring-pinned)**: K_t=3, r=1 mm, a=0.25 mm → q = 1/(1+0.25)=0.8 exakt,
  K_f=1+0.8*2=2.6 exakt, `notch_endurance_limit(Se,2.6) == Se/2.6` exakt.
- **Monotonie (Input wird konsumiert)**: Größeres r (stumpfer Kerb) → q↑ und K_f↑
  (→ K_t); kleineres r (scharfer Kerb) → q↓ und K_f↓ (→ 1). Jeder Parameter (kt, r, a)
  bewegt den Output.
- **Eigenschaft (Hypothesis)**: Für endliches r>0 und a>0 gilt strikt 1 < K_f < K_t
  (150 Beispiele); K_f ist nicht-fallend bei wachsendem r; Se_notched * K_f == Se.
- **Komposition im Check**: safety_factor == Se/(K_f·nominal) == se_notched/nominal
  (Identität); local_effective == K_f·nominal; ok kippt exakt bei nominal == Se_notched
  (just-below ok+sf>1, just-above !ok+sf<1, at-boundary ok+sf==1).
- **Determinismus**: gleiche Inputs → identisches Dict (A5-Kontrakt für pure Funktion).

## Negativtests (jeder dokumentierte Guard — laute Failure, nie stiller Default)
- `notch_sensitivity(r≤0)` → ValueError("notch radius must be positive")
- `notch_sensitivity(a<0)` → ValueError("Peterson constant a must be non-negative")
- `fatigue_notch_factor(kt<1)` → ValueError("stress-concentration factor K_t must be >= 1")
- `notch_endurance_limit(Se≤0)` → ValueError("smooth endurance limit Se must be positive")
- `notch_endurance_limit(kf<1)` → ValueError("fatigue notch factor K_f must be >= 1")
- `notch_fatigue_check(nominal≤0)` → ValueError("nominal alternating stress must be positive")
- Sub-Guards propagieren exakt durch `notch_fatigue_check` (K_t, r, a, Se).

## Befund während des Audits
- Alle Anker, Monotonie- und Eigenschaftstests halten (Hypothesis 150+ Beispiele).
- Keine Abweichung zwischen Formel im Quellcode und den unabhängig gerechneten Ankern.
- Der `local_effective == 0 → inf` Zweig im Check ist unreachable (nominal>0 + kf≥1 Guard
  schließen ihn); das ist kein Defekt (Guard schützt vorher). Keine Änderung nötig.
- Kein NaN/Inf-Crash bei validen Inputs; Guards decken die dokumentierten Fälle.
- Hypothesis-Strategien auf positive endliche Werte begrenzt — Subnormale werden
  vermieden (Float-Artefakt, kein Modul-Defekt).
- `hypothesis` ist bereits in pyproject.toml dev-deps deklariert (kein Edit nötig).

## 4 Linsen
- **L1 Wahrheit:** Jede Kernbehauptung gegen unabhängigen Anker (algebraische Inverse,
  explizite Berechnung von q/K_f/Se_notched) und gegen Hypothesis-Eigenschaften geprüft —
  keine selbstreferenzielle "es sieht richtig aus".
- **L2 Drift:** Tests prüfen beobachtbares Verhalten (Rückgabewerte, exakte Messages,
  Monotonie, Identitäten), nicht Interna. Default-Konventionen und Einheiten (mm/MPa)
  aus Docstring übernommen. Determinismus explizit.
- **L3 Vollständigkeit/Naht:** Alle 4 Public-Funktionen + alle 6 dokumentierten Guard-Pfade
  + Kompositions-Identität + Kipppunkt + Property-Invarianzen. Kein Mock von Upstream;
  nur pre-existing stdlib + declared hypothesis. Legacy unangetastet.
- **L4 Realisierbarkeit:** Honest Boundary aus Docstring respektiert (empirischer
  Peterson-Fit für high-cycle uniaxial reversed fatigue von Metallen; a muss
  werkstoff-spezifisch geliefert werden; kein Low-Cycle, kein multiaxial, kein
  Risswachstum). Keine blanket NaN/Inf-Guards als Feature-Creep. Nur echte stille
  Fehler (nicht dokumentierte) würden Edit rechtfertigen — keiner gefunden.

**Fazit:** Das Modul ist REAL. Die Closed-Forms sind live und korrekt; Guards sind
hart und exakt dokumentiert. Depth-Audit erfüllt den Auftrag ohne Quell-Edit.
