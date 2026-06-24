# Depth-Audit — `section_optimizer.py` (T04)

**Verdict: REAL (proposer/gate split genuine) — with ONE genuine defect fixed: an honest-abstention path that was dead code.**

## Was geprüft wurde
`section_optimizer.py` schlägt die leichteste rechteckige Kragträger-Sektion vor (Minimierung von
`b·h·L`) unter der Biege-Streckgrenze `σ = 6·F·L/(b·h²) ≤ σ_allow` und lässt das deterministische
Gate (`verification.cegis.cantilever_yield_check` + z3-Beweis `verification.smt`) das Vorschlag-
Ergebnis **unabhängig** re-verifizieren. Backlog-Bezug: GENESIS_PLATFORM_PLAN — generatives Design
(Agent-B) in der ehrlichen Proposer/Gate-Form.

## Befund: was REAL ist
- **Closed-Form echt konsumiert.** Die gemeldete `stress` ist exakt `6·F·L/(b·h²)` (unabhängig
  nachgerechnet, `rel=1e-12`), `safety_factor == σ_allow/stress`, `volume == b·h·L`. Kein kanonischer
  Stub: größeres `σ_allow` → strikt kleineres Volumen; größere Last → schwerere Sektion.
- **Proposer/Gate-Split echt.** `propose_and_verify.gate_passed` wird im Test **bit-für-bit** durch
  einen separaten Aufruf von `cantilever_yield_check` reproduziert (für jedes Material im Registry),
  und das Gate weist eine absichtlich unterdimensionierte Sektion zurück (kein Gummistempel).
- **`σ_allow` geerdet** in der Material-Streckgrenze (`materials.get_material`, provenance-tragend),
  nie eine anonyme Konstante. z3-Verdikt ehrlich (proved / unavailable, nie stiller Pass).

## Genuiner Defekt (gefixt) — tote Abstention
Vor dem Fix war die dokumentierte ehrliche Abstention `feasible=False` ("no design within the bounds
meets the stress limit") **strukturell unerreichbar**: Die Breite `b` war nach oben unbeschränkt, also
absorbierte selbst eine absurde Überlast eine Lösung (empirisch: `F=1e9, L=1e6, σ_allow=1e-6` →
`feasible=True`, `b≈7.2e6 mm`). Das `feasible`-Feld + der `return …, False`-Zweig waren toter Code —
eine Fassade gegen Kernprinzip §4 (ehrliche Abstention ist erwünschter Output).

**Minimaler Fix:** Parameter `max_wall: float = inf` (echte Fertigungsgrenze = max. Bauraum/Wandmaß).
Default `inf` → **alles bestehende Verhalten unverändert** (alle Alttests grün, CLI-Caller unberührt).
Bei endlichem `max_wall`, wenn keine Sektion in `[min_wall, max_wall]` die Spannung hält, gibt die
Suche ehrlich `feasible=False` (`stress=inf`) zurück — `propose_and_verify` zertifiziert dann nichts
(`gate_passed=False`, Detail "no section …"). Kein Feature-Creep über den Defekt hinaus.

## 4 Linsen
- **L1 Wahrheit:** Spannung/Volumen/SF gegen unabhängige Closed-Form geprüft (`rel=1e-12`); Gate-
  Verdikt unabhängig reproduziert. Keine ungeerdete Zahl.
- **L2 Drift:** Fix strikt auf den toten Abstention-Zweig begrenzt; `max_wall=inf` bewahrt das
  Optimum byte-genau (Regressionstest `test_finite_max_wall_does_not_change_…`).
- **L3 Vollständigkeit/Naht:** Negative-Batterie vollständig (nicht-positive `force/arm/σ_allow`,
  `safety_factor≤0`, unbekanntes Material); Abstention-Naht jetzt testbar; Hypothesis-Invariante
  (Proposer und Gate widersprechen sich nie über den Eingaberaum).
- **L4 Realisierbarkeit:** `max_wall` ist eine reale Bauraumgrenze; offline, deterministisch, keine
  neue Abhängigkeit (stdlib + hypothesis, bereits deklariert).

## Tests
`tests/test_section_optimizer_characterization.py` — 22 neue Tests inkl. Property-Based-Invariante.
Lauf: `PYTHONPATH=src pytest tests/test_section_optimizer_characterization.py tests/test_section_optimizer.py`
→ **33 passed**.
