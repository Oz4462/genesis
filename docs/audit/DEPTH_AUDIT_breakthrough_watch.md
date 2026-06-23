# Depth-Audit: `src/gen/grenzverschiebung/breakthrough_watch.py`

**Verdict: FACADE (now fixed) → REAL.**

Die Headline-Behauptung — *„beobachtet neue Tools/Papers/Materialien und liefert einen
`FrontierUpdate`, der die Roadmap-Gaps adressiert"* — war auf `main` eine Facade.
`watch_frontier` konsumierte von der Eingabe-`DevelopmentFrontMap` **ausschließlich
`.traum`** und gab eine **fixe, hartkodierte Item-Liste** mit Konserven-Strings
(`relevanz_fuer_gap="Energie-Dichte P1"` usw.) zurück, die mit den realen Gaps DIESER
Karte (`front_map.fehlende_faehigkeiten`, `front_map.grenzen`) nichts zu tun hatten.

## Der Defekt (bestätigt)

```python
traum = front_map.traum            # einziges konsumiertes Feld
if "jetpack" in traum.lower() ...: # substring-match auf den Traum
    items = [ FrontierItem(..., relevanz_fuer_gap="Energie-Dichte P1", ...), ... ]  # KONSERVE
else:
    items = [ FrontierItem(..., relevanz_fuer_gap="Grundlegende Bewertung", ...) ]  # KONSERVE
```

Folgen, jeweils ein Verstoß gegen *„kein faktischer Output ohne Bezug"* / *„keine stillen
Defaults"*:

- `front_map.fehlende_faehigkeiten` und `front_map.grenzen` wurden **nie gelesen** → das
  Verb *beobachtet … die Roadmap-Gaps* war unwahr; die Gaps der Karte beeinflussten den
  Output nicht.
- Eine Karte ganz **ohne** Gaps lieferte trotzdem fabrizierte Items (kein ehrliches Leer).
- Die `relevanz_fuer_gap`-Strings (`"Energie-Dichte P1"`, `"Redundante Flugkontrolle P2"`)
  referenzierten Gaps, die in keiner echten Map vorkommen — reine Konserve.

## Was real gemacht wurde (Fix, nur `breakthrough_watch.py`)

Die Items werden jetzt **aus den realen offenen Gaps der Eingabe-Map abgeleitet**:

1. **`_open_gaps(front_map)`** sammelt deterministisch alle realen offenen Gaps:
   alle `fehlende_faehigkeiten` plus jeden `grenzen`-Schlüssel, dessen `Grenztyp` **nicht**
   `KNOWN_POSSIBLE` ist (bereits Machbares ist kein Watch-Ziel). Ordnungserhaltende
   Deduplizierung.
2. Pro offenem Gap: der kuratierte **Jetpack-Domänen-Katalog** (Energie/Control/Recovery,
   nur bei bemannter-Flug-Domäne aktiv) wird per Stichwort gegen den **echten Gap-Text**
   gematcht. Jedes emittierte `FrontierItem.relevanz_fuer_gap` ist exakt dieser reale
   Gap-String — nie eine Konserve.
3. Findet sich für einen Gap **kein** bekannter Durchbruch → ein ehrliches
   **Abstinenz-Watch-Item** (`typ="Watch"`), das den Gap benennt, statt einen Treffer zu
   erfinden (Kernprinzip 4: *„Ich weiß es nicht" ist gültig*).
4. Hat die Map **gar keinen** offenen Gap → **leerer, abstinenter** `FrontierUpdate`
   (`items == []`), nicht die alte Konserve.

Der reiche Jetpack-Katalog bleibt als regressions-geschützter Spezialfall erhalten, ist
aber jetzt **input-gebunden**: ein Katalog-Item erscheint nur, wenn die Map einen
passenden offenen Gap trägt. Nimmt man der Flug-Map den Energie-Gap, verschwindet das
Solid-State-Battery-Item (Test
`test_jetpack_catalog_item_disappears_when_its_gap_is_absent`). Determinismus, `run_id`-
Durchreichung, Typ-Hints, Docstrings und ein dokumentierter Fehlerzustand (`TypeError`
bei `front_map=None`, fail-loud) bleiben/sind gewahrt.

Abwärtskompatibilität: Die kuratierten Item-**Titel** (`Solid-State…`, `Dissimilar
Redundant FC…`, `Ballistic Parachute…`) sind unverändert, daher matcht der Downstream-
`boundary_reviser` weiterhin (seine Tests bleiben grün).

## Beleg, dass das Modul jetzt REAL ist

Neue Datei `tests/test_breakthrough_watch_characterization.py` treibt das echte
`watch_frontier` (nie gemockt):

- **Gap-Bindung (L1)** — jede `relevanz_fuer_gap` ist ein echter offener Gap der Map;
  die alten Konserven-Strings (`"Energie-Dichte P1"`, `"Solid-State"`) lecken **nicht** in
  eine fremde Map (Brücke/Turbine).
- **Input-Sensitivität (L2)** — verschiedene Gaps → verschiedene Updates; Katalog-Item
  verschwindet, wenn sein Gap fehlt (auch im Jetpack-Pfad → input-derived bewiesen).
- **Ehrliches Leer (L4)** — Map ohne offene Gaps → `items == []`, abstinente
  Zusammenfassung, `run_id` durchgereicht; `known_possible`-Grenzen zählen nicht als offen.
- **Regression (L3)** — die volle Jetpack-Map liefert weiterhin die drei kuratierten
  Durchbrüche, jeder an einen realen Gap gebunden.
- **Fail-loud** — `watch_frontier(None)` → `TypeError`.
- **Property-based (Hypothesis)** — über beliebige Gap-Listen ist jede `relevanz_fuer_gap`
  ein Eingabe-Gap und jeder Gap wird genau adressiert; leere Liste → leerer Update.

Alle 11 neuen Tests grün; `test_boundary_reviser` (2) und `test_breakthrough_bridge`
bleiben grün. Backlog-Bezug: härtet das in `GENESIS_PLATFORM_PLAN.md §3.3` genannte
Grenzverschiebungs-Modul `breakthrough_watch` gegen Facade-Output ab.

## 4 Linsen

- **L1 Wahrheit:** Output ist an reale Map-Gaps gebunden; keine fabrizierten Relevanzen.
- **L2 Drift:** geänderte Eingabe ändert den Output messbar (Item folgt dem Gap).
- **L3 Vollständigkeit/Naht:** Jetpack-Reichtum erhalten; Downstream-`boundary_reviser`
  durch stabile Titel ungebrochen; jeder offene Gap erhält genau eine Antwort.
- **L4 Realisierbarkeit/Abstention:** kein Gap → ehrlich leer; unbekannter Durchbruch →
  Watch-Item statt Erfindung; `None`-Eingabe → fail-loud.
