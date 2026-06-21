"""KiCad export + verification (Teil 2, Stein 6).

The KiCad NETLIST is the complete electrical interchange (every component, every
net, every pin connection) — importable into Pcbnew. The generator emits a valid
S-expression netlist; the verifier is the honesty gate — balanced parens, the
export header, EVERY declared component present (none silently dropped), and NO
node referencing an undeclared component (no dangling). A graphical .kicad_sch
with routed wires needs KiCad's symbol libraries and is a declared gap; the
schematic skeleton here is grid-placed (no all-at-origin overlap) and connects via
global labels. Verifiers must be NON-VACUOUS. Offline, deterministic.

Run:  pytest tests/test_kicad.py
"""

from __future__ import annotations


from gen.cad.kicad import to_kicad_netlist, verify_kicad_netlist
from gen.core.state import Net, Netlist
from gen.electronics import Component


def _parts():
    comps = [
        Component(id="U1", name="MCU", kind="mcu", v_nom=3.3, i_max=0.1,
                  p_max_dissip=0.5, footprint_mm=(10, 10, 1)),
        Component(id="R1", name="10k", kind="resistor", v_nom=0.0, i_max=0.01,
                  p_max_dissip=0.1, footprint_mm=(2, 1, 0.5)),
    ]
    nets = [Net(name="VCC", pins=["U1.VCC", "R1.1"]),
            Net(name="GND", pins=["U1.GND", "R1.2"])]
    return comps, Netlist(pins=[], nets=nets)


def test_kicad_netlist_is_valid_complete_and_verifies():
    """Tracer: the netlist is valid S-expr, carries every component and net, and the
    verifier passes its own output."""
    comps, nl = _parts()
    text = to_kicad_netlist(nl, comps)
    chk = verify_kicad_netlist(text, components=comps, netlist=nl)
    assert chk.ok, chk.issues
    assert "(export" in text and "(components" in text and "(nets" in text
    assert '(ref "U1")' in text and '(ref "R1")' in text      # all components, none dropped
    assert '(name "VCC")' in text and '(name "GND")' in text  # all nets


def test_netlist_verifier_catches_a_dangling_node():
    """A net referencing a component that was never declared is a dangling reference —
    the verifier must flag it (non-vacuous)."""
    comps, _ = _parts()                                          # U1, R1
    bad_nl = Netlist(pins=[], nets=[Net(name="VCC", pins=["U1.VCC", "U99.1"])])
    text = to_kicad_netlist(bad_nl, comps)
    chk = verify_kicad_netlist(text, components=comps, netlist=bad_nl)
    assert not chk.ok and any("dangling" in i.lower() and "U99" in i for i in chk.issues)


def test_netlist_verifier_catches_a_dropped_component():
    """A truncated netlist (the old stub's [:8] disease) must fail — every declared
    component has to appear."""
    comps, nl = _parts()                                         # U1, R1
    full = to_kicad_netlist(nl, comps)
    truncated = "\n".join(ln for ln in full.splitlines() if '(ref "R1") (value' not in ln)
    chk = verify_kicad_netlist(truncated, components=comps, netlist=nl)
    assert not chk.ok and any("R1" in i and ("dropped" in i.lower() or "missing" in i.lower())
                              for i in chk.issues)


def test_schematic_includes_all_components_grid_placed_and_verifies():
    """The schematic skeleton carries ALL components (the old stub dropped past 8) at
    DISTINCT grid positions (the old stub put them all at the origin)."""
    from gen.cad.kicad import to_kicad_schematic, verify_kicad_schematic

    comps = [Component(id=f"U{i}", name=f"part{i}", kind="mcu", v_nom=3.3, i_max=0.1,
                       p_max_dissip=0.5, footprint_mm=(5, 5, 1)) for i in range(10)]
    nl = Netlist(pins=[], nets=[Net(name="VCC", pins=[f"U{i}.1" for i in range(10)])])
    text = to_kicad_schematic(comps, nl)
    chk = verify_kicad_schematic(text, components=comps, netlist=nl)
    assert chk.ok, chk.issues
    assert chk.n_components == 10 and text.count("(symbol ") == 10   # all 10, not [:8]
    assert chk.n_nets == 1 and text.count("(global_label ") == 1     # connectivity present


def test_schematic_verifier_catches_overlap_and_truncation():
    """The hand-broken old-stub style (all at origin, only 2 of 3 components) must fail."""
    from gen.cad.kicad import verify_kicad_schematic

    comps = [Component(id=f"U{i}", name="p", kind="r", v_nom=0.0, i_max=0.0,
                       p_max_dissip=0.0, footprint_mm=(1, 1, 1)) for i in range(3)]
    bad = ('(kicad_sch (version 1) (generator "x")\n'
           '  (symbol (lib_id "Device:R") (at 0 0 0) (unit 1) (property "Reference" "U0" (at 0 0 0)))\n'
           '  (symbol (lib_id "Device:R") (at 0 0 0) (unit 1) (property "Reference" "U1" (at 0 0 0)))\n'
           ")")
    chk = verify_kicad_schematic(bad, components=comps)
    assert not chk.ok
    assert any("overlap" in i.lower() for i in chk.issues)          # all-at-origin caught
    assert any("U2" in i and "truncation" in i.lower() for i in chk.issues)  # dropped caught

    # overlap is POSITION-only: two DIFFERENT-kind symbols at the same (at) still overlap
    mixed = ('(kicad_sch (version 1) (generator "x")\n'
             '  (symbol (lib_id "Device:U") (at 0 0 0) (unit 1) (property "Reference" "U0" (at 0 0 0)))\n'
             '  (symbol (lib_id "Device:R") (at 0 0 0) (unit 1) (property "Reference" "U1" (at 0 0 0)))\n'
             ")")
    chk2 = verify_kicad_schematic(mixed, components=comps[:2])
    assert not chk2.ok and any("overlap" in i.lower() for i in chk2.issues)


def test_netlist_is_deterministic_and_escapes_strings():
    """Identical inputs give identical output; a quote in a value is escaped so the
    S-expression stays valid and still verifies."""
    comps = [Component(id="U1", name='a"b"c', kind="mcu", v_nom=0.0, i_max=0.0,
                       p_max_dissip=0.0, footprint_mm=(1, 1, 1))]
    nl = Netlist(pins=[], nets=[Net(name="N1", pins=["U1.A"])])
    a = to_kicad_netlist(nl, comps)
    b = to_kicad_netlist(nl, comps)
    assert a == b                                                  # deterministic
    assert '\\"' in a                                              # the value quote is escaped
    assert verify_kicad_netlist(a, components=comps, netlist=nl).ok  # still valid + complete


def test_netlist_uses_bare_integer_code_and_verifier_catches_floating_and_malformed():
    """KiCad .net needs a BARE integer net code (code 1), not (code "1"). And the
    verifier rejects a floating (0-node) net and a malformed pin reference."""
    comps, _ = _parts()
    text = to_kicad_netlist(Netlist(pins=[], nets=[Net(name="VCC", pins=["U1.A"])]), comps)
    assert "(code 1)" in text and '(code "1")' not in text          # bare integer

    bad = Netlist(pins=[], nets=[Net(name="FLOAT", pins=[]), Net(name="BAD", pins=["U1"])])
    chk = verify_kicad_netlist(to_kicad_netlist(bad, comps), components=comps, netlist=bad)
    assert not chk.ok
    assert any("floating" in i.lower() for i in chk.issues)        # 0-node net
    assert any("malformed" in i.lower() for i in chk.issues)       # "U1" has no .pin


def test_verifier_recovers_an_escaped_quote_in_a_ref():
    """A ref/value containing a quote is escaped in the text; the verifier's
    escape-aware extraction must recover it, not mis-flag it as dropped/dangling."""
    comps = [Component(id='U"1', name="x", kind="mcu", v_nom=0.0, i_max=0.0,
                       p_max_dissip=0.0, footprint_mm=(1, 1, 1))]
    nl = Netlist(pins=[], nets=[Net(name="N", pins=['U"1.A'])])
    chk = verify_kicad_netlist(to_kicad_netlist(nl, comps), components=comps, netlist=nl)
    assert chk.ok, chk.issues


# === .kicad_pcb placement export (Teil 2 Rest-Risiko: replaces the old (module ...) stub) ===

def _placement(ref, x, y, rot=(0.0, 0.0, 90.0)):
    from gen.electronics import PlacementHint
    return PlacementHint(ref_des=ref, pos_mm=(x, y, 0.0), rot_deg=rot)


def test_kicad_pcb_uses_footprint_keyword_zrotation_and_verifies():
    """The PCB export must use the v6+ (footprint ...) keyword (NOT KiCad-5 (module ...)),
    place every component by ref_des, and put ONLY the Z rotation in (at ...) — not the
    whole 3-tuple the old stub stringified into a broken S-expr."""
    from gen.cad.kicad import to_kicad_pcb, verify_kicad_pcb

    comps = [Component(id=f"U{i}", name=f"p{i}", kind="mcu", v_nom=3.3, i_max=0.1,
                       p_max_dissip=0.5, footprint_mm=(5, 5, 1), package=f"lib:fp{i}")
             for i in range(3)]
    placements = [_placement(f"U{i}", 10.0 * i, 5.0 * i) for i in range(3)]
    text = to_kicad_pcb(placements, comps)
    chk = verify_kicad_pcb(text, placements=placements)
    assert chk.ok, chk.issues
    assert text.lstrip().startswith("(kicad_pcb")
    assert "(footprint " in text and "(module " not in text     # modern keyword, not the old stub
    assert '(at 0 0 90)' in text                                 # z-rotation only, not a tuple
    assert '"F.Cu" signal' in text                               # typed layer stack
    for i in range(3):
        assert f'reference "U{i}"' in text                       # all placements present
        assert f'"lib:fp{i}"' in text                            # footprint resolved by ref_des


def test_kicad_pcb_verifier_catches_dropped_placement_and_malformed_at():
    """Non-vacuous: a truncated export (placement dropped — the old zip() tail-drop) and a
    leaked rotation tuple in (at ...) must both fail the verifier."""
    from gen.cad.kicad import to_kicad_pcb, verify_kicad_pcb

    comps = [Component(id="U1", name="p", kind="mcu", v_nom=0.0, i_max=0.0,
                       p_max_dissip=0.0, footprint_mm=(1, 1, 1))]
    placements = [_placement("U1", 1.0, 1.0), _placement("U2", 2.0, 2.0)]

    # both placements appear even though only U1 has a matching component (no positional drop)
    text = to_kicad_pcb(placements, comps)
    assert verify_kicad_pcb(text, placements=placements).ok
    assert 'reference "U2"' in text

    # a truncated pcb (U2 dropped) must fail
    chk = verify_kicad_pcb(to_kicad_pcb(placements[:1], comps), placements=placements)
    assert not chk.ok and any("U2" in i and "dropped" in i.lower() for i in chk.issues)

    # the old rot-tuple leak `(at 1 1 (0.0, 0.0, 90.0))` must be caught as malformed
    broken = ('(kicad_pcb (version 20231120) (layers (0 "F.Cu" signal)) '
              '(footprint "x" (at 1 1 (0.0, 0.0, 90.0)) (fp_text reference "U1")))')
    chk2 = verify_kicad_pcb(broken, placements=[_placement("U1", 1.0, 1.0)])
    assert not chk2.ok and any("malformed" in i.lower() for i in chk2.issues)


def test_export_placement_wrapper_gates_its_output():
    """The electronics wrapper delegates to cad.kicad AND gates: valid placements yield a
    verified .kicad_pcb (header + every ref present)."""
    from gen.electronics import export_placement_to_kicad_pcb

    comps = [Component(id="U1", name="MCU", kind="mcu", v_nom=3.3, i_max=0.1,
                       p_max_dissip=0.5, footprint_mm=(10, 10, 1), package="lib:U")]
    text = export_placement_to_kicad_pcb([_placement("U1", 1.0, 1.0)], comps)
    assert text.lstrip().startswith("(kicad_pcb") and 'reference "U1"' in text
    assert "(module " not in text
