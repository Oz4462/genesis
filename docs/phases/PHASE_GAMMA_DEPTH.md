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

### 2. Verbindungselemente & Passung
Norm-Schraube (M-Größe, Länge, Kopf) → Lochgröße im Druckteil (Durchgang vs.
Gewinde vs. Heat-Set-Insert). **„Norm-Schraube → empfohlener Bohrdurchmesser" als
belegte Referenz-Claims** (z. B. ISO 273), nie hardcodiert. Loch-Quantity grounded
in diesem Claim; Fit über die bestehenden Ausdrucks-Constraints (Loch ≥ Welle +
Spiel, `test_fits.py`). Loch-Typ (Durchgang/Gewinde/Insert) als DECISION.

### 3. Komponenten-Kompatibilität
„Was passt perfekt zusammen": Maße/Stecker/Spannung. Deterministisch wo möglich
(Constraints zwischen grounded Spec-Quantities: `bore == shaft`, `v_supply ==
v_device`); sonst belegte Empfehlung + ehrliche Lücke. Kein erfundenes „passt".

### 4. Elektronik (eigene Domäne)
Getrennte **Elektronik-BOM** (`BomItem.domain = ELECTRONIC` oder
`spec.electronics`). Empfohlene Geräte (Controller, Sensoren, Netzteil,
Verkabelung) mit grounded Spec (Spannung V, Strom A, Leistung W, Pinout) je aus
**Datenblatt-Claim**. Spannungs-/Strom-Kompatibilität als Constraints (elektrische
Einheiten A/V/W/Ω/Ah). Jede Empfehlung belegt, sonst Lücke.

### 5. Montage-Detail & Ort
`Step` um **`tool`** (Werkzeug) + **`torque`** (Quantity N·m, grounded/decision)
erweitern; Reihenfolge/Prüfpunkt bestehen schon. **`SiteRequirements`:** Platzbedarf
(Envelope ≤ verfügbarer Platz, deterministischer Constraint), Stromanschluss,
Belüftung, indoor/outdoor, Sicherheitsabstände — je grounded/declared. Umgebungs-
Werte aus Datenblatt-/Norm-Claims oder als begründete DECISION.

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
