# Depth-Audit: `src/gen/identity_research.py`

**Aufgabe T05** — Bounded Identity Falsifier + Witness Finder.
**Verdikt: REAL.** Keine Quellcode-Änderung nötig (Prinzip „change nothing if correct").

Neuer Facade-Detektor: `tests/test_identity_research_characterization.py` (16 Tests,
inkl. 2 Hypothesis-Property-Tests + 3 Negativtests). Legacy-Tests unverändert grün.

## Headline-Claim & Beweis

Das Modul ist deterministisch und LLM-frei. Wahrheit entsteht durch **DEDUKTION**
(`prove_identity`: ein echter Kernel oder CAS etabliert `simplify(lhs-rhs)==0`) oder durch
**FALSIFIKATION** (`falsify`: ein deterministisches Gitter findet kein Gegenbeispiel).
Daten-/Gitter-Konsistenz ist ein **Gate, kein Beweis**; eine falsche Identität wird mit
einem **konkreten Gegenbeispiel-Witness REFUTED**; `assess_identity` liefert ehrlichen
Status + Severity und merged niemals zwei verschiedene Claims fälschlich.

Jeder Test ist ein echter Facade-Detektor: er prüft entweder, dass sich der Output
**bedeutsam ändert, wenn ein treibender Input sich ändert** (Input wird wirklich
konsumiert, keine Konstante), oder dass ein dokumentierter **Fail-loud/Abstention-Pfad
exakt feuert**.

### Was die Tests konkret nachweisen
- **DEDUKTION** ist echt und gehaltsgetrieben: ein Polynom (`(x+1)²==x²+2x+1`) wird vom
  **z3-QF_NRA-Kernel** entschieden (`method=z3_qfnra`, `z3_certified`), eine
  Trig-Identität (`sin²+cos²==1`) fällt aus dem Polynomfragment heraus und wird per **CAS**
  bewiesen (`cas_simplify`). Der Pfad wird aus dem Inhalt gewählt, nicht hartcodiert.
- **Gitter ist ein Gate**: `prove_identity(..., grid_passed=False)` verweigert den Beweis
  selbst bei einer *wahren* Identität (`method=none`, `admitted`) — kein fabrizierter
  Beweis (keine stillen Defaults).
- **Witness ist echt**: bei einer falschen Identität wird `lhs-rhs` am gemeldeten Witness
  **unabhängig nachgerechnet** und ist nachweislich ≠ 0. Property-Test: für alle `c∈[1,9]`
  ist `x²==x²+c` REFUTED mit Residuum exakt `-c`.
- **Manifest wird konsumiert**: `sqrt(x²)==x` flippt REFUTED (auf R, Gegenbeispiel x<0)
  → SURVIVED_NOVEL (auf R+) bei sonst identischem Input.
- **Kein falscher Merge**: der Fingerprint kollabiert nur `proved_equal` (x+y==y+x ≙ 2x==x+x)
  auf |0; eine falsche Relation und ein anderer `manifest_hash` ergeben verschiedene
  Fingerprints.
- **Negativpfade**: undeklariertes Symbol → `_parse` wirft `ValueError` (fail-loud) bzw.
  `assess_identity` → honest INCONCLUSIVE, severity 0, keine geratene Wahrheit.

## 4 Linsen

- **L1 Wahrheits-Linse:** Keine faktische Aussage ohne Beleg. Wahrheit kommt nur aus
  z3-Kernel (rigoros), CAS (heuristisch, sicheres Fragment) oder Gitter-Überleben;
  `cas_certified`/`z3_certified` ist ehrlich als **nicht** Lean-kernel-verifiziert markiert.
  Severity wird bei REFUTED auf 0 gesetzt — keine Information aus einem Widerspruch.
- **L2 Drift-Linse:** Docstrings decken sich mit dem Code: „SURVIVED != universal identity",
  „grid refutation overrides CAS", „false merge forbidden". Der Witness-Re-Check schließt
  Drift zwischen behauptetem und tatsächlichem Gegenbeispiel aus. Kein Drift gefunden.
- **L3 Vollständigkeits-/Naht-Linse:** Getestet sind alle drei Headline-Funktionen plus die
  Nahtstellen (parse-Fehler → INCONCLUSIVE; grid-Gate → Beweisverweigerung; Manifest-Domain
  → Status-Flip). `assess_inequality`/`explore_family`/`persist_*` sind außerhalb des
  Headline-Scopes und bleiben von den bestehenden Tests abgedeckt.
- **L4 Realisierbarkeits-Linse:** Tests nutzen nur stdlib + bereits deklarierte Deps
  (sympy, mpmath, hypothesis, z3 via `importorskip` für den kernel-spezifischen Fall), keine
  Netzwerk-/Subprozess-Abhängigkeit, deterministisch (exakte sympy-Anker, keine `random()`),
  schnell (~4 s). Voll reproduzierbar (Kernprinzip 5).

## Abgleich GENESIS_PLATFORM_PLAN

Math-Research-Branch „Bounded Identity Falsifier" (erster Stein): bestätigt als REAL und
gegen Fassade abgesichert — Deduktion + Falsifikation + ehrliche Abstention sind durch
ausführbare Tests belegt, nicht nur behauptet.
