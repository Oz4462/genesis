"""aero — import + honest calibration of REAL drones into GENESIS's δ FLIGHT axes.

The flight analog of ``gen.humanoids``: it brings real, shipping drones in as GROUND-TRUTH reference
data and runs GENESIS's own closed-form δ-flight validators (``gen.flight``) against their PUBLISHED
specs — calibrating and proving (or correcting) GENESIS's flight physics on real designs rather than
only on its own generated vehicles.

  * ``drone_catalog`` — the verified, source-cited spec record for 15 real drones across the size
    spectrum (Crazyflie nano → 5" FPV → DJI consumer/cinematic → fixed-wing → heavy agricultural),
    each value carrying the source it was confirmed from (URDF dynamics file, manufacturer datasheet,
    or vendor thrust table). An unconfirmed value is an honest ``None``, never a guess. Two drones
    (Crazyflie, a generic 5" racer) carry the gym-pybullet-drones URDF's empirically-fitted thrust
    coefficient k_f, giving a SECOND, model-independent ground truth for the momentum-theory power.

  * ``calibration`` — drives GENESIS's δ-flight validators (rotor-hover/momentum-theory, battery
    endurance, ESC/C-rating current budget, PD-attitude) against each catalogued drone's specs and
    emits the honest agreement/gap table, plus the documented CALIBRATION FINDINGS where GENESIS over-
    or under-predicted on a real shipping drone and the formula was corrected against ground truth.

  * ``scaling_laws`` — drone DESIGN LAWS fitted from the fleet (hover-thrust vs mass, flight-time vs
    battery-Wh/mass, prop-diameter vs mass), kept ONLY where they validate OUT OF SAMPLE
    (leave-one-out), and reported with their honest verdict — a law that does not generalise is a
    valid negative result, not a stored prior.

Deterministic, offline (the gym-pybullet-drones URDFs are pre-cloned to /home/genesis/drone_data/;
the catalog hard-codes the parsed/published numbers so import needs no filesystem I/O). numpy only
for the scaling-law fits; the catalog + calibration are pure stdlib. Every spec carries its source;
nothing is fabricated. This is the flight analog of the humanoid-training task that grew the humanoid
catalog 7→25 and calibrated the leg-torque axis against real robots.
"""
