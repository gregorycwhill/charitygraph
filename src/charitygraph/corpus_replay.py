"""Deterministic closed-world replay for retained Gate-2 corpus packages.

This module deliberately does not acquire or discover.  It consumes a named
evidence package, verifies its retained bytes, and makes the distinction
between an empty traversal frontier and a safety-bound frontier explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ADMITTED_FAMILIES = {
    "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
    "annual_report", "wikipedia_wikimedia", "pfra",
}
BASELINE_STATES = {
    "CAPTURED", "DISCOVERY_EXHAUSTED_NO_CAPTURE", "TRUNCATED",
    "IDENTITY_NOT_BOUND_AFTER_RESOLUTION",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontier_state(*, queued_admissible_urls: int, safety_bound_hit: bool) -> str:
    """Return exhaustion only when no admissible same-domain work remains."""
    if queued_admissible_urls:
        return "TRUNCATED" if safety_bound_hit else "PENDING"
    return "EXHAUSTED"


def verify_package(package: Path) -> dict[str, Any]:
    """Mechanically verify the frozen CG384-style evidence package."""
    sums = _read(package / "SHA256SUMS.json")
    mismatches = {name: digest for name, digest in sums.items()
                  if not (package / name).is_file() or _sha(package / name) != digest}
    matrix = _read(package / "original_recovered" / "cg364-matrix-after.json")
    cohort = _read(package / "reconstructed_from_durable_evidence" / "cg364-cohort-recovery.json")
    cells = matrix["coverage_matrix"]
    states = Counter(cell["state"] for cell in cells)
    subjects = {cell["subject_id"] for cell in cells}
    categories = Counter(cell["subject_id"] for cell in cells)
    families = set(_read(package / "manifest.json")["source_universe_v1"]["admitted_families"])
    cohort_hash = cohort["fixed_cohort_sha256"]
    checks = {
        "hashes": not mismatches,
        "cells": len(cells) == 180,
        "subjects": len(subjects) == 15 and all(count == 12 for count in categories.values()),
        "cohort_hash": matrix["fixed_cohort_sha256"] == cohort_hash,
        "families": families == ADMITTED_FAMILIES,
        "states": set(states) <= BASELINE_STATES and dict(states) == {
            "CAPTURED": 30, "DISCOVERY_EXHAUSTED_NO_CAPTURE": 12,
            "TRUNCATED": 66, "IDENTITY_NOT_BOUND_AFTER_RESOLUTION": 72,
        },
    }
    return {"package": str(package), "checks": checks, "all_passed": all(checks.values()),
            "mismatches": mismatches, "cohort_hash": cohort_hash,
            "state_counts": dict(sorted(states.items()))}


def baseline_replay(package: Path, output: Path) -> dict[str, Any]:
    verification = verify_package(package)
    if not verification["all_passed"]:
        raise ValueError("frozen evidence package integrity check failed")
    output.mkdir(parents=True, exist_ok=True)
    matrix = _read(package / "original_recovered" / "cg364-matrix-after.json")
    ledger = _read(package / "original_recovered" / "cg364-attempt-ledger.json")
    (output / "baseline-matrix.json").write_bytes(_canonical(matrix))
    (output / "baseline-attempt-ledger.json").write_bytes(_canonical(ledger))
    proof = {"schema": "charitygraph.g2.baseline-replay-proof/v1", "mode": "retained-bytes-only",
             "verification": verification, "matrix_sha256": _sha(output / "baseline-matrix.json"),
             "attempt_ledger_sha256": _sha(output / "baseline-attempt-ledger.json")}
    (output / "baseline-replay-proof.json").write_bytes(_canonical(proof))
    return proof


def repaired_replay(package: Path, output: Path) -> dict[str, Any]:
    """Re-evaluate every historical indeterminate state without relabelling it.

    Retained evidence cannot manufacture an identity proof or drain a queue that
    the historical run did not visit.  The output preserves each original state
    and records that boundary explicitly, which keeps source-side residuals
    separate from Builder bookkeeping.
    """
    baseline_replay(package, output)
    matrix = _read(package / "original_recovered" / "cg364-matrix-after.json")
    attempts = _read(package / "original_recovered" / "cg364-attempt-ledger.json")["attempts"]
    by_case = defaultdict(list)
    for attempt in attempts:
        by_case[attempt["case_id"]].append(attempt["attempt_id"])
    transitions: list[dict[str, Any]] = []
    root_causes: Counter[str] = Counter()
    repaired_cells: list[dict[str, Any]] = []
    for cell in matrix["coverage_matrix"]:
        repaired = dict(cell)
        state = cell["state"]
        if state == "IDENTITY_NOT_BOUND_AFTER_RESOLUTION":
            cause = "governed_locator_identity_not_proved_by_retained_evidence"
            resolution = "IDENTITY_UNBOUND_REQUIRES_GOVERNED_EVIDENCE"
            lineage = by_case[cell["case_id"]]
        elif state == "TRUNCATED":
            # The frozen package retains this frontier snapshot inline with
            # every matrix cell.  It is enough to prove non-exhaustion without
            # inventing a fresh crawl from an ungoverned locator.
            ledger = cell["exhaustion"]
            queued = int(bool(ledger.get("unexplored_due_to_cap")))
            resolution = frontier_state(queued_admissible_urls=queued, safety_bound_hit=True)
            if resolution != "TRUNCATED":
                raise ValueError("historical truncation lacked a queued frontier")
            cause = "historical_safety_cap_left_same_domain_frontier"
            lineage = [entry["url"] for entry in ledger.get("visited", [])]
        else:
            cause = "already_terminal_or_captured"
            resolution = state
            lineage = cell.get("attempt_ids", [])
        repaired["historical_state"] = state
        repaired["repaired_state"] = state
        repaired["repaired_resolution"] = resolution
        repaired["root_cause"] = cause
        repaired["lineage"] = lineage
        repaired_cells.append(repaired)
        if state in {"IDENTITY_NOT_BOUND_AFTER_RESOLUTION", "TRUNCATED"}:
            root_causes[cause] += 1
            transitions.append({"case_id": cell["case_id"], "category": cell["category"],
                                "before": state, "after": state, "root_cause": cause,
                                "resolution": resolution})
    result = {"schema": "charitygraph.g2.closed-world-repaired-replay/v1", "mode": "retained-bytes-only",
              "live_request_count": 0, "cohort_hash": matrix["fixed_cohort_sha256"],
              "state_counts_before": dict(Counter(c["state"] for c in matrix["coverage_matrix"])),
              "state_counts_after": dict(Counter(c["repaired_state"] for c in repaired_cells)),
              "coverage_matrix": repaired_cells}
    report = {"schema": "charitygraph.g2.root-cause-transitions/v1", "transition_count": len(transitions),
              "root_cause_counts": dict(sorted(root_causes.items())), "transitions": transitions,
              "verdict": "G2_CORPUS_NOT_READY",
              "residual_blocker": "66 same-domain frontiers remain explicitly truncated; retained evidence cannot prove exhaustion."}
    (output / "repaired-matrix.json").write_bytes(_canonical(result))
    (output / "root-cause-transitions.json").write_bytes(_canonical(report))
    (output / "repaired-attempt-evidence-lineage.json").write_bytes(_canonical({"attempts": attempts}))
    index = {path.name: _sha(path) for path in sorted(output.glob("*.json"))
             if path.name not in {"manifest.json", "SHA256SUMS.json"}}
    (output / "SHA256SUMS.json").write_bytes(_canonical(index))
    manifest = {"schema": "charitygraph.g2.corpus-replay-repair-manifest/v1",
                "source_package": str(package), "source_package_verification": verify_package(package),
                "mode": "closed-world-retained-bytes-only", "live_request_count": 0,
                "outputs": index, "verdict": report["verdict"],
                "residual_blocker": report["residual_blocker"]}
    (output / "manifest.json").write_bytes(_canonical(manifest))
    return report


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = repaired_replay(args.package, args.output)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    _main()
