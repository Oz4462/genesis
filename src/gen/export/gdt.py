"""GD&T feature-control annotations + multi-sheet drawing PDF (residual L4 depth).

Honest scope
------------
* Feature-control **frames as TEXT blocks** on DXF (position / flatness / profile)
  using envelope dimensions from the OCCT section — never invented sizes.
* General tolerance note: ISO 2768-m (medium) as a **stated assumption** with
  explicit citation — not a certified drawing stamp.
* Multi-view drawing **PDF** via matplotlib (when available) or a minimal pure-PDF
  fallback. This is a machine package drawing, not a PE-stamped shop release.

Surface finish Ra callouts and title-block sign-off remain optional fields with
honest defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from ..core.errors import ExportError

#: ISO 2768-1:1989 general tolerances — medium (m) linear tolerances (mm),
#: simplified bands for overall envelope annotation (not full table lookup).
ISO_2768_M_SOURCE = (
    "ISO 2768-1:1989 General tolerances — Part 1: Tolerances for linear and "
    "angular dimensions without individual tolerance indications (class m medium)"
)


@dataclass(frozen=True)
class GdtFrame:
    """One feature-control frame (ISO 1101 style, simplified)."""

    characteristic: str  # e.g. "⟂", "⌖", "⏥", "⌀"
    tolerance_mm: float
    datum: str = "A"
    note: str = ""


def iso_2768_m_linear_tol_mm(nominal_mm: float) -> float:
    """Linear general tolerance (mm) for ISO 2768-m at a nominal size.

    Bands (simplified from ISO 2768-1 table for class m):
      0.5–3 → 0.1; 3–6 → 0.1; 6–30 → 0.2; 30–120 → 0.3; 120–400 → 0.5; 400–1000 → 0.8
    Raises on non-positive nominal.
    """
    if not (nominal_mm == nominal_mm) or nominal_mm <= 0:
        raise ValueError("iso_2768_m_linear_tol_mm: nominal_mm must be finite > 0")
    n = float(nominal_mm)
    if n <= 3:
        return 0.1
    if n <= 6:
        return 0.1
    if n <= 30:
        return 0.2
    if n <= 120:
        return 0.3
    if n <= 400:
        return 0.5
    if n <= 1000:
        return 0.8
    return 1.2


def default_gdt_frames(dx: float, dy: float) -> list[GdtFrame]:
    """Default frames for a rectangular envelope: position of outline + flatness."""
    t_pos = iso_2768_m_linear_tol_mm(max(dx, dy))
    t_flat = max(0.05, t_pos * 0.5)
    return [
        GdtFrame(
            characteristic="⌖",
            tolerance_mm=t_pos,
            datum="A",
            note="position of envelope outline (general)",
        ),
        GdtFrame(
            characteristic="⏥",
            tolerance_mm=t_flat,
            datum="A",
            note="flatness of primary face (assumption)",
        ),
    ]


def annotate_gdt_frames(
    dxf_text: str,
    *,
    dx: float,
    dy: float,
    frames: list[GdtFrame] | None = None,
    surface_finish_ra_um: float | None = 3.2,
) -> str:
    """Inject GD&T feature-control TEXT + general tolerance note into a DXF.

    Frames are drawn as multi-line TEXT near the upper-right of the envelope.
    Requires ezdxf. Never invents envelope size — caller supplies dx/dy from section.
    """
    try:
        import ezdxf
    except ImportError as exc:  # pragma: no cover
        raise ExportError("annotate_gdt_frames requires ezdxf") from exc

    if not (dx > 0 and dy > 0):
        raise ExportError(f"annotate_gdt_frames: positive envelope required, got {dx}x{dy}")

    frames = frames if frames is not None else default_gdt_frames(dx, dy)
    try:
        doc = ezdxf.read(StringIO(dxf_text))
    except Exception as exc:
        raise ExportError(f"annotate_gdt_frames: parse failed: {exc}") from exc

    msp = doc.modelspace()
    # place block to the right of part
    x0 = dx / 2.0 + max(8.0, dx * 0.15)
    y0 = dy / 2.0
    line_h = max(2.5, max(dx, dy) * 0.04)
    tol_note = (
        f"GENERAL TOL: ISO 2768-m | unless otherwise stated | {ISO_2768_M_SOURCE[:48]}…"
    )
    msp.add_text(
        tol_note,
        dxfattribs={"height": line_h * 0.7, "insert": (x0, y0 + line_h * 2)},
    )
    if surface_finish_ra_um is not None:
        msp.add_text(
            f"SURFACE: Ra {surface_finish_ra_um:g} µm (default mill; confirm drawing note)",
            dxfattribs={"height": line_h * 0.7, "insert": (x0, y0 + line_h)},
        )
    for i, fr in enumerate(frames):
        # simplified FCF text: | char | tol | DATUM |
        block = (
            f"| {fr.characteristic} | {fr.tolerance_mm:.3f} | {fr.datum} |"
            + (f"  ({fr.note})" if fr.note else "")
        )
        msp.add_text(
            block,
            dxfattribs={"height": line_h, "insert": (x0, y0 - i * line_h * 1.4)},
        )
    # datum triangle label on bottom-left
    msp.add_text(
        "DATUM A (primary seating face)",
        dxfattribs={
            "height": line_h * 0.65,
            "insert": (-dx / 2.0, -dy / 2.0 - line_h * 2.5),
        },
    )

    buf = StringIO()
    doc.write(buf)
    return buf.getvalue()


def render_drawing_pdf(
    views: dict[str, dict[str, Any]],
    *,
    title: str = "GENESIS manufacturing drawing",
    run_id: str | None = None,
    out_path: str | Path | None = None,
) -> bytes:
    """Multi-view drawing PDF (top/front/right + notes).

    ``views`` maps view name → {dx, dy, dims_text?, gdt_lines?}.
    Uses matplotlib PdfPages when available; else a minimal pure-PDF with text.
    """
    if not views:
        raise ValueError("render_drawing_pdf: views must be non-empty")

    try:
        return _pdf_matplotlib(views, title=title, run_id=run_id, out_path=out_path)
    except Exception:
        data = _pdf_minimal(views, title=title, run_id=run_id)
        if out_path is not None:
            Path(out_path).write_bytes(data)
        return data


def _pdf_matplotlib(
    views: dict[str, dict[str, Any]],
    *,
    title: str,
    run_id: str | None,
    out_path: str | Path | None,
) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    buf = BytesIO()
    path_or_buf: Any = str(out_path) if out_path else buf
    with PdfPages(path_or_buf) as pdf:
        # sheet 1: title + all view envelopes
        fig, axes = plt.subplots(1, min(3, len(views)), figsize=(11.69, 8.27))  # A4 landscape-ish
        if not hasattr(axes, "__iter__"):
            axes = [axes]
        fig.suptitle(f"{title}\nrun_id={run_id or 'n/a'} | ISO 2768-m general tol.", fontsize=11)
        for ax, (name, meta) in zip(axes, views.items()):
            dx = float(meta["dx"])
            dy = float(meta["dy"])
            ax.add_patch(
                plt.Rectangle((-dx / 2, -dy / 2), dx, dy, fill=False, linewidth=1.5)
            )
            ax.set_aspect("equal")
            ax.set_xlim(-dx * 0.7, dx * 0.7)
            ax.set_ylim(-dy * 0.7, dy * 0.7)
            ax.set_title(f"{name}  ({dx:.2f} × {dy:.2f} mm)")
            ax.set_xlabel("mm")
            ax.grid(True, alpha=0.3)
            tol = iso_2768_m_linear_tol_mm(max(dx, dy))
            ax.text(
                0.02,
                0.02,
                f"tol ±{tol} mm (2768-m)\nGD&T: position+flatness on DXF",
                transform=ax.transAxes,
                fontsize=7,
                va="bottom",
            )
        for ax in list(axes)[len(views) :]:
            ax.axis("off")
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # sheet 2: notes
        fig2, ax2 = plt.subplots(figsize=(11.69, 8.27))
        ax2.axis("off")
        notes = [
            f"Title: {title}",
            f"Run: {run_id or 'n/a'}",
            f"General tolerances: ISO 2768-m ({ISO_2768_M_SOURCE})",
            "GD&T frames: simplified ISO 1101 text FCFs on companion DXF (not PE stamped)",
            "Surface finish default Ra 3.2 µm unless otherwise stated",
            "This PDF is a GENESIS package drawing — confirm against certified CAD for release",
            "",
            "Views:",
        ]
        for name, meta in views.items():
            notes.append(
                f"  - {name}: {meta['dx']:.3f} x {meta['dy']:.3f} mm envelope"
            )
        ax2.text(0.05, 0.95, "\n".join(notes), va="top", family="monospace", fontsize=9)
        pdf.savefig(fig2)
        plt.close(fig2)

    if out_path:
        return Path(out_path).read_bytes()
    return buf.getvalue()


def _pdf_minimal(
    views: dict[str, dict[str, Any]],
    *,
    title: str,
    run_id: str | None,
) -> bytes:
    """Minimal single-page PDF (text only) without third-party deps beyond stdlib."""
    lines = [
        title,
        f"run_id: {run_id or 'n/a'}",
        f"General tol: ISO 2768-m — {ISO_2768_M_SOURCE}",
        "Views:",
    ]
    for name, meta in views.items():
        lines.append(f"  {name}: {meta['dx']:.3f} x {meta['dy']:.3f} mm")
    lines.append("GD&T: see companion DXF feature-control frames")
    content = "\n".join(lines)
    # Escape for PDF string
    esc = content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 50 750 Td 12 TL ({esc[:2000]}) Tj ET"
    # multi-line: simple approach — one Tj with newlines via T*
    parts = []
    for i, ln in enumerate(lines[:40]):
        e = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i == 0:
            parts.append(f"BT /F1 10 Tf 50 750 Td ({e}) Tj")
        else:
            parts.append(f"0 -14 Td ({e}) Tj")
    parts.append("ET")
    stream = "\n".join(parts)
    stream_b = stream.encode("latin-1", errors="replace")
    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream_b)} >>stream\n".encode("ascii")
        + stream_b
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


__all__ = [
    "GdtFrame",
    "ISO_2768_M_SOURCE",
    "iso_2768_m_linear_tol_mm",
    "default_gdt_frames",
    "annotate_gdt_frames",
    "render_drawing_pdf",
]
