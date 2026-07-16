"""Load the vision/demo product catalog (audit B2).

Separates authored VISION narratives from ledger claims. Physics still gates
quantities; this module only exposes the catalog metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CATALOG = Path(__file__).resolve().parents[2] / "data" / "vision_catalog.yaml"


def vision_catalog_path() -> Path:
    return _CATALOG


def load_vision_catalog() -> dict[str, Any]:
    """Load ``data/vision_catalog.yaml``. Raises if missing (no silent empty catalog)."""
    if not _CATALOG.is_file():
        raise FileNotFoundError(f"vision catalog missing at {_CATALOG}")
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("load_vision_catalog requires PyYAML") from exc
    data = yaml.safe_load(_CATALOG.read_text(encoding="utf-8")) or {}
    if data.get("content_kind") != "vision_demo":
        raise ValueError("vision catalog must declare content_kind: vision_demo")
    return data


def list_vision_entry_ids() -> list[str]:
    """Flat list of all vision entry ids."""
    cat = load_vision_catalog()
    ids: list[str] = []
    for mod in cat.get("modules") or []:
        for e in mod.get("entries") or []:
            if e.get("id"):
                ids.append(str(e["id"]))
    return ids
