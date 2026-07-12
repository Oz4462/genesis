"""report — one-shot, reproducible printout of the humanoid import + validation status.

Run:  PYTHONPATH=src .venv/bin/python -m gen.humanoids.report

Prints, for every catalogued robot: the verified source + license, the local asset status, the parsed
structural facts (where a model is present), and the GENESIS physics-axis vs published-spec agreement
table. Honest by construction — gaps and blockers are printed as such; nothing is fabricated.

The 'independent vs corroborating' note matters: where a robot's published mass/DOF was itself read
FROM the downloaded model (TienKung/Berkeley/Asimov), the structural 'agree' is corroboration that the
parse is self-consistent and engine-load-ready, NOT an independent confirmation of the vendor's number.
The genuinely independent calibration is the actuation axis on AGILOped (paper-sourced motor ratings,
no parsed model involved) and the closed-form ZMP/torque anchors.
"""

from __future__ import annotations

from .catalog import ASSETS, SPECS, robots
from .scaling_laws import summarise as scaling_summary
from .validation import format_table, validate_all


def main() -> None:
    print("=" * 90)
    print("GENESIS × REAL OPEN-SOURCE HUMANOIDS — acquisition + validation report")
    print("=" * 90)

    print("\n--- ACQUISITION / LICENSE / LOCAL ASSETS ---")
    for key in robots():
        spec, asset = SPECS[key], ASSETS[key]
        native = "URDF/MJCF-native" if asset.model_path else "spec-only / model-blocked"
        print(f"\n{spec.name}  [{native}]")
        print(f"  repo:    {asset.repo_url}")
        print(f"  license: {asset.license}  — {asset.license_note}")
        print(f"  local:   {asset.local_dir}")
        if asset.model_path:
            print(f"  model:   {asset.model_path}  ({asset.model_format})")
        print(f"  formats: {', '.join(asset.extra_formats) if asset.extra_formats else '—'}")
        print(f"  status:  {asset.status_note}")

    print("\n\n--- GENESIS PHYSICS-AXIS  vs  PUBLISHED SPEC  (agreement / gap) ---")
    print(format_table(validate_all()))

    print("\n\n--- DISCOVERED DESIGN LAWS (fitted from the fleet, kept iff out-of-sample valid) ---")
    print(scaling_summary())

    print("\n\n--- HONESTY NOTE ---")
    print("  TienKung/Berkeley/Asimov mass+DOF were read FROM the downloaded model, so their")
    print("  structural 'agree' is self-consistency + engine-load-readiness, not independent vendor")
    print("  confirmation. The independent calibration of GENESIS's physics is the AGILOped actuation")
    print("  axis (paper-sourced RMD-X6-40 ratings, no parsed model) and the closed-form ZMP/torque")
    print("  anchors. Compute axis is a gap for all: none of these open models publish onboard TOPS.")


if __name__ == "__main__":
    main()
