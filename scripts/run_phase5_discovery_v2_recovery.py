"""Provider-free deterministic recovery of retained Discovery V2 results."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from charitygraph.contracts import ProgramServiceDiscoveryOutputV2
from charitygraph.discovery_evidence_normalization import (
    TRANSFORM_ID,
    TRANSFORM_VERSION,
    canonical_hash,
    normalize_discovery_output,
)
from charitygraph.phase5_semantic_contracts import HISTORICAL_DISCOVERY_V2_CONTRACT, REGISTRY


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _response_text(response: dict[str, Any]) -> str:
    return next(content["text"] for output in response["output"] if output.get("type") == "message" for content in output.get("content", []) if content.get("type") == "output_text")


def _meaning_rows(output: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    rows = []
    for proposal in output["proposals"]:
        for entry in proposal["evidence"]:
            rows.append((entry["evidence_id"], entry["role"], entry.get("note")))
            rows.extend((entry["evidence_id"], meaning["role"], meaning.get("note")) for meaning in entry.get("additional_meanings", []))
    return rows


def _retained_original_outputs() -> list[dict[str, Any]]:
    paths = (
        Path(r"C:\CharityGraph-runtime\phase5-discovery-v2-six-subject-slice-utf8-correction-v1\provider-output.jsonl"),
        Path(r"C:\CharityGraph-runtime\phase5-first-paid-discovery-control-v6\provider-output.jsonl"),
    )
    outputs = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            envelope = json.loads(line)
            body = envelope["response"]["body"]
            outputs.append(json.loads(_response_text(body)))
    return outputs


def recover(runtime_root: Path) -> dict[str, Any]:
    manifest = _read(runtime_root / "standard-request-manifest.json")["ordered_request_items"]
    by_id = {row["provider_request_item_id"]: row for row in manifest}
    corrected_rows = _read(runtime_root / "provider-free-corrected-reconciliation.json")["rows"]
    corrected_contract = next(row for row in REGISTRY if row.contract_id == HISTORICAL_DISCOVERY_V2_CONTRACT.contract_id and row.contract_version == "2.1")
    records = []
    original_outputs = _retained_original_outputs()
    if len(original_outputs) != 7:
        raise AssertionError(f"expected seven retained original outputs, got {len(original_outputs)}")
    direct_valid = normalized = 0
    proposal_counts = Counter()
    meaning_count = 0
    additional_count = 0
    combination_counts = Counter()
    for reconciliation in corrected_rows:
        item = by_id[reconciliation["request_item_id"]]
        stem = reconciliation["request_item_id"].split(":", 1)[1]
        response_path = runtime_root / "standard-results" / f"requestitem_{stem}.json"
        response = _read(response_path)
        raw = json.loads(_response_text(response))
        evidence_ids = (item["evidence_locator_id"],)
        historical_identity = HISTORICAL_DISCOVERY_V2_CONTRACT.identity_hash(evidence_ids)
        corrected_identity = corrected_contract.identity_hash(evidence_ids)
        base = {
            "provider_request_item_id": item["provider_request_item_id"],
            "provider_response_id": response["id"],
            "subject_id": reconciliation["subject_id"],
            "abn": item["abn"],
            "rank": item["rank"],
            "charity_name": item["charity_name"],
            "raw_response_artifact": str(response_path),
            "raw_response_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
            "historical_contract_identity_hash": historical_identity,
            "corrected_contract_identity_hash": corrected_identity,
            "authorized_evidence_ids": list(evidence_ids),
            "provider_operations": 0,
        }
        proposal_counts.update([len(raw["proposals"])])
        try:
            parsed = ProgramServiceDiscoveryOutputV2.model_validate(raw)
            direct_valid += 1
            normalized_output = None
            state = "historical_provider_valid"
            additional = 0
        except Exception:
            normalized_output = normalize_discovery_output(raw)
            ProgramServiceDiscoveryOutputV2.model_validate(normalized_output)
            normalized += 1
            state = "deterministically_normalized"
            additional = sum(len(entry.get("additional_meanings", [])) for proposal in normalized_output["proposals"] for entry in proposal["evidence"])
            roles = {meaning[1] for meaning in _meaning_rows(normalized_output)}
            combination_counts["+".join(sorted(roles))] += 1
            if _meaning_rows(raw) != _meaning_rows(normalized_output):
                raise AssertionError(f"meaning loss or invention for {item['abn']}")
            if {k: v for k, v in raw.items() if k != "proposals"} != {k: v for k, v in normalized_output.items() if k != "proposals"}:
                raise AssertionError(f"top-level semantic drift for {item['abn']}")
            if [set(p) - {"evidence"} for p in raw["proposals"]] != [set(p) - {"evidence"} for p in normalized_output["proposals"]]:
                raise AssertionError(f"proposal semantic drift for {item['abn']}")
            base.update({
                "transform_id": TRANSFORM_ID,
                "transform_version": TRANSFORM_VERSION,
                "input_raw_result_hash": canonical_hash(raw),
                "normalized_result_hash": canonical_hash(normalized_output),
                "replay_normalized_result_hash": canonical_hash(normalize_discovery_output(json.loads(json.dumps(raw)))),
                "normalized_output": normalized_output,
                "lineage_kind": "deterministic_derivation_no_provider_attempt",
            })
            if base["normalized_result_hash"] != base["replay_normalized_result_hash"]:
                raise AssertionError(f"normalization replay drift for {item['abn']}")
        meaning_count += len(_meaning_rows(normalized_output or raw))
        additional_count += additional
        records.append({**base, "state": state, "proposal_count": len(raw["proposals"]), "additional_meanings_count": additional})
    if direct_valid != 78 or normalized != 15:
        raise AssertionError(f"unexpected cohort result: direct={direct_valid}, normalized={normalized}")
    original_proposals = [len(output["proposals"]) for output in original_outputs]
    all_proposal_counts = [*original_proposals, *(row["proposal_count"] for row in records)]
    original_meanings = sum(len(_meaning_rows(output)) for output in original_outputs)
    return {
        "report_type": "phase5_discovery_v2_top100_deterministic_recovery",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_operations": 0,
        "historical_provider_state": {"direct_valid": direct_valid + len(original_outputs), "historical_validation_failures": normalized, "original_valid_outputs": len(original_outputs)},
        "current_usable_state": {"usable_subjects": len(records) + len(original_outputs), "direct_historical": direct_valid + len(original_outputs), "deterministically_normalized": normalized},
        "statistics": {
            "total_proposals": sum(all_proposal_counts),
            "proposal_count_distribution": dict(sorted(Counter(all_proposal_counts).items())),
            "total_evidence_meanings": meaning_count + original_meanings,
            "unique_evidence_locator_count": len({item["evidence_locator_id"] for item in manifest}) + 7,
            "proposals_using_additional_meanings": sum(row["additional_meanings_count"] > 0 for row in records),
            "additional_meaning_count": additional_count,
            "recovered_role_combinations": dict(sorted(combination_counts.items())),
        },
        "transform": {"id": TRANSFORM_ID, "version": TRANSFORM_VERSION, "replay_hashes_match": True},
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-discovery-v2-top100-remainder-standard-v1"))
    args = parser.parse_args()
    result = recover(args.runtime_root)
    output = args.runtime_root / "corrected-discovery-recovery.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    print(canonical_hash(result))


if __name__ == "__main__":
    main()
