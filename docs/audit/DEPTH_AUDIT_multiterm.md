# Depth-Audit: `src/gen/discovery/multiterm.py`

**Task:** T01 — additive multi-term discovery (`discover_multiterm`, `multiterm_out_of_sample_validate`).
**Verdict: REAL** (with one genuine silent-default defect found and fixed).

## Was geprüft wurde

Charakterisierungs-Test `tests/test_multiterm_characterization.py` (29 Fälle inkl. 3 Property-Tests
mit Hypothesis), der die vier Maschinen-Bausteine als *berechnet, nicht gefälscht* nachweist:

| Anspruch | Beweis im Test | Ergebnis |
|---|---|---|
| **Lineare lstsq-Anpassung ist exakt + datengetrieben** | Drei Koeffizienten-Paare → drei passend zurückgewonnene Koeffizienten; distinct in → distinct out; Determinismus bei gleichem Input | REAL |
| **Greedy-Vorwärtsselektion ist eine echte Schleife** | Term-Anzahl folgt der Datenstruktur (2-Term-Gesetz → 2, Kepler-Potenzgesetz → 1); `max_terms` + `improvement_threshold` steuern den Eintritt nachweisbar | REAL |
| **Pruning feuert und ist schwellen-/inputabhängig** | Kinematik bleibt exakt 2 Terme (transienter Blend-Term wird genullt+entfernt); hohes `prune_rel_tol` über-prunt auf 1 | REAL |
| **Held-out-Scoring rechnet auf TRAIN, bewertet auf HELD-OUT** | echtes Gesetz transferiert (test_R²>0.99, Gap<1e-3); Rauschen kollabiert; Score variiert mit dem Split-Seed → wirklich aus Held-out-Punkten berechnet | REAL |

**Property-Invarianten (Hypothesis, alle positiven Koeffizienten):**
- gemeldetes `r_squared`/`rmse` == unabhängig nachgerechnetes R²/RMSE aus der Vorhersage (kein Canned-Wert);
- Linearität der kleinsten Quadrate: Ziel ×k ⇒ jeder Koeffizient ×k;
- bedingte Exaktheit: wenn Greedy ein sauberes R²≈1-2-Term-Gesetz findet, sind die zurückgewonnenen
  Koeffizienten exakt die erzeugenden.

## Gefundener + behobener Defekt (L4-Kantenfall / „keine stillen Defaults")

`discover_multiterm(..., max_terms=0)` (und negativ) lieferte **still ein erfundenes 1-Term-Gesetz**:
bei `max_terms < 1` läuft die Greedy-Schleife (`while len(selected) < max_terms`) nie, `selected`
bleibt leer, und der `not selected`-Fallback — der *nur* für singuläre Fits / leeren Pool gedacht ist —
griff und gab `pool[0]` zurück. Ein Modell mit < 1 Term ist sinnlos; ein geratenes, input-unabhängiges
Ergebnis statt eines lauten Fehlers verletzt das Kernprinzip „keine stillen Defaults bei faktischen
Dingen". **Fix:** expliziter Guard `if max_terms < 1: raise ValueError(...)` direkt am Funktionsanfang;
der Fallback bleibt für den legitimen singulären-Fit-Fall erhalten. Regressionstest:
`test_max_terms_below_one_is_a_hard_error_not_a_silent_law` (parametrisiert 0/-1/-5).

## Bewusst NICHT geändert (dokumentierte ehrliche Grenze, kein Bug)

Greedy/OMP ist **nicht** global optimal: für manche Koeffizienten-Verhältnisse wählt der erste Zug einen
dimensional gültigen „Blend"-Term und landet in einem schlechteren lokalen Optimum (R² < 1). Das ist im
Modul-Docstring als ehrliche Grenze deklariert und wird **out-of-sample** ehrlich gefangen — kein
In-Sample-Term-Count-Versprechen für alle Eingaben. Der Property-Test asserted darum die *garantierten*
Invarianten (interne Konsistenz, Linearität), nicht globale Optimalität.

## 4 Linsen
- **L1 Wahrheit:** Mathematik (lstsq, Selektion, Pruning, Held-out-R²) verifiziert berechnet, nicht canned.
- **L2 Drift:** ein echter Silent-Default (`max_terms<1`) gefunden + geschlossen; sonst kein Drift Doc↔Code.
- **L3 Vollständigkeit/Naht:** alle bestehenden Tests grün; neuer Test kollidiert pfadfrei (`_characterization`-Suffix).
- **L4 Realisierbarkeit:** Fix minimal, fail-loud, ohne Verhaltensänderung am Happy Path.
