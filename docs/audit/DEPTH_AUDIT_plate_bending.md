# Depth-Audit: `src/gen/plate_bending.py`

**Verdikt: REAL.** Kein Quell-Edit nötig — alle Formeln und Wächter sind echt
berechnet bzw. feuern wie dokumentiert. Neuer Facade-Detektor:
`tests/test_plate_bending_characterization.py` (11 Tests, davon 4 property-based via
Hypothesis). Volle Suite `test_plate_bending*.py`: 24 passed.

## Was geprüft wurde (4 Linsen)

**L1 — Wahrheit / Closed-Form-Gegencheck.** Jede Kirchhoff-Form wird im Test
unabhängig (longhand `_ref_*`-Funktionen) nachgerechnet und gegen das Modul gehalten:
- Flexur-Steifigkeit `D = E·t³/(12·(1−ν²))` → Stahl-Anker `D = 2 403 846.15…`.
- Eingespannt: `w = q·R⁴/(64·D) = 0.065 mm`, `σ_Rand = 3·q·R²/(4·t²) = 30.0 MPa`
  (Anker q=0.1 MPa, R=100, t=5, E=210000, ν=0.3) — auf rel_tol 1e-12 getroffen.
- Gelenkig deutlich weicher: `w_ss/w_clamped = (5+ν)/(1+ν) = 4.0769…` exakt.

**L2 — Drift / kein stiller Default.** Property-Tests (200 Beispiele je) über einen
gefegten Eingaberaum beweisen, dass die Eingaben WIRKLICH konsumiert werden, nicht
gecannt: `D ∝ t³` (Faktor k³ unabhängig von E, ν), `w ∝ R⁴` und `∝ 1/t³`, der
Weichheits-Quotient `(5+ν)/(1+ν) > 1` für ν∈(−1,0.5), und
`safety_factor = allowable/max_stress` mit `ok = (SF ≥ 1)`. Die `edge`-Wahl selektiert
nachweislich eine andere Formel (clamped 30 MPa ≠ simply_supported 49.5 MPa).

**L3 — Vollständigkeit / Naht.** Negativ-Test deckt jeden dokumentierten Wächter ab:
ValueError bei nicht-positivem E / Dicke / Radius / allowable_stress, bei ν an/außerhalb
der offenen Schranken (−1, 0.5) und bei unbekanntem `edge`-String. „Ein Gate ohne Test
existiert nicht" — jetzt existieren sie.

**L4 — Realisierbarkeit / Randfälle.** Eine fp-Subtilität entdeckt und sauber
behandelt (kein Bug): der Anker-Stress ist `30.0000000000000004`, daher liefert
`allowable=30.0` ein SF knapp < 1 → `ok=False`. Das ist korrektes `SF ≥ 1`-Verhalten,
kein Defekt; der Boundary-Test ankert deshalb an dem vom Modul berechneten Stress
(× 0.99 / 1.0 / 1.01) statt an einem gerundeten Literal.

## Abgleich GENESIS_PLATFORM_PLAN
Deckt die 2-D-Biege-Achse (CAD/CAE-Kern) ab: ehrliche, quellengestützte Kirchhoff-
Closed-Forms (Timoshenko & Woinowsky-Krieger 1959; Roark) mit hartem Gate
(`plate_bending_check`) — keine Halluzination, ehrliche Grenze (klein-Auslenkung,
kreisförmig, uniform) im Docstring deklariert.
