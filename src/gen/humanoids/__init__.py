"""humanoids — import + honest validation of REAL open-source humanoid robots into GENESIS.

This package brings ~25 real open-source humanoids in as GROUND-TRUTH reference data and runs GENESIS's
own closed-form physics axes against their PUBLISHED specs — calibrating and proving GENESIS's humanoid
physics on real designs rather than only on its own generated robots. The original 7 in-house references
(TienKung, Berkeley Humanoid Lite, Asimov v1, AGILOped, Fourier N1, K-Scale K-Bot, InMoov) were joined
2026-06-24 by 18 more parsed from the local MuJoCo-Menagerie clone (Unitree G1/H1, Booster T1, Berkeley
Humanoid, Apptronik Apollo, PAL TALOS, PNDbotics Adam, ROBOTIS OP3, Agility Cassie, ToddlerBot) and the
robot_descriptions cache (Atlas v4, NASA Valkyrie, Fourier GR-1, Unitree H1-2, JVRC-1, Draco3, iCub,
ergoCub). Each new entry's mass / DOF / per-joint knee torque is PARSED from its model file (sourced),
never guessed; an unconfirmed value is an honest ``None``.

  * ``scaling_laws`` — humanoid DESIGN LAWS fitted from the fleet (knee torque ≈ k·m·g·leg), kept ONLY
    where they validate out-of-sample (leave-one-out), and used as priors to sanity-check a design
    (incl. AETHON). Mass-vs-height is honestly REJECTED (does not generalise). The discovery arm.

  * ``model_parser`` — stdlib-only structural parse of the downloaded URDF/MJCF (links, actuated DOF,
    total mass, inertials, mesh existence, units sanity). The in-environment validation that the
    imported models are real and well-formed (no pybullet/mujoco in this venv).
  * ``catalog`` — the verified, source-cited spec record for each robot (the facts the physics axes
    are checked against), and the local asset paths.
  * ``validation`` — drives GENESIS's kinematics/actuation/compute axes against each robot's specs and
    emits the honest agreement/gap table (closed-form vs published-spec).
  * ``insim`` — loads the real URDFs into a real physics engine (PyBullet, headless) and measures
    structure, pose statics (inverse-dynamics torque + CoM), a drop/stability test and a PD
    stand/balance demo. The in-ENGINE deliverable (needs PyBullet).
  * ``validation_insim`` — the honest GENESIS-closed-form-vs-PyBullet comparison ON the real models
    (mass, static joint torque, ZMP/balance), plus the engine-only dynamic-stability findings.
    Run:  ``python -m gen.humanoids.validation_insim``.

Deterministic, offline (assets pre-downloaded). Every spec carries its source; nothing is fabricated.
The closed-form path (catalog/validation) is numpy/scipy-only; the in-engine path (insim/
validation_insim) requires PyBullet and skips cleanly when it is absent. Models live OUTSIDE the repo
at /home/genesis/humanoid_assets/ (kept clear of the running crew campaign's git operations).
"""
