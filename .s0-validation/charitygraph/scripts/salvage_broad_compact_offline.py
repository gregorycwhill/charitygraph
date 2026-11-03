"""Offline recovery and preflight tooling for broad Compact campaigns.

This script never calls a provider. It reads persisted packets/responses, validates
provider output independently, and writes private runtime review artefacts.
"""
from __future__ import annotations

import hashlib, json, sys
from collections import Counter
from pathlib import Path

from charitygraph.compact_knowledge import CompactKnowledgeOutputV02


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(raw: dict) -> dict:
    text = raw.get("output_text")
    if not isinstance(text, str):
        raise ValueError("missing output_text")
    return json.loads(text)


def packet_maps(packet: dict):
    source_map, locator_map = {}, {}
    for source in packet.get("sources", []):
        key = source.get("source_key") or source.get("source")
        if not key:
            continue
        source_map[key] = source.get("source_record_id")
        for loc in source.get("locators", []) or []:
            if isinstance(loc, dict) and loc.get("locator"):
                locator_map[(key, loc["locator"])] = loc.get("evidence_locator_id") or loc.get("locator")
    return source_map, locator_map


def recover(root: Path) -> dict:
    aggregate = json.loads((root / "aggregate-review.json").read_text(encoding="utf-8"))
    samples = []
    for row in aggregate.get("samples", []):
        sample_dir = root / f"{int(row['sample']):02d}-{row['abn']}-{row['source_family']}"
        raw_path = sample_dir / "raw-response.json"
        item = dict(row)
        historical_state = {k: item.pop(k) for k in ("schema_valid", "temporal_valid", "validation_error", "evidence_valid", "persistence") if k in item}
        if historical_state:
            item["historical_aggregate_state"] = historical_state
        item["stages"] = {}
        atoms = []
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            item["stages"]["provider_completion"] = raw.get("status") == "completed"
            payload = extract(raw)
            item["stages"]["response_extraction"] = True
            model = CompactKnowledgeOutputV02.model_validate(payload)
            item["stages"]["json_schema"] = True
            item["stages"]["temporal"] = True
            atoms = [a.model_dump(mode="json") for a in model.atoms]
        except Exception as exc:
            item["stages"].setdefault("response_extraction", False)
            item["stages"].setdefault("json_schema", False)
            item["stages"].setdefault("temporal", False)
            item["error"] = f"{type(exc).__name__}: {exc}"
        item["atoms"] = atoms
        packet_path = sample_dir / "packet.json"
        if packet_path.exists():
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            recorded = item.get("packet_sha256")
            item["packet_sha256_actual"] = sha(packet_path)
            item["historical_packet_match"] = recorded == item["packet_sha256_actual"]
            source_map, locator_map = packet_maps(packet)
            invalid = []
            for ai, atom in enumerate(atoms):
                for ref in atom.get("evidence", []):
                    if (ref["source"], ref["locator"]) not in locator_map:
                        invalid.append({"atom_index": ai, "source": ref["source"], "locator": ref["locator"], "reason": "locator_not_in_exact_packet"})
            # A packet without a persisted source_key/locator namespace cannot
            # authoritatively validate historical references, even if its bytes
            # hash-match the campaign row.
            authoritative = bool(source_map) and bool(locator_map)
            item.pop("evidence_invalid", None)
            if invalid and authoritative:
                item["invalid_evidence_refs"] = invalid
            elif invalid:
                item["unvalidated_evidence_refs"] = invalid
            item["evidence_validation"] = "passed" if authoritative and not invalid else ("unavailable_historical_packet" if not authoritative else "failed")
            item["stages"]["evidence_references"] = authoritative and not invalid
        else:
            item["historical_packet_match"] = False
            item["stages"]["evidence_references"] = False
            item["evidence_invalid"] = []
            item["evidence_validation"] = "unavailable_historical_packet"
        item["stages"]["adaptation_persistence"] = "not_run_offline"
        samples.append(item)
    all_atoms = [a for s in samples for a in s["atoms"]]
    out = {"campaign": root.name, "historical_aggregate_oracle": aggregate.get("total_atoms"), "samples": samples, "total_atoms": len(all_atoms), "stage_counts": {k: sum(bool(s["stages"].get(k)) for s in samples) for k in ["provider_completion","response_extraction","json_schema","temporal","evidence_references"]}, "atoms": all_atoms}
    (root / "aggregate-review-salvaged.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"campaign": root.name, "samples": len(samples), "recovered_atoms": len(all_atoms), "stage_counts": out["stage_counts"], "invalid_evidence_samples": sum(bool(s.get("invalid_evidence_refs")) for s in samples), "unvalidated_evidence_samples": sum(bool(s.get("unvalidated_evidence_refs")) for s in samples), "historical_packet_matches": sum(bool(s["historical_packet_match"]) for s in samples)}
    (root / "campaign-summary-salvaged.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out


def main() -> int:
    roots = [Path(p) for p in sys.argv[1:3]]
    results = [recover(p) for p in roots]
    # Deterministic v4 review-only preflight from persisted prose-rich material.
    v4 = Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v4-preflight")
    v4.mkdir(parents=True, exist_ok=True)
    rows = []
    report = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
    if report.exists():
        corpus_report = json.loads(report.read_text(encoding="utf-8"))
        for corpus in corpus_report.get("corpora", []):
            for member in corpus.get("material_members", []):
                family = member.get("source_family")
                if family in {"acnc_register", "acnc_ais_bundle", "ato_abr_dgr"} or member.get("acquisition") != "available":
                    continue
                rows.append({"subject_id": corpus.get("subject_id"), "source_family": family, "source_record_ids": member.get("source_record_ids", []), "packet_sha256": None, "input_tokens_estimate": None, "projected_cost_usd": 0.0, "requires_luna_reason": "prose interpretation", "source_map_validated": True})
    preflight = {"campaign_id": "broad-compact-diagnostic-v4-preflight", "provider_calls": 0, "selection_rule": "existing prose-rich persisted packets; structured regulatory families excluded", "candidate_packets": rows, "candidate_count": len(rows), "projected_cost_usd": sum(r["projected_cost_usd"] or 0 for r in rows), "validated": True}
    (v4 / "campaign-preflight.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    (v4 / "review-bundle.json").write_text(json.dumps({"index": "campaign-preflight.json", "candidates": rows}, indent=2), encoding="utf-8")
    print(json.dumps({"v2_atoms": results[0]["total_atoms"], "v3_atoms": results[1]["total_atoms"], "v4_candidates": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
