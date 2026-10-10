"""Freeze the CG357 source-acquisition cohort from the governed 100-subject map.

This is intentionally a metadata-only selection.  It never reads source prose,
prior semantic candidates, model output, or an acquisition result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


# Five evenly-spaced rank strata, with three fixed rank positions per stratum.
# The choice is made before acquisition and is independent of outcome.
SELECTED_RANKS = (1, 4, 7, 21, 25, 28, 40, 44, 49, 54, 67, 71, 84, 90, 100)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def build(identity_map: dict[str, object]) -> dict[str, object]:
    rows = identity_map.get("rows")
    if identity_map.get("identity_map_hash") != "55dc192a4d226fc3769f8408d5fdf6467f11710b9687f8f72c3f2a0ba10024aa" or not isinstance(rows, list) or len(rows) != 100:
        raise ValueError("CG357 requires the verified 100-subject governed identity map")
    by_rank = {int(row["rank"]): row for row in rows}
    if set(SELECTED_RANKS) - set(by_rank):
        raise ValueError("governed identity map is missing a selected rank")
    cases = []
    for ordinal, rank in enumerate(SELECTED_RANKS, start=1):
        row = by_rank[rank]
        # Challenge/blind labels are allocation labels only; they do not encode
        # an expected semantic outcome.
        arm = "challenge" if ordinal <= 10 else "blind"
        cases.append({
            "case_id": f"CG357-{ordinal:02d}", "subject_id": row["subject_id"],
            "abn": row["abn"], "display_name": row["display_name"], "rank": rank,
            "arm": arm,
            "selection_role": f"rank_stratum_{((rank - 1) // 20) + 1}_{arm}",
        })
    material = {
        "contract": "cg357-frozen-cohort-v1", "run_id": "CG-SEMANTIC-EVIDENCE-READINESS-EXECUTION-357-TERRA",
        "identity_map_hash": identity_map["identity_map_hash"], "identity_subject_count": 100,
        "selection_rule": "fixed ranks 1,4,7,21,25,28,40,44,49,54,67,71,84,90,100 from the governed map; first ten allocation-labelled challenge and final five blind",
        "replacement_rule": "no substitution after freeze; only objectively invalid governed subject identity may be replaced by the next unused rank in the same 20-rank stratum, recorded as a new manifest",
        "cases": cases,
    }
    return {**material, "cohort_sha256": sha(material)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cohort = build(json.loads(args.identity_map.read_text(encoding="utf-8")))
    # The freeze timestamp is deliberately recorded outside the hash-addressed
    # selection material so a deterministic rerun preserves cohort identity.
    result = {**cohort, "frozen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"cohort": str(args.out), "cohort_sha256": cohort["cohort_sha256"], "case_count": len(cohort["cases"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
