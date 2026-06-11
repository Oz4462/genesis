# γ-DEPTH — Spezifikation bis zum letzten Detail (sourced-or-gap)

> **Zweck:** Die γ-Bauanleitung von „strukturell vollständig" zu „real umsetzbar bis
> zum letzten Detail" führen — Beschaffung, Verbindungselemente, Kompatibilität,
> Elektronik, Montage, Ort. **Aufbau wie die Phasen-Dokumente.**
>
> **Die durchgängige Invariante (nicht verhandelbar):** Jedes faktische Detail —
> Bezugsquelle, Bestellnummer/Norm, Preis, Bauteil, Datenblatt-Spec — ist entweder
> ein **belegter VERIFIED-Claim (α)** oder eine **deklarierte/nachgerechnete Größe
> (γ)**. **Kein erfundener Shop, kein erfundener Preis, kein erfundenes Bauteil,
> kein erfundener Wert.** Im Zweifel: **ehrliche Lücke** statt Halluzination. Das
> ist exakt die α/β/γ-Garantie, auf Beschaffungs-/Domänen-Details angewandt.

## Das Architektur-Prinzip: sourced-or-gap

Jedes neue Detail ist eine von drei Sorten — und jede hat ihren bestehenden Wächter:

| Sorte | Beispiel | Wächter |
|---|---|---|
| **Faktischer Wert** (Preis, Maß, Spannung) | „4,50 € Stückpreis", „M4 = 4 mm", „5 V" | GROUNDED-Quantity: Wert **wörtlich** im VERIFIED-Claim (C-4) |
| **Faktischer Text** (Supplier, Bestellnummer, Bauteil-Name) | „McMaster 91290A115" | muss **wörtlich** in einem VERIFIED-Grounding-Claim stehen (String-Pendant zu C-4) |
| **Deklarierte Wahl** (Material, Verfahren, Spielmaß) | „PLA", „Durchgangsloch", „0,2 mm Spiel" | DECISION mit Begründung (C-7) |

Existiert für ein behauptetes Detail **kein** VERIFIED-Claim, wird es **nicht
behauptet** — es erscheint als explizite Lücke (`gaps`). Genau wie ein
unverankerter Approach (β) oder ein unbelegter Wert (γ) nie in den Output gelangt.

**Ehrliche Konsequenz des Offline-Modus (Owner-Vorgabe „keine Live-Runs"):** Reale
Beschaffungs-/Datenblatt-Claims entstehen erst durch Live-α-Recherche. Offline wird
der **Mechanismus** mit gescripteten Claims bewiesen (wie α/β/γ); ohne Claim
**abstrahiert** GENESIS ehrlich („Bezugsquelle/Preis offline nicht belegbar").

---

## Die sechs Tiefen-Module

### 1. Sourcing-BOM (Beschaffung) — **Keystone**
Pro BOM-Zeile (besonders Nicht-Druckteile: Schrauben, Muttern, Lager, Inserts):
Bezugsquelle + Bestellnummer/Norm + Richtpreis. **Modell:** `Sourcing(supplier,
part_number, price_quantity_id?, grounding≥1)` an `BomItem`. **GATE γ C-16:**
grounding VERIFIED+α-sound; supplier & part_number **wörtlich** in einem
Grounding-Claim; Preis als GROUNDED-Quantity (Wert wörtlich, C-4, Währung als
Einheit). Kein Grounding ⟹ Sourcing wird gedroppt, Lücke ausgewiesen.

### 2. Verbindungselemente & Passung ✅
Norm-Schraube (M-Größe, Länge, Kopf) → Lochgröße im Druckteil (Durchgang vs.
Gewinde vs. Heat-Set-Insert). **„Norm-Schraube → empfohlener Bohrdurchmesser" als
belegte Referenz-Claims** (z. B. ISO 273), nie hardcodiert. Loch-Quantity grounded
in diesem Claim — der Wert (4,5 mm) steht **wörtlich** im Claim (C-4). Fit über die
bestehenden Ausdrucks-Constraints (Loch ≥ Welle + Spiel, `test_fits.py`). Loch-Typ
(Durchgang/Gewinde/Insert) als DECISION. **Bewiesen:** `test_fasteners.py` —
Durchgangsloch, Gewinde-Kernloch (tap drill), Heat-Set-Insert-Bohrung, je grounded;
ein **erfundener** Bohrdurchmesser (nicht im Claim) → `VALUE_NOT_IN_GROUNDING`.
Kein neuer Mechanismus; Referenzdaten kommen aus Live-α-Recherche.

### 3. Komponenten-Kompatibilität ✅
„Was passt perfekt zusammen": Maße/Stecker/Spannung. Deterministisch wo möglich
(`eq`/`ge`-Constraints zwischen grounded Spec-Quantities: `shaft == bore`,
`v_device == v_supply`, `i_supply >= i_draw`); sonst belegte Empfehlung + ehrliche
Lücke. **Bewiesen:** `test_compatibility.py` — Wellen-Lager-Maß-Match,
Spannungs-Match, Strom-Headroom, je Mismatch gefangen (`CONSTRAINT_VIOLATION`);
keine undeklarierte Kompatibilität wird **erfunden** (`test_no_invented_compatibility`).
Nicht-numerische Kompatibilität (Steckertyp) bleibt eine belegte Aussage, kein
deterministischer Check — ehrlich über die Grenze.

### 4. Elektronik (eigene Domäne) ✅
Getrennte **Elektronik-BOM** via `BomItem.domain = ELECTRONIC` (Default
MECHANICAL); die CLI rendert „Bill of materials (mechanical)" und „(electronics)"
getrennt. Empfohlene Geräte (Controller, Sensoren, Netzteil, Verkabelung) mit
grounded Spec (Spannung V, Strom A, Leistung W, Widerstand Ω, Kapazität Ah) je aus
**Datenblatt-Claim** — dieselben Sourcing-/Grounding-Regeln wie Mechanik. **Neue
elektrische Einheiten** in `units.py`: V, ohm/Ω, Ah, Wh (+ Skalen: mAh→3,6,
Ah→3600). Spannungs-/Strom-Kompatibilität als Constraints (§3). **Bewiesen:**
`test_electronics.py` — Einheiten-Dimensionen/Skalen, grounded E-BOM-Zeile passt
das Gate, CLI-Split mechanical/electronics.

### 5. Montage-Detail & Ort ✅
`Step` um **`tool`** (Werkzeug) + **`torque_quantity_id`** (Quantity N·m,
grounded/decision) erweitert; Reihenfolge/Prüfpunkt bestehen schon. GATE γ löst
das Drehmoment auf (dangling). **`SiteRequirements`** auf `Specification.site`:
`available_space` (Tripel von quantity_ids L×W×H) — GATE δ prüft **deterministisch**,
dass jede Komponenten-Hüllbox in den verfügbaren Platz passt (achsenparallel, jede
Orientierung via sortierte Dimensionen; zu groß → `SITE_SPACE_EXCEEDED`).
`requirements`: Belüftung, indoor/outdoor, Stromanschluss, Sicherheitsabstände —
je `Decision` (claim-informed), nie erfundener Bedarf; GATE γ validiert sie (C-7).
**Bewiesen:** `test_assembly_site.py` (8) — Werkzeug/Drehmoment, Drehmoment-dangling,
Platz-passt, zu-groß-gefangen, Orientierung, Bedarfe validiert, Platz-dangling,
CLI-Render. **Ehrliche Grenze:** der Box-in-Box-Fit ist konservativ (keine
Diagonal-Rotation) — sagt nie fälschlich „passt".

### 6. Finaler End-to-End-Lauf (Capstone)
Eine echte Idee → vollständige Spezifikation mit **Mechanik + Elektronik +
Beschaffung + Montage + Ort**, durch **alle** Gates α/β/γ/δ. Scripted-world-
Akzeptanztest, der die durchgängige sourced-or-gap-Invariante end-to-end beweist;
CLI-Demo. Reale Daten folgen mit Live-α-Recherche.

---

## Reihenfolge & Status

1. **Sourcing-Keystone** (setzt das sourced-or-gap-Muster) — *in Arbeit*.
2. Fastener→Loch (belegte Referenz + Fit).
3. Komponenten-Kompatibilität (Constraints).
4. Elektronik-Domäne (E-BOM + elektrische Einheiten + Kompatibilität).
5. Montage-Detail + Ort (Step-Erweiterung + SiteRequirements).
6. End-to-End-Capstone (alle Gates).

Jedes Modul: gate-first, offline beweisbar, Drift- + Halluzinations-Audit je
Abschluss, kein Live-Run. Quellen für Referenzdaten (ISO 273 Bohrtabellen,
Datenblätter, Preise) werden bei Live-α-Recherche als Claims belegt — bis dahin
ehrliche Lücke.
