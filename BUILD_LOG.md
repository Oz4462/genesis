# BUILD_LOG

## 2026-06-23 — T05 Depth-Audit + Härtung `discovery/simulated_data.py`

Verdikt **REAL**: `problem_from_simulation`/`discover_from_simulation` sampeln echt eine geschlossene
Form, generieren die Zieldaten selbst und gewinnen das Gesetz dimensional zurück (kein Stub).
Neue Charakterisierungssuite `tests/test_simulated_data_characterization.py` (21 Tests, inkl.
2 Hypothesis-Property-Tests: Potenzgesetz-Recovery für eine Familie + `baked`-Round-Trip-Identität;
Negativ-Kontrolle additive Form; alle dokumentierten Guards).

**Gefundener + behobener Defekt (L2):** Namens-Kollision (zwei Eingaben gleichen Namens, oder
Eingabe == Konstante) kollabierte still auf eine Spalte und korrumpierte den dimensionalen Solve.
Minimaler Eindeutigkeits-Guard in `problem_from_simulation` → lautes `ValueError` („keine stillen
Defaults"). Öffentliche Signaturen + Sampling unverändert; vorbestehende Tests grün (27 passed).
Details: `docs/audit/DEPTH_AUDIT_simulated_data.md`.
