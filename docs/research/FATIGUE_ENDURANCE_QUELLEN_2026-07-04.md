# Quellen-Notiz: Dauerfestigkeits-Basis gedruckter CF-Polymere (TP2-Follow-up)

> **Zweck:** Die TP2-DECISION `q_endurance_basis = 0.30·UTS` („additiv gefertigte Polymere,
> Schichthaftung; konservativer als Metall-üblich 0.4–0.5") wartet laut Spec auf ein Datenblatt.
> Diese Notiz sammelt reale Quellen als Entscheidungsgrundlage. **Sie hebt die Provenienz NICHT
> selbst auf GROUNDED** — Anwendbarkeits-Urteil (Kurz- vs. Endlosfaser, Orientierung, R-Verhältnis)
> ist Council-/Owner-Sache. Recherche: 2026-07-04, Web-Suche, Claude.

## Gefundene Anker

1. **Endlosfaser-CFK-Zugbänder (3D-gedruckt):** Dauerfestigkeit ≈ 500 MPa bei R=0.1/10 Hz
   ≈ **38 % der UTS**; konventionell gefertigte IMS60-Bänder ≈ 46 % UTS.
   → [Investigations on the Fatigue Behaviour of 3D-Printed Continuous Carbon Fibre-Reinforced
   Polymer Tension Straps (PMC9611383)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9611383/)
2. **FDM-PA-CF unidirektional:** UTS bis 719±46 MPa; Ermüdung bei 80 % UTS >1 Mio. Zyklen
   ohne Versagen, bei 90 % UTS Versagen nach 50k — (Endlosfaser-Regime, NICHT Kurzfaser).
   → [Static and Fatigue Properties of 3D Printed Continuous Carbon Fiber Nylon
   Composites (academia.edu)](https://www.academia.edu/162467827/Static_and_Fatigue_Properties_of_3D_Printed_Continuous_Carbon_Fiber_Nylon_Composites)
3. **Kanonisches Review (FDM-Polymere/Komposite):** breite Streuung der Ermüdungsdaten,
   starke Orientierungs-/Raster-Abhängigkeit — KEIN einheitlicher Endurance-Faktor für
   Kurzfaser-FDM ableitbar.
   → [Fatigue behaviour of FDM-3D printed polymers, polymeric composites and architected
   cellular materials (ScienceDirect S0142112320305399)](https://www.sciencedirect.com/science/article/pii/S0142112320305399)
4. Ergänzend: [Review Additive Manufacturing of Continuous Fiber-Reinforced Polymer
   Composites (PMC11207325)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11207325/) ·
   [Optimization of fatigue limit in AM fiber reinforced polymer composites (Springer
   2025)](https://link.springer.com/article/10.1007/s40964-025-00961-5) ·
   [Stratasys FDM Nylon 12CF Datenblatt](https://www.stratasys.com/en/materials/materials-catalog/fdm-materials/nylon-12cf/)

## Ehrliche Einordnung (Empfehlungs-Entwurf, nicht ratifiziert)

- Die 38–46 %-Anker gelten für **Endlosfaser**-Drucke; die Humanoid-Teile sind
  **Kurzfaser**-CF-Nylon — dafür zeigt das Review (#3) breite Streuung ohne belastbaren
  Einzelwert. Die TP2-DECISION **0.30·UTS bleibt damit als konservative Untergrenze
  verteidigbar**; eine Hebung auf GROUNDED bräuchte entweder das Stratasys-12CF-Ermüdungsblatt
  (falls es Wöhler-Daten enthält — prüfen) oder eigene Probestab-Messung (δ⁺-Pfad).
- Konsequenz für die dünne Kerb-Marge 1.04 (printed): mit 0.38·UTS statt 0.30 stiege sie
  auf ≈1.3 — **erst nach Council-Ratifikation** und nur, falls Endlosfaser-Übertragbarkeit
  begründet wird (derzeit nicht gegeben).

*Sources: siehe verlinkte Titel oben (PMC 9611383, academia.edu 162467827, ScienceDirect
S0142112320305399, PMC 11207325, Springer s40964-025-00961-5, stratasys.com).*
