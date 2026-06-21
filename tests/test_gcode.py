"""G-code generation + verification (Teil 2, Stein 5).

"Real G-code" must be VALID and VERIFIED, not a prose stub. The generator emits a
2.5D outside-profile program (RS-274 / ISO 6983) for a rectangular footprint with
an explicit tool-radius offset and stepdown passes; the verifier is the honesty
gate — it parses the program and proves units/absolute set before motion, spindle
on before the first cut and off at the end, every coordinate within bounds, no
rapid through material, and the target depth reached. The verifier must be
NON-VACUOUS: a hand-broken program fails. Offline, deterministic.

Run:  pytest tests/test_gcode.py
"""

from __future__ import annotations

import pytest

from gen.cad.gcode import GCodeProgram, generate_profile_gcode, verify_gcode


def test_generated_profile_gcode_is_valid_safe_and_bounded():
    """Tracer: a generated profile program verifies clean — valid RS-274, spindle
    safety, bounded toolpath, and it reaches the target depth."""
    prog = generate_profile_gcode(120.0, 80.0, 6.0)        # 120x80 plate, 6 mm deep
    assert isinstance(prog, GCodeProgram)
    chk = verify_gcode(prog)
    assert chk.ok, chk.issues                              # the generator's own output is valid
    text = prog.text()
    assert "G21" in text and "G90" in text                 # metric + absolute
    assert "M3" in text and "M5" in text and "M30" in text  # spindle on/off + program end
    assert prog.bounds_mm["z"][0] <= -6.0 + 1e-9           # reaches the target depth
    assert prog.assumptions and prog.gaps                  # feeds/speeds + CAM scope stated


def test_verifier_is_non_vacuous_catches_a_gouge():
    """A rapid (G0) lateral move while the tool is below the stock top is a gouge —
    the verifier must flag it, else it is a rubber stamp."""
    bad = ["G21", "G90", "M3 S1000",
           "G1 Z-2 F100",        # plunge into material
           "G0 X50 Y50",         # RAPID laterally while in material -> gouge
           "M5", "M30"]
    chk = verify_gcode(bad)
    assert not chk.ok and any("gouge" in i.lower() for i in chk.issues)


def test_verifier_catches_missing_spindle_and_motion_before_setup():
    """Cutting without a started spindle, and motion before G21/G90, must both fail."""
    no_spindle = ["G21", "G90", "G1 Z-1 F100", "G1 X10 Y0 F300", "M30"]
    chk1 = verify_gcode(no_spindle)
    assert not chk1.ok and any("spindle" in i.lower() for i in chk1.issues)

    before_setup = ["M3 S1000", "G1 Z-1 F100", "G21", "G90", "M5", "M30"]
    chk2 = verify_gcode(before_setup)
    assert not chk2.ok and any("before G21/G90" in i for i in chk2.issues)


def test_generated_path_offsets_outward_and_respects_the_envelope():
    """The outside-profile path is offset outward by the tool radius, so a part-only
    envelope rejects it and a part+tool envelope accepts it."""
    from gen.cad.gcode import GCODE_DEFAULT_TOOL_DIAMETER_MM

    prog = generate_profile_gcode(100.0, 50.0, 3.0, tool_diameter_mm=4.0)
    assert prog.bounds_mm["x"][1] == 100.0 + 2.0          # width + radius (4/2)
    tight = {"x": (0.0, 100.0), "y": (0.0, 50.0), "z": (-3.0, 5.0)}
    assert not verify_gcode(prog, envelope_mm=tight).ok    # outward offset overruns
    roomy = {"x": (-2.0, 102.0), "y": (-2.0, 52.0), "z": (-3.0, 5.0)}
    assert verify_gcode(prog, envelope_mm=roomy).ok

    # determinism + a default-tool sanity on the radius offset
    a = generate_profile_gcode(60.0, 40.0, 2.0)
    b = generate_profile_gcode(60.0, 40.0, 2.0)
    assert a.lines == b.lines
    assert a.bounds_mm["x"][1] == 60.0 + GCODE_DEFAULT_TOOL_DIAMETER_MM / 2.0


def test_generate_profile_fails_loud_on_bad_dimensions():
    """A non-positive / non-finite dimension yields no honest program — refuse."""
    for bad in [(0.0, 50.0, 3.0), (100.0, 0.0, 3.0), (100.0, 50.0, 0.0),
                (float("nan"), 50.0, 3.0), (float("inf"), 50.0, 3.0)]:
        with pytest.raises(ValueError):
            generate_profile_gcode(*bad)
    # feeds and spindle speed are guarded >= 1 (a 0 or sub-1 feed would emit F0/S0)
    for kw in [{"cut_feed_mm_min": 0.0}, {"plunge_feed_mm_min": -10.0},
               {"spindle_rpm": 0}, {"cut_feed_mm_min": 0.5}]:
        with pytest.raises(ValueError):
            generate_profile_gcode(60.0, 40.0, 2.0, **kw)


def test_verifier_catches_missing_feed_no_retract_and_rapid_plunge():
    """The hardened verifier rejects a cut with no feed rate, a program that ends in
    the material (no retract), a rapid plunge into material, and a spindle without
    a speed — each a real machinist red flag."""
    no_feed = ["G21", "G90", "M3 S1000", "G1 Z-1", "G1 X10 Y0", "G0 Z5", "M5", "M30"]
    assert any("feed rate" in i.lower() for i in verify_gcode(no_feed).issues)

    no_retract = ["G21", "G90", "M3 S1000", "G1 Z-2 F100", "G1 X10 Y0 F300", "M5", "M30"]
    assert any("material" in i.lower() for i in verify_gcode(no_retract).issues)

    rapid_plunge = ["G21", "G90", "M3 S1000", "G0 Z-3", "G1 X10 Y0 F300", "G0 Z5", "M5", "M30"]
    assert any("gouge" in i.lower() for i in verify_gcode(rapid_plunge).issues)

    no_speed = ["G21", "G90", "M3", "G1 Z-1 F100", "G0 Z5", "M5", "M30"]
    assert any("speed" in i.lower() for i in verify_gcode(no_speed).issues)

    # a cut AFTER the spindle is stopped (M5) must be caught (spindle_on cleared on M5)
    cut_after_stop = ["G21", "G90", "M3 S1000", "G1 Z-1 F100", "G0 Z5", "M5",
                      "G1 X10 Y0 F300", "M30"]
    assert any("spindle" in i.lower() for i in verify_gcode(cut_after_stop).issues)
