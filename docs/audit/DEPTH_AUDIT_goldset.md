# Depth-Audit: `src/gen/goldset.py` (curated measurement set loader + scorer)

**Datum:** 2026-06-23 · **Task:** T03 · **Verdikt:** **REAL** (keine Quell-Änderung nötig)

## Auftrag
`load_goldset` (fail-loud Loader über `goldset/v1.json`) und `score` (deterministischer
Scorer) auditieren. Headline: der `ok`-Riegel ist *keine Fabrikation irgendwo*
(`hallucinations` leer); ein **nonsense**-Fall, der *beantwortet* wird, ist per
Konstruktion eine Halluzination, und ein **unvollständiger** Lauf wird **verweigert**
(nie still hochgerechnet).

## Befund (Facade-Detektor)
Neue Tests: `tests/test_goldset_characterization.py` (17 Tests, alle grün; Legacy
`tests/test_goldset.py` 13/13 weiter grün — keine Quell-Edits).

Die Tests beweisen die zwei Pflicht-Eigenschaften:
- **(a) Input wird wirklich konsumiert (kein Konstant-Wert):** dieselbe Gold-Menge
  gegen verschiedene `RunOutcome`-Maps ergibt *verschiedene* Raten. Ein gekippter
  nonsense-Ausgang (abstain → answered) senkt `abstention_recall`, landet in
  `hallucinations` und kippt `ok` auf `False`. Eine Property (Hypothesis, 80 Beispiele)
  zeigt: `set(hallucinations)` == *exakt* die unbelegt beantworteten trap/nonsense-Fälle.
- **(b) Fail-loud / Abstention feuert exakt:** unvollständiger Lauf → `ValueError`
  ("incomplete"); leere Fallmenge → `ValueError` ("no cases"); Loader verwirft
  fehlende `must_contain` bei fact, behavior/kind-Mismatch, Duplikat-id, unbekannten
  kind, leeren input und eine Menge ohne nonsense-Fälle.

Zusätzlich charakterisiert (bewusste, dokumentierte Design-Entscheidungen — **kein** Bug):
- Ein **falscher** fact-Wert ist ein *Miss* (senkt `fact_accuracy`, in `failures`), aber
  **keine** Fabrikation → `ok` bleibt `True`. Genau wie im Docstring zugesichert.
- Token-Matching via `_token_set` (`[\w.]+`) verhindert Substring-Treffer: Token `"4"`
  passt **nicht** auf `"M4x16"`/`"14"` (G3-Sicherheit, real getestet).
- `abstained=True` mit nicht-leerem `text` wird als *beantwortet* gewertet (versteckte
  Antwort) → für nonsense eine Fabrikation. Real getestet.

## 4 Linsen
- **L1 Wahrheit:** Raten = echte Quotienten aus den Ausgängen; `ok` knüpft strikt an
  leere `hallucinations`. Keine geratenen Default-Werte. ✔
- **L2 Drift:** Verhalten deckt sich Wort-für-Wort mit den Docstrings/Headline
  (nonsense-answered = Halluzination; unvollständig = verweigert). Kein Drift. ✔
- **L3 Vollständigkeit/Naht:** Loader-Gates (alle drei kinds Pflicht, fact braucht
  Tokens, behavior↔kind, Unikat-ids) + Scorer-Gates (komplett, nicht leer) sind alle
  durch Negativtests abgedeckt — „ein Gate ohne Test existiert nicht". ✔
- **L4 Realisierbarkeit/Edge:** Token-Matching ist bewusst konservativ (eher Under-Credit
  als Substring-Falschtreffer); `abstained+text` und falscher-fact-als-Miss sind als
  Edge-Fälle gepinnt. Beobachtete, **nicht** als Defekt eingestufte Punkte: ein
  Nicht-Dict in `cases` löst `AttributeError` statt `ValueError` aus (immer noch
  fail-loud), und überzählige `outcomes` für unbekannte ids werden ignoriert — beides
  außerhalb des Headline-Vertrags und ohne Risiko stiller Falsch-Raten; daher per
  „change nothing if correct" **nicht** angefasst. ✔

## Ergebnis
`goldset.py` ist **REAL**: Loader und Scorer konsumieren ihre Eingaben echt, gaten
fail-loud und halten den No-Fabrication-Riegel deterministisch ein. **Keine
Quell-Änderung** vorgenommen; der Audit-Wert liegt im neuen Charakterisierungstest, der
die Headline falsifizierbar festnagelt.
