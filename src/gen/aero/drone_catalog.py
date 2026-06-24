"""drone_catalog — the verified, source-cited reference record for each real drone.

The flight analog of ``gen.humanoids.catalog``. This is the GROUND TRUTH that GENESIS's δ-FLIGHT axes
(``gen.flight``) are calibrated against. Every number carries the source it was confirmed from (a
gym-pybullet-drones URDF dynamics file, a manufacturer datasheet/spec page, a vendor thrust table, or
an official prop part designation), following the project rule: no factual value without a source.
Where a spec could not be confirmed it is an honest ``None`` (a real gap), never a guess — consumer
manufacturers in particular do NOT publish motor KV / per-motor thrust / thrust-to-weight, so those
are ``None`` for the DJI/Autel fleet, on purpose.

Two kinds of fact, kept distinct (mirrors the humanoid catalog):
  * ``DroneSpec`` — the PUBLISHED / parsed design figures, each field a ``Cited(value, source)``.
  * ``DroneAsset`` — the LOCAL provenance: for the gym-pybullet-drones models, the URDF path actually
    on disk; for the published-spec drones, the spec/datasheet URL (no local model — an honest state).

A note on ``max_total_thrust_n`` (the input ``flight.rotor_hover_check`` needs but consumer drones do
not advertise): it is populated ONLY when it is genuinely sourced —
  * gym-pybullet-drones drones: ``thrust2weight × weight`` from the URDF's empirically-fitted k_f
    (a real-dynamics number, see ``model_parser``);
  * drones with a published max-gross-takeoff-weight (heavy/agri/cinema): MTOW·g is the airframe's
    own stated lift limit, a sound and sourced upper bound on total thrust;
  * FPV builds with a vendor motor thrust table: n_rotors × per-motor max thrust.
For consumer drones with none of these it is an honest ``None``, and the rotor-hover gate reports a gap
rather than inventing a thrust. This honesty is exactly what surfaces the calibration finding (the
T/W≥2 screen is right for thrust-limited drones but mis-classifies efficient cinematic drones that hover
far below half throttle — see ``calibration``).

Offline, deterministic, pure stdlib, no I/O at import (paths are strings). The gym-pybullet-drones
clone lives OUTSIDE the repo at /home/genesis/drone_data/ to stay clear of the crew campaign's git ops.

Sources legend used in citations:
  URDF      = gym-pybullet-drones <properties> in the named .urdf (MIT, github.com/utiasDSL/gym-pybullet-drones)
  datasheet = the manufacturer's official datasheet/spec page (URL in the asset record)
  prop-pn   = the official propeller part-number designation (e.g. DJI 9455S, 5328S) → diameter
  thrust-tbl= a vendor's published static-thrust test table (T-Motor/iFlight/BetaFPV)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: gym-pybullet-drones clone root (pre-downloaded; MIT).
DRONE_DATA_ROOT = "/home/genesis/drone_data/gym-pybullet-drones"
_URDF_DIR = f"{DRONE_DATA_ROOT}/gym_pybullet_drones/assets"


@dataclass(frozen=True)
class Cited:
    """A single value with the source it was verified from (mirrors humanoids.catalog.Cited)."""
    value: float | int | str | None
    source: str

    def __repr__(self) -> str:
        return f"{self.value!r}⟨{self.source}⟩"

    @property
    def known(self) -> bool:
        """True iff this field carries a real numeric/string value (not an honest gap)."""
        return self.value is not None


@dataclass(frozen=True)
class DroneSpec:
    """Published/parsed design figures for one drone, each field sourced. ``None`` = unconfirmed gap.

    Units are SI-ish-as-published and converted by the calibration layer: mass in kg, prop diameter in
    m, battery capacity in Wh AND mAh (both where known — Wh feeds endurance, mAh×C feeds current),
    voltage in V, flight time in min. ``max_total_thrust_n`` is populated only when genuinely sourced
    (see module docstring)."""
    key: str
    name: str
    maker: str
    klass: str                          #: "nano" | "fpv" | "consumer" | "cinematic" | "fixed_wing" | "heavy"
    n_rotors: Cited
    mass_kg: Cited                      #: all-up / takeoff mass (ready to fly, with battery)
    prop_diameter_m: Cited
    battery_cells: Cited                #: LiPo "S" count (or None where chemistry/topology differs)
    battery_voltage_v: Cited            #: nominal pack voltage
    battery_capacity_mah: Cited
    battery_wh: Cited
    max_flight_time_min: Cited          #: published max flight time (note hover vs forward in source)
    primary_source: str
    # ── the dynamics-grade fields (often gaps for consumer drones — honest None) ──
    max_total_thrust_n: Cited | None = None   #: total max thrust [N] (only when sourced; see docstring)
    motor_kv: Cited | None = None             #: motor KV (rev/min per volt) — usually FPV-only
    per_motor_max_thrust_n: Cited | None = None  #: per-rotor max static thrust [N] (vendor table)
    thrust2weight: Cited | None = None        #: published max T/W (gym-pybullet / FPV builds)
    # ── fixed-wing extras (None for multirotors) ──
    wingspan_m: Cited | None = None
    wing_area_m2: Cited | None = None
    notes: str = ""


@dataclass(frozen=True)
class DroneAsset:
    """Local provenance for one drone: the on-disk URDF (gym-pybullet-drones) or the spec/datasheet URL."""
    key: str
    source_url: str
    license: str
    license_note: str
    model_path: str | None              #: local URDF the model_parser can read; None = spec-only
    model_format: str | None            #: "urdf" | None
    status_note: str = ""


# Standard gravity for the catalog's own derived helpers (CGPM); the gym-pybullet ground truth uses the
# simulator's 9.8 internally (model_parser.SIM_GRAVITY) — both documented where they matter.
_G = 9.80665


# ── Published / parsed specs (each value sourced) ─────────────────────────────────────────────────

SPECS: dict[str, DroneSpec] = {

    # ============================ NANO (gym-pybullet-drones URDF, real k_f dynamics) ===============
    "crazyflie2x": DroneSpec(
        key="crazyflie2x", name="Crazyflie 2.x (cf2x)", maker="Bitcraze", klass="nano",
        n_rotors=Cited(4, "URDF cf2x.urdf (4 prop links)"),
        mass_kg=Cited(0.027, "URDF cf2x.urdf base_link <mass>=0.027 kg (= the CF2.0 figure the sim uses; "
                             "the CF2.1 datasheet Rev3 lists 29 g takeoff weight — see notes)"),
        prop_diameter_m=Cited(0.0462696, "URDF cf2x.urdf prop_radius=2.31348e-2 m → 46.27 mm dia "
                                         "(the CF's 45 mm-class prop)"),
        battery_cells=Cited(1, "Bitcraze CF2.1 datasheet Rev3: single-cell LiPo"),
        battery_voltage_v=Cited(3.7, "1S LiPo nominal (Bitcraze CF2.1 datasheet Rev3, 250 mAh LiPo)"),
        battery_capacity_mah=Cited(250.0, "Bitcraze CF2.1 datasheet Rev3 §10: '1 x 250mAh LiPo battery'"),
        battery_wh=Cited(0.925, "250 mAh × 3.7 V = 0.925 Wh (derived from datasheet capacity+voltage)"),
        max_flight_time_min=Cited(7.0, "Bitcraze CF2.1 datasheet Rev3 §5: 'Flight time with stock battery: 7 minutes'"),
        primary_source="github.com/utiasDSL/gym-pybullet-drones cf2x.urdf + Bitcraze CF2.1 datasheet Rev3",
        max_total_thrust_n=Cited(0.595354, "URDF cf2x.urdf: thrust2weight(2.25)×weight(9.8×0.027) per "
                                           "BaseAviary derived MAX_THRUST = 4·k_f·MAX_RPM²"),
        thrust2weight=Cited(2.25, "URDF cf2x.urdf <properties thrust2weight=2.25>"),
        notes="THE research nano-quad (gym-pybullet-drones / many papers). 7 mm coreless DC motors. The "
              "URDF mass (27 g, CF2.0) vs datasheet 29 g (CF2.1) differ by 2 g of hardware revision; both "
              "are recorded with their source. k_f=3.16e-10, k_m=7.94e-12 are EMPIRICALLY FITTED (arXiv "
              "1608.05786, Förster ETH thesis) — the model-independent thrust ground truth.",
    ),
    "gpd_racer": DroneSpec(
        key="gpd_racer", name="gym-pybullet-drones 'racer' (generic 5\")", maker="utiasDSL (sim model)",
        klass="fpv",
        n_rotors=Cited(4, "URDF racer.urdf (4 prop links)"),
        mass_kg=Cited(0.830, "URDF racer.urdf base_link <mass>=0.830 kg"),
        prop_diameter_m=Cited(0.254, "URDF racer.urdf prop_radius=12.7e-2 m → 254 mm = 10\" dia "
                                     "(the sim's scaled 'racer'; note real 5\" FPV props are 127 mm — "
                                     "this model uses a larger disk, recorded as-is)"),
        battery_cells=Cited(None, "the sim racer URDF carries no battery spec"),
        battery_voltage_v=Cited(None, "not in URDF"),
        battery_capacity_mah=Cited(None, "not in URDF"),
        battery_wh=Cited(None, "not in URDF"),
        max_flight_time_min=Cited(None, "not in URDF (dynamics-only model)"),
        primary_source="github.com/utiasDSL/gym-pybullet-drones racer.urdf",
        max_total_thrust_n=Cited(33.9188, "URDF racer.urdf: thrust2weight(4.17)×weight(9.8×0.830) per "
                                          "BaseAviary derived MAX_THRUST"),
        thrust2weight=Cited(4.17, "URDF racer.urdf <properties thrust2weight=4.17>"),
        notes="A generic agile-quad dynamics model in gym-pybullet-drones (k_f=8.47e-9, k_m=2.13e-11). "
              "Carries a real fitted thrust coefficient → second model-grade ground truth for the "
              "hover/momentum axes alongside the Crazyflie. NOT a shipping product (a sim airframe).",
    ),

    # ============================ FPV FREESTYLE (real shipping product, vendor specs) ===============
    "iflight_nazgul5_v3": DroneSpec(
        key="iflight_nazgul5_v3", name="iFlight Nazgul5 V3 (6S)", maker="iFlight", klass="fpv",
        n_rotors=Cited(4, "iFlight Nazgul5 V3 (5\" freestyle quad)"),
        mass_kg=Cited(0.660, "iFlight/GetFPV Nazgul5 V3 6S: ~660 g AUW with a 6S 1400 mAh pack "
                             "(435 g dry without battery)"),
        prop_diameter_m=Cited(0.127, "iFlight Nazgul5 V3: 5\" tri-blade props → 127 mm"),
        battery_cells=Cited(6, "iFlight Nazgul5 V3 6S edition (22.2 V LiPo)"),
        battery_voltage_v=Cited(22.2, "6S LiPo nominal (iFlight Nazgul5 V3 6S)"),
        battery_capacity_mah=Cited(1400.0, "iFlight/GetFPV Nazgul5 V3 6S recommended 1400 mAh 6S pack"),
        battery_wh=Cited(31.08, "1400 mAh × 22.2 V = 31.08 Wh (derived from the recommended pack)"),
        max_flight_time_min=Cited(None, "freestyle flight time is throttle-dependent (no single hover "
                                        "spec published) — honest gap"),
        primary_source="getfpv.com/iflight-nazgul5-v3-analog-5-fpv-freestyle-bnf-6s.html + shop.iflight.com "
                       "(XING2 2207 datasheet TEST REPORT, read from the manufacturer image)",
        max_total_thrust_n=Cited(56.32, "4 × iFlight XING2 2207 (1855KV-class) per-motor max 1436 gf on an "
                                        "HQ 5140 (5×4×3) prop at 6S, read from iFlight's datasheet TEST "
                                        "REPORT image → 4×1.436 kgf×g ≈ 56.3 N total (the 51466 prop gives "
                                        "1685 gf/motor → 66.1 N; HQ5140 is the conservative shipping prop)"),
        motor_kv=Cited(1800.0, "iFlight XING-E Pro 2207 1800KV (the Nazgul5 V3 6S motor; the closely-"
                              "matched XING2 2207 datasheet is 1855KV)"),
        per_motor_max_thrust_n=Cited(14.08, "iFlight XING2 2207 1855KV: 1436 gf max on HQ 5140 at 6S "
                                            "(100 % throttle, 33.53 A) — verified from the iFlight "
                                            "datasheet TEST REPORT image (51466 prop: 1685 gf)"),
        thrust2weight=Cited(8.7, "≈56.3 N max thrust / (0.660 kg × g = 6.47 N) ≈ 8.7× (typical 5\" "
                                "freestyle 8:1–14:1; the 51466-prop figure gives ~10×)"),
        notes="THE canonical 5\" freestyle quad (XING-E Pro 2207 1800KV, BLITZ F7). A real shipping FPV "
              "product anchoring the 'fpv' class floor (T/W≈9× — far above the universal 2.0, the over-"
              "lax end of the calibration finding). Per-motor thrust is from iFlight's XING2 2207 datasheet "
              "TEST REPORT (read from the manufacturer image): 1436 gf on HQ 5140, 1685 gf on Gemfan 51466 "
              "at 6S full throttle — the HQ5140 (conservative) value is used for max_total_thrust.",
    ),

    # ============================ CONSUMER (DJI/Autel official spec pages) ==========================
    # Motor KV / per-motor thrust / T/W are NOT published by consumer makers → honest None throughout.
    "dji_mini4pro": DroneSpec(
        key="dji_mini4pro", name="DJI Mini 4 Pro", maker="DJI", klass="consumer",
        n_rotors=Cited(4, "quadcopter by design (airframe; not stated numerically on spec page)"),
        mass_kg=Cited(0.249, "DJI Mini 4 Pro specs: takeoff weight < 249 g (standard battery)"),
        prop_diameter_m=Cited(None, "DJI does not publish Mini 4 Pro prop diameter"),
        battery_cells=Cited(2, "DJI specs: 7.32 V nominal ⇒ 2S Li-ion"),
        battery_voltage_v=Cited(7.32, "DJI Mini 4 Pro specs: 7.32 V nominal (standard Intelligent Flight Battery)"),
        battery_capacity_mah=Cited(2590.0, "DJI Mini 4 Pro specs: 2590 mAh standard battery"),
        battery_wh=Cited(18.96, "DJI Mini 4 Pro specs: 18.96 Wh standard battery"),
        max_flight_time_min=Cited(34.0, "DJI Mini 4 Pro specs: max 34 min (forward flight); 30 min max hover"),
        primary_source="dji.com/mini-4-pro/specs",
        notes="Sub-249 g class (regulatory). 30 min HOVER per DJI — the figure the endurance axis should "
              "use for a hover screen (34 min is forward flight). Props/KV/thrust not published.",
    ),
    "dji_air3": DroneSpec(
        key="dji_air3", name="DJI Air 3", maker="DJI", klass="consumer",
        n_rotors=Cited(4, "quadcopter by design"),
        mass_kg=Cited(0.720, "DJI Air 3 specs: takeoff weight 720 g"),
        prop_diameter_m=Cited(0.2210, "DJI Air 3 low-noise prop part spec 8.7×4.7 in → 221 mm dia (prop-pn)"),
        battery_cells=Cited(4, "DJI Air 3 specs: 14.76 V nominal ⇒ 4S"),
        battery_voltage_v=Cited(14.76, "DJI Air 3 specs: 14.76 V nominal"),
        battery_capacity_mah=Cited(4241.0, "DJI Air 3 specs: 4241 mAh"),
        battery_wh=Cited(62.6, "DJI Air 3 specs: 62.6 Wh"),
        max_flight_time_min=Cited(46.0, "DJI Air 3 specs: max 46 min (forward @28.8 km/h); 42 min max hover"),
        primary_source="dji.com/air-3/specs",
        notes="42 min HOVER per DJI (verified against the official spec page). Mid-size folding consumer.",
    ),
    "dji_mavic3classic": DroneSpec(
        key="dji_mavic3classic", name="DJI Mavic 3 Classic", maker="DJI", klass="consumer",
        n_rotors=Cited(4, "quadcopter by design"),
        mass_kg=Cited(0.895, "DJI Mavic 3 Classic specs: takeoff weight 895 g"),
        prop_diameter_m=Cited(None, "DJI does not publish a numeric Mavic 3 prop diameter (A/B mount only)"),
        battery_cells=Cited(4, "DJI Mavic 3-series battery: 14.76 V nominal ⇒ 4S"),
        battery_voltage_v=Cited(14.76, "DJI Mavic 3-series battery spec (retailer mirror of DJI): 14.76 V nominal"),
        battery_capacity_mah=Cited(5000.0, "DJI Mavic 3 Classic specs: 5000 mAh"),
        battery_wh=Cited(77.0, "DJI Mavic 3 Classic specs: 77 Wh"),
        max_flight_time_min=Cited(46.0, "DJI Mavic 3 Classic specs: max 46 min; 40 min max hover"),
        primary_source="dji.com/mavic-3-classic/specs",
        notes="40 min HOVER per DJI. Nominal voltage is from a reputable retailer mirror of the DJI sheet "
              "(DJI's English page omits it) — flagged in the source.",
    ),
    "dji_phantom4pro_v2": DroneSpec(
        key="dji_phantom4pro_v2", name="DJI Phantom 4 Pro V2.0", maker="DJI", klass="consumer",
        n_rotors=Cited(4, "quadcopter by design"),
        mass_kg=Cited(1.375, "DJI Phantom 4 Pro V2.0 specs: 1375 g (incl. battery + props)"),
        prop_diameter_m=Cited(0.2388, "DJI 9455S prop = 9.4 in dia → 238.8 mm (prop-pn, official propulsion)"),
        battery_cells=Cited(4, "DJI PH4-5870mAh-15.2V battery ⇒ 4S (15.2 V)"),
        battery_voltage_v=Cited(15.2, "DJI Phantom 4 Pro V2.0 Intelligent Flight Battery: 15.2 V"),
        battery_capacity_mah=Cited(5870.0, "DJI Phantom 4 Pro V2.0 specs: 5870 mAh"),
        battery_wh=Cited(89.2, "DJI Phantom 4 Pro V2.0 specs: 89.2 Wh"),
        max_flight_time_min=Cited(30.0, "DJI Phantom 4 Pro V2.0 specs: ~30 min"),
        primary_source="dji.com/phantom-4-pro-v2/specs",
        notes="Classic prosumer fixed-arm quad. 9455S props are an official DJI designation → real prop dia.",
    ),
    "autel_evolite_plus": DroneSpec(
        key="autel_evolite_plus", name="Autel EVO Lite+", maker="Autel Robotics", klass="consumer",
        n_rotors=Cited(4, "quadcopter by design"),
        mass_kg=Cited(0.835, "Autel EVO Lite+ aircraft specs: 835 g"),
        prop_diameter_m=Cited(None, "Autel does not publish EVO Lite+ prop diameter"),
        battery_cells=Cited(3, "Autel EVO Lite battery: 11.13 V nominal ⇒ 3S"),
        battery_voltage_v=Cited(11.13, "Autel EVO Lite battery spec: 11.13 V nominal (12.75 V max)"),
        battery_capacity_mah=Cited(6175.0, "Autel EVO Lite battery spec: 6175 mAh"),
        battery_wh=Cited(68.7, "Autel EVO Lite battery: 11.13 V × 6175 mAh = 68.7 Wh (Autel spec, cross-checks)"),
        max_flight_time_min=Cited(40.0, "Autel EVO Lite+ specs: max 40 min; 38 min max hover"),
        primary_source="shop.autelrobotics.com/pages/evo-lite-series-specifications-aircraft",
        notes="3S pack is unusual for this class (most are 4S) — a useful spread point. 38 min HOVER.",
    ),

    # ============================ FPV / CINEMATIC (DJI official + prop part numbers) ================
    "dji_fpv": DroneSpec(
        key="dji_fpv", name="DJI FPV (2021)", maker="DJI", klass="fpv",
        n_rotors=Cited(4, "quadcopter by design"),
        mass_kg=Cited(0.795, "DJI FPV specs: ~795 g"),
        prop_diameter_m=Cited(0.1346, "DJI 5328S prop = 5.3 in dia → 134.6 mm (prop-pn, tri-blade)"),
        battery_cells=Cited(6, "DJI FPV specs: 22.2 V nominal ⇒ 6S"),
        battery_voltage_v=Cited(22.2, "DJI FPV specs: 22.2 V nominal"),
        battery_capacity_mah=Cited(2000.0, "DJI FPV specs: 2000 mAh"),
        battery_wh=Cited(44.4, "DJI FPV specs: 44.4 Wh (at 0.5C)"),
        max_flight_time_min=Cited(20.0, "DJI FPV specs: ~20 min (forward @40 km/h); ~16 min max hover"),
        primary_source="dji.com/support/product/dji-fpv",
        notes="DJI's 2021 hybrid FPV/consumer drone. 6S, 5.3\" tri-blade. ~16 min HOVER — a high-power "
              "design (the endurance gap vs the 720 g consumer Air 3's 42 min is a real efficiency signal).",
    ),
    "dji_avata2": DroneSpec(
        key="dji_avata2", name="DJI Avata 2", maker="DJI", klass="cinematic",
        n_rotors=Cited(4, "quadcopter by design (ducted cinewhoop)"),
        mass_kg=Cited(0.377, "DJI Avata 2 specs: ~377 g"),
        prop_diameter_m=Cited(0.07566, "DJI 3032S prop = 75.66 mm dia (prop-pn, official Avata 2 props)"),
        battery_cells=Cited(4, "DJI Avata 2 specs: 14.76 V nominal ⇒ 4S"),
        battery_voltage_v=Cited(14.76, "DJI Avata 2 specs: 14.76 V nominal (17 V max charge)"),
        battery_capacity_mah=Cited(2150.0, "DJI Avata 2 specs: 2150 mAh"),
        battery_wh=Cited(31.7, "DJI Avata 2 specs: 31.7 Wh (at 0.5C)"),
        max_flight_time_min=Cited(23.0, "DJI Avata 2 specs: ~23 min (forward @21.6 km/h); ~21 min max hover"),
        primary_source="dji.com/avata-2/specs",
        notes="Ducted cinewhoop (prop-guarded). Small 3\" props at 4S. 21 min HOVER. Ducts add static "
              "thrust real builders exploit — momentum theory (open rotor) is a lower bound here.",
    ),

    # ============================ FIXED-WING (no rotor-hover applicability — boundary case) =========
    "sensefly_ebee_x": DroneSpec(
        key="sensefly_ebee_x", name="senseFly eBee X", maker="senseFly (AgEagle)", klass="fixed_wing",
        n_rotors=Cited(1, "single rear pusher brushless motor (fixed-wing; 'rotor count' = motor count)"),
        mass_kg=Cited(1.6, "senseFly eBee X specs: MTOW ~1.6 kg (incl. camera + battery)"),
        prop_diameter_m=Cited(None, "eBee X pusher prop diameter not published"),
        battery_cells=Cited(None, "eBee X battery cells/Wh not on public spec page"),
        battery_voltage_v=Cited(None, "not published"),
        battery_capacity_mah=Cited(None, "not published"),
        battery_wh=Cited(None, "not published (standard vs endurance battery referenced, no capacity)"),
        max_flight_time_min=Cited(90.0, "senseFly eBee X specs: up to 90 min (endurance battery + S.O.D.A.)"),
        primary_source="sensefly.com/drones/ebee-x",
        wingspan_m=Cited(1.16, "senseFly eBee X specs: 116 cm wingspan"),
        wing_area_m2=Cited(None, "eBee X wing area not published"),
        notes="A fixed-wing mapping UAV: it does NOT hover, so rotor-hover/momentum theory does NOT apply "
              "(its lift is the wing). Included as the BOUNDARY case proving the flight axes self-select "
              "off where they are physically invalid. Cruise 11–30 m/s.",
    ),
    "skywalker_x8": DroneSpec(
        key="skywalker_x8", name="Skywalker X8", maker="Skywalker Technology (kit)", klass="fixed_wing",
        n_rotors=Cited(1, "single electric pusher (typical build; flying wing)"),
        mass_kg=Cited(1.72, "UAVMODEL Skywalker X8 product page: PNP weight 1.72 kg (empty 1.22 kg; "
                            "vendor structural MTOW 6 kg)"),
        prop_diameter_m=Cited(None, "kit — no standardized prop"),
        battery_cells=Cited(None, "kit — builder-dependent"),
        battery_voltage_v=Cited(None, "builder-dependent"),
        battery_capacity_mah=Cited(None, "builder-dependent"),
        battery_wh=Cited(None, "builder-dependent"),
        max_flight_time_min=Cited(None, "vendor '120 min' claim is config-dependent/optimistic — not "
                                        "recorded as a fact"),
        primary_source="uavmodel.com/products/skywalker-x8-2122mm-uav-fixed-wing",
        wingspan_m=Cited(2.12, "UAVMODEL Skywalker X8: 2120 mm wingspan"),
        wing_area_m2=Cited(0.80, "UAVMODEL Skywalker X8: wing area 80 dm² = 0.80 m²"),
        notes="Popular flying-wing FPV/UAV platform (a kit, so propulsion/battery are builder-specific → "
              "honest gaps). Fixed-wing: rotor-hover N/A. Wing area IS published → a wing-loading point.",
    ),

    # ============================ HEAVY / AGRICULTURAL / CINEMA (MTOW → sourced max thrust) =========
    "freefly_alta_x": DroneSpec(
        key="freefly_alta_x", name="Freefly Alta X", maker="Freefly Systems", klass="heavy",
        n_rotors=Cited(4, "Freefly Alta X specs: 4 motors"),
        mass_kg=Cited(10.86, "Freefly Alta X specs: empty/standard weight 10.86 kg (23.94 lb)"),
        prop_diameter_m=Cited(0.840, "Freefly Alta X specs: 33×9 in props → 840 mm dia"),
        battery_cells=Cited(12, "Freefly Alta X specs: 44.4 V nominal ⇒ 12S, two packs"),
        battery_voltage_v=Cited(44.4, "Freefly Alta X specs: 44.4 V nominal"),
        battery_capacity_mah=Cited(16000.0, "Freefly Alta X specs: 16 Ah-class pack (×2), 20C"),
        battery_wh=Cited(1420.8, "44.4 V × 16 Ah = 710.4 Wh/pack × 2 packs = 1420.8 Wh (derived)"),
        max_flight_time_min=Cited(None, "Freefly does not publish a single flight time (payload-dependent)"),
        primary_source="freeflysystems.com/alta-x/specs",
        max_total_thrust_n=Cited(341.91, "MTOW 34.86 kg × g — the airframe's own stated max-gross lift "
                                         "limit (Freefly spec) is a sound sourced bound on total thrust"),
        notes="Heavy-lift cinema quad. MTOW 34.86 kg (empty 10.86, payload 15.06). 33\" low-disk-loading "
              "props, 100 A/motor. MTOW·g gives a SOURCED max thrust → a real heavy-end hover anchor. "
              "T/W at empty weight is very high (≈3.2); the binding case is loaded.",
    ),
    "dji_matrice350": DroneSpec(
        key="dji_matrice350", name="DJI Matrice 350 RTK", maker="DJI", klass="heavy",
        n_rotors=Cited(4, "DJI M350 RTK: quadcopter frame"),
        mass_kg=Cited(6.47, "DJI Matrice 350 RTK specs: ~6.47 kg with 2× TB65 batteries"),
        prop_diameter_m=Cited(0.5334, "DJI 2110s prop = 21 in class → 533.4 mm (model-number designation)"),
        battery_cells=Cited(12, "DJI TB65 battery: 44.76 V ⇒ 12S; two used"),
        battery_voltage_v=Cited(44.76, "DJI TB65 spec: 44.76 V"),
        battery_capacity_mah=Cited(5880.0, "DJI TB65 spec: 5880 mAh (per battery; 2 used)"),
        battery_wh=Cited(526.4, "DJI TB65: 263.2 Wh/battery × 2 = 526.4 Wh (DJI spec)"),
        max_flight_time_min=Cited(55.0, "DJI M350 RTK specs: max 55 min (no payload, ~8 m/s, windless)"),
        primary_source="enterprise.dji.com/matrice-350-rtk/specs",
        max_total_thrust_n=Cited(90.24, "MTOW 9.2 kg × g — DJI's stated max takeoff weight (spec) as the "
                                        "sourced bound on total thrust"),
        notes="Industrial survey/inspection quad. MTOW 9.2 kg (empty ~3.77, with 2×TB65 ~6.47). 21\" props. "
              "55 min is no-payload forward; loaded hover is shorter. MTOW·g = sourced max thrust. MASS "
              "BASIS for T/W: the operating mass is the 6.47 kg battery-loaded weight (DJI), giving T/W = "
              "90.24 N / 63.5 N = 1.42 — and fully loaded to its 9.2 kg MTOW the airframe runs T/W ≈ 1.0. "
              "EITHER basis is well below the universal 2.0 floor: this is the false-fail finding, robust "
              "to the mass baseline. It is the calibration's headline case.",
    ),
    "dji_agras_t40": DroneSpec(
        key="dji_agras_t40", name="DJI Agras T40", maker="DJI", klass="heavy",
        n_rotors=Cited(8, "DJI Agras T40 specs: 8 rotors (coaxial twin-rotor on 4 arms)"),
        mass_kg=Cited(38.0, "DJI Agras T40: ~38 kg unladen (widely cited; DJI lists 90 kg MTOW spraying — "
                            "the empty figure is less cleanly primary-sourced, flagged)"),
        prop_diameter_m=Cited(1.3716, "DJI Agras T40 specs: 54 in props → 1371.6 mm dia"),
        battery_cells=Cited(14, "DJI BAX601 battery: 52.22 V ⇒ ~14S (52.22/3.7≈14.1)"),
        battery_voltage_v=Cited(52.22, "DJI BAX601 spec: 52.22 V"),
        battery_capacity_mah=Cited(30000.0, "DJI BAX601 spec: 30000 mAh"),
        battery_wh=Cited(1566.6, "DJI BAX601: 52.22 V × 30 Ah = 1566.6 Wh (derived from spec)"),
        max_flight_time_min=Cited(None, "agricultural sprayers are rated by area/coverage, not a single "
                                        "hover-time figure — honest gap"),
        primary_source="DJI Agras T40 spec (drdrone.com mirror of the DJI sheet)",
        max_total_thrust_n=Cited(882.6, "MTOW 90 kg (spraying) × g — DJI's stated max takeoff weight as "
                                        "the sourced bound on total thrust"),
        notes="The agricultural extreme: 8 coaxial rotors, 54\" props, 90 kg MTOW (101 kg spreading), 40 L "
              "tank. Coaxial pairs lose ~15-20 % vs isolated rotors (a real momentum-theory caveat the "
              "single-disk screen does not model — noted, not silently wrong).",
    ),
}


# ── Local asset / license provenance ──────────────────────────────────────────────────────────────

ASSETS: dict[str, DroneAsset] = {
    "crazyflie2x": DroneAsset(
        key="crazyflie2x", source_url="github.com/utiasDSL/gym-pybullet-drones (cf2x.urdf)",
        license="MIT", license_note="permissive — usable incl. commercially (© 2020 Jacopo Panerati)",
        model_path=f"{_URDF_DIR}/cf2x.urdf", model_format="urdf",
        status_note="URDF-native with empirically-fitted k_f/k_m dynamics; the model_parser reproduces "
                    "the simulator's MAX_THRUST/HOVER_RPM exactly. Datasheet facts (battery/flight time) "
                    "from Bitcraze CF2.1 datasheet Rev3.",
    ),
    "gpd_racer": DroneAsset(
        key="gpd_racer", source_url="github.com/utiasDSL/gym-pybullet-drones (racer.urdf)",
        license="MIT", license_note="permissive (© 2020 Jacopo Panerati)",
        model_path=f"{_URDF_DIR}/racer.urdf", model_format="urdf",
        status_note="URDF-native dynamics model (not a shipping product). Real fitted k_f → ground truth.",
    ),
    "dji_mini4pro": DroneAsset(
        key="dji_mini4pro", source_url="dji.com/mini-4-pro/specs", license="proprietary (spec data only)",
        license_note="specs cited for reference/calibration; no DJI software/firmware used",
        model_path=None, model_format=None,
        status_note="spec-only (no public CAD/URDF). Props/KV/thrust not published by DJI → honest gaps.",
    ),
    "dji_air3": DroneAsset(
        key="dji_air3", source_url="dji.com/air-3/specs", license="proprietary (spec data only)",
        license_note="specs cited for reference/calibration", model_path=None, model_format=None,
        status_note="spec-only; key fields independently re-verified against the live DJI spec page.",
    ),
    "dji_mavic3classic": DroneAsset(
        key="dji_mavic3classic", source_url="dji.com/mavic-3-classic/specs",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; nominal voltage via a reputable retailer mirror of the DJI sheet.",
    ),
    "dji_phantom4pro_v2": DroneAsset(
        key="dji_phantom4pro_v2", source_url="dji.com/phantom-4-pro-v2/specs",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; 9455S prop part number gives a real prop diameter.",
    ),
    "autel_evolite_plus": DroneAsset(
        key="autel_evolite_plus",
        source_url="shop.autelrobotics.com/pages/evo-lite-series-specifications-aircraft",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None, status_note="spec-only; 3S pack (unusual) — useful spread.",
    ),
    "iflight_nazgul5_v3": DroneAsset(
        key="iflight_nazgul5_v3",
        source_url="getfpv.com/iflight-nazgul5-v3-analog-5-fpv-freestyle-bnf-6s.html",
        license="vendor spec", license_note="vendor product-page + iFlight motor specs cited for reference",
        model_path=None, model_format=None,
        status_note="spec-only; real shipping 5\" freestyle quad with a published motor (XING-E 2207 "
                    "1800KV) and vendor thrust data → a sourced max-thrust → the fpv-class hover anchor.",
    ),
    "dji_fpv": DroneAsset(
        key="dji_fpv", source_url="dji.com/support/product/dji-fpv",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None, status_note="spec-only; 5328S prop part number → real dia.",
    ),
    "dji_avata2": DroneAsset(
        key="dji_avata2", source_url="dji.com/avata-2/specs",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; ducted (cinewhoop) — momentum theory is a lower bound on its static thrust.",
    ),
    "sensefly_ebee_x": DroneAsset(
        key="sensefly_ebee_x", source_url="sensefly.com/drones/ebee-x",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; FIXED-WING boundary case (does not hover).",
    ),
    "skywalker_x8": DroneAsset(
        key="skywalker_x8", source_url="uavmodel.com/products/skywalker-x8-2122mm-uav-fixed-wing",
        license="vendor spec (kit)", license_note="vendor product-page specs cited for reference",
        model_path=None, model_format=None,
        status_note="spec-only; kit (propulsion/battery builder-specific → gaps). Fixed-wing.",
    ),
    "freefly_alta_x": DroneAsset(
        key="freefly_alta_x", source_url="freeflysystems.com/alta-x/specs",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; MTOW·g gives a sourced max thrust — a heavy-lift hover anchor.",
    ),
    "dji_matrice350": DroneAsset(
        key="dji_matrice350", source_url="enterprise.dji.com/matrice-350-rtk/specs",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None, status_note="spec-only; MTOW·g = sourced max thrust.",
    ),
    "dji_agras_t40": DroneAsset(
        key="dji_agras_t40", source_url="DJI Agras T40 spec (drdrone.com mirror of DJI sheet)",
        license="proprietary (spec data only)", license_note="specs cited for reference/calibration",
        model_path=None, model_format=None,
        status_note="spec-only; 8 coaxial rotors (coaxial-loss caveat noted). MTOW·g = sourced max thrust.",
    ),
}


# ── Ordering + accessors (mirror humanoids.catalog) ───────────────────────────────────────────────

_NANO = ["crazyflie2x"]
_FPV = ["gpd_racer", "iflight_nazgul5_v3", "dji_fpv", "dji_avata2"]
_CONSUMER = ["dji_mini4pro", "dji_air3", "dji_mavic3classic", "dji_phantom4pro_v2", "autel_evolite_plus"]
_FIXED_WING = ["sensefly_ebee_x", "skywalker_x8"]
_HEAVY = ["freefly_alta_x", "dji_matrice350", "dji_agras_t40"]


def drones() -> list[str]:
    """Every catalogued drone key, grouped nano → fpv → consumer → fixed-wing → heavy."""
    return [*_NANO, *_FPV, *_CONSUMER, *_FIXED_WING, *_HEAVY]


def model_native_drones() -> list[str]:
    """Keys whose downloaded asset has a machine-readable URDF the model_parser can validate."""
    return [k for k in drones() if ASSETS[k].model_path is not None]


def multirotors() -> list[str]:
    """Keys that actually HOVER (multirotor) — the drones the rotor-hover/momentum axis applies to.
    Excludes fixed-wing, whose lift is the wing (rotor-hover is physically invalid there)."""
    return [k for k in drones() if SPECS[k].klass != "fixed_wing"]


def hover_thrust_demand_n(key: str) -> float | None:
    """The per-vehicle hover thrust the whole craft must produce = m·g [N], from the sourced mass.

    Returns ``None`` for a drone with no confirmed mass. This is the demand the rotor-hover screen
    compares the (sourced) ``max_total_thrust`` against; computed with the CGPM g used across GENESIS."""
    m = SPECS[key].mass_kg.value
    return _G * float(m) if isinstance(m, (int, float)) else None
