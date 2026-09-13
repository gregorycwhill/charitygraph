import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from charitygraph.phase5_standard_transport import StandardAmbiguous, StandardProviderResponse
from charitygraph.phase6_confirmation import (
    _canonical,
    execute_run,
    prepare_review_materials,
    prepare_run,
    provider_schema,
)


ABN = "12345678901"
SUBJECT_ID = "subject:test-phase6-confirmation"
SCOPE = {
    "scope_id": "scope:test-phase6-confirmation",
    "scope_kind": "organisation",
    "label": "Test Charity",
    "resolution": "private_experiment_candidate_only",
}


def _write_export(root: Path, monkeypatch, *, slice_id="outcomes", repeat=True):
    root.mkdir()
    task = {
        "task_id": f"phase6-condition-a:{slice_id}:{ABN}",
        "condition": "A_source_only",
        "slice_id": slice_id,
        "subject_id": SUBJECT_ID,
        "subject_name": "Test Charity",
        "abn": ABN,
        "analyst_questions": ["What is explicitly supported?"],
        "allowed_scope_ids": [SCOPE],
        "additional_program_or_service_scope_ids": [],
        "scope_note": "Organization scope only.",
        "sources": [{
            "source_record_id": "srcrec:test",
            "source_family": "official_website",
            "source_role": "official_homepage",
            "evidence_locator_id": "locator:test",
            "source_date": "unknown unless stated in supplied text",
            "retrieved_at": "not recorded in clean corpus manifest",
            "effective_period": None,
            "exact_transmitted_representation": "A frozen source representation for private test fixtures.",
        }],
        "unavailable_sources": [],
    }
    raw = _canonical(task) + b"\n"
    (root / "tasks").mkdir()
    (root / "tasks" / "task.json").write_bytes(raw)
    manifest = {
        "provider_calls": 0,
        "source_acquisitions": 0,
        "candidate_outputs_read": 0,
        "candidate_propositions_included": 0,
        "answer_fields_included": 0,
        "tasks": [{
            "task_id": task["task_id"],
            "path": "tasks/task.json",
            "task_sha256": hashlib.sha256(raw).hexdigest(),
            "source_input_hashes": ["a" * 64],
            "source_count": 1,
            "source_repeat_count": 1,
        }],
        "task_count": 1,
    }
    manifest_raw = _canonical(manifest) + b"\n"
    (root / "manifest.json").write_bytes(manifest_raw)
    monkeypatch.setattr("charitygraph.phase6_confirmation.CONDITION_A_MANIFEST_SHA256", hashlib.sha256(manifest_raw).hexdigest())
    monkeypatch.setattr("charitygraph.phase6_confirmation.COHORTS", {slice_id: {ABN: ("test boundary", repeat)}})
    return task, manifest


def _walk_schema(schema):
    if isinstance(schema, dict):
        yield schema
        for key in ("properties", "$defs"):
            for item in schema.get(key, {}).values():
                yield from _walk_schema(item)
        if isinstance(schema.get("items"), dict):
            yield from _walk_schema(schema["items"])
        for item in schema.get("anyOf", []):
            yield from _walk_schema(item)
    elif isinstance(schema, list):
        for item in schema:
            yield from _walk_schema(item)


@pytest.mark.parametrize("slice_id, expected_variants", [("outcomes", 7), ("commitments", 6), ("capacity", 11)])
def test_provider_schema_is_slice_bound_strict_supported_anyof(slice_id, expected_variants):
    schema = provider_schema(slice_id, SUBJECT_ID, SCOPE, ["locator:a", "locator:b"])
    assert schema["type"] == "object"
    assert schema["properties"]["slice_id"]["enum"] == [slice_id]
    assert schema["properties"]["subject_id"]["enum"] == [SUBJECT_ID]
    assert len(schema["properties"]["propositions"]["items"]["anyOf"]) == expected_variants
    raw = json.dumps(schema)
    assert "oneOf" not in raw and "discriminator" not in raw and '"const"' not in raw
    for value in _walk_schema(schema):
        if value.get("type") == "object":
            assert value["additionalProperties"] is False
            assert set(value["required"]) == set(value["properties"])
    if slice_id == "capacity":
        assert "CurrentAvailability" not in schema["$defs"]


def test_prepare_pins_exact_repeat_identity_cost_and_unique_tickets(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _task, _manifest = _write_export(export, monkeypatch)
    run = tmp_path / "run"
    result = prepare_run(export, run)
    prepared = json.loads((run / "execution-manifest.json").read_bytes())
    assert result["task_count"] == 2
    assert result["provider_calls"] == 0
    assert result["source_acquisitions"] == 0
    assert result["conservative_exposure_total_aud"] == "0.032370"
    assert len({row["request_item_id"] for row in prepared["tasks"]}) == 2
    assert len({row["physical_attempt_id"] for row in prepared["tasks"]}) == 2
    first, second = prepared["tasks"]
    assert first["prompt_sha256"] == second["prompt_sha256"]
    assert first["schema_sha256"] == second["schema_sha256"]
    assert first["source_content_sha256"] == second["source_content_sha256"]
    assert first["request_body_sha256"] != second["request_body_sha256"]
    assert "A frozen source representation" not in (run / "execution-manifest.json").read_text(encoding="utf-8")
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select count(*) from tickets where state='prepared'").fetchone()[0] == 2


def test_execute_is_one_shot_and_review_packets_leave_reviewer_fields_blank(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch)
    run = tmp_path / "run"
    prepare_run(export, run)
    preflight = execute_run(run, export, dry_run=True)
    assert preflight["preflight"] == "passed_no_provider_crossing"
    assert preflight["provider_calls"] == 0
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    class FakeClient:
        calls = 0

        def create_response_once(self, body_bytes):
            self.calls += 1
            req = json.loads(body_bytes)
            packet = {"slice_id": "outcomes", "subject_id": SUBJECT_ID, "propositions": []}
            body = {
                "id": f"resp_test_{self.calls}",
                "model": req["model"],
                "status": "completed",
                "incomplete_details": None,
                "output": [{"content": [{"type": "output_text", "text": json.dumps(packet)}]}],
                "usage": {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}},
            }
            raw = json.dumps(body).encode()
            return StandardProviderResponse(200, f"req_test_{self.calls}", body, raw)

    client = FakeClient()
    monkeypatch.setattr("charitygraph.phase6_confirmation.OpenAIHTTPStandardClient", lambda: client)
    result = execute_run(run, export)
    assert result["provider_calls"] == 2
    assert client.calls == 2
    assert list((run / "candidate-packets").glob("*.json"))
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select count(*) from tickets where state='completed' and provider_posts=1").fetchone()[0] == 2
    materials = prepare_review_materials(run, export)
    assert materials["paired_task_count"] == 1
    assert materials["reviewer_fields_empty"] is True
    assert (run / "review-materials" / "proposition-adjudication-worksheet.csv").exists()
    with pytest.raises(ValueError, match="prior provider crossing"):
        execute_run(run, export)
    assert client.calls == 2


def test_ambiguous_transport_is_not_retried(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=False)
    run = tmp_path / "run"
    prepare_run(export, run)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    class AmbiguousClient:
        calls = 0

        def create_response_once(self, _body):
            self.calls += 1
            raise StandardAmbiguous("synthetic timeout after POST")

    client = AmbiguousClient()
    monkeypatch.setattr("charitygraph.phase6_confirmation.OpenAIHTTPStandardClient", lambda: client)
    result = execute_run(run, export)
    assert result["provider_calls"] == 1
    assert client.calls == 1
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select state from tickets").fetchone()[0] == "ambiguous"
    with pytest.raises(ValueError, match="prior provider crossing"):
        execute_run(run, export)
    assert client.calls == 1
