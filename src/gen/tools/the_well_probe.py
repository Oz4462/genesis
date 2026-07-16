"""The Well probe — stream-only access to PolymathicAI physics simulation datasets.

``The Well`` is a ~15 TB multi-dataset collection
(https://github.com/PolymathicAI/the_well). GENESIS never bulk-downloads it.

This probe:
  * lists known datasets with honest size notes (catalog, offline)
  * optionally streams **at most** a few batches from Hugging Face
    (``hf://datasets/polymathic-ai/…``) when ``the_well`` is installed
  * refuses non-stream / bulk paths (hard policy for laptop storage)
  * fails loud with install/network gaps — never fabricates simulation tensors

Optional dependency: ``pip install the_well`` (in a venv). Absent package →
``status=unavailable`` with install guidance.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

#: Official HF collection base used by The Well loaders.
WELL_HF_BASE = "hf://datasets/polymathic-ai/"

#: Hard caps — laptop storage policy (never train on full Well here).
MAX_PROBE_BATCHES = 3
DEFAULT_PROBE_BATCHES = 1

#: Curated catalog (metadata only). Sizes are approximate public ranges;
#: always re-check HF before any intentional local download.
# Source: Polymathic README — datasets range ~6.9 GB–5.1 TB each, ~15 TB total.
WELL_DATASET_CATALOG: dict[str, dict[str, Any]] = {
    "active_matter": {
        "domain": "active / soft matter",
        "laptop_hint": "preferred probe target (often among smaller sets)",
        "hf_dataset": "polymathic-ai/active_matter",
        "approx_size_note": "check HF card before local download; prefer stream",
    },
    "turbulent_radiative_layer_2D": {
        "domain": "fluid / radiative",
        "laptop_hint": "may be large — stream only",
        "hf_dataset": "polymathic-ai/turbulent_radiative_layer_2D",
        "approx_size_note": "check HF card; do not bulk-download on laptop",
    },
    "shear_flow": {
        "domain": "fluid dynamics",
        "laptop_hint": "stream only unless size verified << free disk",
        "hf_dataset": "polymathic-ai/shear_flow",
        "approx_size_note": "check HF card before local download",
    },
    "gray_scott": {
        "domain": "reaction–diffusion",
        "laptop_hint": "often used as compact PDE benchmark — still stream first",
        "hf_dataset": "polymathic-ai/gray_scott",
        "approx_size_note": "check HF card before local download",
    },
    "acoustic_scattering": {
        "domain": "acoustics",
        "laptop_hint": "stream only",
        "hf_dataset": "polymathic-ai/acoustic_scattering",
        "approx_size_note": "check HF card before local download",
    },
}


@dataclass(frozen=True)
class WellProbeResult:
    """Honest outcome of a The Well probe (never fabricates tensors)."""

    status: str  # ok | unavailable | error | catalog
    dataset: str
    split: str
    stream: bool
    max_batches: int
    batches_seen: int
    package_available: bool
    sample_summary: dict[str, Any] = field(default_factory=dict)
    gaps: tuple[str, ...] = ()
    quelle: str = (
        "gen.tools.the_well_probe + PolymathicAI/the_well "
        "(https://github.com/PolymathicAI/the_well)"
    )
    disk_policy: str = (
        "stream-only; max_batches≤3; no the-well-download without explicit "
        "operator opt-in outside GENESIS; refuse full 15TB collection"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def the_well_package_available() -> bool:
    """True iff the optional ``the_well`` package imports."""
    try:
        import the_well
        return True
    except ImportError:
        return False


def list_well_catalog() -> dict[str, dict[str, Any]]:
    """Offline catalog of known datasets (no network, no package required)."""
    return {k: dict(v) for k, v in WELL_DATASET_CATALOG.items()}


def format_catalog() -> str:
    """Human-readable catalog for CLI."""
    lines = [
        "GENESIS — The Well probe (stream-only, storage-safe)",
        "",
        "Collection: ~15TB across ~16 physics simulation datasets",
        "Policy: NEVER bulk-download; stream ≤3 batches or metadata catalog only",
        f"Package the_well installed: {the_well_package_available()}",
        "",
        "Known probe targets (metadata; verify size on HF before any local copy):",
    ]
    for name, meta in sorted(WELL_DATASET_CATALOG.items()):
        lines.append(f"  · {name}")
        lines.append(f"      domain: {meta['domain']}")
        lines.append(f"      hint:   {meta['laptop_hint']}")
        lines.append(f"      hf:     {meta['hf_dataset']}")
    lines += [
        "",
        "Usage:",
        "  python -m gen --mode well-probe --demo          # catalog only",
        "  python -m gen --mode well-probe active_matter   # stream 1 batch if package present",
        "  export HF_HOME=/tmp/hf_cache_well               # keep HF cache off main disk",
        "",
        "Install (venv only — do not system-pip):",
        "  python -m venv ~/venvs/the_well && source ~/venvs/the_well/bin/activate",
        "  pip install the_well",
        "",
        "Full collection download is FORBIDDEN in GENESIS tooling.",
    ]
    return "\n".join(lines)


def _summarize_batch(batch: Any) -> dict[str, Any]:
    """Extract shape/type summary from a batch without storing the tensor payload."""
    summary: dict[str, Any] = {"type": type(batch).__name__}
    if isinstance(batch, dict):
        keys = list(batch.keys())
        summary["keys"] = keys[:32]
        shapes: dict[str, str] = {}
        for k in keys[:16]:
            v = batch[k]
            shape = getattr(v, "shape", None)
            if shape is not None:
                shapes[str(k)] = str(tuple(shape))
            else:
                shapes[str(k)] = type(v).__name__
        summary["shapes"] = shapes
    elif hasattr(batch, "shape"):
        summary["shape"] = str(tuple(batch.shape))
    return summary


def probe_well_dataset(
    dataset_name: str = "active_matter",
    *,
    split: str = "train",
    max_batches: int = DEFAULT_PROBE_BATCHES,
    stream: bool = True,
    base_path: str | None = None,
) -> WellProbeResult:
    """Probe one Well dataset with a hard stream/batch cap.

    Parameters
    ----------
    dataset_name:
        Catalog key (e.g. ``active_matter``).
    split:
        Usually ``train`` / ``valid`` / ``test``.
    max_batches:
        Number of DataLoader batches to pull (capped at ``MAX_PROBE_BATCHES``).
    stream:
        Must be True. GENESIS refuses non-stream bulk paths.
    base_path:
        Override data root. Default is HF streaming base.
    """
    name = (dataset_name or "active_matter").strip()
    max_batches = max(1, min(int(max_batches), MAX_PROBE_BATCHES))

    if not stream:
        return WellProbeResult(
            status="error",
            dataset=name,
            split=split,
            stream=False,
            max_batches=max_batches,
            batches_seen=0,
            package_available=the_well_package_available(),
            gaps=(
                "stream=False refused: GENESIS The Well probe is stream-only "
                "(laptop storage policy; collection is ~15TB)",
            ),
        )

    # CI / offline operator path: explicit fixture — never real tensors, never bulk data.
    if os.environ.get("GENESIS_WELL_FIXTURE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return WellProbeResult(
            status="fixture",
            dataset=name,
            split=split,
            stream=True,
            max_batches=max_batches,
            batches_seen=0,
            package_available=the_well_package_available(),
            sample_summary={
                "fixture": True,
                "note": (
                    "CI/offline fixture — NOT real The Well simulation data; "
                    "no tensors loaded; catalog metadata only"
                ),
                "catalog": WELL_DATASET_CATALOG.get(name, {}),
                "hf_base": WELL_HF_BASE,
            },
            gaps=(
                "fixture mode (GENESIS_WELL_FIXTURE=1): zero batches, zero fabricated physics",
                "for real samples: install the_well in a venv and unset GENESIS_WELL_FIXTURE",
            ),
        )

    if name not in WELL_DATASET_CATALOG and base_path is None:
        # Still allow unknown names if package can resolve them, but flag gap
        catalog_gap = (
            f"dataset {name!r} not in GENESIS offline catalog "
            f"(known: {', '.join(sorted(WELL_DATASET_CATALOG))}); "
            "will try package resolution if available"
        )
    else:
        catalog_gap = None

    if not the_well_package_available():
        gaps = [
            "optional package 'the_well' not installed",
            "install in a venv: pip install the_well",
            "then re-run: python -m gen --mode well-probe active_matter",
            "until then: catalog metadata only (no tensors)",
        ]
        if catalog_gap:
            gaps.insert(0, catalog_gap)
        return WellProbeResult(
            status="unavailable",
            dataset=name,
            split=split,
            stream=True,
            max_batches=max_batches,
            batches_seen=0,
            package_available=False,
            sample_summary={
                "catalog": WELL_DATASET_CATALOG.get(name, {}),
                "hf_base": WELL_HF_BASE,
            },
            gaps=tuple(gaps),
        )

    # Package present — stream at most max_batches
    try:
        from the_well.data import WellDataset  # type: ignore[import-untyped]
        from torch.utils.data import DataLoader
    except ImportError as exc:
        return WellProbeResult(
            status="unavailable",
            dataset=name,
            split=split,
            stream=True,
            max_batches=max_batches,
            batches_seen=0,
            package_available=True,
            gaps=(
                f"the_well import partial failure: {exc}",
                "install full deps in venv (torch may be required)",
            ),
        )

    root = base_path or os.environ.get("GENESIS_WELL_BASE", WELL_HF_BASE)
    # Force HF streaming path unless operator set an explicit local base
    if not root.startswith("hf://") and not os.environ.get("GENESIS_WELL_ALLOW_LOCAL"):
        # Local path only if explicitly allowed — still batch-capped
        if not os.path.isdir(root):
            return WellProbeResult(
                status="error",
                dataset=name,
                split=split,
                stream=True,
                max_batches=max_batches,
                batches_seen=0,
                package_available=True,
                gaps=(
                    f"local well base {root!r} missing; use HF stream "
                    f"(default {WELL_HF_BASE}) or set GENESIS_WELL_ALLOW_LOCAL=1 "
                    "only after verifying free disk for ONE dataset",
                ),
            )

    try:
        ds = WellDataset(
            well_base_path=root,
            well_dataset_name=name,
            well_split_name=split,
        )
        loader = DataLoader(ds, batch_size=1)
        summaries: list[dict[str, Any]] = []
        n = 0
        for batch in loader:
            summaries.append(_summarize_batch(batch))
            n += 1
            if n >= max_batches:
                break
    except Exception as exc:
        gaps = [
            f"stream failed: {type(exc).__name__}: {exc}",
            "check network, Hugging Face access, and dataset name",
            "HF collection: https://huggingface.co/collections/polymathic-ai/the-well-67e129f4ca23e0447395d74c",
        ]
        if catalog_gap:
            gaps.insert(0, catalog_gap)
        return WellProbeResult(
            status="error",
            dataset=name,
            split=split,
            stream=True,
            max_batches=max_batches,
            batches_seen=0,
            package_available=True,
            sample_summary={"catalog": WELL_DATASET_CATALOG.get(name, {})},
            gaps=tuple(gaps),
        )

    if n == 0:
        return WellProbeResult(
            status="error",
            dataset=name,
            split=split,
            stream=True,
            max_batches=max_batches,
            batches_seen=0,
            package_available=True,
            gaps=("dataset opened but yielded zero batches",),
        )

    gaps_out: list[str] = []
    if catalog_gap:
        gaps_out.append(catalog_gap)
    gaps_out.append(
        "probe only — not a trained surrogate; do not treat samples as certified physics"
    )

    return WellProbeResult(
        status="ok",
        dataset=name,
        split=split,
        stream=True,
        max_batches=max_batches,
        batches_seen=n,
        package_available=True,
        sample_summary={
            "batches": summaries,
            "base_path": root,
            "catalog": WELL_DATASET_CATALOG.get(name, {}),
        },
        gaps=tuple(gaps_out),
    )


def format_probe_result(result: WellProbeResult) -> str:
    """CLI-friendly report."""
    lines = [
        "GENESIS — The Well probe",
        f"  status:     {result.status}",
        f"  dataset:    {result.dataset}",
        f"  split:      {result.split}",
        f"  stream:     {result.stream}",
        f"  package:    {result.package_available}",
        f"  batches:    {result.batches_seen}/{result.max_batches}",
        f"  disk_policy:{result.disk_policy}",
        f"  quelle:     {result.quelle}",
    ]
    if result.sample_summary:
        lines.append(f"  summary:    {result.sample_summary}")
    if result.gaps:
        lines.append("  gaps:")
        for g in result.gaps:
            lines.append(f"    · {g}")
    return "\n".join(lines)
