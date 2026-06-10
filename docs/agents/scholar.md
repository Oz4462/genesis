# Agent: `scholar` — die Tiefe

> Liest abgerufene Quellen und extrahiert **atomare, einzeln prüfbare** Fakten —
> jeden mit Quelle und wörtlichem Stützzitat. Erfindet nichts.

## Verantwortung (eine Sache)
Aus dem **tatsächlich abgerufenen** Text einer Kandidatenquelle Claims
extrahieren, die die Frage beantworten. Jeder Claim trägt: Quelle, kurzes
wörtliches Zitat, Status `UNVERIFIED`.

## Was `scholar` NICHT tut
- Kein „Allgemeinwissen", keine Interpolation: sagt die Quelle es nicht, gibt es
  keinen Claim.
- Keine Claims aus nicht-abgerufenen Quellen (fehlgeschlagener Fetch → kein Claim).
- Keine Verifikation (das ist `skeptic`).

## Code-Garantie gegen Halluzination (der Kern)
Für jeden vom LLM vorgeschlagenen Claim wird geprüft, ob sein Zitat **wörtlich
in der abgerufenen Quelle vorkommt** (whitespace-normalisiert). Findet sich das
Zitat nicht, ist es eine Erfindung des Modells → der Claim wird **verworfen** und
geloggt. Diese Prüfung ist Code, nicht Vertrauen.

## Input / Output
- **Input:** `RunState` mit `candidates`.
- **Output:** `RunState` mit neuen `claims` (Status `UNVERIFIED`), zusätzlich im
  Ledger persistiert (Quellenzwang dort erneut erzwungen).

## Tools
- `WebFetchTool` (Quelle vollständig laden; Fehlschlag → kein Claim).
- `LLMClient` (Extraktion; Modell-ID wird als `model` am Claim vermerkt → A6).

## Determinismus
Claim-IDs sind deterministisch aus `(run_id, Quelle, Claim-Text)` abgeleitet →
gleicher Lauf erzeugt gleiche IDs (A5). Bereits vorhandene IDs werden übersprungen.

## Fehlerverhalten
- Fetch-Fehler → Claim entfällt, Log-Eintrag.
- Unparsebare LLM-Ausgabe (`LLMOutputError`) → diese Quelle übersprungen, Log,
  kein Abbruch, keine erfundenen Claims.

## Tests (Pflicht)
- Gültige Extraktion mit echtem Zitat → Claim mit Quelle, Status UNVERIFIED.
- Zitat NICHT im Quelltext → Claim verworfen (Halluzinations-Guard).
- Fetch-Fehler → kein Claim.
- Unparsebare LLM-Ausgabe → kein Claim, kein Crash.
- Claim ohne Quelle ist strukturell unmöglich (Konstruktor/ Ledger).
