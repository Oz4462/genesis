# Depth-Audit: `src/gen/fracture.py` (LEFM crack axis)

**Verdikt: REAL.** Keine Quell-Änderung nötig — alle vier öffentlichen Funktionen rechnen
ihre Lehrbuch-Closed-Forms exakt, nicht als kanonisierte Konstanten, und jeder dokumentierte
Fail-Loud-Pfad feuert. T04 fügt nur die Charakterisierungs-Tests + dieses Dokument hinzu.

## Abgedeckte Oberfläche
`stress_intensity`, `critical_crack_size`, `fracture_check`, `paris_life`
(neu: `tests/test_fracture_characterization.py`, 21 Tests, alle grün; Legacy
`tests/test_fracture.py` 14 Tests bleiben grün — keine Regression).

## Anker (independent cross-checks, kein geteiltes Algebra)
- **K = Y·σ·√(πa)** gegen den Irwin-Anker `K(1,100,1) = 100·√π = 177.2453850905516`
  MPa·√mm; plus Hypothesis-Eigenschaft: K ist linear in Y und σ, skaliert wie √a
  (`K(Y,σ,4a) = 2·K`).
- **a_c = (1/π)·(K_IC/(Y·σ))²** als EXAKTE Inverse von `stress_intensity`: Hypothesis-
  Round-Trip über 200 Beispiele — `K(Y, σ, a_c) == K_IC` (rel_tol 1e-9); Anker
  `a_c(2000,1,100) = 400/π = 127.32395447351628` mm; Skalierung a_c ~ K_IC², ~1/Y², ~1/σ².
- **fracture_check** komponiert K und a_c aus den Teilfunktionen, `safety_factor == K_IC/K`,
  `ok` kippt exakt bei `a == a_c`; `a == 0 → K == 0 → SF = +inf` (dokumentierter Zweig);
  Default `Y = 1.12` (Kantenriss) bestätigt.
- **paris_life** gegen eine unabhängige Trapez-Integration von `dN = da/(C·dK^m)`
  (200 000 Schritte, kein geteiltes Algebra) für m=3 UND m=4 (rel_tol 1e-2); Anker
  `N(m=3) = 17480.851358949647`; `N ~ 1/C` exakt; Hypothesis-Monotonie: tieferer
  Anfangsriss ⇒ strikt kürzere Restlebensdauer.

## Negativtests (keine stillen Defaults)
- `stress_intensity(a<0)` → ValueError; `critical_crack_size` lehnt nicht-positives
  K_IC / Y / σ ab; `fracture_check(σ≤0)` → ValueError; `paris_life`: m==2 →
  NotImplementedError (Power-Form dividiert durch 0), a_final≤a_initial → ValueError,
  nicht-positives C / Δσ / Risslänge → ValueError.

## Befund während des Audits
Ein erster Hypothesis-Lauf der √a-Skalierungs-Eigenschaft fiel bei `a = 5e-324`
(Subnormal/Denormal) — `4.0·a` rundet im Denormal-Bereich, das ist ein Float-Artefakt der
Test-Strategie, KEIN Defekt im Modul (die geschlossene Form ist korrekt). Strategie auf
`a ≥ 1e-3` begrenzt; danach hält die Eigenschaft. → bestätigt: kein Quell-Edit.

## 4 Linsen
- **L1 Wahrheit:** Jede Behauptung gegen einen independenten Anker (Closed-Form-Inverse bzw.
  numerische Integration) geprüft — keine selbstreferenzielle Zusicherung.
- **L2 Drift:** Tests gegen das beobachtbare Verhalten (Rückgabewerte/Exceptions), nicht
  gegen die Implementierung; Default-Y und Einheiten-Konvention aus dem Docstring gepinnt.
- **L3 Vollständigkeit/Naht:** Alle vier öffentlichen Funktionen + alle dokumentierten
  Guards + Grenzfälle (a=0, SF-Kipppunkt, m=2-Sonderfall) abgedeckt; Legacy-Test unberührt.
- **L4 Realisierbarkeit:** Honest boundary aus dem Docstring respektiert — LEFM mit
  konstantem Y, Mode I, kein J-Integral/CTOD, kein Y(a/W); die Tests behaupten nichts
  darüber hinaus.
