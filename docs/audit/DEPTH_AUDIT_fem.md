# Depth-Audit: `src/gen/fem.py` (Euler-Bernoulli Balken-FEM)

**Verdikt: REAL.** `fem.py` ist ein echter Direct-Stiffness-FEM-Solver (Hermite-
kubisches 2-Knoten-Euler-Bernoulli-Balkenelement, reines numpy), keine getarnte
Formel. Keine Quell-Änderung nötig — alle Guards und alle Zahlen halten dem
Closed-Form-Abgleich stand.

## Beweis-Strategie (Facade-Killer)
Eine getarnte "FEM" könnte einfach die dokumentierte Formel zurückgeben. Der
Test schließt das aus, indem er nicht nur *Übereinstimmung mit der Formel*,
sondern echtes **Assembly + Solve-Verhalten** verlangt:

1. **Closed-Form-Anker (unabhängig im Test nachgerechnet):**
   - Spitzen-Durchbiegung δ = F·L³/(3·E·I)
   - Wurzel-Biegemoment M = F·L
   - Wurzel-Biegespannung σ = M·c/I = 6·F·L/(b·h²)
   - Flächenträgheitsmoment I = b·h³/12
   FEM-Resultat stimmt jeweils bis ~Maschinengenauigkeit (`rel_tol=1e-9`).

2. **Inputs werden wirklich konsumiert** (eine Konstante könnte das nicht):
   δ ∝ F (verdoppeln → ×2), δ ∝ L³ (×8), δ ∝ 1/E und ∝ 1/I (×0.5). Geprüft.

3. **Statische Bestimmtheit als subtiler Anker:** M = F·L darf *nicht* von E oder
   I abhängen — ein Fake, der das Moment aus `Durchbiegung·EI` rückrechnet, würde
   driften. Test bestätigt Invarianz.

4. **Mesh-Unabhängigkeit (n=1 vs n=32 identisch):** beweist, dass `n_elements`
   tatsächlich ein assembliertes, gelöstes Gleichungssystem steuert und das
   Balkenelement für dieses Modell exakt ist — eine Einzeiler-Formel würde das
   Argument ignorieren.

5. **Property-based (Hypothesis):** über zufällige (E, b, h, L, F, n_elements)
   — inkl. negativer Lasten — gilt δ = F·L³/(3·E·I) und M = |F·L| flächendeckend.

6. **Negativtests (Pflicht):** jeder dokumentierte Guard feuert `ValueError`:
   nicht-positive E/I/L, nicht-positiver Querschnitt (b, h), `n_elements < 1`.
   Symmetrie + Rigid-Body-Singularität der Elementsteifigkeit zusätzlich geprüft.

## 4-Linsen-Notiz
- **L1 Wahrheit:** Jede faktische Zahl ist gegen einen geschlossenen, im Modul
  selbst dokumentierten Ausdruck verankert; zwei unabhängige Wege (FEM-Solve und
  Hand-Formel) stimmen überein → keine Halluzination.
- **L2 Drift:** `root_moment` ist statisch bestimmt und nachweislich E/I-invariant;
  kein verstecktes Rückrechnen, kein stiller Default — Guards werfen statt zu raten.
- **L3 Vollständigkeit/Naht:** Querschnitt → Elementsteifigkeit → Assembly/BC/Solve
  → Moment → Spannung als durchgehende Kette getestet; Mesh-Invarianz schließt die
  Naht zwischen "ein Element" und "viele Elemente".
- **L4 Realisierbarkeit:** ehrliche Grenze (im Modul-Docstring deklariert): 1-D
  Euler-Bernoulli-Balkentheorie, KEIN 3-D-Kontinuums-FEM (keine Spannungs-
  konzentration, keine Platten/Schalen). Der Test prüft nur, was das Modul
  beansprucht — nicht mehr.

## Geänderte Quelldateien
Keine. `fem.py` blieb byte-stabil ("change nothing if correct").

## Test
`tests/test_fem_characterization.py` — 25 passed.
