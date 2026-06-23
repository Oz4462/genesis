# Depth-Audit: `src/gen/pipelines/designer.py` (T05)

**Verdikt vor Fix: PARTIAL-FACADE.** **Verdikt nach Fix: REAL (generischer Pfad input-getrieben).**

## Befund (Facade-Smell)

`map_to_designer_spec(concept, ingenieur)` hatte zwei Pfade:

- **Jetpack-Branch** (`'jetpack' in idea or 'flug' in idea`): reichhaltig, handkuratiert,
  echte Ergonomie/Form/Bedien-Inhalte. → REAL für genau diesen Kanon-String.
- **Generischer `else`-Branch**: gab **fixe** Listen zurück
  (`ErgonomieAnforderung("Basic Fit", …)`, `FormEntscheidung("Einfache Form", …)`,
  `BedienSzenario("Basic Use", …)`), die **weder `concept` noch `ingenieur` lasen**.
  Die einzige input-abhängige Stelle war ein abgeschnittenes `source_idea[:40]` in der
  Zusammenfassung — kosmetisch. Damit erzeugten **zwei beliebige verschiedene
  Nicht-Jetpack-Inputs identische `bedien_szenarien`/`form`/`ergo`**. Die Headline
  „leitet aus dem realen Output des prior Moduls ab" galt nur für den Jetpack-String.
  → Verstoß gegen „keine stillen Defaults bei faktischen Dingen".

## Fix (input-getrieben + ehrliche Lücke)

Neue Hilfsfunktion `_generic_designer_spec(concept, ingenieur)` leitet jetzt aus den
**tatsächlichen** prior-Stein-Feldern ab:

- **Bedien-Szenarien** (Kern-Naht zu Safety/Regulatorik): **ein Szenario je
  `ingenieur.failure_modes`** (Fehlerfall, mit dessen realer `detection` als Massnahme)
  **+ ein Szenario je `concept.main_assemblies`** (Normalbedienung). Konkrete
  Missbrauchs-Analyse bleibt explizit als `Lücke` markiert (kommt aus Elektriker/Safety).
- **Ergonomie** je Baugruppe (Zweck + Schnittstellen zitiert); Anthropometrie bleibt `Lücke`.
- **Form** je Baugruppe (Form folgt Funktion); Ästhetik-Feinheiten bleiben offen.
- **Fehlerfall — beide leer** (`main_assemblies == [] and failure_modes == []`):
  explizite **Abstention**. Alle drei Listen tragen `Lücke`-Marker statt fabrizierter
  Sicherheit. Kein `ValueError`, weil ein leerer prior-Stein ein gültiger
  „ich-weiß-es-noch-nicht"-Zustand ist (Kernprinzip 4), der ehrlich markiert wird.

Der **Jetpack-Branch ist verbatim erhalten** (protected regression).

## Welche Inputs werden jetzt genuin konsumiert?

| Output-Feld | abgeleitet aus |
|---|---|
| `bedien_szenarien` (Fehlerfälle) | `ingenieur.failure_modes[*].{name,beschreibung,aus_baugruppe,detection,quelle}` |
| `bedien_szenarien` (Bedienung) | `concept.main_assemblies[*].{name,purpose,quelle}` |
| `ergonomie_anforderungen` | `concept.main_assemblies[*].{name,purpose,interfaces,quelle}` |
| `form_entscheidungen` | `concept.main_assemblies[*].{name,purpose,interfaces,quelle}` |
| `zusammenfassung` | `len(main_assemblies)`, `len(failure_modes)` |

## Test-Beleg (`tests/test_designer_characterization.py`)

- **Facade-Killer**: zwei distinkte Nicht-Jetpack-Inputs → distinkte `bedien_szenarien`;
  Input-Namen (`"Motor blockiert"`/`"Akku überhitzt"`) tauchen nur im jeweils richtigen
  Spec auf (keine Kreuz-Kontamination durch geteilten Stub).
- **Detection-Fluss**: `FailureMode.detection` → `BedienSzenario.massnahme` (1:1).
- **Zähl-Invariante**: `#bedien == #failure_modes + #assemblies`.
- **Negativtest (Abstention)**: beide leer → nur `Lücke`-markierte Einträge.
- **Nur-Baugruppen / nur-Failure-Modes** Pfade.
- **Protected Regression**: Jetpack-Branch unverändert (2 Ergo / 2 Form / 3 Bedien,
  inkl. „Missbrauch").
- **Property-based (Hypothesis)**: für beliebige (jetpack/flug-freie) Mengen von
  Baugruppen + Failure-Modes gilt die Zähl-Invariante und jeder Input-Name erscheint
  in genau einem Szenario (kein stilles Verschlucken, keine Fabrikation).

## 4 Linsen

- **L1 Wahrheit**: keine erfundenen Bedien-/Ergonomie-Fakten mehr; alles entweder aus
  Input abgeleitet oder als `Lücke` deklariert.
- **L2 Drift**: Headline („aus prior Output abgeleitet") deckt sich jetzt mit dem Code
  für *alle* Inputs, nicht nur den Jetpack-Kanon.
- **L3 Vollständigkeit/Naht**: Naht zu Safety/Regulatorik (Bedien/Missbrauch) und
  CAD/Elektriker bleibt; Jetpack-Demo unangetastet.
- **L4 Realisierbarkeit/Edge**: leerer Input → ehrliche Abstention statt Crash oder
  geratener Sicherheit; nur-Failure-Modes- und nur-Baugruppen-Kanten getestet.

## Backlog-Bezug

`GENESIS_PLATFORM_PLAN.md §4.6` (Designer-Pipeline). Offen bleibt (ehrlich als `Lücke`):
echte Anthropometrie-/Perzentil-Daten und detaillierte Missbrauchs-Szenarien — diese
müssen aus Architekt-Nutzerdaten bzw. Elektriker/Safety-Steinen nachgeliefert werden.
