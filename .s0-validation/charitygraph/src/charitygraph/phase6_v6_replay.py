"""Diagnostic replay of unchanged historical V4 Outcomes responses under V6."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from .openai_client import _output_text
from .phase6_semantic_contracts import (
    OutcomeClaimV6, Phase6SemanticOutputV6Replay, phase6_v5_validation_context,
    validate_scope_bindings,
)
from .phase6_v5_campaign import CONDITION_A_MANIFEST_SHA256, _sha, _task_map
from .phase6_v6_campaign import V4_REQUEST_IDS, V4_RESPONSE_SHA256


def replay_outcomes_v4_under_v6(source_dir: Path, v4_review_dir: Path) -> dict[str, Any]:
    """Validate immutable V4 output bytes with the V6 shape and source bindings."""
    source_manifest, tasks = _task_map(source_dir)
    if source_manifest.get("condition_a_manifest_sha256", CONDITION_A_MANIFEST_SHA256) != CONDITION_A_MANIFEST_SHA256:
        raise ValueError("frozen Condition A manifest identity mismatch")
    records = []
    for abn, expected_hash in V4_RESPONSE_SHA256.items():
        path = v4_review_dir / "raw-v4-provider-responses" / f"requestitem_{V4_REQUEST_IDS[abn]}.json"
        raw = path.read_bytes()
        digest = _sha(raw)
        if digest != expected_hash:
            raise ValueError(f"historical V4 response bytes changed for {abn}")
        response = json.loads(raw.decode("utf-8"))
        packet = json.loads(_output_text(response))
        task = tasks[("outcomes", abn)]
        if packet.get("contract_version") != "phase6-corrected-contracts-v3":
            raise ValueError("historical contract echo changed")
        prop_errors = []
        adapter = TypeAdapter(list[OutcomeClaimV6])
        try:
            parsed = Phase6SemanticOutputV6Replay.model_validate(packet)
            validate_scope_bindings(parsed, {task["allowed_scope_ids"][0]["scope_id"]})
            for proposition in parsed.propositions:
                _validate_bindings(proposition, task)
            state = "passes"
            count = len(parsed.propositions)
        except ValidationError as exc:
            state = "fails_v6_observation_basis"
            errors = exc.errors(include_input=False)
            count = len(packet.get("propositions", []))
            # Validate each original proposition independently so that one new
            # requirement does not hide unrelated V6 regressions in the record.
            for index, proposition in enumerate(packet.get("propositions", [])):
                try:
                    with phase6_v5_validation_context():
                        one = adapter.validate_python([proposition])[0]
                    _validate_bindings(one, task)
                except ValidationError as item_exc:
                    prop_errors.extend({"proposition_index": index, "loc": item["loc"], "type": item["type"], "message": item["msg"]} for item in item_exc.errors(include_input=False))
                except ValueError as item_exc:
                    prop_errors.append({"proposition_index": index, "type": "binding_error", "message": str(item_exc)})
            # Keep concise validation paths and messages; never serialize source text.
            errors = [{"loc": item["loc"], "type": item["type"], "message": item["msg"]} for item in errors]
        except ValueError as exc:
            state, count, errors = "fails_v6_binding", len(packet.get("propositions", [])), [{"message": str(exc)}]
        else:
            errors = []
        records.append({
            "abn": abn, "subject_name": task["subject_name"], "request_item_id": f"requestitem:{V4_REQUEST_IDS[abn]}",
            "response_sha256": digest, "proposition_count": count,
            "v6_replay_status": state, "v6_validation_errors": errors,
            "per_proposition_unintended_failures": prop_errors,
            "valid_propositions_under_v6": count - len({item["proposition_index"] for item in prop_errors}),
            "response_bytes_modified": False,
        })
    return {
        "report_type": "phase6_v6_offline_replay_of_unchanged_v4_outcomes",
        "condition_a_manifest_sha256": CONDITION_A_MANIFEST_SHA256,
        "response_count": len(records),
        "pass_count": sum(item["v6_replay_status"] == "passes" for item in records),
        "expected_semantic_rejection_count": sum(item["v6_replay_status"] == "fails_v6_observation_basis" for item in records),
        "unexpected_binding_failure_count": sum(item["v6_replay_status"] == "fails_v6_binding" for item in records),
        "records": records,
        "provider_calls": 0,
        "source_acquisitions": 0,
    }


def _validate_bindings(proposition: Any, task: dict[str, Any]) -> None:
    allowed_scope = task["allowed_scope_ids"][0]
    if proposition.scope.scope_kind != allowed_scope["scope_kind"] or proposition.scope.scope_label != allowed_scope["label"]:
        raise ValueError("scope kind/label differs from frozen task")
    sources = {source["evidence_locator_id"]: source for source in task["sources"]}
    for evidence in getattr(proposition, "evidence", ()):
        source = sources.get(evidence.locator_id)
        if source is None or evidence.source_role != source["source_role"]:
            raise ValueError("source locator or carrier role differs from frozen task")
        if evidence.source_date is not None or evidence.retrieved_at is not None:
            raise ValueError("historical output adds dates absent from frozen evidence")
