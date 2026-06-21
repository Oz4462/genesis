# Tier-3 — SMT Constraint Feasibility + Tier-3 Abschluss (2026-06-14)

## SMT-Feasibility (umgesetzt)

- **`src/gen/verification/constraint_smt.py`** (`smt`-Extra, geführter z3-Import):
  `check_feasibility(constraints) -> FeasibilityResult` schließt die Lücke, die
  `constraint_consistency.py` selbst benennt — **transitive/globale Infeasibility**
  (a>b, b>c, c>a) — und liefert den **Unsat-Core** (die konfligierenden Constraint-ids).
  Honest boundary: relationale Struktur (jede Seiten-Expression = eine Real-Variable,
  Zahlen als Konstanten; compound-Arithmetik opak). Idee aus PROMETHEUS/trust-core (z3),
  nativ + schlank auf Genesis' `Constraint`.
- **Verifikation:** `tests/test_constraint_smt.py` 5/5 — entscheidend: der transitive Fall
  wird von `find_contradictions` **verfehlt** (`== []`) und vom SMT-Check **gefangen**
  (infeasible + Core {k1,k2,k3}). Volle Suite **868 passed, 19 skipped**; ruff sauber.

## Tier-3 — finale Disposition (erledigt)

| Kandidat | Entscheidung | Begründung |
|---|---|---|
| **ATLAS arXiv-Ingest** | ✅ integriert (`ArxivBackend`) | direkter Fit Gap #2; live gegen echte API bewiesen |
| **PROMETHEUS Z3** | ✅ integriert (`constraint_smt`) | schließt Genesis' selbst-dokumentierte transitive-Infeasibility-Lücke |
| **buch-llm-Detektoren** | ⏭ zurückgestellt | Lizenz kein Blocker (Ozans Programm), aber buch-domänenspezifisch (Prämisse/Voice/Pacing) → kein sauberer Fit für Genesis-Specs |
| **CHORUS** (synth. Adversarial-Personas) | ⏭ zurückgestellt | echter Fit wäre ein zusätzlicher Live-LLM-Judge im Consensus; braucht die schwere Synthetik-Population-Engine → kein MVP-Mehrwert über den bestehenden N-Judge-Consensus hinaus |
| **AGORA** (Agenten-Budget-Auktionen) | ⏭ zurückgestellt | nur bei realer Multi-Agent-Skalierung nötig; aktuell kein Bedarf |

**Fazit:** Die zwei Tier-3-Kandidaten mit echtem, testbarem Genesis-Mehrwert sind integriert
und live/offline bewiesen. Die übrigen sind bewusst und begründet zurückgestellt (kein
Force-Fit) — Tier-3 ist damit abgeschlossen. Reaktivierbar als eigene PoV-gegatete Specs,
falls ein konkreter Bedarf entsteht (z. B. CHORUS-Judge bei Multi-Agent-Skalierung).

## Deferred (Verdrahtung, owner-gated Core)

- `check_feasibility` optional in `pipeline.assess_specification` einhängen (z3 ist Extra →
  geführt, kein harter Core-Gate-Dep; konsistent mit dem „deferred optional layer", den
  `constraint_consistency` bereits beschreibt).
