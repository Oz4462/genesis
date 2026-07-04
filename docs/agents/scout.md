# Agent: `scout` — die Breite

> Findet *Kandidaten-Quellen* zu jeder Teilfrage. Erzeugt **keine Fakten**.
> Seine einzige Tugend ist Reichweite ohne Erfindung.

## Verantwortung (eine Sache)
Zu jeder Teilfrage breit Quellen finden (Web, akademisch) und als
`SourceCandidate` zurückgeben — URL/ID + kurze Relevanznotiz. Nicht lesen, nicht
extrahieren, nicht bewerten.

## Was `scout` NICHT tut
- Keine Fakten/Claims erzeugen.
- Keine Quelle erfinden: zurückgegeben wird nur, was ein Backend wirklich lieferte.
- Kandidaten NICHT als „abgerufen" markieren (`fetched_ok=False`) — das Abrufen
  ist `scholar`s Aufgabe.

## Input / Output
- **Input:** `RunState` mit `sub_questions` (Fallback: die Originalfrage).
- **Output:** `RunState` mit ergänzten, deduplizierten `candidates`.

## Tools
- `SearchBackend`s (z. B. `semantic_scholar`, `web`). Optional ein `LLMClient`
  nur zur **Query-Formulierung** (Queries sind keine Fakten).

## Fehler-/Degradationsverhalten
- Fällt ein Backend aus (`SearchBackendError`), wird das in `state.log` notiert
  und mit den übrigen Backends weitergemacht — sichtbar degradieren, nicht still
  scheitern, nicht erfinden.
- Kann die LLM keine Queries liefern (LLM-/Parse-Fehler oder Nicht-Array-Antwort),
  wird der Teilfragetext selbst als Query benutzt — und die Degradation in
  `state.log` notiert (D11: best-effort, aber nie still; sonst ist ein
  breiten-armer Lauf im Nachhinein nicht reproduzierbar/diagnostizierbar).

## Tests (Pflicht)
- Kandidaten aus mehreren Backends werden gesammelt und dedupliziert.
- Backend-Ausfall → geloggt, Lauf bricht nicht ab, übrige Kandidaten da.
- Ohne LLM wird der Teilfragetext als Query genutzt.
