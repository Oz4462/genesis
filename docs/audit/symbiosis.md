# Depth-Audit: `discovery/symbiosis.py` — Grok cross-model symbiosis

**Datum:** 2026-06-23 · **Modul:** `src/gen/discovery/symbiosis.py` · **Test:**
`tests/discovery/test_symbiosis_characterization.py`

## Headline-Claim
Cross-Model-Symbiose / Drift-Check (CLAUDE.md §3): ein **zweites Modell** (anderer Familie als der
Generator, z. B. `grok-build` vs. `claude-opus-4-8`) **verifiziert den Generator unabhängig**;
Übereinstimmung wird angenommen (kein Drift), Widerspruch wird als **Drift** ausgewiesen und niemals
still als „verifiziert" durchgewinkt. Single-Model-Selbstcheck zählt nicht als Verifikation.

## Verdikt: **REAL (nach gezielter Ergänzung)**

### Befund vor dem Fix — PARTIAL-FACADE bzgl. des wörtlichen §3-Claims
`symbiosis_discover` / `council_discover` waren echt, nutzten als Verifikator aber den
**deterministischen Gate** (`judge_candidate`), nicht ein zweites *Modell*. Das ist eine starke
Trennung (modellfrei), erfüllte aber nicht die wörtliche „Modell-gegen-Modell"-Drift-Prüfung aus
CLAUDE.md §3: es existierte keine Funktion, die ein zweites Modell unabhängig dieselbe Frage
beantworten lässt und Uneinigkeit als Drift meldet.

### Fix — `cross_model_drift_check(...) -> DriftReport`
Dependency-injizierter `LLMClient`-Verifikator (offline via `ScriptedLLM`, live via CLI). Drei
ehrliche, sich gegenseitig ausschließende Verdikte; `verified=True` **nur** bei echter
Cross-Model-Korroboration:

| Fall | Bedingung | `verified` | `drift` | `status` |
|------|-----------|-----------|---------|----------|
| Korroboration | Gate-bestandener Verifikator-Vorschlag matcht den Claim | True | False | `corroborated` |
| Drift | Verifikator lief, korroborierte aber nicht | False | True | `drift` |
| Abstention | Verifikator-Fehler / Timeout | False | False | `abstention` |

Guards: `assert_different_families(generator, verifier)` ⇒ `ModelConflictError` bei gleicher
Familie (Selbstcheck wird **vor** jedem Modellaufruf verweigert). Verifikator-Exception ⇒ ehrliche
Abstention statt Fake-„verified". Der Match ist exponenten-basiert mit Toleranz (fehlender Schlüssel
= Exponent 0, also dieselbe physikalische Form).

### Belege (Tests, alle offline, kein Netz)
- `test_agreeing_verifier_corroborates_with_no_drift` — Zustimmung ⇒ `verified=True, drift=False`.
- `test_disagreeing_verifier_flags_drift_and_does_not_verify` — Widerspruch ⇒ `drift=True,
  verified=False` (Kern-Anti-Facade-Assertion: kein stiller Durchlauf).
- `test_empty_verifier_response_does_not_verify` — kein verwertbarer Vorschlag ⇒ nicht verifiziert.
- `test_same_family_self_check_is_refused` — gleiche Familie ⇒ `ModelConflictError` (Negativtest).
- `test_verifier_error_yields_honest_abstention_not_fake_verified` — Timeout ⇒ ehrliche Abstention
  (Negativtest).
- `test_wrong_law_verifier_never_falsely_verifies` — **Property (Hypothesis):** ein Verifikator, der
  je ein anderes als das wahre Kepler-Gesetz vorschlägt, kann *niemals* `verified=True` erzeugen.

## 4 Linsen
- **L1 Wahrheit:** `verified` ist ausschließlich an unabhängige Cross-Model-Korroboration gekoppelt;
  keine Behauptung ohne zweites, gegated bestätigtes Modell-Urteil.
- **L2 Drift:** Uneinigkeit wird explizit als `drift` ausgegeben statt geschluckt; Verifikator-Fehler
  als `abstention` statt Fake-Pass.
- **L3 Vollständigkeit/Naht:** drei erschöpfende, disjunkte Verdikte; bestehende
  `symbiosis_discover`/`council_discover`-Pfade unverändert (Regression grün).
- **L4 Realisierbarkeit:** Verifikator dependency-injiziert ⇒ offline reproduzierbar testbar
  (`ScriptedLLM`/Stub), live über die vorhandenen CLIs.

**PLATFORM_PLAN-Abgleich:** stützt das Cross-Model-Prinzip (Wissensbasis/Verifikation) — der zweite
Modell-Brain widerlegt jetzt nachweisbar, statt nur zu echoen.
