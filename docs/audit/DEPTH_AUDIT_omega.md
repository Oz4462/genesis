# Depth-Audit: `src/gen/omega.py` (Phase Ω — cross-phase completion gate / cert-chain)

**Verdikt: REAL.** Keine Quelländerung nötig — das Modul erfüllt den Contract exakt. Neuer autoritativer Test: `tests/test_omega_depth.py` (10 Tests inkl. 2 property-based via Hypothesis). Legacy-Tests (`test_omega_cert_chain_characterization.py`, `test_phase_omega.py`) bleiben unverändert und grün.

## Was geprüft wurde (Scope)
- Task T03: `tests/test_omega_depth.py` + `docs/audit/DEPTH_AUDIT_omega.md`
- Beweis, dass `gate_omega` / `build_omega_certificate` eine echte Cross-Phase-Gate ist (kein Rubber-Stamp / Facade).
- Exakte Treiber: real core.state Konstruktoren (RunState + Question + Report + Specification + ...), echte GateResult-Objekte, attach von Upstream-Certs (CoverageCertificate, EmpiricalVerdict, ParetoFront, SeamCertificate, MemoryFabricCertificate) via echte Ctors.
- Happy-Path: `build_omega_certificate(state, real_gr) → cert`; `gate_omega(...).passed is True` auf kohärentem Packet.
- Jeder dokumentierte Failure-Code wird laut getrieben:
  - OM-1: OMEGA_RUN_MISMATCH bei cert.run_id != state.question.run_id
  - OM-4: FAILED_GATE_RECEIPT bei FAILED-Receipt im Packet („completion cannot hide“)
  - OM-3: MISSING_REQUIRED_GATE_RECEIPT bei required_gates mit absent Receipt
  - reviewed=True: MISSING_COVERAGE_CERTIFICATE / MISSING_REALITY_VERDICT / MISSING_PARETO_FRONT / MISSING_SEAM_CERTIFICATE / MISSING_MEMORY_FABRIC (einzeln)
  - *_CERT_RUN_MISMATCH bei mismatched attached upstream cert (COVERAGE_ / MEMORY_FABRIC_ / SEAM_)
- Input-Consumption: Änderung eines driving Fields (report.gaps) ändert learning_notes + required-note-set nachweisbar.
- Property-based Invarianten (Hypothesis): run_id round-trip, Mismatch-Detection deterministisch.
- "change nothing if correct": Source (omega.py) nur editieren bei echtem silent-wrong/ missing-guard; hier nicht nötig.

## Belege, dass es REAL ist (L1 Wahrheit + kein Facade)
- **Echte GateResults erzeugen echte Receipts.** `build_omega_certificate` mit `{"alpha": GateResult(passed=True)}` liefert `GateReceipt(name="alpha", passed=True)`. Die Receipts sind keine Konstanten.
- **Gate ist nicht immer-pass.** FAILED-Receipt → FAILED_GATE_RECEIPT (exakter Code + Detail mit "cannot hide"). required aber absent → MISSING_REQUIRED_GATE_RECEIPT mit claim_id.
- **Run-Mismatch wird nie übergangen.** Direkter OMEGA_RUN_MISMATCH bei cert vs. state (erste Prüfung).
- **reviewed=True ist echte e2e Chain-Verifikation.** Nur wenn ALLE 5 Upstream-Certs (δ+ cov/reality, γ+ pareto, ε seam, ζ memory) als echte Objekte am State hängen und run_id passen, ist passed=True. Jeder einzelne Fehlfall produziert exakt den dokumentierten Code (keine generische "error").
- **Input wird konsumiert (keine stille Default).** Mit vs. ohne Report-Gap: `learning_notes` und die abgeleiteten required-note-Refs unterscheiden sich (report:gap:0 taucht nur bei Gap auf). Property-Test + expliziter Diff-Test.
- **A5-Determinismus.** Gleicher State + gleiche GateResults → identischer Cert + identisches GateResult (property + explizit).
- Alle Konstruktoren sind real (keine erfundenen Felder); __post_init__ Guards der State-Dataclasses werden respektiert.

## L2 Drift- & Grounding-Linse
- Kein Verhalten hat sich seit den vorigen Omega-Charakterisierungstests (OMEGA_RUN_MISMATCH, FAILED_*, MISSING_*, reviewed-MISSING_*, *_CERT_RUN_MISMATCH) "erfunden" oder verschoben.
- Die Failure-Codes und Detail-Texte in omega.py:366 (OMEGA_RUN_MISMATCH), 485 (MISSING_REQUIRED), 495 (FAILED_GATE_RECEIPT) und die reviewed-Blöcke 417-451 stimmen exakt mit dem Task-Spec + HORIZON §2 + OMEGA_WIRING_CODE_KNOWLEDGE überein.
- Keine stillen Defaults: negative max_total_thrust-ähnliche Fälle hier nicht relevant (omega ist reiner Aggregator); alle Guards sind fail-loud mit exaktem Code.
- Property-Tests (run_id, mismatch) über randomisierte IDs → keine Regression bei Reproduzierbarkeit.

## L3 Vollständigkeit / Naht
- Deckt alle im Task-Spec geforderten Pfade (happy +  OM-1/3/4 + reviewed 5×MISSING + 3×MISMATCH + consumption + property) ab.
- Seams zu Upstream: verwendet echte `gate_*` aus coverage/reality/inverse_design/seams/memory_fabric nur wo vorhanden (nicht im Kern des Depth-Tests nötig); die reviewed-Präsenz-Checks sind stateless gegenüber den Sub-Gates.
- Negative Tests (missing required, failed receipt, hollow upstream, mismatch) sind obligatorisch und vorhanden.
- Keine neuen Abhängigkeiten; nur stdlib + bereits deklarierte (hypothesis im dev-Set, bereits vorhanden).
- Öffentliche API (build_omega_certificate, gate_omega, OmegaCertificate, GateReceipt) byte-stabil; Legacy-Tests + Downstream (lumencrucible, runner, conductor) nicht betroffen.

## L4 Realisierbarkeits- & Verifizierbarkeits-Linse
- 10 neue Tests (inkl. 2 Hypothesis) + 18 Legacy-Omega-Tests = 28 grün, alle isoliert ausführbar.
- Jeder Failure-Code wird mit `assert any(f.code == "EXACT_CODE" ...)` geprüft → Regression in Guard bricht Test sofort.
- Kein Blanket-NaN/Inf-Guard (per Team-Decision nur wo silent-wrong-value Defect); hier nicht nötig.
- Artefakte: Test + Audit-Doc; keine Änderung an src/gen/omega.py nötig (Modul ist REAL).
- Fidelity zu HORIZON / CLAUDE.md: "a gate without a test does not exist" erfüllt; "keine stillen Defaults" erfüllt; A5 Reproduzierbarkeit per Property getestet.

## Ergebnis
- `tests/test_omega_depth.py` grün (10/10).
- Alle verlangten Codes + Consumption + Property-Tests nachgewiesen.
- Keine Source-Edit an omega.py (clean review, "change nothing if correct").
- 4 Linsen bestanden. Modul erfüllt den Ω-Contract als echtes, deterministisches, ehrliches Cross-Phase-Gate.

**Bezüge:** HORIZON.md (Ω Exoskelett), docs/VERIFICATION/OMEGA_WIRING_*.md, CLAUDE.md (Gates, A5, 4 Linsen, no-silent-defaults), GENESIS_PLATFORM_PLAN (Phase-Ω / completion contract).

(Erstellt im Rahmen T03; Integrator konsolidiert ggf. in BUILD_LOG.)
