# Depth-Audit: `src/gen/security.py`

**Verdikt: REAL** — keine Quelländerung nötig (`change nothing if correct`).

## Auftrag
Tiefenprüfung der drei geschlossenen Krypto-Sizing-Checks (ε-Krypto-Achse, δ-Layer)
gegen ihre **zitierten** geschlossenen Formen, um zu beweisen, dass die Zahlen
**berechnet** und nicht **gecanned/geechot** sind, plus mindestens ein Negativtest pro
dokumentiertem Fail-Loud-Pfad.

## Was geprüft wurde (`tests/test_security_characterization.py`, 16 Tests, alle grün)

### Headline-Zahlen sind echt berechnet (Input wird konsumiert)
- **Birthday-Bound (Katz & Lindell):** `p ≈ q²/2^(n+1)`.
  - Punkt-für-Punkt gegen unabhängig gerechnetes `q²/2^(n+1)` an 5 Stellen im
    `p « 1`-Regime.
  - **q²-Gesetz:** Verdopplung von `q` **vervierfacht** `p`, Verdreifachung → 9×
    (ein Konstanten-Stub kann dieses Verhältnis nicht reproduzieren).
  - **Pro Extra-Bit Raum halbiert sich `p`** (`2^(n+1)` verdoppelt sich).
  - Clamp bei `1.0` außerhalb des Regimes; `safety_factor = max/p` exakt, trackt `p`
    (mehr Uses → kleinerer SF → fällt; `2^32` Uses bei 96 bit → SF 2, `2^33` → SF 0.5).
  - Default-Schranke = NIST `2^-32` (`GCM_IV_COLLISION_BOUND`).
- **NIST SP 800-57 Part 1 Rev. 5 Table 2:** AES-128 ≡ RSA-3072 ≡ ECC-P-256 = 128 bit
  exakt; **alle** RSA/DH-Zeilen (15360→256, 7680→192, 3072→128, 2048→112, 1024→80)
  plus Granularität (3071→112, <1024→0) → beweist Tabellen-**Lookup**, keine Konstante;
  symmetrisch = Schlüssellänge für beliebige Größen; ECC = `key_bits/2` für beliebige
  Größen; `safety_factor = strength/required`.
- **NIST SP 800-38D §8.3:** GCM-Random-IV-Budget = `2^32` Invocations/Key, inklusiv an
  der Grenze; `safety_factor = max/n` (halbes Budget → SF 2, 0 → `inf`), `ok` konsistent
  mit der berechneten Zahl.

### Negativtests (dokumentierte Fail-Loud-Pfade feuern exakt)
- `birthday_collision_probability`: `space_bits ≤ 0` → `ValueError`; `n_uses < 0` →
  `ValueError`.
- `birthday_bound_check`: `max_collision_prob ∉ (0, 1]` (0.0 und 1.5) → `ValueError`.
- `security_strength_bits`: unbekannter Mechanismus (`"kyber"`) → `ValueError`
  (**nie ein geratener Wert**); `key_bits ≤ 0` → `ValueError`.
- `key_security_check`: `required_bits ≤ 0` → `ValueError`.
- `gcm_invocation_budget_check`: `n_invocations < 0` → `ValueError`;
  `max_invocations ≤ 0` → `ValueError`.

### Property-based (Hypothesis, Invarianten über den Eingaberaum)
- `p == min(q²/2^(n+1), 1)` für alle gültigen Eingaben (200 Beispiele).
- q²-Skalierung (Verdopplung → 4×) im ungeclampten Regime.
- ECC = `k/2`, symmetrisch = `k` für beliebige `k`.
- GCM-`safety_factor == max/n` und `ok ⇔ n ≤ 2^32`.
- `key_security ok ⇔ strength ≥ required` und `safety_factor == strength/required`.

## 4-Linsen
- **L1 Wahrheit:** Jede Headline-Zahl gegen ihre **zitierte** geschlossene Form
  verifiziert (Birthday-Bound, SP 800-57 Table 2, SP 800-38D §8.3) — berechnet, nicht
  geechot. Skalierungsgesetze (q², Halbierung pro Bit, max/n) schließen einen
  Konstanten-Stub aus.
- **L2 Drift:** Docstrings entsprechen dem Verhalten; alle versprochenen `ValueError`
  feuern wie dokumentiert; keine stillen Defaults (unbekannter Mechanismus → Exception,
  nie geratene Stärke) — deckt sich mit Kernprinzip „Keine stillen Defaults".
- **L3 Vollständigkeit/Naht:** Alle drei Validatoren + ihre reinen Hilfsfunktionen
  (`birthday_collision_probability`, `security_strength_bits`) abgedeckt; neuer Test
  trägt das `_characterization`-Suffix und lässt `tests/test_security.py` unberührt
  (kein Churn). Gate-Auto-Select bleibt von `tests/test_security.py` abgedeckt.
- **L4 Realisierbarkeit:** rein stdlib, offline, deterministisch, keine neue
  Abhängigkeit (`hypothesis` ist bereits deklarierte Test-Dep). Honest boundary aus dem
  Modul-Docstring respektiert: die Checks dimensionieren PARAMETER, beweisen kein
  Protokoll und ersetzen keinen Kryptografen.

## Abgleich GENESIS_PLATFORM_PLAN
Gehört zur ε-Krypto-/δ-Physik-Achse („erste MathBrain-Erträge", §55): geschlossene,
zitierbare Sizing-Formeln als hartes Gate. Audit bestätigt sie als ehrlich berechnet —
kein Backlog-Eintrag wird offen, keine Fassade gefunden.
