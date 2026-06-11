# Agent: `architect` (Phase γ)

## Verantwortung
Strukturiert die Idee + den verankerten `Approach` + die VERIFIED-Claims des Laufs
zu einer vollständigen `Specification`: Größen (`Quantity`) mit deklarierter
Herkunft, Komponenten mit parametrischer CSG-Geometrie, Stückliste, Schritte mit
Prüfkriterium, numerische Constraints, Entscheidungsblatt. **Erzeugt keine Fakten**
— exakt dieselbe Disziplin wie `conductor` (Report) und `synthesizer` (Approaches).

## Grenzen (nicht verhandelbar)
- **Wertzwang:** Eine GROUNDED-Quantity wird nur übernommen, wenn jede grounding-
  claim_id im VERIFIED-Set liegt UND der Wert wörtlich (numerisch, digit-boundary-
  geprüft) im Text eines Grounding-Claims steht. Sonst: Drop + Log.
- **Rechenzwang:** Für DERIVED-Quantities liefert das LLM nur `formula` + `inputs`.
  Der Wert wird hier von Code berechnet (`verification/derivation.py`,
  topologisch). Ein vom LLM „vorgerechneter" Wert wird ignoriert und überschrieben.
- **Entscheidungszwang:** DECISION-Quantities/`Decision`s ohne Begründung sind
  versteckte Entscheidungen → Drop + Log.
- **Keine Teil-Spezifikation:** Der zusammengebaute Kandidat wird gegen
  `gate_gamma` selbst-geprüft (dieselbe reine Funktion, die der `conductor`
  nutzt). Scheitert der Self-Check (dangling Referenz, unvollständiger Schritt,
  unbaubare Reihenfolge, kaputte Geometrie, verletzte Constraint, fehlender
  Anker), wird **nichts** behauptet: leere Spezifikation + benannte Lücke.
- **Kein Anker, keine Spezifikation:** Ohne verankerten Approach (β-Kette)
  abstainiert der Agent ehrlich.

## I/O
- **Input:** `RunState` (`claims`, `approaches`, `question`).
- **Output:** schreibt ausschließlich `state.specification` (Agent-Ownership);
  idempotent über Refine-Runden (baut jedes Mal neu auf).

## Tools
Keine externen Tools. Ein `LLMClient` (Generator-Familie) für den Struktur-
Vorschlag; Safe-Evaluator für Arithmetik; `gate_gamma` für den Self-Check.

## Cross-Model
Die faktische Substanz (Claims) ist bereits cross-model durch den `skeptic`
verifiziert. Der `architect` verifiziert nicht selbst — er strukturiert
Verifiziertes (Urteils-, keine Faktenleistung; wie `synthesizer`).

## Fehlerzustände
- `LLMOutputError` (unparsebare Antwort) → Abstention mit Lücke, kein Crash.
- Strukturfehler im Vorschlag → Self-Check-Fail → Abstention mit Details im Log
  und in `gaps`.
- Konstruktor-Guards (`UngroundedValueError`, `InvalidDerivationError`,
  `UndeclaredDecisionError`) → betroffenes Element wird gedroppt und geloggt;
  niemals still übernommen.

## Tests
`tests/test_architect.py` (positiv + negativ: erfundener Wert wird gedroppt,
LLM-Arithmetik wird ignoriert/überschrieben, kein Anker → Abstention,
strukturdefekter Vorschlag → Abstention statt Teil-Spec) sowie
`tests/test_phase_gamma_acceptance.py` (Klassen A–D end-to-end).
