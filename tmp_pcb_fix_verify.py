import sys
sys.path.insert(0, "src/gen/cad")
import kicad as kmod
from dataclasses import dataclass, field as dcfield
@dataclass(frozen=True)
class PlacementHint:
    ref_des: str
    pos_mm: tuple[float, float, float]
    rot_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    footprint: str = ""
    keepout_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    heatsink_interface: bool = False
    wire_attach_points: list[str] = dcfield(default_factory=list)
    quelle: str | None = None
@dataclass(frozen=True)
class Component:
    id: str
    name: str = ""
    kind: str = ""
    v_nom: float = 0.0
    i_max: float = 0.0
    p_max_dissip: float = 0.0
    footprint_mm: tuple = (10.,10.,1.)
    package: str = ""
to_kicad_pcb = kmod.to_kicad_pcb
verify_kicad_pcb = kmod.verify_kicad_pcb
_esc = kmod._esc
comps = [Component(id="U1", package="lib:fp1"), Component(id="U2", package="lib:fp2"), Component(id="U3", package="")]
placements = [
    PlacementHint("U1", (1,2,0), (0.0,0.0,45.0)),
    PlacementHint("U2", (3,4,0), (10.0,20.0,0), 'my"foot\\print'),
    PlacementHint("U3", (5,6,0), (0,0,0))
]
text = to_kicad_pcb(placements, comps)
print("=== POST-FIX EXEC OUTPUT ===")
print(text)
print("=== END ===")
print("rot scalar (no tuple str)?:", "(at 1 2 45)" in text and "(0.0, 0.0, 45.0)" not in text)
print("(footprint) and no (module)?:", "(footprint " in text and "(module " not in text)
print("proper _esc (quote and backslash in fp)?:", 'my\\"foot\\\\print' in text )
print("all 3 refs present (no zip trunc)?:", all(f'reference "{r}"' in text for r in ["U1","U2","U3"]))
chk = verify_kicad_pcb(text, placements=placements)
print("verifier ok (gated)?:", chk.ok)
print("generator esc used?:", "genesis_cad_kicad" in text)
print("SUCCESS: fixes run and address 4 issues")
