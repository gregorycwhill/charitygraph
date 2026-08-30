"""Recover diagnostics from the completed private calibration run only."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from charitygraph.whole_card_calibration import WholeCardExtractionOutput, locator_resolves  # noqa: E402

RUN = Path(r"C:\CharityGraph-runtime\whole-card-calibration-v01-20260830T024044Z")
REPORT = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")


def schema_shape_valid(value: object) -> tuple[bool, str | None]:
    """Check the strict JSON shape without applying cross-field rules."""
    if not isinstance(value, dict):
        return False, "top-level value must be an object"
    if set(value) != {"section_assessments", "observations"}:
        return False, "top-level keys do not match the strict schema"
    assessments = value.get("section_assessments")
    if not isinstance(assessments, list) or len(assessments) != 20:
        return False, "section_assessments must contain exactly 20 items"
    required_assessment = {"section_id", "status", "note"}
    statuses = {"observations_found", "insufficient_evidence", "not_applicable", "deferred"}
    for item in assessments:
        if not isinstance(item, dict) or set(item) != required_assessment:
            return False, "section assessment shape is invalid"
        if not isinstance(item["section_id"], int) or not 1 <= item["section_id"] <= 20 or item["status"] not in statuses:
            return False, "section assessment field is invalid"
        if item["note"] is not None and not isinstance(item["note"], str):
            return False, "section assessment note is invalid"
    observations = value.get("observations")
    if not isinstance(observations, list):
        return False, "observations must be an array"
    required_observation = {"section_id", "scope", "proposition", "epistemic_status", "temporal_scope", "evidence", "qualifications"}
    for item in observations:
        if not isinstance(item, dict) or set(item) != required_observation:
            return False, "observation shape is invalid"
    return True, None


def main() -> None:
    packet = json.loads((RUN / "packet.json").read_text(encoding="utf-8"))
    raw = json.loads((RUN / "gpt-5.6-terra-raw.json").read_text(encoding="utf-8"))
    parsed = json.loads(raw["raw_output"])
    (RUN / "returned-output.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    schema_valid, schema_error = schema_shape_valid(parsed)
    structural_valid = True
    structural_error = None
    if schema_valid:
        try:
            WholeCardExtractionOutput.model_validate(parsed)
        except Exception as exc:
            structural_valid = False; structural_error = str(exc)[:500]
    else:
        structural_valid = False
    spaces = {s["source_record_id"]: {x["locator"] for x in s["locators"]} for s in packet["sources"]}
    invalid = []
    for index, observation in enumerate(parsed.get("observations", [])):
        for evidence in observation.get("evidence", []):
            source = evidence.get("source_record_id"); locator = evidence.get("packet_locator")
            if source not in spaces:
                reason = "source_record_id is absent from packet"
                nearest = []
            elif not locator_resolves(locator, spaces[source]):
                reason = "packet locator is outside the cited source line namespace"
                nearest = []
                try:
                    start = int(locator.split(":L", 1)[1].split("]", 1)[0])
                    nearest = sorted(spaces[source], key=lambda x: abs(int(x.split(":L", 1)[1].split("]", 1)[0]) - start))[:3]
                except Exception:
                    pass
            else:
                continue
            invalid.append({"observation_index": index, "section_id": observation.get("section_id"), "proposition": observation.get("proposition"), "source_record_id": source, "packet_locator": locator, "failure_reason": reason, "nearest_valid_locators": nearest})
    report = json.loads(REPORT.read_text(encoding="utf-8")); fred = next(s for s in report["subjects"] if s["abn"] == "46070556642"); corpus = next(c for c in report["corpora"] if c["subject_id"] == fred["subject_id"])
    included = {s["source_record_id"] for s in packet["sources"]}; db = sqlite3.connect(CATALOG)
    reconciliation = []
    for member in corpus["material_members"]:
        for source_id in member["source_record_ids"]:
            row = db.execute("select source_family,source_role from source_records where source_record_id=?", (source_id,)).fetchone()
            reconciliation.append({"source_record_id": source_id, "source_family": row[0] if row else None, "source_role": row[1] if row else None, "classification": ("included" if source_id in included else "intentionally_excluded_scaffolding" if row and row[1] in {"robots", "sitemap"} else "missing_unresolvable")})
    db.close()
    prompt = (RUN / "prompt.txt").read_bytes(); supplied = Path(r"C:\Users\grego\.codex\attachments\33c22785-dd6d-470a-974e-9e535c6b8c07\pasted-text.txt").read_bytes(); versioned = Path(__file__).with_name("whole_card_semantic_calibration_v01_prompt.txt").read_bytes()
    diagnostics = {"json_schema_valid": schema_valid, "json_schema_error": schema_error, "twenty_section_cross_field_valid": structural_valid, "cross_field_error": structural_error, "citation_source_record_valid": not invalid, "invalid_evidence_references": invalid, "corpus_packet_reconciliation": reconciliation, "packet_sources_without_pfra": not any(x["source_family"] == "pfra" for x in reconciliation), "official_selected_pages_present": any(x["source_role"] == "official_page" and x["classification"] == "included" for x in reconciliation), "explanation": {"pfra": "Fred's frozen corpus member set contains no PFRA member.", "official_pages": "The frozen Fred set contains an official homepage plus robots/sitemap scaffolding, but no official_page members; selected pages were therefore unavailable without rerunning acquisition/ranking."}, "prompt_sha256": hashlib.sha256(prompt).hexdigest(), "supplied_prompt_sha256": hashlib.sha256(supplied).hexdigest(), "versioned_prompt_sha256": hashlib.sha256(versioned).hexdigest(), "prompt_bytes_equal": prompt == supplied == versioned, "luna_failure": {"error_class": "OpenAIRequestError", "transport_requests": 2, "detail": "No response detail was persisted by the original harness."}}
    (RUN / "validation-diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / "corpus-packet-reconciliation.json").write_text(json.dumps(reconciliation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"invalid_citations": len(invalid), "json_schema_valid": schema_valid, "twenty_section_cross_field_valid": structural_valid, "prompt_bytes_equal": prompt == supplied, "reconciliation_rows": len(reconciliation)}, indent=2))


if __name__ == "__main__":
    main()
