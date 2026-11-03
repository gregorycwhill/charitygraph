"""Build a blinded Condition-A export from already-frozen Phase 6 requests.

This utility reads only the saved preparation requests. It does not inspect raw
provider responses or candidate files and performs no source acquisition.
Generated source representations belong in a private evaluation directory,
never in Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .phase5_standard_transport import body_sha256, canonical_standard_body_bytes


ANALYST_QUESTIONS = {
    "outcomes": [
        "What outcome does the organization say it seeks, and what outcome does it say was observed or measured?",
        "Is the evidence an input, activity, output, observed outcome, contribution claim, or causal finding reported by a source?",
        "Which program, population, denominator, and period does each reported measure cover?",
        "Who conducted or published any evaluation, and what methods, comparator, and limitations are stated?",
        "What is unknown, mixed, negative, inconclusive, absent from the reviewed source, or not processed?",
    ],
    "commitments": [
        "What policy, principle, target, pledge, or obligation is stated, by whom, and for what scope and period?",
        "Is there evidence of a planned action, self-reported implementation, independently observed practice, external verification, or formal compliance finding?",
        "Does implementation evidence cover the whole organization, a named program or site, or only a reporting period?",
        "Is implementation evidence absent from the reviewed sources, or is there affirmative evidence of non-implementation?",
    ],
    "capacity": [
        "What service is described, at what organization, program, or service scope, and for whom?",
        "What eligibility, referral, location, or access conditions does the retained source state?",
        "What does the source say about availability, and as of what date?",
        "Is a capacity quantity, unit, or limit explicitly supported, or is capacity unknown?",
        "Which answer cannot be made because the source is stale, unavailable, unprocessed, silent, or ambiguous?",
    ],
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_request(source_root: Path, row: dict[str, Any]) -> tuple[dict, dict, dict]:
    ordinal = row.get("replicate_ordinal") or 0
    path = source_root / f"{row['slice_id']}__{row['abn']}__{ordinal}.json"
    item = json.loads(path.read_text(encoding="utf-8"))
    body = item["provider_request_body"]
    if body_sha256(canonical_standard_body_bytes(body)) != row["request_body_sha256"]:
        raise ValueError(f"request body hash mismatch for {row['logical_request_id']}")
    payload = json.loads(body["input"][1]["content"][0]["text"])
    if payload.get("slice_id") != row["slice_id"] or payload.get("abn") != row["abn"]:
        raise ValueError(f"request identity mismatch for {row['logical_request_id']}")
    return item, body, payload


def build_source_only_export(source_root: Path, output_root: Path) -> dict[str, Any]:
    """Write one source-only task per unique slice/subject, rejecting drift."""

    source_root = Path(source_root)
    output_root = Path(output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite a non-empty evaluation export: {output_root}")
    prep = json.loads((source_root / "preparation.json").read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in prep["requests"]:
        grouped[(row["slice_id"], row["abn"])].append(row)

    output_root.mkdir(parents=True, exist_ok=True)
    task_dir = output_root / "tasks"
    task_dir.mkdir()
    task_manifest = []
    for (slice_id, abn), rows in sorted(grouped.items()):
        # Prefer the original single/first run. Replicate rows may be used only
        # when no primary task exists; all repeated frozen source inputs must agree.
        rows = sorted(rows, key=lambda r: (r.get("replicate_ordinal") is not None, r.get("replicate_ordinal") or 0))
        selected = rows[0]
        _, _, payload = _read_request(source_root, selected)
        source_refs = {x["evidence_locator_id"]: x for x in selected["source_refs"]}
        source_items = []
        for src in payload["sources"]:
            ref = source_refs.get(src["evidence_locator_id"])
            if ref is None:
                raise ValueError(f"source locator absent from frozen manifest: {src['evidence_locator_id']}")
            exact_content = src["content"]
            source_items.append({
                "source_record_id": src["source_record_id"],
                "source_family": src["source_family"],
                "source_role": src["source_role"],
                "source_artifact_id": src["source_artifact_id"],
                "representation_artifact_id": src.get("representation_artifact_id"),
                "evidence_locator_id": src["evidence_locator_id"],
                "locator_kind": ref.get("locator_kind"),
                "source_locator": src.get("source_locator"),
                "source_date": src.get("source_date"),
                "retrieved_at": src.get("retrieved_at"),
                "effective_period": ref.get("effective_period"),
                "evidence_representation_sha256": hashlib.sha256(exact_content.encode("utf-8")).hexdigest(),
                "exact_transmitted_representation": exact_content,
            })
        package = {
            "task_id": f"phase6-condition-a:{slice_id}:{abn}",
            "condition": "A_source_only",
            "slice_id": slice_id,
            "subject_id": payload["subject_id"],
            "subject_name": payload["subject_name"],
            "abn": abn,
            "analyst_questions": ANALYST_QUESTIONS[slice_id],
            "allowed_scope_ids": [payload["organization_scope"]],
            "additional_program_or_service_scope_ids": [],
            "scope_note": "The frozen request supplied no additional durable program/service scope IDs; retain named sub-organization scopes as unresolved unless separately supported by this packet.",
            "sources": source_items,
            "unavailable_sources": payload.get("unavailable_sources", []),
        }
        package_bytes = json.dumps(package, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        filename = f"{slice_id}__{abn}.json"
        (task_dir / filename).write_bytes(package_bytes)

        # Repeated same-subject requests may differ in run wording, but the exact
        # transmitted evidence package, scope allowance, and missingness must match.
        frozen_packet_identity = _canonical({
            "sources": [{k: v for k, v in x.items() if k != "exact_transmitted_representation"} for x in source_items],
            "source_content_hashes": [x["evidence_representation_sha256"] for x in source_items],
            "scope": payload["organization_scope"],
            "unavailable": payload.get("unavailable_sources", []),
        })
        for repeat in rows[1:]:
            _, _, repeat_payload = _read_request(source_root, repeat)
            repeat_refs = {x["evidence_locator_id"]: x for x in repeat["source_refs"]}
            repeat_package = []
            for src in repeat_payload["sources"]:
                ref = repeat_refs[src["evidence_locator_id"]]
                repeat_package.append({
                    "source_record_id": src["source_record_id"], "source_family": src["source_family"],
                    "source_role": src["source_role"], "source_artifact_id": src["source_artifact_id"],
                    "representation_artifact_id": src.get("representation_artifact_id"),
                    "evidence_locator_id": src["evidence_locator_id"], "locator_kind": ref.get("locator_kind"),
                    "source_locator": src.get("source_locator"), "source_date": src.get("source_date"),
                    "retrieved_at": src.get("retrieved_at"), "effective_period": ref.get("effective_period"),
                    "evidence_representation_sha256": hashlib.sha256(src["content"].encode("utf-8")).hexdigest(),
                })
            repeat_identity = _canonical({
                "sources": repeat_package,
                "source_content_hashes": [x["evidence_representation_sha256"] for x in repeat_package],
                "scope": repeat_payload["organization_scope"],
                "unavailable": repeat_payload.get("unavailable_sources", []),
            })
            if repeat_identity != frozen_packet_identity:
                raise ValueError(f"same-subject frozen source inputs differ across repeats: {repeat['logical_request_id']}")
        task_manifest.append({
            "task_id": package["task_id"], "path": f"tasks/{filename}",
            "task_sha256": hashlib.sha256(package_bytes).hexdigest(),
            "source_count": len(source_items), "source_input_hashes": [x["evidence_representation_sha256"] for x in source_items],
            "frozen_request_sha256": selected["request_body_sha256"],
            "source_repeat_count": len(rows),
        })

    manifest = {
        "export_version": "phase6-condition-a-source-only-v1",
        "provider_calls": 0,
        "source_acquisitions": 0,
        "candidate_outputs_read": 0,
        "candidate_propositions_included": 0,
        "answer_fields_included": 0,
        "tasks": task_manifest,
        "task_count": len(task_manifest),
        "warning": "Private blinded evaluation material. Keep separate from candidate outputs and restrict access to assigned source-only analysts.",
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (output_root / "manifest.json").write_bytes(manifest_bytes)
    manifest["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preparation_directory", type=Path, help="Directory containing preparation.json and frozen request JSON files")
    parser.add_argument("output_directory", type=Path, help="New private output directory; must be absent or empty")
    args = parser.parse_args()
    print(json.dumps(build_source_only_export(args.preparation_directory, args.output_directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
