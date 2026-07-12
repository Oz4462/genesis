"""Real KiCad validation + export via the ``kicad-cli`` binary (Stein 6, made real).

``cad/kicad.py`` emits KiCad S-expression text and self-checks it with an internal
regex verifier. That proves OUR file is well-formed by OUR rules. THIS module closes
the loop with the ground truth: it runs the actual ``kicad-cli`` so KiCad's OWN
engine consumes the file. KiCad accepting a ``.kicad_pcb`` and emitting Gerbers /
STEP / SVG is a far stronger statement than a regex pass — it is the manufacturer's
toolchain validating the board.

What is REAL here (KiCad 7, ``kicad-cli 7.0.11``, verified on this box):
  * ``export_pcb`` — KiCad loads our ``.kicad_pcb`` and exports SVG / Gerbers / STEP.
    Success means KiCad genuinely parsed and rendered the board (real validation +
    real manufacturing output). Our ``cad.kicad.to_kicad_pcb`` output IS accepted.
  * ``export_netlist`` — KiCad loads a ``.kicad_sch`` and emits a netlist
    (kicadsexpr / spice / …). This is the real schematic-validation path.

HONEST LIMITATION (measured, not assumed): KiCad 7 REJECTS the minimal schematic
SKELETON from ``cad.kicad.to_kicad_schematic`` ("could not load schematic file") —
the skeleton omits ``lib_symbols``, per-symbol UUIDs and pin instances that KiCad's
loader requires (the skeleton's docstring already declares it is "NOT a guaranteed
drop-in import"). So ``export_netlist`` works on KiCad-authored schematics and is the
verification harness for them, but cannot yet validate our own skeleton; emitting a
KiCad-loadable schematic is the declared next step (see report). ERC/DRC are NOT in
KiCad 7's CLI (added in KiCad 8) — also declared, not faked.

Failure is LOUD and typed (``ToolError``): a missing binary, a non-zero exit, or —
critically — KiCad's CLI quirk of returning 0 while writing NO output and an error
message (we detect the missing/empty output and the error text, never reporting a
fabricated success).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import ToolError

#: The KiCad CLI binary; override with GENESIS_KICAD_CLI for a nonstandard install.
_DEFAULT_KICAD_CLI = "kicad-cli"

#: KiCad CLI sometimes prints these on a failed load while STILL exiting 0 — we treat
#: their presence (or a missing output file) as failure, never a fabricated success.
_ERROR_MARKERS = (
    "could not load",
    "konnte",            # German: "Konnte ... nicht laden"
    "nicht laden",
    "error",
    "failed",
)


def kicad_cli() -> str:
    """Resolve the kicad-cli binary path/name (env override else the default)."""
    return os.environ.get("GENESIS_KICAD_CLI", _DEFAULT_KICAD_CLI)


def kicad_cli_available() -> bool:
    """True iff the kicad-cli binary is found on PATH (skip-guard for callers/tests)."""
    return shutil.which(kicad_cli()) is not None


def kicad_version() -> str:
    """Return the kicad-cli version string. Raises ToolError if the binary is absent."""
    binary = kicad_cli()
    if shutil.which(binary) is None:
        raise ToolError("kicad-cli", f"binary {binary!r} not found on PATH")
    proc = subprocess.run([binary, "version"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolError("kicad-cli", f"`version` exited {proc.returncode}: {proc.stderr}")
    return proc.stdout.strip()


@dataclass(frozen=True)
class KiCadCliResult:
    """Outcome of a real kicad-cli invocation.

    ``ok``       KiCad genuinely produced the expected output.
    ``outputs``  paths of the files KiCad actually wrote (verified to exist & non-empty).
    ``detail``   KiCad's message (errors surfaced verbatim — no fabrication).
    ``command``  the exact argv, for reproducibility.
    """

    ok: bool
    outputs: list[str]
    detail: str
    command: list[str]


def _run_cli(args: list[str], *, expect: list[Path], timeout: float = 120.0) -> KiCadCliResult:
    """Run kicad-cli and verify it actually produced ``expect`` (non-empty files).

    Guards against KiCad's exit-0-but-no-output failure mode: success REQUIRES every
    expected path to exist and be non-empty AND no error marker in the output.
    Raises ToolError if the binary is missing or the subprocess cannot run.
    """
    binary = kicad_cli()
    if shutil.which(binary) is None:
        raise ToolError("kicad-cli", f"binary {binary!r} not found on PATH")
    argv = [binary, *args]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ToolError("kicad-cli", f"timed out after {timeout}s: {' '.join(argv)}") from exc
    except OSError as exc:
        raise ToolError("kicad-cli", f"could not run {argv!r}: {exc}") from exc

    combined = (proc.stdout + "\n" + proc.stderr).strip()
    produced = [p for p in expect if p.exists() and p.stat().st_size > 0]
    has_error_text = any(m in combined.lower() for m in _ERROR_MARKERS)

    ok = (
        proc.returncode == 0
        and len(produced) == len(expect)
        and not has_error_text
    )
    return KiCadCliResult(
        ok=ok,
        outputs=[str(p) for p in produced],
        detail=combined or f"exit={proc.returncode}",
        command=argv,
    )


def export_pcb(
    pcb_path: str | Path,
    out_dir: str | Path,
    *,
    fmt: str = "svg",
    layers: str = "F.Cu,B.Cu",
) -> KiCadCliResult:
    """Run KiCad's own engine over a ``.kicad_pcb`` to validate + export it.

    ``fmt``: ``"svg"`` (render), ``"gerbers"`` (manufacturing fab files), or
    ``"step"`` (3D). A successful result means KiCad PARSED and exported the board —
    real validation that the file from ``cad.kicad.to_kicad_pcb`` is a genuine,
    loadable KiCad board, plus real downstream artifacts. ``layers`` applies to
    svg/gerbers (KiCad requires at least one).

    Raises:
        ToolError: binary missing / subprocess failure / unsupported ``fmt``.
    """
    pcb_path = Path(pcb_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pcb_path.is_file():
        raise ToolError("kicad-cli", f"PCB file not found: {pcb_path}")

    if fmt == "svg":
        out = out_dir / (pcb_path.stem + ".svg")
        args = ["pcb", "export", "svg", "--layers", layers, "-o", str(out), str(pcb_path)]
        expect = [out]
    elif fmt == "step":
        out = out_dir / (pcb_path.stem + ".step")
        args = ["pcb", "export", "step", "--force", "-o", str(out), str(pcb_path)]
        expect = [out]
    elif fmt == "gerbers":
        # gerbers writes multiple files into the dir; require the job file as proof.
        args = ["pcb", "export", "gerbers", "--layers", layers, "-o",
                str(out_dir) + "/", str(pcb_path)]
        expect = [out_dir / (pcb_path.stem + "-job.gbrjob")]
    else:
        raise ToolError("kicad-cli", f"unsupported pcb export format {fmt!r} "
                                     "(use svg / gerbers / step)")
    return _run_cli(args, expect=expect)


def export_netlist(
    sch_path: str | Path,
    out_path: str | Path,
    *,
    fmt: str = "kicadsexpr",
) -> KiCadCliResult:
    """Run KiCad's engine over a ``.kicad_sch`` to emit a netlist — the real
    schematic-validation path.

    ``fmt`` is a kicad-cli netlist format (``kicadsexpr``, ``spice``, ``kicadxml``,
    ``orcadpcb2``, …). A successful result means KiCad LOADED and traced the
    schematic. NOTE: KiCad 7 rejects the minimal skeleton from
    ``cad.kicad.to_kicad_schematic`` (see module docstring) — this works on
    KiCad-authored schematics and is the verification harness for them.

    Raises:
        ToolError: binary missing / subprocess failure.
    """
    sch_path = Path(sch_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not sch_path.is_file():
        raise ToolError("kicad-cli", f"schematic file not found: {sch_path}")
    args = ["sch", "export", "netlist", "--format", fmt, "-o", str(out_path), str(sch_path)]
    return _run_cli(args, expect=[out_path])


__all__ = [
    "kicad_cli",
    "kicad_cli_available",
    "kicad_version",
    "KiCadCliResult",
    "export_pcb",
    "export_netlist",
]
