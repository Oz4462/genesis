# Agent: `conductor` — der Orchestrator

> Steuert den Lauf und stellt den Endbericht zusammen. Erzeugt **selbst keine
> Fakten** — jede faktische Aussage stammt aus einem Ledger-Claim.

## Verantwortung (eine Sache)
Frage → (optional) Teilfragen → `scout` → `scholar` → `skeptic` → Bericht;
Gate auslösen; bei Nichtbestehen begrenzt nachrecherchieren oder als Lücke
ausweisen.

## Was `conductor` NICHT tut
- Keine eigenen Fakten. Der Bericht wird ausschließlich aus Ledger-Claims gebaut.
- Behauptet **nur** Claims mit Status `VERIFIED` und `confidence ≥ τ`.
- `REFUTED`/`UNSUPPORTED`/zu unsichere `VERIFIED` erscheinen nie als Tatsache —
  sie werden als **Lücken** ausgewiesen.

## Konstruktionsgarantie
`_assemble` ist konservativ: nur belegte, ausreichend sichere Claims werden
behauptet (jeder Satz → `claim_id` in `statement_to_claim`); alles andere geht in
`gaps`. Dadurch besteht der Bericht GATE α per Konstruktion — der Refine-Loop ist
die Absicherung, nicht der Normalfall.

## Input / Output
- **Input:** `RunState` mit `Question`.
- **Output:** `RunState` mit `sub_questions`, `claims` (über die Subagenten) und
  `report` (nur aus Ledger-Claims).

## Refine-Loop
Bis `max_refine_rounds`: recherchieren → zusammenstellen → Gate prüfen. Besteht
das Gate, Stopp. Sonst nächste Runde; nach Limit verbleibende Punkte als Lücken.

## Tests (Pflicht)
- VERIFIED-Claim erscheint im Bericht, Gate besteht.
- UNSUPPORTED/REFUTED erscheinen NICHT als Tatsache, sondern als Lücke; Gate besteht.
- Jeder Bericht-Satz mappt auf einen existierenden Ledger-Claim (keine erfundenen).
