# Agent: `synthesizer` — der Strukturierer (Phase β)

> Bildet aus den **verifizierten** Claims distinkte Lösungsansätze. Erzeugt
> **keine Fakten**. Seine einzige Tugend ist Struktur ohne Erfindung — dieselbe
> Rolle wie `conductor`, nur für den Lösungsraum.

## Verantwortung (eine Sache)
VERIFIED-Claims (mit confidence ≥ τ) zu benannten `Approach`-Objekten clustern: je
Ansatz die **Grounding-Claims** (belegen, dass der Ansatz existiert / für dieses
Problem genutzt wird) und die **Trade-off-Claims** (Eigenschaften, Vor-/Nachteile).
Referenziert ausschließlich `claim_id`s — behauptet selbst nichts.

## Was `synthesizer` NICHT tut
- Keine Fakten/Claims erzeugen; keine neuen Quellen.
- Keinen Ansatz erfinden: ein Ansatz ohne ≥1 **VERIFIED**-Grounding wird verworfen.
- Keine erfundenen `claim_id`s übernehmen: vom LLM genannte IDs, die nicht in der
  VERIFIED-Menge stehen, werden im **Code** fallengelassen — der Halluzinations-Guard
  ist Code, kein Vertrauen (wie `scholar`s Verbatim-Zitat-Check).

## Input / Output
- **Input:** `RunState` mit `claims` (nach `skeptic`; Status gesetzt).
- **Output:** `RunState` mit `approaches` — bei jedem Lauf **neu gebaut** (idempotent
  über die Refine-Runden des `conductor`).

## Tools
- Ein `LLMClient` (Pflicht), nur zum **Clustern/Benennen** — ein Urteil, kein Fakt,
  exakt wie `scout`s Query-Formulierung. Labels sind keine Fakten. Generator-Familie:
  Strukturieren ist keine Verifikation; die zugrunde liegenden Claims wurden bereits
  cross-model vom `skeptic` verifiziert, also bleibt die Cross-Model-Garantie erhalten.

## Fehler-/Degradationsverhalten
- Keine VERIFIED-Claims → kein Ansatz (Abstention), geloggt.
- Unparsebare LLM-Ausgabe → Abstention (keine Ansätze), geloggt — nie erfinden.
- Ansatz ohne überlebende VERIFIED-Verankerung → verworfen, geloggt.

## Garantie gegenüber GATE β
Weil jeder emittierte Ansatz nur in VERIFIED-Claims (≥ τ) verankert ist und nur
existierende VERIFIED-`claim_id`s als Trade-offs trägt, **besteht der erzeugte
`SolutionReport` GATE β per Konstruktion** — wie der `conductor` GATE α per
Konstruktion besteht. Das Gate bleibt der unabhängige Backstop.

## Tests (Pflicht)
- Mehrere VERIFIED-Claims → ≥2 verankerte Ansätze; jedes Grounding ⊆ VERIFIED.
- LLM nennt erfundene `claim_id` → fallengelassen; Ansatz ohne Grounding → kein Ansatz.
- LLM unparsebar → Abstention.
- UNSUPPORTED/under-confidence-Claim wird nie als Grounding aufgenommen.
