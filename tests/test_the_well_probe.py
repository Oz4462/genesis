"""The Well probe — storage-safe stream-only policy (no bulk download)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.tools.the_well_probe import (  # noqa: E402
    MAX_PROBE_BATCHES,
    WELL_DATASET_CATALOG,
    format_catalog,
    format_probe_result,
    list_well_catalog,
    probe_well_dataset,
    the_well_package_available,
)


def test_catalog_offline_nonempty():
    cat = list_well_catalog()
    assert "active_matter" in cat
    assert "laptop_hint" in cat["active_matter"]


def test_format_catalog_mentions_stream_policy():
    text = format_catalog()
    assert "stream" in text.lower()
    assert "15TB" in text or "15 TB" in text or "15 TB" in text


def test_probe_refuses_non_stream():
    r = probe_well_dataset("active_matter", stream=False)
    assert r.status == "error"
    assert any("stream" in g.lower() for g in r.gaps)


def test_probe_caps_max_batches():
    # When package missing, still records the capped max_batches
    r = probe_well_dataset("active_matter", max_batches=99, stream=True)
    assert r.max_batches == MAX_PROBE_BATCHES


def test_probe_without_package_is_unavailable_not_fabricated():
    if the_well_package_available():
        # Environment has the package — still must not invent if stream fails;
        # at least package_available is True.
        r = probe_well_dataset("active_matter", max_batches=1)
        assert r.package_available is True
        assert r.status in ("ok", "error", "unavailable")
        assert r.batches_seen <= MAX_PROBE_BATCHES
    else:
        r = probe_well_dataset("active_matter", max_batches=1)
        assert r.status == "unavailable"
        assert r.batches_seen == 0
        assert r.package_available is False
        assert any("not installed" in g for g in r.gaps)
        # Must not claim tensors
        assert "batches" not in r.sample_summary or not r.sample_summary.get("batches")


def test_format_probe_result_includes_gaps():
    r = probe_well_dataset("active_matter", stream=False)
    text = format_probe_result(r)
    assert "status" in text.lower() or "status:" in text
    assert "error" in text or "stream" in text.lower()


def test_catalog_keys_are_strings():
    for k, v in WELL_DATASET_CATALOG.items():
        assert isinstance(k, str) and k
        assert "domain" in v and "hf_dataset" in v
