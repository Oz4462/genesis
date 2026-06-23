# Depth-Audit: `discovery/universe_bridge.py`

**Datum:** 2026-06-23
**Auditor:** T05 (claude builder)
**Verdikt:** **REAL** — keine Quelländerung nötig.

## Headline-Claim
Die Universe-Simulator-Bridge SIMULIERT ein System mit dem In-Process-Referenz-Backend
und bringt das Ergebnis **zurück durch die Gates**: die simulierten Daten laufen durch
`discover_new_formulas`, und nur ein gate-bestätigtes Gesetz wird gemeldet. Der Output des
Simulators wird nie vertraut — er wird gegated wie reale Messdaten.

## Befund
Der Claim hält. `bridge_discover` ruft `backend.run(spec)` auf, das ein echtes
`DiscoveryProblem` aus deterministischer numpy-Physik baut, und reicht dieses an
`discover_new_formulas` weiter. Das gemeldete `discovered_law`/`verdict` kommt
ausschließlich aus `discovery.validated[0]` bzw. den Records — also aus dem Gate, nicht
aus dem Backend. Es gibt keinen Pfad, der die Backend-Ausgabe ungegatet als Gesetz ausgibt.

Belege (alle in `tests/test_universe_bridge_characterization.py`, 9 Tests grün):

- **two_body_orbit → Kepler.** `T ∝ a^(3/2)·mu^(-1/2)`, `verdict == "bestaetigt"`,
  `validated[]` befüllt, Exponent `a == 1.5`, `mu == -0.5`, Koeffizient `== 2π` aus den
  Daten gefittet. Beweist: simulierte Daten passieren Dimensions-, Recompute- und Fit-Gate.
- **harmonic_oscillator.** Exponent `m == +0.5`, `k == -0.5` korrekt zurückgewonnen.
- **Input wird wirklich konsumiert (kein Canned-Wert).**
  - Das simulierte Observable ist exakt die geschlossene Form (gegen unabhängig gerechnetes
    `2π·a^1.5·mu^-0.5` gepinnt); ein anderer Sweep liefert ein anderes Array.
  - Ein größeres `mu` skaliert jede Periode exakt mit `sqrt(mu_lo/mu_hi)` → `params` treibt
    die Simulation. (Hinweis: Exponenten/Koeffizient sind bei einem exakten Potenzgesetz
    *Invarianten* — das ist Korrektheit, nicht Facade; die Eingabe-Konsumtion wird daher am
    simulierten Datenarray und an unterschiedlichen Systemen nachgewiesen.)
  - Orbit vs. Oszillator liefern unterschiedliche Exponenten-Signaturen.
- **Negativtest.** Ein unbekanntes System (`warp_drive`) wirft `ValueError`
  ("cannot simulate") — kein fabriziertes Gesetz (keine stillen Defaults).
- **`should_offload`-Grenze.** `len ≤ max → False`, `len > max → True`, auch am
  dokumentierten Default-Cap `DEFAULT_MAX_LOCAL_POINTS`.
- **Property-Test (Hypothesis).** Über zufällige Sweep-Bereiche und `mu` bleibt der
  `a`-Exponent invariant bei exakt 3/2 und der Verdikt `bestaetigt` — die Exponenten kommen
  aus der Dimensionsanalyse, nicht aus Rausch-Fitting.

## 4 Linsen
- **L1 Wahrheits-Linse:** Kein faktischer Output ohne Gate. `discovered_law` ist immer der
  `expression`-String eines durch `discover_new_formulas` validierten Kandidaten; das Backend
  liefert nur Daten, nie ein Verdikt. ✔
- **L2 Drift-Linse:** Docstring (Zeilen 1–19, 134–143) verspricht exakt das implementierte
  Verhalten (SIMULATE → DISCOVER → GATE, Backend ungetrustet). Kein Drift gefunden;
  Docstring unverändert korrekt. ✔
- **L3 Vollständigkeits-/Naht-Linse:** Naht Backend↔Engine ist sauber — `run` baut ein
  vollständiges `DiscoveryProblem` (target/inputs/constants/run_id), `bridge_discover`
  konsumiert ausschließlich dessen Gate-Resultat. Der `SimulatorBackend`-Protocol-Seam ist
  deklariert; ein externes HPC-Backend ist Drop-in, keine versteckte Pflicht. Grenze
  ehrlich: nur Potenzgesetz-Systeme im Referenz-Backend (`_SYSTEMS`). ✔
- **L4 Realisierbarkeits-Linse:** Offline, deterministisch, numpy-only — läuft ohne externe
  Infrastruktur; getestet ohne Netzwerk/Subprozess. ✔

## Abgleich GENESIS_PLATFORM_PLAN
Erfüllt den „Universe Explorer"-Backlog-Punkt (SIMULATE→DISCOVER→VERIFY-Schleife): die
Bridge schließt die Schleife ehrlich, indem simulierte Welten durch denselben Gate-Pfad wie
reale Daten laufen. Keine offene Lücke für dieses Modul; die generelle Engine-Grenze
(nur Potenz-/Π-Gruppen, keine transzendenten Kopplungen) ist in `engine.py` dokumentiert
und nicht Sache dieses Moduls.

## Quelländerungen
Keine. Das Modul war bereits korrekt; nur ein neuer Charakterisierungstest wurde hinzugefügt.
