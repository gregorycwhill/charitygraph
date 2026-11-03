"""Record the requested G3 run as unissued when frozen boundaries fail."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PACKET_PATH = ROOT / "evidence/gate3-v15-provider-free-execution-preflight/frozen-execution-packets.json"
PREP_INVENTORY = ROOT / "evidence/gate3-v15-provider-free-execution-preflight/artifact-sha256-inventory.json"
ACQUISITION = Path(r"C:\CharityGraph-runtime\artifacts\g3-fresh-36-v15\source-universe\acquisition-ledger.json")
OBJECTS = ACQUISITION.parent / "source-objects"
EXPECTED = {
    "branch": "gate3-cg406-remediation",
    "head": "5cd1b7e3688481336f619e8fd6b07cd423a25099",
    "packet_manifest_sha256": "bc321f06a5873997562828fda0b689995a101ab56e9848b6e4dbbbfb4b4f60db",
    "acquisition_ledger_sha256": "ad979ba27b6060a5d218fabb4025d20924a12fda4a4e3771f34c8edfa5e55b10",
    "preflight_inventory_sha256": "e25e396126d1417afcb26644c6899c4fa877fdeb86ce3ebe61def2d50f199cd3",
}

def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def write(name: str, value: object) -> None:
    (OUT / name).write_bytes(canonical(value))

def main() -> None:
    import subprocess
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    packet_bytes = PACKET_PATH.read_bytes()
    packet_doc = json.loads(packet_bytes)
    acquisition_bytes = ACQUISITION.read_bytes()
    acquisition_doc = json.loads(acquisition_bytes)
    preflight_inventory_bytes = PREP_INVENTORY.read_bytes()
    checks = {
        "branch_expected": branch == EXPECTED["branch"],
        "head_expected": head == EXPECTED["head"],
        "packet_manifest_expected": digest(packet_bytes) == EXPECTED["packet_manifest_sha256"],
        "acquisition_ledger_expected": digest(acquisition_bytes) == EXPECTED["acquisition_ledger_sha256"],
        "preflight_inventory_expected": digest(preflight_inventory_bytes) == EXPECTED["preflight_inventory_sha256"],
        "packet_count_36": len(packet_doc.get("packets", [])) == 36,
        "unique_question_ids_36": len({p["envelope"]["bound_question_identity"] for p in packet_doc.get("packets", [])}) == 36,
    }
    source_hash_checks = []
    for row in acquisition_doc.get("rows", []):
        h = row.get("payload_sha256")
        if row.get("acquisition_state") == "ACQUIRED" and h:
            path = OBJECTS / h
            source_hash_checks.append({"sha256": h, "present": path.is_file(), "matches": path.is_file() and digest(path.read_bytes()) == h})
    checks["all_acquired_source_hashes_verified"] = bool(source_hash_checks) and all(x["present"] and x["matches"] for x in source_hash_checks)

    rights_required = {"rights_decision_id", "transmitted_representation_sha256", "provider_transmission_allowed", "rights_evidence_sha256"}
    request_required = {"prompt", "request_body", "response_schema", "model", "reasoning_effort", "delivery_mode"}
    rights_complete = all(all(rights_required <= set(item) for item in p.get("provider_visible_evidence", [])) for p in packet_doc.get("packets", []))
    request_complete = all(request_required <= set(p) for p in packet_doc.get("packets", []))
    checks["artifact_bound_rights_decisions_present"] = rights_complete
    checks["frozen_provider_request_configuration_present"] = request_complete
    blocked_reasons = []
    if not rights_complete:
        blocked_reasons.append("Packet evidence entries lack artifact-bound rights decision IDs, exact transmitted representation hashes, and affirmative transmission decision records.")
    if not request_complete:
        blocked_reasons.append("Candidate packet objects contain no frozen prompt, provider request body, response schema, model, reasoning effort, or delivery mode; they are marked FROZEN_PROVIDER_FREE_CANDIDATE.")
    blocked_reasons.append("No run-bound trusted provider authorization artifact matching this exact request plan hash and aggregate ceiling is present; the repository provider gate is default-deny.")

    candidate_evidence = [item for packet in packet_doc.get("packets", []) for item in packet.get("provider_visible_evidence", [])]
    rights_bindings = [{"evidence_id": item.get("evidence_id"), "source_family": item.get("source_family"),
        "source_locator": item.get("source_locator"), "payload_sha256": item.get("payload_sha256"),
        "candidate_representation_hash": item.get("payload_sha256"), "authoritative_rights_decision_id": None,
        "source_record_id": None, "acquisition_lineage_ids": [], "affirmative_transmission_permission": False,
        "disposition": "EXCLUDED_FROM_TRANSMISSION",
        "reason": "No artifact-bound rights decision, governed source record, acquisition lineage, or exact authorized transmitted-representation binding is present."}
        for item in candidate_evidence]
    by_family = {}
    for row in rights_bindings:
        family = row["source_family"]
        by_family[family] = by_family.get(family, 0) + 1
    write("rights-binding-ledger.json", {"candidate_evidence_count": len(rights_bindings),
        "authorized_count": 0, "excluded_count": len(rights_bindings), "excluded_by_family": by_family,
        "policy_identity": "CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1 is a policy identity, not an artifact-level decision",
        "bindings": rights_bindings})
    write("request-compilation-status.json", {"status": "NOT_COMPILED",
        "candidate_question_count": len(packet_doc.get("packets", [])), "final_execution_packets": 0,
        "prompt_present_in_candidate": False, "strict_provider_response_json_schema_present": False,
        "runtime_v1_5_contract_schema": "charitygraph.generic-discovery-demand-contract/v1.5",
        "runtime_validator": "validate_discovery_result", "note": "The available validator is structural validation code, not a provider response JSON Schema. Constructing a prompt or output schema here would create new semantic execution bindings."})
    write("trusted-authorization-status.json", {"product_owner_decision": "Greg authorized up to USD 2.00 for one 36-case run",
        "run_bound_authorization_artifact": None, "provider_gate": "RealProviderExecutionGate default-deny; authorization must match run_id and plan_hash",
        "status": "NOT_REQUESTABLE_UNTIL_EXACT_REQUEST_PLAN_EXISTS", "additional_trusted_confirmation": "required by user instruction"})

    attempts = [{"question_id": p["envelope"]["bound_question_identity"], "packet_identity": p["packet_identity"],
                 "attempt_count": 0, "physical_request_count": 0, "status": "BLOCKED_NOT_ISSUED",
                 "provider_request_sha256": None, "provider_response_sha256": None, "validation": "NOT_RUN",
                 "usage": None, "cost_usd": "0.000000", "failure": "pre-transmission integrity gate: " + " ".join(blocked_reasons)}
                for p in packet_doc.get("packets", [])]
    write("verified-frozen-inputs.json", {"expected": EXPECTED, "actual": {"branch": branch, "head": head,
        "packet_manifest_sha256": digest(packet_bytes), "acquisition_ledger_sha256": digest(acquisition_bytes),
        "preflight_inventory_sha256": digest(preflight_inventory_bytes)}, "checks": checks,
        "acquired_source_object_hashes_checked": len(source_hash_checks), "source_object_hash_checks": source_hash_checks,
        "status": "PASS_HASHES_BUT_EXECUTION_GATES_FAIL" if checks["all_acquired_source_hashes_verified"] else "FAIL"})
    write("attempt-ledger.json", {"question_count": len(attempts), "attempts": attempts, "physical_semantic_requests": 0, "retries": 0})
    write("validation-results.json", {"status": "NOT_RUN", "reason": "No requests issued because rights and executable request configuration were not established."})
    write("failures-and-missingness.json", {"status": "BLOCKED_BEFORE_TRANSMISSION", "blocked_question_count": len(attempts), "reasons": blocked_reasons})
    write("experiment-configuration.json", {"requested": {"model": "gpt-5.6-luna", "reasoning_effort": "low", "delivery_mode": "standard", "max_physical_requests": 36, "retries": 0, "aggregate_max_usd": "2.00"}, "frozen_packet_configuration": "ABSENT", "trusted_local_provider_authorization": "NOT_ESTABLISHED_FOR_THIS_RUN", "semantic_provider_calls": 0})
    (OUT / "raw-responses.jsonl").write_bytes(b"")
    manifest = {"schema": "charitygraph.g3-fresh36-semantic-execution/v1", "status": "G3_FRESH36_EXECUTION_BLOCKED",
        "branch": branch, "head": head, "physical_requests": 0, "successful_http_responses": 0,
        "mechanically_valid_outputs": 0, "failed_or_invalid_outputs": 0, "not_issued": len(attempts),
        "actual_usd": "0.000000", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        "oracle_access": 0, "retries": 0, "baseline_changes": 0, "blocked_reasons": blocked_reasons,
        "input_checks": checks, "candidate_evidence_objects": len(rights_bindings),
        "rights_approved_evidence_objects": 0, "excluded_evidence_objects": len(rights_bindings),
        "excluded_by_family": by_family, "final_execution_packets": 0}
    manifest["execution_manifest_sha256"] = digest(canonical(manifest))
    write("execution-manifest.json", manifest)
    inventory = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name not in {"artifact-sha256-inventory.json", "inventory-sha256.txt"}:
            inventory[path.name] = digest(path.read_bytes())
    write("artifact-sha256-inventory.json", {"artifacts": inventory})
    inv_hash = digest((OUT / "artifact-sha256-inventory.json").read_bytes())
    (OUT / "inventory-sha256.txt").write_text(inv_hash + "  artifact-sha256-inventory.json\n", encoding="ascii")
    print(json.dumps({"checks": checks, "blocked_reasons": blocked_reasons, "execution_manifest_sha256": manifest["execution_manifest_sha256"], "inventory_sha256": inv_hash}, sort_keys=True))

if __name__ == "__main__":
    main()
