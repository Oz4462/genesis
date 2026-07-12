"""report — one-shot, reproducible printout of the drone import + δ-flight-validator calibration.

Run:  PYTHONPATH=src .venv/bin/python -m gen.aero.report

Prints, for every catalogued drone: the verified source + license + local asset status, then GENESIS's
δ-flight-axis vs published-spec agreement/gap table, the CALIBRATION FINDINGS (what GENESIS got wrong on
real shipping drones + the fix), and the discovered scaling laws (kept iff out-of-sample valid). Honest
by construction — gaps and inapplicable axes (fixed-wing) are printed as such; nothing is fabricated.

The 'model-independent vs published' note matters: the gym-pybullet-drones drones (Crazyflie, racer)
carry an EMPIRICALLY-FITTED thrust coefficient k_f, so their max-thrust is a real-dynamics ground truth
the momentum axis is checked against; the DJI/heavy drones' max-thrust is derived from a published MTOW
(a sourced bound), and consumer drones publish NO thrust/KV at all (honest gaps). The genuinely
independent calibration of the T/W gate is the spread of real shipping drones (M350 1.42× → Nazgul 9×).
"""

from __future__ import annotations

from .calibration import calibration_findings, format_table, validate_all
from .drone_catalog import ASSETS, SPECS, drones, model_native_drones
from .scaling_laws import summarise as scaling_summary


def main() -> None:
    print("=" * 92)
    print("GENESIS × REAL DRONES — acquisition + δ-FLIGHT validator calibration report")
    print("=" * 92)

    print(f"\n{len(drones())} drones catalogued ({len(model_native_drones())} with a machine-readable "
          f"URDF the model_parser validates); spanning nano → fpv → consumer → fixed-wing → heavy.")

    print("\n--- ACQUISITION / LICENSE / LOCAL ASSETS ---")
    for key in drones():
        spec, asset = SPECS[key], ASSETS[key]
        native = "URDF-native (real k_f dynamics)" if asset.model_path else "spec-only"
        print(f"\n{spec.name}  [class '{spec.klass}' | {native}]")
        print(f"  source:  {asset.source_url}")
        print(f"  license: {asset.license}  — {asset.license_note}")
        if asset.model_path:
            print(f"  model:   {asset.model_path}  ({asset.model_format})")
        print(f"  status:  {asset.status_note}")

    print("\n\n--- GENESIS δ-FLIGHT AXIS  vs  PUBLISHED SPEC  (agreement / gap) ---")
    print(format_table(validate_all()))

    print("\n\n--- CALIBRATION FINDINGS (where GENESIS was wrong on real drones + the fix) ---")
    print(calibration_findings())

    print("\n\n--- DISCOVERED DESIGN LAWS (fitted from the fleet, kept iff out-of-sample valid) ---")
    print(scaling_summary())

    print("\n\n--- HONESTY NOTE ---")
    print("  The gym-pybullet-drones drones (Crazyflie, racer) carry an empirically-fitted k_f, so their")
    print("  max-thrust is a real-dynamics ground truth. DJI/heavy max-thrust is MTOW·g (a sourced bound,")
    print("  not a measured thrust). Consumer makers publish NO motor KV / per-motor thrust / T/W → those")
    print("  are honest gaps (the rotor-hover axis reports a gap rather than inventing a thrust). Fixed-")
    print("  wing drones do not hover → the rotor-hover/momentum axis self-selects OFF (not a fake pass).")
    print("  These are GENESIS's CLOSED-FORM screens, not CFD or a flight sim: a passed check is")
    print("  necessary, not sufficient (the gen.flight honest-boundary note holds).")


if __name__ == "__main__":
    main()
