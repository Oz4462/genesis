"""Generate real montage step diagrams (PNG/SVG) — never stock photos.

Closes the "no step images" gap with **machine-generated** orthographic assembly
diagrams (boxes + labels + torque callouts) via PIL. These are not photographs;
they are honest engineering illustrations for the package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_step_png(
    step: dict[str, Any],
    *,
    width: int = 640,
    height: int = 400,
    out_path: str | Path | None = None,
) -> bytes:
    """Render one montage step as a PNG diagram (PIL)."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None

    n = step.get("n", 0)
    title = str(step.get("title") or f"Step {n}")
    action = str(step.get("action") or "")
    torque = step.get("torque_nm")
    fastener = step.get("fastener")

    # header bar
    draw.rectangle([0, 0, width, 48], fill=(15, 23, 42))
    draw.text((16, 14), f"Step {n}: {title}"[:70], fill=(226, 232, 240), font=font)

    # part block
    bx, by, bw, bh = 80, 90, 200, 140
    draw.rectangle([bx, by, bx + bw, by + bh], outline=(14, 165, 233), width=3)
    draw.rectangle(
        [bx + 8, by + 8, bx + bw - 8, by + bh - 8], outline=(100, 116, 139), width=1
    )
    part_name = str(step.get("part_name") or "assembly")
    draw.text((bx + 16, by + bh // 2 - 6), part_name[:24], fill=(15, 23, 42), font=font)

    # fastener callout
    if torque is not None:
        draw.ellipse([340, 120, 400, 180], outline=(245, 158, 11), width=3)
        draw.text(
            (410, 130),
            f"{fastener or 'M?'} @ {torque} Nm",
            fill=(15, 23, 42),
            font=font,
        )
        draw.line([400, 150, bx + bw, by + bh // 2], fill=(245, 158, 11), width=2)

    # action text
    draw.multiline_text(
        (40, 260),
        _wrap(action, 70),
        fill=(51, 65, 85),
        font=font,
        spacing=4,
    )
    # checks
    y = 320
    for c in (step.get("checks") or [])[:3]:
        draw.text((40, y), f"☐ {c}"[:80], fill=(71, 85, 105), font=font)
        y += 18

    draw.text(
        (16, height - 22),
        "GENESIS generated diagram (not a photograph)",
        fill=(148, 163, 184),
        font=font,
    )

    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(data)
    return data


def _wrap(text: str, width: int) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if len(trial) > width and cur:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)


def render_all_step_diagrams(
    steps: list[dict[str, Any]],
    images_dir: str | Path,
) -> list[dict[str, Any]]:
    """Write PNG for each step; return steps with ``image`` paths filled."""
    out_dir = Path(images_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    updated: list[dict[str, Any]] = []
    for s in steps:
        n = int(s.get("n") or 0)
        fname = f"step_{n:02d}.png"
        path = out_dir / fname
        render_step_png(s, out_path=path)
        u = dict(s)
        u["image"] = str(path.as_posix())
        u["image_kind"] = "generated_diagram"
        updated.append(u)
    return updated
