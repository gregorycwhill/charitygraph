"""Read-only diagnostic replay of frozen Phase 6 V4 provider responses.

This module deliberately has no provider client or candidate-store dependency.
It only parses supplied response bytes against the V4 and V5 contracts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .openai_client import _output_text
from .phase6_confirmation import mechanical_validate_v5_replay
from .phase6_semantic_contracts import Phase6SemanticOutput


def replay_v4_response_set(
    response_paths: list[Path],
    tasks: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Return a non-mutating V4/V5 validation ledger for the exact response files."""
    records: list[dict[str, Any]] = []
    for response_path in sorted(response_paths):
        raw = response_path.read_bytes()
        response = json.loads(raw.decode("utf-8"))
        packet = json.loads(_output_text(response))
        task = tasks[(packet["slice_id"], packet["subject_id"])]
        v4_errors: list[dict[str, Any]] = []
        try:
            Phase6SemanticOutput.model_validate(packet)
        except ValidationError as exc:
            v4_errors = [
                error for error in exc.errors(include_input=False)
                if "first-party epistemic class conflicts with source role" in error["msg"]
            ]
        try:
            parsed = mechanical_validate_v5_replay(task, packet)
            v5_state = "passes"
            v5_errors: list[dict[str, Any]] = []
            proposition_count = len(parsed.propositions)
        except ValidationError as exc:
            v5_state = "fails"
            v5_errors = exc.errors(include_input=False)
            proposition_count = len(packet.get("propositions", ()))
        records.append({
            "response_file": response_path.name,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "logical_task_id": response.get("metadata", {}).get("logical_task_id"),
            "slice_id": packet["slice_id"],
            "subject_id": packet["subject_id"],
            "v4_carrier_rule_error_count": len(v4_errors),
            "v5_replay_state": v5_state,
            "v5_errors": v5_errors,
            "proposition_count": proposition_count,
        })
    return {
        "report_type": "phase6_v5_offline_replay",
        "response_count": len(records),
        "v4_carrier_rule_error_count": sum(item["v4_carrier_rule_error_count"] for item in records),
        "v5_pass_count": sum(item["v5_replay_state"] == "passes" for item in records),
        "v5_fail_count": sum(item["v5_replay_state"] == "fails" for item in records),
        "records": records,
    }


def write_private_replay_report(path: Path, report: dict[str, Any]) -> str:
    """Write a deterministic private diagnostic artifact and return its SHA-256."""
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()
