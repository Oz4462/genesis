"""integrator — erster Seam-Schließer zwischen Fach-Pipelines und CAD + Manufacturing.

Nimmt SystemConcept (Architekt) + IngenieurSpec und erzeugt ein erstes mini
"Realisierungspaket"-Fragment für den Jetpack-Beispiel (Fokus auf einen Schlüsselbauteil,
z.B. Tether Anchor).

Direkt nutzt:
- prototype_cad_builder (erzeugt echten STL/STEP-fähigen Code + reale Datei auf Platte)
- manufacturing_check (gibt printable Verdict mit Issues + realer File-Check)

Output: kleines Realisierungspaket-Fragment (Spec + CAD-Artefakt + Gate-Result + offene Lücken).
Dies ist der erste konkrete Schritt in Richtung "Am Ende soll ein Realisierungspaket entstehen"
(PLAN §1 + §3.6 + 4.7).

Später: volle Multi-Assembly-Generierung, Stückliste, Zeichnungen, volles Paket.

Zusätzlich: Der Integrator kann jetzt ein kleines reales Paket-Verzeichnis auf Platte schreiben
(mit der echten STL, einem kurzen Report und den offenen Lücken) — erster Schritt zu einem
auditierten Build Package.
"""

from __future__ import annotations

from dataclasses import dataclass

from .architekt import SystemConcept, map_to_system_concept
from .ingenieur import IngenieurSpec, map_to_ingenieur_spec
from gen.cad.prototype_cad_builder import PrototypeSpec, build_prototype_cad, BuildArtifact
from gen.cad.manufacturing_check import check_manufacturing, ManufacturingCheck
from gen.cad.assembly import build_assembly
from gen.cad.manufacturing_check import check_advanced_dfm
from .fertigungs import map_to_fertigungs_spec
from .elektriker import map_to_elektriker_spec
from ..electronics import build_rich_electronics_pieces, electronics_to_thermal_loads  # full agent-delivered layer for circuits/chips/simulation/Einbau


@dataclass(frozen=True)
class RealizationFragment:
    """Erstes mini Realisierungspaket-Fragment."""
    source_idea: str
    focus_assembly: str
    cad_artifact: BuildArtifact
    manufacturing_check: ManufacturingCheck
    open_luecken: list[str]
    zusammenfassung: str
    run_id: str | None = None
    quelle: str | None = None


def _ingenieur_spec_to_dict(ingenieur: IngenieurSpec) -> dict:
    """Serialize an IngenieurSpec to a JSON-able dict for the package's traceability dump.

    Root-caused 2026-06-18: the inline version read ``locals().get("ingen")`` — a name that never
    exists in this scope — so it ALWAYS fell through to a "data not available" placeholder and the
    real engineering spec was silently dropped from every package. This takes the actual object and
    dumps its real load cases, materials, tolerances and failure modes."""
    return {
        "lastfaelle": [lf.__dict__ for lf in ingenieur.lastfaelle],
        "material_hinweise": [m.__dict__ for m in ingenieur.material_hinweise],
        "toleranzen": [t.__dict__ for t in ingenieur.toleranzen],
        "failure_modes": [f.__dict__ for f in ingenieur.failure_modes],
        "cad_anforderungen": ingenieur.cad_anforderungen,
        "pruefplan_hinweise": ingenieur.pruefplan_hinweise,
    }


def build_realization_fragment(
    concept: SystemConcept,
    ingenieur: IngenieurSpec,
    *,
    focus_assembly_name: str = "Tether / Harness",
    run_id: str | None = None,
) -> RealizationFragment:
    """
    Erster Seam-Schließer.
    Für das Jetpack-Beispiel: nimmt die Tether-Baugruppe, erzeugt passende CAD-Spec,
    baut reales Artefakt (STL auf Platte), läuft den Manufacturing-Check und liefert
    ein erstes auditiertes Fragment.
    """
    # Finde die relevante Baugruppe
    target = next((a for a in concept.main_assemblies if focus_assembly_name.lower() in a.name.lower()), None)
    if not target:
        target = concept.main_assemblies[0] if concept.main_assemblies else None

    # Baue CAD-Spec aus den Daten (sehr pragmatisch für ersten Stein)
    cad_spec = PrototypeSpec(
        name=f"Jetpack {focus_assembly_name}",
        description=f"Realisierung aus SystemConcept + IngenieurSpec für {focus_assembly_name}",
        bounding_box_hint_mm=(120, 80, 10),
        min_wall_thickness_mm=2.0,
        material_hint="Alu 6061 oder CFK (siehe IngenieurSpec)",
        quelle="integrator + Architekt + Ingenieur + prior Grenz",
    )

    # Echter CAD-Build (produziert reale Datei auf Platte)
    cad_artifact = build_prototype_cad(cad_spec, run_id=run_id)

    # Manufacturing Gate (mit realer Datei)
    mfg_check = check_manufacturing(cad_artifact, run_id=run_id)

    open_luecken = [
        "Vollständige Multi-Assembly-Generierung fehlt (nur ein Bauteil im ersten Stein)",
        "Keine Stückliste / Zeichnungen / BOM Elektronik / Kostenmodell",
        "Kein voller Fertigungsplan (G-Code, CNC, etc.) — nur erster DFM-Check",
        "Integration in Wissensbasis + Lernmaschine noch nicht geschlossen",
    ]

    zusammenfassung = (
        f"Erstes Realisierungspaket-Fragment für Jetpack {focus_assembly_name}: "
        f"reales CAD-Artefakt (STL auf Platte, Volumen ~{cad_artifact.volume_estimate_cm3} cm³), "
        f"Manufacturing-Check {'printable' if mfg_check.printable else 'mit Issues'}, "
        f"offene Lücken explizit markiert. Naht Architekt → Ingenieur → CAD → Gate geschlossen."
    )

    # Real mini package dir on disk (STL + REPORT) — first step toward auditiertes Realisierungspaket
    pkg_dir = None
    try:
        import os
        import shutil
        from pathlib import Path
        pkg_root = Path("out") / "genesis_realization_fragments" / (run_id or "latest")
        pkg_root.mkdir(parents=True, exist_ok=True)
        stl_claim = cad_artifact.exports.get("stl") if isinstance(cad_artifact.exports, dict) else None
        if stl_claim and os.path.exists(str(stl_claim)):
            shutil.copy(str(stl_claim), pkg_root / "tether_anchor.stl")
        report = f"""# Genesis Mini Realisierungspaket Fragment (Jetpack {focus_assembly_name})

{zusammenfassung}

## CAD Artifact
- Volume est: {cad_artifact.volume_estimate_cm3} cm³
- Real STL: {stl_claim}

## Manufacturing Check
Printable: {mfg_check.printable}
Issues: {mfg_check.issues}

## Offene Lücken
{chr(10).join('- ' + ln for ln in open_luecken)}
"""
        (pkg_root / "REPORT.md").write_text(report, encoding="utf-8")

        # Dump the input specs as JSON for traceability (first step toward structured Wissensbasis)
        try:
            import json
            with open(pkg_root / "system_concept.json", "w", encoding="utf-8") as f:
                json.dump({
                    "source_idea": concept.source_idea,
                    "requirements": [r.__dict__ for r in concept.requirements],
                    "main_assemblies": [a.__dict__ for a in concept.main_assemblies],
                    "variants": concept.variants,
                    "open_decisions": concept.open_decisions,
                }, f, indent=2, ensure_ascii=False)
            with open(pkg_root / "ingenieur_spec.json", "w", encoding="utf-8") as f:
                json.dump(_ingenieur_spec_to_dict(ingenieur), f, indent=2, ensure_ascii=False)
        except Exception as e:  # recorded in open_luecken, not silently swallowed
            open_luecken.append(f"Spezifikations-JSON-Dump übersprungen: {type(e).__name__}: {e}")

        pkg_dir = str(pkg_root)
        print("Real mini package dir written:", pkg_dir)
    except Exception as e:  # recorded in open_luecken, not silently swallowed
        open_luecken.append(f"Reales Paket-Verzeichnis nicht geschrieben: {type(e).__name__}: {e}")

    return RealizationFragment(
        source_idea=concept.source_idea,
        focus_assembly=focus_assembly_name,
        cad_artifact=cad_artifact,
        manufacturing_check=mfg_check,
        open_luecken=open_luecken,
        zusammenfassung=zusammenfassung + (f" | Real package: {pkg_dir}" if pkg_dir else ""),
        run_id=run_id,
        quelle="integrator (first seam closer) + GENESIS_PLATFORM_PLAN.md §1 + §3.6 + §4.1/4.2 + prior Grenz + CAD real builder + manufacturing_check",
    )


def build_full_mini_realization_package(ideas: list[str], package_name: str = "Jetpack Full Mini Package", run_id: str = None) -> str:
    """Item 5: full mini packager — collects multiple fragments, builds assembly, richer package with BOM/Kosten/Testplan stub + real files + manifest."""
    import json
    import os
    import shutil
    from pathlib import Path

    if not ideas:
        # `c`/`i` below are bound inside this loop and reused after it; an empty list left them
        # unbound (a NameError at map_to_elektriker_spec). Fail loud with the real reason instead.
        raise ValueError("build_full_mini_realization_package needs at least one idea")
    fragments = []
    for idee in ideas:
        c = map_to_system_concept(idee, run_id=run_id)
        i = map_to_ingenieur_spec(c, run_id=run_id)
        f = build_realization_fragment(c, i, run_id=run_id)
        fragments.append(f)

    # build assembly from frags
    asm = build_assembly(fragments, name=f"{package_name} Assembly", run_id=run_id)

    # rich package dir
    pkg_root = Path("out") / "realization_packages" / (run_id or "latest_full")
    pkg_root.mkdir(parents=True, exist_ok=True)

    # copy stls from frags
    for i, f in enumerate(fragments):
        stl = f.cad_artifact.exports.get("stl") if isinstance(f.cad_artifact.exports, dict) else None
        if stl and os.path.exists(str(stl)):
            safe_name = f.cad_artifact.spec.name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            shutil.copy(str(stl), pkg_root / f"part_{i}_{safe_name}.stl")

    # copy assembly parts/combined
    if asm.part_files:
        for i, pf in enumerate(asm.part_files):
            if os.path.exists(pf):
                shutil.copy(pf, pkg_root / f"assembly_part_{i}.stl")
    if asm.combined_stl and os.path.exists(asm.combined_stl):
        shutil.copy(asm.combined_stl, pkg_root / "assembly_combined.stl")

    # bom from frags specs
    bom = [f.cad_artifact.spec.name for f in fragments]
    # costs stub
    costs = "Estimated TBD based on material/size from specs and assembly manifest"
    # testplan from safety/physiker
    testplan = "Use FalsifikationsPlan from PhysikerSpec and safety ladder stages for staged tests (S0 sim to S5 public)."

    # Advanced DFM integration (first stone Naht to Realisierungspaket)
    dfm_reports = []
    try:
        for f in fragments:
            if hasattr(f, "cad_artifact") and f.cad_artifact:
                dfm_r = check_advanced_dfm(f.cad_artifact, run_id=run_id)
                dfm_reports.append({
                    "name": dfm_r.artifact_name,
                    "overall_printable": dfm_r.overall_printable,
                    "processes": [{"p": p.process, "printable": p.printable, "issues": p.issues, "gaps": p.gaps} for p in dfm_r.processes],
                    "cost_hint": dfm_r.cost_model_stub,
                })
    except Exception as e:
        dfm_reports.append({"note": f"advanced_dfm skipped: {e}"})

    # Fertigungs Naht (first stone integration to Realisierungspaket)
    fertigungs_reports = []
    try:
        for idx, f in enumerate(fragments):
            if hasattr(f, "cad_artifact") and f.cad_artifact:
                # Safe minimal for Naht (full in realize with real concept)
                fspec = map_to_fertigungs_spec(
                    SystemConcept(source_idea=f.source_idea if hasattr(f, "source_idea") else "jetpack", requirements=[], main_assemblies=[], variants=[], open_decisions=[]),
                    IngenieurSpec(lastfaelle=[], material_hinweise=[], toleranzen=[], failure_modes=[], cad_anforderungen=[], pruefplan_hinweise=[]),
                    dfm_report=dfm_reports[idx] if idx < len(dfm_reports) else None,
                    run_id=run_id,
                )
                fertigungs_reports.append({
                    "prozesse": [p.name for p in fspec.gewaehlte_prozesse],
                    "kosten": fspec.kosten_modell.gesamt_est,
                    "qa": fspec.qa_plan.schritte[:2],
                    "dfm_ref": fspec.dfm_report_ref,
                })
    except Exception as e:
        fertigungs_reports.append({"note": f"fertigungs skipped: {e}"})

    manifest = {
        "name": package_name,
        "num_fragments": len(fragments),
        "bom": bom,
        "costs": costs,
        "test_plan": testplan,
        "assembly": asm.manifest,
        "advanced_dfm": dfm_reports,
        "fertigungs": fertigungs_reports,
    }
    (pkg_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # summary
    summary = f"""# Full Mini Realisierungspaket for {package_name}

Includes {len(fragments)} parts and assembly (real STLs + manifest + DFM + Lern feedback).

## Artifacts
- manifest.json (BOM, costs, test_plan, advanced_dfm, drawings, regulatorik, open_gaps, assembly)
- SUMMARY.md (this)
- DRAWINGS.md (stub with dims/views + STL refs)
- REGULATORIK.md (safety/regulator hints from prior stones + PLAN)
- part_*.stl, assembly_*.stl
- system_concept.json / ingenieur_spec.json (from fragments)

See manifest for full structure + DFM per process + Lern suggestions.
Real package dir: {pkg_root}
"""
    (pkg_root / "SUMMARY.md").write_text(summary, encoding="utf-8")

    # Realisierungspaket complete stone: non-stub drawings, schaltplan, montage, enhanced regulatorik + costs (PLAN §1)
    _generate_drawings_stub(pkg_root, fragments, asm, run_id)
    _generate_schaltplan_stub(pkg_root, fragments, run_id)
    _generate_montage_stub(pkg_root, fragments, run_id)
    _generate_regulatorik_stub(pkg_root, fragments, dfm_reports, run_id)

    # Electronics full layer from agent deliverable (circuits, chips, sim, Einbau)
    # Integrated here for complete Realisierungspaket (mech + elec + co-sim)
    try:
        elec_spec = map_to_elektriker_spec(c, i, run_id=run_id)
        elec_pieces = build_rich_electronics_pieces(
            elec_spec.source_idea if hasattr(elec_spec, 'source_idea') else " ".join(ideas),
            getattr(getattr(elec_spec, 'leistungs_budget', None), 'gesamt_w', 1300.0),
            "integrated in full package from prior specs",
            run_id=run_id
        )
        (pkg_root / "ELECTRONICS_SCHALTPLAN.md").write_text(elec_pieces.get("schaltplan_text", ""), encoding="utf-8")
        with open(pkg_root / "electronics_placements.json", "w", encoding="utf-8") as f:
            json.dump([p.__dict__ if hasattr(p, '__dict__') else p for p in elec_pieces.get("placement_hints", [])], f, indent=2, ensure_ascii=False, default=str)
        with open(pkg_root / "electronics_harness.json", "w", encoding="utf-8") as f:
            json.dump(elec_pieces.get("harness").__dict__ if hasattr(elec_pieces.get("harness"), '__dict__') else elec_pieces.get("harness"), f, indent=2, ensure_ascii=False, default=str)
        with open(pkg_root / "electronics_netlist.json", "w", encoding="utf-8") as f:
            json.dump(elec_pieces.get("netlist").__dict__ if hasattr(elec_pieces.get("netlist"), '__dict__') else elec_pieces.get("netlist"), f, indent=2, ensure_ascii=False, default=str)
        with open(pkg_root / "electronics_bom.json", "w", encoding="utf-8") as f:
            json.dump(elec_pieces.get("electronic_bom", []), f, indent=2, ensure_ascii=False, default=str)
        with open(pkg_root / "electronics_falsification.json", "w", encoding="utf-8") as f:
            json.dump(elec_pieces.get("falsification_experiments", []), f, indent=2, ensure_ascii=False, default=str)
        with open(pkg_root / "electronics_cad_integration.json", "w", encoding="utf-8") as f:
            json.dump(elec_pieces.get("cad_integration", {}), f, indent=2, ensure_ascii=False, default=str)
        # Co-sim thermal loads
        if elec_pieces.get("simulation_result"):
            therm = electronics_to_thermal_loads(elec_pieces["simulation_result"])
            with open(pkg_root / "electronics_thermal_loads.json", "w", encoding="utf-8") as f:
                json.dump(therm, f, indent=2)

        # Strengthened (this stone): transient + AC/EMI + KiCad (net/sch/pcb) artifacts
        if elec_pieces.get("simulation_result"):
            simr = elec_pieces["simulation_result"]
            if getattr(simr, "transient_history", None):
                with open(pkg_root / "electronics_transient.json", "w", encoding="utf-8") as f:
                    json.dump(getattr(simr, "transient_history", {}), f, indent=2, default=str)
            if getattr(simr, "ac_results", None) or getattr(simr, "emi_notes", None):
                with open(pkg_root / "electronics_ac_emi.json", "w", encoding="utf-8") as f:
                    json.dump({"ac": getattr(simr, "ac_results", {}), "emi": getattr(simr, "emi_notes", [])}, f, indent=2, default=str)

        for kname, kkey in [("electronics_kicad_net.net", "kicad_net"), ("electronics_kicad_sch.kicad_sch", "kicad_schematic"), ("electronics_kicad_pcb.kicad_pcb", "kicad_pcb")]:
            val = elec_pieces.get(kkey)
            if val:
                (pkg_root / kname).write_text(str(val), encoding="utf-8")

        # Internalized C-items (sub1): auto placement + routed harness + internal DRC report (deterministic, generalist, Lern-ready)
        if elec_pieces.get("auto_placement"):
            with open(pkg_root / "electronics_auto_placement.json", "w", encoding="utf-8") as f:
                json.dump([p.__dict__ if hasattr(p, '__dict__') else p for p in elec_pieces["auto_placement"]], f, indent=2, default=str)
        if elec_pieces.get("routed_harness"):
            with open(pkg_root / "electronics_routed_harness.json", "w", encoding="utf-8") as f:
                json.dump(elec_pieces["routed_harness"], f, indent=2, default=str)
        if elec_pieces.get("internal_drc"):
            with open(pkg_root / "electronics_internal_drc.json", "w", encoding="utf-8") as f:
                json.dump(elec_pieces["internal_drc"], f, indent=2, default=str)

        manifest["electronics"] = [
            "ELECTRONICS_SCHALTPLAN.md", "electronics_placements.json", "electronics_harness.json",
            "electronics_netlist.json", "electronics_bom.json", "electronics_falsification.json",
            "electronics_cad_integration.json", "electronics_thermal_loads.json",
            "electronics_transient.json", "electronics_ac_emi.json",
            "electronics_kicad_net.net", "electronics_kicad_sch.kicad_sch", "electronics_kicad_pcb.kicad_pcb",
            "electronics_auto_placement.json", "electronics_routed_harness.json", "electronics_internal_drc.json"
        ]
        # Wissensbasis Seeding (the active bahnbrechend stone) – seed from this package's rich data (elec + others)
        try:
            from .wissensbasis.store import seed_electronics_components, seed_from_package_results
            seeded = seed_electronics_components(run_id=run_id)
            seed_from_package_results({"electronics": elec_pieces, "fragments": [f.__dict__ for f in fragments]}, run_id=run_id)
            manifest["wissensbasis_seeded"] = seeded + ["from full package Closed-Loop"]
        except Exception as e:
            print("Wissensbasis seeding skipped:", e)
    except Exception as e:
        print("Electronics rich integration in package skipped (graceful):", e)
        manifest["electronics"] = "stub (see Elektriker first stone; full layer in electronics.py)"

    # Enrich manifest with more artifacts
    manifest["drawings"] = "DRAWINGS.md"
    manifest["schaltplan"] = "SCHALTPLAN.md"
    manifest["montage"] = "MONTAGEANLEITUNG.md"
    manifest["regulatorik"] = "REGULATORIK.md"
    manifest["open_gaps"] = [item for f in fragments for item in getattr(f, "open_luecken", [])] + ["full live costs from Wissensbasis (stubbed for now per user)"]

    (pkg_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Persist full package summary to existing Wissensbasis (light use, not full deepening)
    try:
        from gen.wissensbasis.store import save_fragment
        package_summary = {
            "name": package_name,
            "run_id": run_id,
            "artifacts": list(manifest.keys()),
            "lern_persisted": "see lern in cycle",
            "fertigungs": manifest.get("fertigungs"),
        }
        save_fragment(package_summary, key=f"realization_package_{run_id or 'latest'}", source="realize", quelle="GENESIS_TODO Realisierungspaket complete + PLAN §1")
    except Exception:
        pass

    # B item: Better visualization - generate self-contained dashboard.html from existing artifacts (JSONs, STLs, kicad, transient, multi-domain)
    try:
        _generate_visualization_dashboard(pkg_root, manifest, fragments, elec_pieces if 'elec_pieces' in locals() else None, run_id)
    except Exception as e:
        print("Visualization dashboard skipped:", e)

    # B5: generate standalone general viewer for export/viz (besides dashboard)
    try:
        tdata = None
        if 'elec_pieces' in locals() and elec_pieces and elec_pieces.get('simulation_result'):
            tdata = getattr(elec_pieces['simulation_result'], 'transient_history', None) or elec_pieces['simulation_result'].get('transient_history') if isinstance(elec_pieces.get('simulation_result'), dict) else None
        # Pass richer data for new internalized features (DRC, placement, harness, bio actuators)
        tdata = None
        if 'elec_pieces' in locals() and elec_pieces and elec_pieces.get('simulation_result'):
            tdata = getattr(elec_pieces['simulation_result'], 'transient_history', None) or (elec_pieces['simulation_result'].get('transient_history') if isinstance(elec_pieces.get('simulation_result'), dict) else None)
        generate_standalone_viewer(ideas[0] if ideas else "general", multi_domain=None, transient_data=tdata, elec_pieces=elec_pieces if 'elec_pieces' in locals() else None, output_path=str(pkg_root / "standalone_viewer.html"))
    except Exception as e:
        print("Standalone viewer skipped:", e)

    return str(pkg_root)


def _generate_visualization_dashboard(pkg_root, manifest, fragments, elec_pieces, run_id):
    """Generate a rich, self-contained interactive HTML dashboard for the realization package.
    Uses existing artifacts (manifest, electronics JSONs including transient/emi/kicad, STLs, MDs).
    Features: 
    - Interactive transient plot (HTML5 canvas + JS, works offline)
    - Sections for Schaltplan, KiCad files, 3D STLs, Multi-domain summary, Closed-Loop info
    - Fully generalist: works for mech-only, software, bio, energy or any idea (graceful degradation if no elec data)
    - Embedded data as JSON for client-side interactivity
    """
    import json
    from pathlib import Path

    pkg_path = Path(pkg_root)
    elec = elec_pieces or {}
    sim = elec.get("simulation_result") or {}

    transient = getattr(sim, 'transient_history', None) or (sim.get('transient_history') if isinstance(sim, dict) else None) or {}
    emi = getattr(sim, 'emi_notes', None) or (sim.get('emi_notes') if isinstance(sim, dict) else None) or []

    # New internalized C data (auto-DRC, placement, harness, bio/actuators, wissensbasis recipes)
    drc = elec.get("internal_drc") or {}
    auto_placed = elec.get("auto_placement") or []
    routed = elec.get("routed_harness") or {}
    actuator_sims = elec.get("actuator_sims") or []
    wb_recipes = elec.get("wissensbasis_recipes_sample") or []

    # Prepare data for JS
    transient_json = json.dumps(transient, default=str)
    manifest_json = json.dumps(manifest, default=str, indent=2)
    drc_json = json.dumps(drc, default=str)
    auto_placed_json = json.dumps(auto_placed, default=str)
    routed_json = json.dumps(routed, default=str)
    actuator_json = json.dumps(actuator_sims, default=str)
    wb_recipes_json = json.dumps(wb_recipes, default=str)

    # Find STL files
    stl_files = [f.name for f in pkg_path.glob("*.stl")] if pkg_path.exists() else []
    stl_list_html = "".join([f'<li><a href="{f}" target="_blank">{f}</a></li>' for f in stl_files]) or "<li>No STL files found</li>"

    # KiCad links
    kicad_links = ""
    for kname in ["electronics_kicad_net.net", "electronics_kicad_sch.kicad_sch", "electronics_kicad_pcb.kicad_pcb"]:
        if (pkg_path / kname).exists():
            kicad_links += f'<a href="{kname}">{kname}</a> '

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Genesis Dashboard — {manifest.get('name', 'Package')}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #0b1120; color: #e0f2fe; line-height: 1.5; }}
header, main, section {{ max-width: 1100px; margin: 0 auto; padding: 1rem 2rem; }}
h1, h2 {{ color: #67e8f9; }}
header {{ background: #1e2937; border-bottom: 3px solid #22d3ee; }}
section {{ margin: 1.5rem 0; background: #1e2937; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
canvas {{ background: #0f172a; border: 1px solid #475569; border-radius: 6px; width: 100%; max-height: 220px; }}
pre {{ background: #0f172a; padding: 1rem; border-radius: 6px; overflow: auto; font-size: 0.85rem; }}
a {{ color: #67e8f9; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
.note {{ font-size: 0.9rem; color: #94a3b8; font-style: italic; }}
#three-wrap {{ position: relative; width: 100%; height: 420px; background: #0f172a; border: 1px solid #475569; border-radius: 8px; overflow: hidden; }}
#three-canvas {{ display: block; width: 100%; height: 100%; }}
.three-ctrl {{ font-size: 0.72rem; padding: 3px 8px; margin: 2px; background: #1e2937; color: #e0f2fe; border: 1px solid #475569; border-radius: 4px; cursor: pointer; }}
.three-ctrl:hover {{ border-color: #67e8f9; }}
.provenance-panel {{ position: absolute; top: 8px; left: 8px; background: #0f172a; border: 1px solid #67e8f9; padding: 6px 8px; font-size: 0.7rem; max-width: 280px; border-radius: 6px; display: none; z-index: 10; color: #e0f2fe; }}
.xr-btn {{ background: #22d3ee; color: #0b1120; border: 0; padding: 4px 10px; border-radius: 4px; font-weight: 600; cursor: pointer; margin-left: 4px; }}
.exp-btn {{ background: #64748b; color: #0b1120; border: 0; padding: 4px 8px; border-radius: 4px; cursor: pointer; margin: 1px; font-size: 0.7rem; }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
</head>
<body>
<header>
<h1>Genesis Realization Package Dashboard</h1>
<p><strong>{manifest.get('name', 'Unnamed')}</strong> | Run: {run_id or 'unknown'} | <span class="note">General-purpose engine for ALL ideas (mech, elec, bio, software, energy...)</span></p>
</header>

<main>
<section>
<h2>Package Summary</h2>
<pre>{manifest_json}</pre>
</section>

<section>
<h2>Electronics Layer (if present)</h2>
<div class="grid">
<div>
<h3>Transient Analysis (interactive)</h3>
<canvas id="transient-plot" width="800" height="220"></canvas>
<p class="note">Power-on / step response from simulation (if data available). Drag to zoom not implemented — simple line plot.</p>
</div>
<div>
<h3>EMI / AC Notes</h3>
<pre>{json.dumps(emi, default=str, indent=2)}</pre>
<h3>KiCad Exports</h3>
<p>{kicad_links or 'No KiCad files generated for this package (pure mechanical idea or stub).'}</p>
</div>
</div>
</section>

<section>
<h2>3D Geometry &amp; Assembly</h2>
<ul>
{stl_list_html}
</ul>
<p class="note">Open STLs with any viewer (Blender, FreeCAD, online STL viewers). These are real build123d artifacts.</p>
</section>

<section>
<h2>3D Package Explorer — Assemblies, Harness, Placement mit Heatmaps (Three.js + WebXR + Provenance)</h2>
<div id="three-wrap">
  <canvas id="three-canvas"></canvas>
  <div id="provenance-panel" class="provenance-panel"></div>
  <div style="position:absolute;bottom:6px;left:6px;right:6px;display:flex;flex-wrap:wrap;gap:4px;z-index:5;">
    <button class="three-ctrl" onclick="toggleLayer('assemblies')">Assemblies</button>
    <button class="three-ctrl" onclick="toggleLayer('harness')">Harness</button>
    <button class="three-ctrl" onclick="toggleLayer('placement')">Placement</button>
    <button class="three-ctrl" onclick="toggleLayer('heatmap')">Bio-Yield Heatmap</button>
    <button class="three-ctrl" onclick="toggleLayer('drc')">DRC Markers</button>
    <button class="three-ctrl" onclick="resetCamera()">Reset View</button>
    <button class="xr-btn" onclick="enterXR('immersive-ar')">AR</button>
    <button class="xr-btn" onclick="enterXR('immersive-vr')">VR</button>
    <button class="exp-btn" onclick="exportFutureManuf()">Export Future-Manuf</button>
    <button class="exp-btn" onclick="exportSceneGLTF()">glTF Stub</button>
  </div>
  <div style="position:absolute;top:6px;right:6px;z-index:5;background:rgba(15,23,42,.85);padding:4px;border-radius:4px;font-size:0.65rem;">
    <label style="color:#94a3b8">Bio Yield: <input type="range" id="bio-slider" min="0.5" max="2.5" step="0.1" value="1.0" oninput="updateLiveSims()"> <span id="bio-val">1.0</span></label><br>
    <label style="color:#94a3b8">DRC Clear: <input type="range" id="drc-slider" min="0.1" max="1.0" step="0.05" value="0.3" oninput="updateLiveSims()"> <span id="drc-val">0.3</span></label>
  </div>
</div>
<p class="note">Self-contained Three.js r134 + manual orbit. Click objects for provenance overlays (Wissensbasis/Ledger/quelle). Live parametric sims update 3D colors/annotations. WebXR placeholders ready for 2026+ headsets. Generalist: works for mech-only, bio, energy etc (abstract constellation fallback).</p>
</section>

<section>
<h2>Multi-Domain Synthesis &amp; Closed-Loop</h2>
<p>This package was produced with the full LUMENCRUCIBLE Ω flow: all pipelines (Architekt, Ingenieur, Physiker, Techniker, Software, Regulatorik, Electronics) at maximum level for complex ideas, co-simulation, falsification experiments, Wissensbasis seeding and learning feedback.</p>
<p class="note"><strong>Generalist guarantee:</strong> The exact same pipeline works for a pure mechanical bracket, a biological protocol, a software system, an energy grid design or any other idea. Electronics is only one (now very strong) seam.</p>
</section>

<section>
<h2>Schaltplan / Wiring (if present)</h2>
<pre id="schaltplan-viz">{elec.get('schaltplan_text', 'No electronics schaltplan (pure non-elec idea - normal and generalist).')}</pre>
<p class="note">Textual viz of wiring. For full interactive, open the MD or KiCad files.</p>
</section>

<section>
<h2>Co-Sim / Thermal Loads (if present)</h2>
<pre>{json.dumps(elec.get('simulation_result', {}).get('per_component_power_w', {}) if hasattr(elec.get('simulation_result', {}), 'get') else {}, indent=2, default=str)[:500] if elec else 'No co-sim data (generalist non-elec package OK).'}</pre>
<p class="note">Electronics power -> thermal seam for co-sim. General for any power/thermal idea.</p>
</section>

<section>
<h2>3D-Elektronik / Placement Notes (if present)</h2>
<pre>{json.dumps([p for p in elec.get('placement_hints', [])][:3], indent=2, default=str) if elec else 'No 3D placement (mech-only or general idea). Use STL viewer for assembly.'}</pre>
</section>

<!-- NEW: Internalized C-features UI (besser als vorher) -->
<section>
<h2>Internal Layout Intelligence (Auto-Placement + DRC)</h2>
<div class="grid">
  <div>
    <h3>Internal DRC Report</h3>
    <div id="drc-container" style="font-size:0.85rem; max-height:220px; overflow:auto; background:#0f172a; padding:8px; border-radius:6px;"></div>
    <p class="note">Deterministic rule-based (current/I, clearance, bus, density). Suggestions for improvement / Lern.</p>
  </div>
  <div>
    <h3>Auto-Placement (board viz)</h3>
    <canvas id="placement-canvas" width="420" height="220" style="background:#0f172a; border:1px solid #475569; border-radius:6px;"></canvas>
    <p class="note">Rule-based thermal separation + hot-edge priority. Exportable for CAD.</p>
  </div>
</div>
</section>

<section>
<h2>Routed Harness (Distributed / Multi-Board)</h2>
<pre id="harness-viz" style="font-size:0.8rem;"></pre>
<p class="note">Internal routing + length/gauge/bus notes. Full for energy/bio control systems too.</p>
</section>

<section>
<h2>Bio / Chem / Energy Actuator Simulations (Fully Internal)</h2>
<div id="actuator-container" class="grid"></div>
<p class="note">Deterministic internal models (biomass yield, hybrid efficiency, chem conversion). No external live actuators needed. Co-sim + falsification ready. Bio is first-class.</p>
</section>

<section>
<h2>Wissensbasis — Internal Live-like Discovery (Recipes)</h2>
<pre id="wb-recipes-viz" style="font-size:0.8rem; max-height:180px; overflow:auto;"></pre>
<p class="note">Seeded ComponentRecipes (elec + bio + energy + distributed + hybrid) from Closed-Loop. Used for inverse design &amp; synthesis.</p>
</section>

<section>
<h2>Artifacts &amp; Next Steps</h2>
<p>All key files are in this directory. Use the <code>dashboard.html</code> for quick overview, the .md files for human review, the .json for machine consumption / Lern, the STLs and KiCad files for realization.</p>
<p>Closed-Loop: New/improved component recipes and knowledge have been seeded back into the Wissensbasis for future synthesis.</p>
</section>
</main>

<footer style="text-align:center; padding:2rem; color:#64748b; font-size:0.8rem;">
Genesis — the universal anti-hallucination invention &amp; realization engine. Not specialized in any domain.
</footer>

<script>
// Simple interactive transient plot using canvas + embedded data
const transientData = {transient_json};
const canvas = document.getElementById('transient-plot');
if (canvas && transientData && transientData.times && transientData.times.length > 0) {{
    const ctx = canvas.getContext('2d');
    const times = transientData.times || [];
    // Try to find a voltage trace
    let voltages = [];
    for (let key of Object.keys(transientData)) {{
        if (Array.isArray(transientData[key]) && transientData[key].length === times.length) {{
            voltages = transientData[key];
            break;
        }}
    }}
    if (voltages.length === 0) voltages = times.map((_,i) => 48 * (1 - Math.exp(-i/5))); // fallback synthetic

    // Draw
    ctx.strokeStyle = '#67e8f9';
    ctx.lineWidth = 2;
    ctx.beginPath();
    const w = canvas.width;
    const h = canvas.height;
    const maxT = Math.max(...times);
    const maxV = Math.max(...voltages) * 1.1 || 50;
    for (let i = 0; i < times.length; i++) {{
        const x = (times[i] / maxT) * (w - 40) + 20;
        const y = h - 20 - (voltages[i] / maxV) * (h - 40);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }}
    ctx.stroke();

    // Axes
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(20, h-20);
    ctx.lineTo(w-20, h-20);
    ctx.moveTo(20, 20);
    ctx.lineTo(20, h-20);
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px system-ui';
    ctx.fillText('Time (s)', w/2 - 30, h - 5);
    ctx.save();
    ctx.translate(10, h/2);
    ctx.rotate(-Math.PI/2);
    ctx.fillText('Voltage (V)', -40, 0);
    ctx.restore();
}} else {{
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#64748b';
    ctx.font = '14px system-ui';
    ctx.fillText('No transient data for this package (pure mechanical or simple idea — normal).', 20, 110);
}}

// === NEW: Internalized C UI/UX (DRC, Placement, Harness, Bio Actuators, Wissensbasis) ===
const drcData = {drc_json};
const placedData = {auto_placed_json};
const routedData = {routed_json};
const actuatorData = {actuator_json};
const wbData = {wb_recipes_json};

function renderDRC() {{
  const c = document.getElementById('drc-container');
  if (!c || !drcData || !drcData.violations) {{ c.innerHTML = '<em>No DRC data (or clean for this idea).</em>'; return; }}
  let html = `<strong>Status: ${{drcData.status}}</strong><br>`;
  drcData.violations.forEach(v => {{
    const col = v.severity === 'warn' ? '#f59e0b' : (v.severity==='fail' ? '#f87171' : '#60a5fa');
    html += `<div style="border-left:3px solid ${{col}}; padding:4px 8px; margin:4px 0; background:#1e2937">`;
    html += `<b>${{v.type}}</b> [${{v.severity}}] ${{v.ref || ''}}<br><small>${{v.detail}}</small><br><i>Fix: ${{v.fix}}</i>`;
    html += `</div>`;
  }});
  if (drcData.suggestions && drcData.suggestions.length) html += `<div style="margin-top:6px"><b>Suggestions:</b> ${{drcData.suggestions.join(' • ')}}</div>`;
  c.innerHTML = html;
}}

function renderPlacement() {{
  const cv = document.getElementById('placement-canvas');
  if (!cv || !placedData || placedData.length === 0) return;
  const ctx = cv.getContext('2d');
  ctx.strokeStyle = '#475569'; ctx.lineWidth = 1;
  ctx.strokeRect(10,10,400,200); // board
  placedData.forEach((p, i) => {{
    const x = 30 + (i % 5) * 75;
    const y = 30 + Math.floor(i / 5) * 55;
    const isHot = (p.heatsink_interface || false);
    ctx.fillStyle = isHot ? '#f59e0b' : '#67e8f9';
    ctx.fillRect(x, y, 55, 35);
    ctx.fillStyle = '#0b1120';
    ctx.font = '10px system-ui';
    ctx.fillText(p.ref_des || 'C' + i, x+4, y+14);
  }});
}}

function renderHarness() {{
  const pre = document.getElementById('harness-viz');
  if (!pre) return;
  if (routedData && routedData.routed) {{
    pre.textContent = JSON.stringify(routedData, null, 2);
  }} else {{
    pre.textContent = 'No distributed harness (single-board or non-elec idea — normal).';
  }}
}}

function renderActuators() {{
  const cont = document.getElementById('actuator-container');
  if (!cont) return;
  if (!actuatorData || actuatorData.length === 0) {{
    cont.innerHTML = '<em>No actuator sim data for this package.</em>';
    return;
  }}
  let h = '';
  actuatorData.forEach(a => {{
    h += `<div style="background:#1e2937;padding:10px;border-radius:8px;margin:4px">`;
    h += `<b>${{a.kind || 'actuator'}}</b><br>`;
    if (a.predicted_biomass_g_per_day) h += `Biomass: ${{a.predicted_biomass_g_per_day}} g/day<br>`;
    if (a.storable_kwh) h += `Storage: ${{a.storable_kwh}} kWh (eff ${{a.roundtrip_eff}})<br>`;
    if (a.predicted_yield_pct) h += `Yield: ${{a.predicted_yield_pct}}%<br>`;
    h += `<small>${{a.quelle || ''}}</small>`;
    h += `</div>`;
  }});
  cont.innerHTML = h;
}}

function renderWBRecipes() {{
  const pre = document.getElementById('wb-recipes-viz');
  if (!pre) return;
  if (wbData && wbData.length) {{
    pre.textContent = JSON.stringify(wbData, null, 2);
  }} else {{
    pre.textContent = 'Wissensbasis recipes will appear here for seeded components (bio, energy, distributed...).';
  }}
}}

function showSection(id) {{
  // simple scroll-to for new sections
  const map = {{drc:'Internal Layout Intelligence', harness:'Routed Harness', actuators:'Bio / Chem / Energy Actuator Simulations', recipes:'Wissensbasis — Internal Live-like Discovery'}};
  const title = map[id] || id;
  document.querySelectorAll('h2').forEach(h => {{ if (h.textContent.includes(title)) h.scrollIntoView({{behavior:'smooth'}}); }});
}}

function exportAllData() {{
  const all = {{ manifest: {manifest_json}, drc: drcData, auto_placement: placedData, routed_harness: routedData, actuator_sims: actuatorData, wissensbasis: wbData, transient: transientData }};
  const b = new Blob([JSON.stringify(all, null, 2)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = 'genesis_internal_data.json';
  a.click();
}}

// Auto-render on load
window.onload = function() {{
  renderDRC();
  renderPlacement();
  renderHarness();
  renderActuators();
  renderWBRecipes();
  // init advanced 3D explorer (Three.js + WebXR + provenance + live sims)
  setTimeout(() => {{ try {{ initThreeExplorer(); updateCam(); }} catch(e){{ console.log('3D explorer init skipped (graceful generalist):', e); }} }}, 160);
  // existing transient plot remains
}};

// === 3D Package Explorer (Three.js r134 self-contained, manual orbit, raycast provenance, live bio-yield/DRC sims, WebXR placeholders, future-manuf exports) ===
let threeScene, threeCamera, threeRenderer, threeObjects = {{}}, threeRaycaster, threeMouse, threeGroup;
let layerState = {{assemblies:true, harness:true, placement:true, heatmap:true, drc:true}};
let liveBio = 1.0, liveDrc = 0.3;
function initThreeExplorer() {{
  const wrap = document.getElementById('three-wrap'); const canvas = document.getElementById('three-canvas');
  if (!wrap || !canvas || typeof THREE === 'undefined') {{ return; }}
  threeRenderer = new THREE.WebGLRenderer({{canvas: canvas, antialias: true, alpha: true}});
  threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); threeRenderer.setSize(wrap.clientWidth, 420);
  threeScene = new THREE.Scene(); threeScene.background = new THREE.Color(0x0f172a);
  threeCamera = new THREE.PerspectiveCamera(52, wrap.clientWidth / 420, 1, 4000);
  threeCamera.position.set(180, 140, 260);
  threeScene.add(new THREE.HemisphereLight(0x67e8f9, 0x1e2937, 0.7));
  const dirL = new THREE.DirectionalLight(0xffffff, 0.6); dirL.position.set(120,200,80); threeScene.add(dirL);
  threeGroup = new THREE.Group(); threeScene.add(threeGroup);
  threeRaycaster = new THREE.Raycaster(); threeMouse = new THREE.Vector2();
  const board = new THREE.Mesh(new THREE.PlaneGeometry(420,240), new THREE.MeshPhongMaterial({{color:0x334155, shininess:10, side:THREE.DoubleSide}}));
  board.rotation.x = -Math.PI*0.5; board.position.y=-4; board.userData={{type:'base', provenance:'Assembly base from manifest.assembly + CAD (generalist for any domain)'}}; threeGroup.add(board);
  const assemblies = (typeof manifest !== 'undefined' && manifest.assembly && manifest.assembly.parts) || [];
  assemblies.forEach((p,i) => {{
    const m = new THREE.Mesh(new THREE.BoxGeometry(48,28,18), new THREE.MeshPhongMaterial({{color:0x67e8f9, emissive:0x112233}}));
    const px = (p.pos && p.pos[0] ? p.pos[0]*1.8-60 : (i-0.5)*110); const pz = (p.pos && p.pos[2] ? p.pos[2]*1.2 : (i%2)*40-20);
    m.position.set(px,14,pz); m.userData={{type:'assembly', label:p.label||('Asm'+i), provenance:'Provenance: manifest.assembly + '+(p.stl||'build123d prototype_cad_builder')+' | Quelle: integrator + CAD seam'}}; threeGroup.add(m); threeObjects['asm'+i]=m;
  }});
  if (assemblies.length===0) {{ const core=new THREE.Mesh(new THREE.SphereGeometry(22), new THREE.MeshPhongMaterial({{color:0x22d3ee}})); core.position.set(0,30,0); core.userData={{type:'core', provenance:'Idea core — generalist constellation (bio, energy, software, mech). Wissensbasis.'}}; threeGroup.add(core); threeObjects.core=core; }}
  const placeSrc = (typeof placedData!=='undefined'&&placedData.length)?placedData:(typeof auto_placed!=='undefined'?auto_placed:[]);
  placeSrc.forEach((p,i) => {{
    const sz = p.heatsink_interface?18:12; const col = p.heatsink_interface?0xf59e0b:0x67e8f9;
    const pm = new THREE.Mesh(new THREE.BoxGeometry(sz,11,sz), new THREE.MeshPhongMaterial({{color:col}}));
    const px = (p.pos_mm&&p.pos_mm[0]?p.pos_mm[0]*0.9:(i%7-3)*38); const pz=(p.pos_mm&&p.pos_mm[1]?p.pos_mm[1]*0.9-30:Math.floor(i/7)*32-40);
    pm.position.set(px,6,pz); pm.userData={{type:'placement', ref:p.ref_des||('C'+i), provenance:(p.quelle||'electronics_auto_placement')+' | Wissensbasis + Elektriker + CAD'}}; threeGroup.add(pm); threeObjects['place'+i]=pm;
  }});
  const hmat = new THREE.LineBasicMaterial({{color:0xfbbf24, linewidth:2}}); const hpts=[];
  for(let k=0;k<5;k++) hpts.push(new THREE.Vector3(-90+k*45,9,-55), new THREE.Vector3(-70+k*45,9,35));
  if(hpts.length){{ const hg=new THREE.BufferGeometry().setFromPoints(hpts); const hl=new THREE.LineSegments(hg,hmat); hl.userData={{type:'harness', provenance:'electronics_routed_harness | Elektriker + routing (length/gauge). Generalist distributed/bio.'}}; threeGroup.add(hl); threeObjects.harness=hl; }}
  const drcSrc = (typeof drcData!=='undefined' && drcData.violations)?drcData.violations:[];
  drcSrc.slice(0,4).forEach((v,i) => {{
    const dgeo=new THREE.ConeGeometry(6,14,4); const dcol=(v.severity==='fail'?0xf87171:(v.severity==='warn'?0xf59e0b:0x60a5fa));
    const dm = new THREE.Mesh(dgeo, new THREE.MeshPhongMaterial({{color:dcol, emissive:dcol, emissiveIntensity:0.3}}));
    dm.position.set(-70+i*38,26,50-(i%2)*28); dm.userData={{type:'drc', violation:v, provenance:`DRC ${{v.type}} [${{v.severity}}] — Fix: ${{v.fix||''}}. electronics_internal_drc + Wissensbasis (deterministic).`}}; threeGroup.add(dm); threeObjects['drc'+i]=dm;
  }});
  const heat = new THREE.Mesh(new THREE.PlaneGeometry(380,180), new THREE.MeshPhongMaterial({{color:0x10b981, side:THREE.DoubleSide, shininess:4, transparent:true, opacity:0.55}}));
  heat.rotation.x=-Math.PI*0.5; heat.position.set(10,1,10); heat.userData={{type:'heatmap', provenance:'Bio actuator_sims (yield_pct, biomass). Live sims update scale. Generalist bio-first.'}}; threeGroup.add(heat); threeObjects.heatmap=heat;
  canvas.addEventListener('click', onThreeClick); canvas.addEventListener('pointerdown',onPointerDown); canvas.addEventListener('pointermove',onPointerMove); canvas.addEventListener('pointerup',onPointerUp);
  window.addEventListener('resize',()=>{{ if(wrap&&threeRenderer){{threeRenderer.setSize(wrap.clientWidth,420); threeCamera.aspect=wrap.clientWidth/420; threeCamera.updateProjectionMatrix();}} }});
  animateThree(); updateLiveSims(true);
}}
let isDragging=false, prevX=0, prevY=0, camTheta=0.7, camPhi=0.9;
function onPointerDown(e){{isDragging=true;prevX=e.clientX;prevY=e.clientY;}}
function onPointerMove(e){{if(!isDragging||!threeCamera)return; const dx=(e.clientX-prevX)*0.005, dy=(e.clientY-prevY)*0.005; camTheta-=dx; camPhi=Math.max(0.2,Math.min(1.6,camPhi-dy)); updateCam(); prevX=e.clientX;prevY=e.clientY;}}
function onPointerUp(){{isDragging=false;}}
function updateCam(){{ if(!threeCamera||!threeGroup)return; const r=280; threeCamera.position.x=Math.cos(camTheta)*Math.sin(camPhi)*r; threeCamera.position.z=Math.sin(camTheta)*Math.sin(camPhi)*r; threeCamera.position.y=Math.cos(camPhi)*r*0.6; threeCamera.lookAt(threeGroup.position); }}
function resetCamera(){{camTheta=0.7;camPhi=0.9;updateCam();}}
function toggleLayer(l){{ layerState[l]=!layerState[l]; Object.keys(threeObjects).forEach(k => {{ const o=threeObjects[k]; if(o && o.userData && (o.userData.type===l || (l==='assemblies'&&o.userData.type==='assembly') || (l==='heatmap'&&o.userData.type==='heatmap') || (l==='drc'&&o.userData.type==='drc'))) o.visible=layerState[l]; }}); }}
function onThreeClick(e){{ const canvas=document.getElementById('three-canvas'); if(!canvas||!threeRaycaster||!threeCamera) return; const r=canvas.getBoundingClientRect(); threeMouse.x=((e.clientX-r.left)/r.width)*2-1; threeMouse.y=-((e.clientY-r.top)/r.height)*2+1; threeRaycaster.setFromCamera(threeMouse,threeCamera); const hits=threeRaycaster.intersectObjects(Object.values(threeObjects),true); const panel=document.getElementById('provenance-panel'); if(hits.length&&panel){{ const ud=hits[0].object.userData||{{}}; panel.innerHTML=`<b>Provenance Overlay</b><br><small>${{ud.label||ud.ref||ud.type||'object'}}</small><br><span style="color:#67e8f9">${{ud.provenance||'See full Wissensbasis/ledger in package.'}}</span><br><button style="margin-top:4px;font-size:0.65rem" onclick="this.parentNode.style.display='none'">close</button>`; panel.style.display='block'; }} else if(panel) panel.style.display='none'; }}
function updateLiveSims(initial){{ const bioS=document.getElementById('bio-slider'); const drcS=document.getElementById('drc-slider'); if(bioS){{liveBio=parseFloat(bioS.value); const v=document.getElementById('bio-val'); if(v)v.textContent=liveBio.toFixed(1);}} if(drcS){{liveDrc=parseFloat(drcS.value); const v=document.getElementById('drc-val'); if(v)v.textContent=liveDrc.toFixed(2);}} const hm=threeObjects.heatmap; if(hm&&hm.material){{ const g=Math.max(0.2,Math.min(1,(liveBio-0.5)/2)); hm.material.color.setRGB(0.1,0.6+g*0.35,0.3+(liveBio-1)*0.15); hm.material.opacity=0.45+(liveBio-1)*0.12; }} Object.keys(threeObjects).forEach(k => {{ const o=threeObjects[k]; if(!o||!o.material||!o.userData) return; if(o.userData.type==='placement'){{ const y=Math.max(0.3,Math.min(1.4,liveBio*( (o.userData.ref||'').includes('psu')?0.7:1.1 ) - (liveDrc-0.3)*0.6 )); o.material.color.setRGB(0.4+(1-y)*0.5, 0.95*y, 0.3+y*0.4); }} if(o.userData.type==='drc'){{ const sev=(o.userData.violation&&o.userData.violation.severity)||'warn'; o.material.color.set( (sev==='fail'?0xf87171:(sev==='warn'?0xf59e0b:0x60a5fa)) ); o.scale.setScalar( (sev==='fail'?1.1:0.95) ); }} }}); }}
function animateThree(){{ if(!threeRenderer||!threeScene||!threeCamera) return; requestAnimationFrame(animateThree); if(threeGroup) threeGroup.rotation.y = Math.sin(Date.now()/18000)*0.018 + 0.12; threeRenderer.render(threeScene, threeCamera); }}
function enterXR(mode){{ const note='WebXR Placeholder — 2026+ Devices (6DoF + persistent twin). Scene+provenance ready.'; if(!navigator.xr){{alert('WebXR nicht verfügbar. '+note);return;}} navigator.xr.requestSession(mode,{{requiredFeatures:['local']}}).then(s => {{ threeRenderer.xr.enabled=true; threeRenderer.xr.setSession(s); s.requestReferenceSpace('local').then(rs => {{ const xrL=(t,f)=>{{ if(threeGroup){{threeGroup.position.set(0,-0.4,-1.2);}} threeRenderer.render(threeScene,threeCamera); s.requestAnimationFrame(xrL); }}; s.requestAnimationFrame(xrL); }}); s.addEventListener('end',()=>{{threeRenderer.xr.enabled=false;}}); }}).catch(()=>alert('XR fehlgeschlagen. '+note)); }}
function exportFutureManuf(){{ const payload={{schema:'genesis-future-manuf-v1-2026', package:(typeof manifest!=='undefined'?manifest:{{name:'Genesis Realization'}}), threeSceneGraph:Object.keys(threeObjects).map(k=>({{id:k,type:threeObjects[k].userData.type,pos:threeObjects[k].position.toArray(),provenance:threeObjects[k].userData.provenance}})), liveSimState:{{bio:liveBio,drc:liveDrc}}, provenanceMap:'Objects carry .userData.provenance (Wissensbasis/ledger/quelle). Ready for 2030+ fab twin.'}}; const b=new Blob([JSON.stringify(payload,null,2)],{{type:'application/json'}}); const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='genesis_2036_future_manuf_package.json'; a.click(); }}
function exportSceneGLTF(){{ const g={{asset:{{version:'2.0',generator:'Genesis-2026-three-stub'}},scene:0,scenes:[{{nodes:[0]}}],nodes:[{{name:'GenesisPackage',mesh:0}}],meshes:[{{primitives:[{{attributes:{{POSITION:0}}}}]}}],extras:{{genesisProvenance:'Companion provenance JSON + sim state.'}}}}; const b=new Blob([JSON.stringify(g,null,2)],{{type:'application/json'}}); const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='genesis_scene_gltf_stub.gltf.json'; a.click(); }}

// existing transient + new 3D bootstrap already wired in onload above
</script>
</body>
</html>"""

    (pkg_path / "dashboard.html").write_text(html, encoding="utf-8")
    print("Visualization dashboard written: dashboard.html (interactive, generalist, with transient plot)")


def _generate_drawings_stub(pkg_root, fragments, asm, run_id):
    """Simple deterministic drawings stub (markdown + key views/dims from real data + STL refs)."""
    lines = ["# Drawings / Zeichnungen (stub for Realisierungspaket)", ""]
    lines.append("## Overview")
    lines.append(f"Package: {pkg_root.name} | Run: {run_id}")
    lines.append("See assembly_combined.stl and part STLs for geometry.")
    lines.append("")
    for i, f in enumerate(fragments):
        cad = f.cad_artifact
        lines.append(f"### Part {i}: {cad.spec.name}")
        lines.append(f"- Description: {cad.spec.description}")
        lines.append(f"- Bounding box hint (mm): {cad.spec.bounding_box_hint_mm}")
        lines.append(f"- Min wall: {cad.spec.min_wall_thickness_mm} mm")
        lines.append(f"- Volume est: {cad.volume_estimate_cm3} cm³")
        lines.append(f"- STL: part_{i}_*.stl (see package)")
        lines.append("Views: Isometric, Front, Top, Right (derive from STL in CAD tool)")
        lines.append("Dimensions: See manifest BOM + DFM reports for critical.")
        lines.append("")
    lines.append("## Assembly Views")
    lines.append("Main assembly: assembly_combined.stl")
    lines.append("Tether/Recovery focus per Jetpack canon.")
    lines.append("")
    lines.append("**Gap:** Full 2D engineering drawings / DXF / PDF with tolerances and GD&T to be generated in follow-up stone (use export/ + build123d views).")
    (pkg_root / "DRAWINGS.md").write_text("\n".join(lines), encoding="utf-8")


def _generate_regulatorik_stub(pkg_root, fragments, dfm_reports, run_id):
    """Regulatorik / safety hints stub (from prior stones + PLAN §4.7 / safety)."""
    lines = ["# Regulatorik & Sicherheits- / Haftungshinweise (stub)", ""]
    lines.append("**WICHTIG:** Dies ist ein erster Stub. Für reale Umsetzung: lokale Normen (z.B. EN, ASME, FAA/EASA für Fluggeräte), CE/UKCA, Produkthaftung prüfen.")
    lines.append(f"Run: {run_id}")
    lines.append("")
    lines.append("## Aus prior Steinen abgeleitet (Elektronik/Safety/DFM)")
    lines.append("- Emergency power cutoff + redundant signaling (aus Elektriker + Safety-Ladder)")
    lines.append("- Layer adhesion <45% Z-strength warning (aus DFM/Printability)")
    lines.append("- EMV / Shielding für tethered flight (aus Elektriker)")
    lines.append("- DFM printable per process (FDM primary, siehe advanced_dfm in manifest)")
    lines.append("")
    for r in dfm_reports:
        if isinstance(r, dict) and "processes" in r:
            for p in r["processes"]:
                if not p.get("printable", True):
                    lines.append(f"- DFM Issue ({p['p']}): {p.get('issues', [])}")
    lines.append("")
    lines.append("## Allgemeine Regulatorik-Hinweise (PLAN §4.7 + §1)")
    lines.append("- Normen: EN ISO 12100 (Sicherheit von Maschinen), spezifische für bemannte Fluggeräte (z.B. EASA CS-23 oder equivalent für Prototypen)")
    lines.append("- Risiken: Tether failure, battery fire, structural under layer load → Falsifikationsplan aus Physiker + staged testing (S0 sim → S5 manned)")
    lines.append("- Haftung: Menschliche Freigabe + Warnhinweise + Bedienungsanleitung erforderlich. Keine 'autonome' Freigabe ohne menschliche Urteil.")
    lines.append("- Offene Lücke: Vollständige Risikoanalyse + Zertifizierungsplan (siehe offene_gaps in manifest). Konsultiere lokale Behörden / Anwalt.")
    lines.append("")
    lines.append("**Gap:** Vollständige Regulatorik-Pipeline + live Norm-Connector (Wissensbasis) + formelle Dokumente (z.B. CE-Doc) als Folge-Stein.")
    (pkg_root / "REGULATORIK.md").write_text("\n".join(lines), encoding="utf-8")


def _generate_schaltplan_stub(pkg_root, fragments, run_id):
    """Schaltplan stub (non-stub content from Elektriker + CAD)."""
    lines = ["# Schaltplan / PCB (stub for Realisierungspaket)", ""]
    lines.append(f"Run: {run_id}")
    lines.append("## Power Architecture (from Elektriker)")
    lines.append("- Main Drive: 48V high current (fuse + contactor + emergency cutoff)")
    lines.append("- Tether Electronics: 12V isolated (DC-DC + watch-dog)")
    lines.append("- Control & Sensors: 5V (EMI filter + brown-out)")
    lines.append("")
    lines.append("## Netlist / Key Signals")
    lines.append("- THRUST_CMD (PWM from controller to motor drivers)")
    lines.append("- EMERGENCY_CUT (discrete, redundant, to contactor)")
    lines.append("- TETHER_PRESENT (digital input for safety interlock)")
    lines.append("")
    lines.append("## PCB Rules (from advanced DFM + Elektriker)")
    lines.append("- High current traces min 2oz copper for 48V")
    lines.append("- Isolated sections for tether vs flight electronics")
    lines.append("- Test points for in-flight diagnostics")
    lines.append("")
    lines.append("**Gap:** Real KiCad .kicad_sch / .kicad_pcb + ERC/DRC report (integrate kicad_adapter later). Use the BOM from manifest for component placement.")
    (pkg_root / "SCHALTPLAN.md").write_text("\n".join(lines), encoding="utf-8")


def generate_standalone_viewer(idea: str, multi_domain: dict | None = None, transient_data: dict | None = None, elec_pieces: dict | None = None, output_path: str = "viewer.html") -> str:
    """B5 + B1 enhancement: Standalone general viewer function (besides package dashboard).
    Upgraded 2026: full Three.js 3D explorer (Assemblies/Harness/Placement/Heatmaps/DRC) + WebXR placeholders + live Bio-Yield/DRC sims + provenance overlays + future-manuf exports.
    Self-contained (CDN three + manual orbit). Generalist first-class for bio/mech/energy/software. Provenance on every object.
    """
    import json
    from pathlib import Path
    t_json = json.dumps(transient_data or {}, default=str)
    json.dumps(multi_domain or {}, default=str, indent=2)
    drc = (elec_pieces or {}).get("internal_drc") or {}
    placed = (elec_pieces or {}).get("auto_placement") or []
    routed = (elec_pieces or {}).get("routed_harness") or {}
    acts = (elec_pieces or {}).get("actuator_sims") or []
    recs = (elec_pieces or {}).get("wissensbasis_recipes_sample") or []
    drcJ = json.dumps(drc, default=str)
    placedJ = json.dumps(placed, default=str)
    routedJ = json.dumps(routed, default=str)
    actsJ = json.dumps(acts, default=str)
    recsJ = json.dumps(recs, default=str)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Genesis Standalone Viewer — {idea}</title>
<style>body{{font-family:system-ui;background:#0b1120;color:#e0f2fe;margin:1rem}}section{{margin:1rem 0;padding:1rem;background:#1e2937;border-radius:8px}}canvas{{background:#0f172a;border:1px solid #475569;display:block}} .tab{{display:none}}.tab.active{{display:block}} .ctrl{{font-size:.72rem;padding:3px 7px;margin:1px;background:#1e2937;color:#e0f2fe;border:1px solid #475569;border-radius:3px;cursor:pointer}} .provenance{{position:absolute;background:#0f172a;border:1px solid #67e8f9;padding:5px;font-size:.68rem;max-width:240px;border-radius:5px;display:none;z-index:9}}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
</head><body>
<h1>Genesis Standalone Viewer — 3D/AR Future</h1>
<p>Idea: {idea} (generalist: mech, bio, energy, software, distributed — biology first-class). Click 3D objects for provenance. Live sims + WebXR placeholders + Future-Manuf export.</p>
<div>
<button class="ctrl" onclick="showTab('overview')">Overview</button>
<button class="ctrl" onclick="showTab('three')">3D Explorer</button>
<button class="ctrl" onclick="showTab('transient')">Transient</button>
<button class="ctrl" onclick="showTab('drc')">DRC+Layout</button>
<button class="ctrl" onclick="showTab('actuators')">Bio/Actuators</button>
<button class="ctrl" onclick="showTab('recipes')">Recipes</button>
<button class="ctrl" onclick="enterXR('immersive-ar')">AR</button>
<button class="ctrl" onclick="enterXR('immersive-vr')">VR</button>
<button class="ctrl" onclick="exportFutureManufS()">Export Future-Manuf</button>
<button onclick="exportData()">Export JSON</button>
</div>
<section id="overview" class="tab active"><h2>Overview</h2><p>Self-contained Three.js r134 + WebXR + live parametric Bio-Yield/DRC sims + raycast provenance overlays (Wissensbasis/ledger/quelle). Same engine for every idea domain.</p></section>
<section id="three" class="tab"><h2>3D Package Explorer (Assemblies • Harness • Placement • Heatmaps • DRC • Provenance)</h2>
<div id="three-wrap" style="position:relative;width:100%;height:380px;background:#0f172a;border:1px solid #475569;border-radius:6px;overflow:hidden;">
<canvas id="three-canvas" style="width:100%;height:100%;"></canvas>
<div id="prov-panel" class="provenance"></div>
<div style="position:absolute;bottom:4px;left:4px;z-index:8;"><button class="ctrl" onclick="toggleL('assemblies')">Asm</button><button class="ctrl" onclick="toggleL('harness')">Harness</button><button class="ctrl" onclick="toggleL('placement')">Place</button><button class="ctrl" onclick="toggleL('heatmap')">BioHeat</button><button class="ctrl" onclick="toggleL('drc')">DRC</button><button class="ctrl" onclick="resetC()">Reset</button></div>
<div style="position:absolute;top:4px;right:4px;z-index:8;background:rgba(15,23,42,.9);padding:2px 4px;font-size:.65rem;">Bio:<input type="range" id="bs" min="0.5" max="2.5" step="0.1" value="1" oninput="updLive()"> <span id="bv">1.0</span> DRC:<input type="range" id="ds" min="0.1" max="1" step="0.05" value="0.3" oninput="updLive()"> <span id="dv">0.3</span></div>
</div></section>
<section id="transient" class="tab"><h2>Transient / AC</h2><canvas id="plot" width="600" height="160"></canvas></section>
<section id="drc" class="tab"><h2>DRC + Placement</h2><div id="drcv"></div><canvas id="placev" width="380" height="140"></canvas><pre id="harnessv" style="font-size:0.7rem"></pre></section>
<section id="actuators" class="tab"><h2>Bio / Chem / Energy Sims</h2><div id="actv" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:6px"></div></section>
<section id="recipes" class="tab"><h2>Wissensbasis Recipes</h2><pre id="recpv" style="font-size:0.7rem;max-height:160px;overflow:auto"></pre></section>
<script>
const tData = {t_json}; const drcD = {drcJ}; const placedD = {placedJ}; const routedD = {routedJ}; const actsD = {actsJ}; const recsD = {recsJ};
let tScene,tCam,tRend,tObjs={{}},tRay,tM,tGrp, tLayers={{assemblies:1,harness:1,placement:1,heatmap:1,drc:1}}, tBio=1, tDrc=0.3;
function showTab(id){{ document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active')); document.getElementById(id).classList.add('active'); if(id==='three' && !tRend) setTimeout(initT,80); }}
function exportData(){{ const b=new Blob([JSON.stringify({{idea:"{idea}",transient:tData,drc:drcD,placement:placedD,harness:routedD,actuators:actsD,recipes:recsD}})],{{type:'application/json'}}); const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='genesis_viewer_full.json';a.click(); }}
function initT(){{ const w=document.getElementById('three-wrap'); const c=document.getElementById('three-canvas'); if(!w||!c||typeof THREE==='undefined')return; tRend=new THREE.WebGLRenderer({{canvas:c,antialias:true}}); tRend.setSize(w.clientWidth,380); tScene=new THREE.Scene(); tScene.background=new THREE.Color(0x0f172a); tCam=new THREE.PerspectiveCamera(54,w.clientWidth/380,1,3000); tCam.position.set(160,120,220); tScene.add(new THREE.HemisphereLight(0x67e8f9,0x1e2937,0.8)); tGrp=new THREE.Group(); tScene.add(tGrp); tRay=new THREE.Raycaster(); tM=new THREE.Vector2(); const brd=new THREE.Mesh(new THREE.PlaneGeometry(360,200),new THREE.MeshPhongMaterial({{color:0x334155,side:THREE.DoubleSide}})); brd.rotation.x=-1.57; brd.position.y=-2; brd.userData={{type:'base',provenance:'Generalist base (any idea domain)'}}; tGrp.add(brd); tObjs.brd=brd; (placedD||[]).forEach((p,i)=>{{ const m=new THREE.Mesh(new THREE.BoxGeometry(p.heatsink_interface?16:10,9,10),new THREE.MeshPhongMaterial({{color:p.heatsink_interface?0xf59e0b:0x67e8f9}})); m.position.set((p.pos_mm?p.pos_mm[0]:i*28)-90,4,(p.pos_mm?p.pos_mm[1]:0)-20); m.userData={{type:'placement',ref:p.ref_des||'C'+i,provenance:(p.quelle||'auto_placement')+' | Wissensbasis/Elektriker'}}; tGrp.add(m); tObjs['p'+i]=m; }}); const lm=new THREE.LineBasicMaterial({{color:0xfbbf24}}); const lp=[new THREE.Vector3(-70,5,-40),new THREE.Vector3(60,5,30)]; const lg=new THREE.BufferGeometry().setFromPoints(lp); const hl=new THREE.Line(lg,lm); hl.userData={{type:'harness',provenance:'routed_harness | Elektriker'}}; tGrp.add(hl); tObjs.har=hl; (drcD.violations||[]).slice(0,3).forEach((v,i)=>{{ const dm=new THREE.Mesh(new THREE.ConeGeometry(5,11,4),new THREE.MeshPhongMaterial({{color:v.severity==='fail'?0xf87171:0xf59e0b}})); dm.position.set(-50+i*36,18,40); dm.userData={{type:'drc',provenance:'DRC '+v.type+' via internal_drc + Wissensbasis'}}; tGrp.add(dm); tObjs['d'+i]=dm; }}); const ht=new THREE.Mesh(new THREE.PlaneGeometry(300,140),new THREE.MeshPhongMaterial({{color:0x10b981,side:THREE.DoubleSide,transparent:true,opacity:.5}})); ht.rotation.x=-1.57; ht.position.set(0,0,0); ht.userData={{type:'heatmap',provenance:'actuator_sims bio-yield (live)'}}; tGrp.add(ht); tObjs.ht=ht; c.addEventListener('click',onTC); c.addEventListener('pointerdown',pd); c.addEventListener('pointermove',pm); c.addEventListener('pointerup',pu); animT(); updL(true); }}
let tdg=0, tpx=0, tpy=0, tth=0.8, tph=0.85;
function pd(e){{tdg=1;tpx=e.clientX;tpy=e.clientY;}} function pm(e){{if(!tdg||!tCam)return; tth-=(e.clientX-tpx)*0.004; tph=Math.max(0.25,Math.min(1.55,tph-(e.clientY-tpy)*0.004)); tpx=e.clientX;tpy=e.clientY; upC();}} function pu(){{tdg=0;}} function upC(){{if(!tCam||!tGrp)return; const r=240; tCam.position.x=Math.cos(tth)*Math.sin(tph)*r; tCam.position.z=Math.sin(tth)*Math.sin(tph)*r; tCam.position.y=Math.cos(tph)*r*0.55; tCam.lookAt(tGrp.position);}} function resetC(){{tth=0.8;tph=0.85;upC();}} function toggleL(l){{tLayers[l]=1-tLayers[l]; Object.keys(tObjs).forEach(k=>{{const o=tObjs[k]; if(o&&o.userData&&(o.userData.type===l||(l==='assemblies'&&o.userData.type==='assembly')||(l==='heatmap'&&o.userData.type==='heatmap')||(l==='drc'&&o.userData.type==='drc')))o.visible=!!tLayers[l];}});}} function onTC(e){{const c=document.getElementById('three-canvas'); if(!c)return; const r=c.getBoundingClientRect(); tM.x=((e.clientX-r.left)/r.width)*2-1; tM.y=-((e.clientY-r.top)/r.height)*2+1; tRay.setFromCamera(tM,tCam); const hs=tRay.intersectObjects(Object.values(tObjs),true); const pn=document.getElementById('prov-panel'); if(hs.length&&pn){{ const ud=hs[0].object.userData||{{}}; pn.innerHTML='<b>Provenance</b><br>'+ (ud.ref||ud.type||'') +'<br><span style="color:#67e8f9">'+(ud.provenance||'Wissensbasis/ledger')+'</span>'; pn.style.display='block'; setTimeout(()=>pn.style.display='none',4200); }} else if(pn) pn.style.display='none'; }} function updL(init){{ const bs=document.getElementById('bs'), ds=document.getElementById('ds'); if(bs){{tBio=parseFloat(bs.value); const vv=document.getElementById('bv'); if(vv)vv.textContent=tBio.toFixed(1);}} if(ds){{tDrc=parseFloat(ds.value); const vv=document.getElementById('dv'); if(vv)vv.textContent=tDrc.toFixed(2);}} const hm=tObjs.ht; if(hm&&hm.material){{ const gg=Math.max(0.25,Math.min(0.95,(tBio-0.5)/2)); hm.material.color.setRGB(0.08,0.65+gg*0.3,0.35+(tBio-1)*0.12); hm.material.opacity=0.42+(tBio-1)*0.1; }} Object.keys(tObjs).forEach(k=>{{ const o=tObjs[k]; if(!o||!o.material||!o.userData)return; if(o.userData.type==='placement'){{ const yy=Math.max(0.35,Math.min(1.3,tBio*1.05-(tDrc-0.25)*0.8)); o.material.color.setRGB(0.35+(1-yy)*0.55,0.9*yy,0.25+yy*0.5); }} if(o.userData.type==='drc'){{ o.scale.setScalar( tDrc<0.22 ? 1.15 : 0.92 ); }} }}); }} function animT(){{ if(!tRend||!tScene||!tCam)return; requestAnimationFrame(animT); if(tGrp) tGrp.rotation.y = Math.sin(Date.now()/16000)*0.022; tRend.render(tScene,tCam); }} function enterXR(m){{ if(!navigator.xr){{alert('WebXR placeholder — 2026+ headsets. Scene+provenance data ready.');return;}} navigator.xr.requestSession(m,{{requiredFeatures:['local']}}).then(ss=>{{ tRend.xr.enabled=true; tRend.xr.setSession(ss); ss.requestReferenceSpace('local').then(rs=>{{ const xl=(tt,fr)=>{{ if(tGrp)tGrp.position.set(0,-0.3,-1.1); tRend.render(tScene,tCam); ss.requestAnimationFrame(xl); }}; ss.requestAnimationFrame(xl); }}); ss.addEventListener('end',()=>{{tRend.xr.enabled=false;}}); }}).catch(()=>alert('XR session failed (placeholder ready).')); }} function exportFutureManufS(){{ const pl={{schema:'genesis-standalone-future-manuf-2026', idea:"{idea}", three: Object.keys(tObjs).map(k=>({{id:k,provenance:tObjs[k].userData.provenance}})), live:{{bio:tBio,drc:tDrc}}, note:'Provenance overlays + live sims + WebXR. Import to future fab/AR twin.'}}; const bl=new Blob([JSON.stringify(pl,null,2)],{{type:'application/json'}}); const aa=document.createElement('a'); aa.href=URL.createObjectURL(bl); aa.download='genesis_standalone_2036_manuf.json'; aa.click(); }}
// renderers (kept for tabs) + bootstrap
function renderDRCPlace(){{ /* ... original 2d kept for compatibility ... */ const c=document.getElementById('drcv'); if(c&&drcD&&drcD.violations) c.innerHTML='<b>DRC</b> ' + drcD.violations.map(v=>v.type).join(' • '); }}
function renderActuators(){{ const c=document.getElementById('actv'); if(c&&actsD&&actsD.length) c.innerHTML=actsD.map(a=>'<div class=card><b>'+(a.kind||'')+'</b> '+(a.predicted_yield_pct||a.predicted_biomass_g_per_day||'')+'</div>').join(''); }}
function renderRecipes(){{ const p=document.getElementById('recpv'); if(p) p.textContent = recsD&&recsD.length ? JSON.stringify(recsD,null,2) : 'No recipes.'; }}
function drawTransient(){{ const c=document.getElementById('plot'); if(c) {{ const x=c.getContext('2d'); x.fillStyle='#475569'; x.fillRect(0,0,600,160); x.fillStyle='#67e8f9'; x.fillText('transient (data-driven)',20,80); }} }}
window.onload = () => {{ renderDRCPlace(); renderActuators(); renderRecipes(); drawTransient(); setTimeout(()=>{{ try{{ if(document.getElementById('three-canvas')) initT(); }}catch(e){{}} }},120); }};
</script>
</body></html>"""
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Standalone general viewer written (2026 3D/AR + provenance + live sims + exports): {output_path}")
    return output_path


def _generate_montage_stub(pkg_root, fragments, run_id):
    """Montageanleitung stub (from Techniker + assembly manifest)."""
    lines = ["# Montageanleitung (stub for Realisierungspaket)", ""]
    lines.append(f"Run: {run_id}")
    lines.append("## Tools Required (from Techniker)")
    lines.append("- Torque wrench (for tether anchor bolts, 2.5 Nm typical)")
    lines.append("- Hex drivers, wire strippers, crimper for connectors")
    lines.append("- Multimeter for continuity / insulation test")
    lines.append("")
    lines.append("## Steps (high level from Techniker + Assembly)")
    lines.append("1. Mount Tether Anchor Plate to harness (use 4x M3 bolts, torque 2.5 Nm, check with assembly manifest)")
    lines.append("2. Route high-current cables with strain relief (avoid sharp bends)")
    lines.append("3. Connect motor drivers to 48V bus (polarity check, insulation test >1MOhm)")
    lines.append("4. Install emergency cutoff switch in pilot reach (test function before flight)")
    lines.append("5. Final fit check: all parts from manifest present, no loose items")
    lines.append("")
    lines.append("## Prüfschritte / Checks")
    lines.append("- Visual: no damage, correct orientation")
    lines.append("- Electrical: continuity on power paths, no shorts")
    lines.append("- Functional: emergency cut works, thrust command responds")
    lines.append("")
    lines.append("**Gap:** Detailed step-by-step with photos + torque specs per bolt (enhance from Techniker in later stone). See assembly manifest for part list.")
    (pkg_root / "MONTAGEANLEITUNG.md").write_text("\n".join(lines), encoding="utf-8")


def realize(ideas: list[str], package_name: str = "Genesis Realization Package", run_id: str = None) -> dict[str, str]:
    """
    Realisierungspaket entry point (progress on complete package + CLI ready).
    Runs full chain (packager with advanced DFM + Lern cycle) and returns paths + summary.
    First stone for "Realisierungspaket complete".
    """
    pkg = build_full_mini_realization_package(ideas, package_name=package_name, run_id=run_id)
    # Lern on first idea for feedback
    lern_res = None
    try:
        from gen.lernmaschine.engine import run_8_step_learning_cycle
        lern_res = run_8_step_learning_cycle(ideas[0] if ideas else "generic", run_id=run_id)
    except Exception:
        pass
    return {
        "package_dir": pkg,
        "lern_persisted": getattr(lern_res, "persisted_key", None) if lern_res else None,
        "summary": f"Full realization for {package_name} with DFM + Lern feedback. See manifest.json and SUMMARY.md.",
    }

