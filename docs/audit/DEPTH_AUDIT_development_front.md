# DEPTH AUDIT — `grenzverschiebung/development_front.py`

**Modul:** `src/gen/grenzverschiebung/development_front.py`
**Headline-Anspruch (PLATFORM_PLAN §3.3):** „Kartiert die Grenze von heute und typisiert
die Grenzen" — wichtigster Output ist die *Experimentleiter*.
**Datum:** 2026-06-23 · **Aufgabe:** T05

---

## Verdikt

**Vorher: PARTIAL-FACADE.** Der reiche, ehrliche Output existierte NUR für den hartcodierten
Jetpack-Substring (`"jetpack" in idee.lower()` bzw. `"mensch"+"fliegen"`). Für jede andere Idee
lieferte der `else`-Zweig ein nahezu fixes Skelett:

- `bekannte_grenzen` wurde nur zu einem **flachen** `{g: MISSING_MEASUREMENT}`-Dict verarbeitet
  (konstanter Typ, ignorierte den Textinhalt → „stiller Default").
- `bekannte_grenzen` tauchten **weder** in `fehlende_faehigkeiten` **noch** in einem
  Experimentleiter-Schritt auf — die Grenzen wurden also nicht in Tests überführt.
- `idee` floss außer in `traum` nirgends ein: `heutige_grenze`, `fehlende_faehigkeiten`,
  `experimentleiter`, `abbruchkriterien` waren für ALLE Nicht-Jetpack-Ideen identisch.
  → Zwei verschiedene Ideen ergaben praktisch dieselbe Map (Facade).
- Ohne Grenzen wurde eine **erfundene** Pseudo-Grenze `"generische Machbarkeit der Idee"`
  fabriziert statt ehrlich abstinent zu sein.
- Leere/Whitespace-`idee` ergab still eine (sinnlose) Map statt lautem Fehler.

**Nachher: REAL (generischer Pfad).** Der headline-Verb *kartieren* konsumiert die Eingabe jetzt
nachweislich; der Jetpack-Pfad bleibt als geschützter Spezialfall erhalten.

---

## Was real gemacht wurde (nur Verhalten, keine Signaturänderung)

1. **Typisierung aus dem Text** — neuer `_klassifiziere_grenze(text) -> Grenztyp` leitet den
   Grenztyp aus Stichworten ab (`widerspricht`→CONTRADICTS, `durchbruch/energiedichte`→
   NEEDS_BREAKTHROUGH, `messung`→MISSING_MEASUREMENT, …). Kein konstanter Default mehr; ohne
   Signal fällt es ehrlich auf MISSING_MEASUREMENT (schwächste Aussage, kein Optimismus).
2. **Jede bekannte Grenze wird dreifach konsumiert:** typisierter Eintrag in `grenzen`,
   Referenz in `fehlende_faehigkeiten`, **und** ein eigener Experimentleiter-Schritt
   („kleinster sicherer Test" pro Grenze).
3. **`idee` fließt ein:** `heutige_grenze` und der erste Experimentleiter-Schritt zitieren die
   konkrete Idee → zwei verschiedene Ideen ergeben meaningfully verschiedene Maps.
4. **Ehrliche Abstinenz:** ohne `bekannte_grenzen` bleibt `grenzen == {}` (keine erfundene
   Pseudo-Grenze); eine Meta-Lücke + ein Hypothese-Schritt bleiben ehrlich erhalten.
5. **Abgeleitete Abbruchkriterien:** Grenzen vom Typ NEEDS_BREAKTHROUGH/CONTRADICTS ziehen
   automatisch ein hartes Stopp-Kriterium nach sich.
6. **Negativpfad:** leere/whitespace `idee` → `ValueError` (keine stille leere Map). Leere
   Grenz-Strings werden herausgefiltert.

Signaturen von `DevelopmentFrontMap`, `ExperimentleiterSchritt`, `Grenztyp` und
`map_development_front` sind **unverändert** (Voraussetzung für die parallelen Tasks 2/3/4).

## Tests (`tests/test_development_front_characterization.py`)

Facade-Killer (scheiterten am alten else-Zweig) + Regression + Property-Test (Hypothesis):
Konsum jeder Grenze, Typ-Ableitung (≥3 verschiedene Typen), zwei-Ideen-≠-eine-Map,
ehrliche Abstinenz (`grenzen == {}`), Whitespace-Filter, `ValueError`-Negativpfad,
intakter Jetpack-Pfad. **13 Tests grün** (inkl. der 2 bestehenden in `test_development_front.py`).

## 4 Linsen

- **L1 (Wahrheit):** Typ folgt aus dem Inhalt, nicht aus einem geratenen Default; ohne Signal
  ehrlich MISSING_MEASUREMENT bzw. leere `grenzen`. Provenance (`quelle`/`run_id`) bleibt.
- **L2 (Drift):** Headline „kartieren/typisieren" deckt sich jetzt mit dem Code für JEDE Idee,
  nicht nur Jetpack. Keine stillen Defaults mehr (Kernprinzip).
- **L3 (Vollständigkeit/Naht):** Jede Grenze wird über alle drei Ausgabefelder hinweg
  konsistent geführt; Jetpack-Pfad als Naht-geschützte Regression erhalten;
  `boundary_reviser`-Konsument (Runtime-Import) bleibt grün.
- **L4 (Realisierbarkeit):** Edge-Cases (leere Idee, Whitespace-Grenzen, kein-Signal-Eingabe,
  Durchbruch-Grenzen) sind abgedeckt; deterministisch, keine neuen Dependencies außer Hypothesis
  (Test-only, bereits deklariert).

**Offen / nächster Stein:** echte Wissensbasis + `capability_gap_analyzer` statt
Stichwort-Heuristik (in `naechste_stufe` ehrlich vermerkt).
