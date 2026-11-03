"""Run the fixed offline I/P/A context extraction into ignored Builder work data."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "src"))

from charitygraph.product_value_context import (
    BASELINE_LOCK_SHA256,
    create_adjudication_packet,
    create_projection_preview,
    derive_context_candidates,
)


def main() -> None:
    work = repo / "work" / "product-value-baseline-2026-09-14"
    source_root = work / "model-assisted-baseline" / "source-only"
    out = work / "deterministic-context"
    generated_at = datetime.now(timezone.utc)
    candidates = derive_context_candidates(source_root, generated_at=generated_at)
    preview = create_projection_preview(candidates, generated_at)
    packet = create_adjudication_packet(candidates, generated_at)

    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(
        json.dumps({"generated_at": generated_at.isoformat(), "status": "CANDIDATES_ONLY", "candidates": candidates}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "adjudication-packet.md").write_text(packet, encoding="utf-8")
    (out / "projection-preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "run-metadata.json").write_text(json.dumps({
        "generated_at": generated_at.isoformat(),
        "baseline_lock_sha256": BASELINE_LOCK_SHA256,
        "candidate_count": len(candidates),
        "governed_items": 0,
        "governed_coverage_states": 0,
        "provider_calls": 0,
        "new_source_acquisitions": 0,
        "human_adjudications": 0,
        "promotions": 0,
        "projection_items": 0,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} candidates to {out}")


if __name__ == "__main__":
    main()
