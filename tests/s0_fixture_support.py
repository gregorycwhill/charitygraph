"""Self-contained filesystem helpers for S0 integration fixtures.

The data package remains a separately versioned repository.  Tests must name
it explicitly (``CHARITYGRAPH_S0_DATA_PACKAGE``) or use the campaign-local
successor checkout; they never infer it from a caller's temporary directory.
"""
from __future__ import annotations

import os
import shutil
import hashlib
import json
from pathlib import Path


def canonical_data_package() -> Path:
    configured = os.environ.get("CHARITYGRAPH_S0_DATA_PACKAGE")
    candidates = [Path(configured)] if configured else []
    # The Terra campaign keeps its immutable successor package beside Builder.
    candidates.append(Path(__file__).resolve().parents[2] / "s0-attempt21-successor-data")
    for candidate in candidates:
        if (candidate / "SCALE_S0_IDENTITY_LINEAGE_V1.json").is_file():
            return candidate
    raise RuntimeError(
        "S0 data package is unavailable; set CHARITYGRAPH_S0_DATA_PACKAGE to "
        "a checkout containing SCALE_S0_IDENTITY_LINEAGE_V1.json"
    )


def copy_data_package(source: Path, destination: Path) -> Path:
    """Copy the lineage-declared package, never an incidental source cache."""
    lineage_path = source / "SCALE_S0_IDENTITY_LINEAGE_V1.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    paths = {"SCALE_S0_IDENTITY_LINEAGE_V1.json", "SCALE_S0_AUTHORISATION_DECISION_2026-09-18.md"}
    paths.update(entry["path"] for entry in lineage["artifacts"])
    for relative in paths:
        origin = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    return destination


def write_pricing_capture(root: Path) -> tuple[Path, str]:
    """Create the smallest governed pricing capture accepted by the real CLI."""
    capture = {
        "schema": "charitygraph-supervisor-pricing-capture-v1",
        "provenance_note": "structured supervisor capture, not over raw upstream HTML",
        "captured_at": "2026-09-25T00:00:00+00:00",
        "model": "gpt-5.6-luna", "currency": "USD",
        "model_pricing": {"input_usd_per_million_tokens": "0.20", "cached_input_usd_per_million_tokens": "0.02", "output_usd_per_million_tokens": "1.20"},
        "web_search_pricing": {"search_content_tokens_billed_at_model_rates": True, "usd_per_1000_calls": "10.00"},
    }
    path = root / "pricing-capture.json"
    raw = json.dumps(capture, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()
