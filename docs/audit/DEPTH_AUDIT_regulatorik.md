# Depth-Audit: `src/gen/pipelines/regulatorik.py` (T03)

**Verdikt vor Fix: FACADE.** **Verdikt nach Fix: REAL (generischer Pfad input-getrieben).**

## Befund (Facade-Smell)

`map_to_regulatorik_spec(concept, ingenieur)` hatte zwei Pfade:

- **Jetpack-Branch** (`'jetpack' in idea or 'flug' in idea`): reichhaltig, handkuratiert,
  EASA + ISO 12100, konkrete high-Risiken (Tether, Battery) mit massnahmen + human freigabe.
  → REAL für genau diesen Kanon-String.
- **Generischer `else`-Branch**: gab **fixe** Werte zurück
  (`Norm("Basic machinery safety (ISO 12100)", ...), Risiko("Generic failure", ...),`
  feste Warnung, feste Freigabe/Haftung/Summary), die **weder `concept` noch `ingenieur` lasen**.
  Die einzige input-abhängige Stelle war ein abgeschnittenes `source_idea[:40]` in der
  Zusammenfassung — kosmetisch. Zwei beliebige Nicht-Jetpack-Inputs produzierten
  **identische Normen + Risiken**. Zudem wurde ISO 12100 blind behauptet, ohne Signal.
  → Verstoß gegen „keine stillen Defaults bei faktischen Dingen" und L1/L2.

## Fix (input-getrieben + ehrliche Lücke)

- Guard am Beginn des generischen Pfads:
  - leere/blank `source_idea` → `ValueError`
  - kein actionable Signal (`failure_modes == [] and lastfaelle == [] and main_assemblies == []`)
    → `ValueError` statt fabriziertem Stub.
- **Normen**: immer explizite Gap-Norm `"keine spezifische Norm ableitbar"` mit Begründung
  aus dem Input-Konzept; niemals blind ISO 12100 im Generic-Pfad.
- **Risiken**:
  - je `FailureMode` → Risiko mit `fm.name`, `fm.beschreibung`, `fm.detection` als `massnahme`,
    `freigabe = "Human sign-off required (derived...)"`, quelle aus fm.
  - je `LoadCase` → Risiko mit Name/Last-Beschreibung + `kraft_oder_moment` in massnahme.
- **Warnhinweise + Summary**: spiegeln `source_idea` + jede `AssemblyConcept` (name, purpose, interfaces).
- **Freigabe/Haftung**: erwähnen die abgeleitete Anzahl von Risiken/Lasten.
- Jetpack-Branch **verbatim erhalten** (protected regression).
- Alle Ableitungen sind deterministisch und nur aus den übergebenen Feldern.

## Welche Inputs werden jetzt genuin konsumiert?

| Output-Feld          | abgeleitet aus |
|----------------------|---------------------------------------------------------------|
| `normen`             | Gap immer; spezifische Norm nur bei Signal (hier nie im Generic) |
| `risiken` (FM)       | `ingenieur.failure_modes[*].{name, beschreibung, aus_baugruppe, detection, quelle}` |
| `risiken` (LC)       | `ingenieur.lastfaelle[*].{name, beschreibung, kraft_oder_moment, quelle}` |
| `warnhinweise`       | `concept.source_idea`, `concept.main_assemblies[*].{name, purpose, interfaces}` |
| `zusammenfassung`    | `#failure_modes`, `#lastfaelle`, `#main_assemblies`, `source_idea` |
| `freigabe_prozess`   | `len(risiken)` (aus Inputs) |
| `haftungsgrenzen`    | Erwähnt deklarierte Lastfälle + Failure-Mitigationen |

## Test-Beleg (`tests/test_regulatorik_characterization.py`)

- **Facade-Killer**: zwei distinkte Nicht-Jetpack-Inputs → distinkte `risiken`-Namen + Warnungen/Summary;
  Failure-Namen (`"Motor blockiert"`) und Load-Namen tauchen nur im korrekten Spec auf.
- **Detection-Fluss**: `FailureMode.detection` → `Risiko.massnahme` (1:1).
- **Lastfall-Ableitung**: `LoadCase` produziert eigenes Risiko mit `kraft_oder_moment`.
- **Assembly-Reflexion**: Assembly-Namen erscheinen in warnhinweise + summary.
- **Norm-Honesty**: Generic → `"keine spezifische Norm ableitbar"` (kein ISO 12100).
- **Negativtest (ValueError)**: blank source_idea → ValueError; zero-signal (keine fms/lcs/assemblies) → ValueError.
- **Only-Lastfaelle**: auch ohne fms werden Risiken aus lastfaelle abgeleitet.
- **Protected Regression**: Jetpack-Branch unverändert (2 Normen, spezifische high-Risiken, "pilot" Freigabe etc.).
- **Property-based (Hypothesis)**: für beliebige (jetpack/flug-freie) Mengen von Assemblies + FMs + LCs
  gilt: Gap-Norm immer, kein ISO, `#risiken >= #fms + #lcs`, und jeder Input-Name taucht in Risiken auf;
  Summary enthält Zählwerte.
- **Real-Mapper-Regression**: `map_to_system_concept` + `map_to_ingenieur_spec` (non-jetpack) + regulatorik
  liefert Gap-Norm + abgeleitete Risiken (aus dem generischen lastfaelle).

## 4 Linsen

- **L1 Wahrheit**: keine erfundenen Normen/Risiken mehr; alles entweder aus Failure-Mode/Lastfall/Assembly
  abgeleitet oder als `"keine spezifische Norm ableitbar"` deklariert. Keine stillen Defaults.
- **L2 Drift**: Headline („aus prior Output abgeleitet") deckt sich jetzt mit dem Code für *alle*
  Inputs, nicht nur den Jetpack-Kanon. Kein blindes ISO mehr.
- **L3 Vollständigkeit/Naht**: Naht zu Architekt (source_idea + assemblies) + Ingenieur (fms + lastfaelle)
  + Regulatorik-Output für Realisierungspaket/Integrator bleibt; Jetpack-Demo unangetastet (L3 seam protected).
  Die 5 Fach-Pipelines (fertigungs/physiker/regulatorik/software/techniker) folgen demselben Muster.
- **L4 Realisierbarkeit/Edge**: leerer/kein-Signal-Input → ehrlicher ValueError (fail-loud) statt
  geratener Sicherheit; nur-Lastfaelle und nur-Failure-Modes Kanten getestet; property tests decken
  große Eingabemengen ab; bestehende legacy Tests (jetpack + generic) bleiben grün.

## Backlog-Bezug

`GENESIS_PLATFORM_PLAN.md §4` (Sicherheits- und Regulatorik-Pipeline) + §4.2 (Ingenieur → Failure-Modes/Lastfälle)
+ die 2026-06-23 Entscheidungen (Fach-Pipelines generischer Pfad input-getrieben, neue Charakterisierungstests,
  4-Linsen + DEPTH_AUDIT pro Modul, keine stillen Defaults, Jetpack protected).

Offen bleibt (ehrliche Lücke):
- echte Normen-Auswahl aus Wissensbasis (CODATA/DLMF + spezifische EN/ISO/ICAO-Connector) — erst
  wenn Elektriker/Physiker/Software detailliertere Signale (z.B. Spannungsklassen, Software-SIL)
  liefern.
- Domänen-spezifische Risiko-Matrizen (z.B. LiDAR-Safety, Hydraulik) — brauchen weitere prior-Steine.

Alle Änderungen beschränkt auf die erlaubten Dateien; keine Mutation von Dataclass-Signaturen.
