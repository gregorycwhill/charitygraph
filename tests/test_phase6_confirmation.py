import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from charitygraph.phase5_standard_transport import StandardAmbiguous, StandardProviderResponse
from charitygraph.phase6_confirmation import (
    CONTRACT_VERSION,
    ProviderSchemaCertificationError,
    _canonical,
    _mechanical_validate,
    certify_provider_schema,
    execute_run,
    prepare_review_materials,
    prepare_run,
    provider_schema,
    preflight_provider_rights,
)
from charitygraph.phase6_semantic_contracts import Phase6SemanticOutput, Phase6SemanticOutputV2


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
            "source_artifact_id": "srcblob:test",
            "source_family": "official_website",
            "source_role": "official_homepage",
            "source_locator": "https://example.test/public",
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


def _rights_decisions(export: Path, path: Path) -> Path:
    task = json.loads((export / "tasks" / "task.json").read_text(encoding="utf-8"))
    rows = []
    for source in task["sources"]:
        artifact_id = source["source_artifact_id"]
        rows.append({"decision_id": "rights:" + artifact_id, "source_artifact_id": artifact_id,
            "source_record_id": source["source_record_id"], "source_origin_url": source["source_locator"], "source_role": source["source_role"],
            "acquisition_lineage_ids": ["acq:test"],
            "transmitted_representation_sha256": hashlib.sha256(source["exact_transmitted_representation"].encode()).hexdigest(),
            "rights_policy_id": "CC_BY_4_0_V1", "provider_processing_policy_id": "test-provider", "rights_basis": "explicit_open_license",
            "evidence_locator": "https://example.test/licence", "evidence_sha256": "a" * 64, "assessed_on": str(date.today()),
            "assessment_scope": "private provider", "local_retention_allowed": True, "provider_transmission_allowed": True,
            "public_redistribution_allowed": False, "licence_identifier": "CC BY 4.0", "licence_or_terms_url": "https://creativecommons.org/licenses/by/4.0/"})
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _walk_schema(schema):
    if isinstance(schema, dict):
        yield schema
        for item in schema.values():
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
    assert schema["properties"]["contract_version"]["enum"] == [CONTRACT_VERSION]
    assert len(schema["properties"]["propositions"]["items"]["anyOf"]) == expected_variants
    raw = json.dumps(schema)
    assert "oneOf" not in raw and "discriminator" not in raw and '"const"' not in raw
    assert all("pattern" not in value for value in _walk_schema(schema))
    assert certify_provider_schema(schema)["certification_status"] == "certified"
    for value in _walk_schema(schema):
        if value.get("type") == "object":
            assert value["additionalProperties"] is False
            assert set(value["required"]) == set(value["properties"])
    if slice_id == "capacity":
        assert "CurrentAvailability" not in schema["$defs"]


def test_previously_rejected_v2_provider_schemas_fail_certification():
    fixture_path = Path(__file__).parent / "fixtures" / "phase6" / "previously-rejected-provider-schemas-v2.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert set(fixture["schemas"]) == {"outcomes", "capacity"}
    for record in fixture["schemas"].values():
        with pytest.raises(ProviderSchemaCertificationError, match="pattern"):
            certify_provider_schema(record["schema"], contract_version="phase6-corrected-contracts-v2")


def test_provider_decimal_string_branch_is_locally_validated_after_pattern_removal():
    schema = provider_schema("outcomes", SUBJECT_ID, SCOPE, ["locator:test"])
    decimal_schema = schema["$defs"]["ActivityReported"]["properties"]["count"]
    assert decimal_schema["anyOf"] == [{"type": "number"}, {"type": "string"}, {"type": "null"}]
    invalid = {
        "contract_version": CONTRACT_VERSION,
        "slice_id": "outcomes",
        "subject_id": SUBJECT_ID,
        "propositions": [{
            "proposition_type": "activity_reported",
            "scope": {"scope_id": SCOPE["scope_id"], "scope_kind": "organisation", "scope_label": SCOPE["label"]},
            "evidence": [{"locator_id": "locator:test", "source_role": "official_homepage"}],
            "epistemic_class": "first_party_claim",
            "activity_kind": "service_delivery",
            "reporting_period": None,
            "count": "not-a-number",
            "unit": None,
        }],
    }
    with pytest.raises(Exception) as exc:
        Phase6SemanticOutput.model_validate(invalid)
    assert any(item["type"] == "decimal_parsing" for item in exc.value.errors(include_input=False))


def test_historical_commitments_failure_is_reproduced_and_v3_reports_only_contract_errors():
    fixture_path = Path(__file__).parent / "fixtures" / "phase6" / "commitments-v2-validation-failure.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    historical = fixture["output"]
    with pytest.raises(Exception) as historical_error:
        Phase6SemanticOutputV2.model_validate(historical)
    old_errors = historical_error.value.errors(include_input=False)
    assert len(old_errors) == 6
    assert [item["type"] for item in old_errors].count("union_tag_invalid") == 4
    assert [item["type"] for item in old_errors].count("value_error") == 2
    assert all("source role" in item["msg"] for item in old_errors if item["type"] == "value_error")

    current = {**historical, "contract_version": CONTRACT_VERSION}
    with pytest.raises(Exception) as current_error:
        Phase6SemanticOutput.model_validate(current)
    new_errors = current_error.value.errors(include_input=False)
    assert len(new_errors) == 2
    assert all(item["type"] == "value_error" for item in new_errors)
    assert all("first-party epistemic class conflicts with source role" in item["msg"] for item in new_errors)
    assert [tuple(item["loc"][:2]) for item in new_errors] == [("propositions", 1), ("propositions", 2)]


def test_prepare_pins_exact_repeat_identity_cost_and_unique_tickets(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _task, _manifest = _write_export(export, monkeypatch)
    run = tmp_path / "run"
    result = prepare_run(export, run)
    prepared = json.loads((run / "execution-manifest.json").read_bytes())
    assert result["task_count"] == 2
    assert result["provider_calls"] == 0
    assert result["source_acquisitions"] == 0
    assert result["conservative_exposure_total_aud"] == "0.032374"
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
    import charitygraph.phase6_confirmation as confirmation

    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch)
    run = tmp_path / "run"
    prepare_run(export, run)
    preflight = execute_run(run, export, dry_run=True)
    assert preflight["preflight"] == "passed_no_provider_crossing"
    assert preflight["provider_calls"] == 0
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setattr("charitygraph.phase6_confirmation.V3_EXECUTION_AUTHORIZED", True)
    original_preflight_request = confirmation._preflight_request
    changed_request = False

    def certify_then_mutate_request_file(row, *args):
        nonlocal changed_request
        certified = original_preflight_request(row, *args)
        if not changed_request:
            request_path = run / "requests" / f"{row['request_item_id'].replace(':', '_')}.json"
            request_path.write_text("{}", encoding="utf-8")
            changed_request = True
        return certified

    monkeypatch.setattr(confirmation, "_preflight_request", certify_then_mutate_request_file)

    class FakeClient:
        calls = 0
        sent_hashes = []

        def create_response_once(self, body_bytes):
            self.calls += 1
            self.sent_hashes.append(hashlib.sha256(body_bytes).hexdigest())
            req = json.loads(body_bytes)
            packet = {"contract_version": CONTRACT_VERSION, "slice_id": "outcomes", "subject_id": SUBJECT_ID, "propositions": []}
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
    result = execute_run(run, export, rights_decisions_path=_rights_decisions(export, tmp_path / "rights.json"))
    assert result["provider_calls"] == 2
    assert client.calls == 2
    with open(run / "execution-manifest.json", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    assert set(client.sent_hashes) == {row["request_body_sha256"] for row in manifest["tasks"]}
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


@pytest.mark.parametrize("packet", [{}, {"contract_version": "phase6-corrected-contracts-v2"}])
def test_response_must_echo_certified_v3_contract_version(packet):
    with pytest.raises(ValueError, match="response contract version"):
        _mechanical_validate({}, packet)


def test_campaign_preflight_fails_closed_before_all_posts_on_any_schema_failure(tmp_path, monkeypatch):
    import charitygraph.phase6_confirmation as confirmation

    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=True)
    run = tmp_path / "run"
    prepare_run(export, run)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    client = type("NeverCalledClient", (), {"calls": 0, "create_response_once": lambda self, _body: setattr(self, "calls", self.calls + 1)})()
    monkeypatch.setattr(confirmation, "OpenAIHTTPStandardClient", lambda: client)
    original_certify = confirmation.certify_provider_schema
    certified = 0

    def fail_second_scheduled_schema(schema, *, contract_version=confirmation.CONTRACT_VERSION):
        nonlocal certified
        certified += 1
        if certified == 2:
            raise ProviderSchemaCertificationError("unsupported provider pattern: lookaround")
        return original_certify(schema, contract_version=contract_version)

    monkeypatch.setattr(confirmation, "certify_provider_schema", fail_second_scheduled_schema)
    result = execute_run(run, export, rights_decisions_path=_rights_decisions(export, tmp_path / "rights.json"))
    assert certified == 2  # The entire campaign was preflighted after the first failure.
    assert result["campaign_preflight"] == "failed_local_pre_send"
    assert result["provider_calls"] == 0
    assert result["source_acquisitions"] == 0
    assert result["attempt_authority_consumed"] == 0
    assert client.calls == 0
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        rows = db.execute("select state,provider_posts,certification_status from tickets order by request_item_id").fetchall()
    assert len(rows) == 2
    assert all(state == "prepared" and posts == 0 for state, posts, _status in rows)
    assert "failed_local_pre_send" in {status for _state, _posts, status in rows}
    assert not (run / "execution-results.json").exists()


def test_ambiguous_transport_is_not_retried(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=False)
    run = tmp_path / "run"
    prepare_run(export, run)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setattr("charitygraph.phase6_confirmation.V3_EXECUTION_AUTHORIZED", True)

    class AmbiguousClient:
        calls = 0

        def create_response_once(self, _body):
            self.calls += 1
            raise StandardAmbiguous("synthetic timeout after POST")

    client = AmbiguousClient()
    monkeypatch.setattr("charitygraph.phase6_confirmation.OpenAIHTTPStandardClient", lambda: client)
    result = execute_run(run, export, rights_decisions_path=_rights_decisions(export, tmp_path / "rights.json"))
    assert result["provider_calls"] == 1
    assert client.calls == 1
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select state from tickets").fetchone()[0] == "ambiguous"
    with pytest.raises(ValueError, match="prior provider crossing"):
        execute_run(run, export)
    assert client.calls == 1


def test_v3_readiness_manifest_cannot_cross_provider_without_new_authority(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=False)
    run = tmp_path / "run"
    prepare_run(export, run)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")

    class NeverCalledClient:
        calls = 0

        def create_response_once(self, _body):
            self.calls += 1
            raise AssertionError("provider call is forbidden by the v3 readiness manifest")

    client = NeverCalledClient()
    monkeypatch.setattr("charitygraph.phase6_confirmation.OpenAIHTTPStandardClient", lambda: client)
    result = execute_run(run, export)
    assert result["execution_status"] == "not_authorized_for_v3_provider_calls"
    assert result["provider_calls"] == 0
    assert client.calls == 0
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select state,provider_posts from tickets").fetchall() == [("prepared", 0)]


def test_provider_rights_preflight_fails_closed_without_artifact_decisions(tmp_path, monkeypatch):
    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=False)
    run = tmp_path / "run"
    prepare_run(export, run)
    result = preflight_provider_rights(run, export, None)
    assert result["rights_preflight"] == "failed_closed"
    assert result["blocked_attempt_count"] == 1
    assert result["provider_calls"] == 0


def test_any_unauthorized_artifact_stops_campaign_before_provider_client(tmp_path, monkeypatch):
    import charitygraph.phase6_confirmation as confirmation

    export = tmp_path / "approved-export"
    _write_export(export, monkeypatch, repeat=False)
    run = tmp_path / "run"
    prepare_run(export, run)
    rights_path = _rights_decisions(export, tmp_path / "rights.json")
    decisions = json.loads(rights_path.read_text(encoding="utf-8"))
    decisions[0]["provider_transmission_allowed"] = False
    rights_path.write_text(json.dumps(decisions), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setattr(confirmation, "V3_EXECUTION_AUTHORIZED", True)

    class NeverCalledClient:
        def __init__(self):
            raise AssertionError("rights failure must happen before provider client construction")

    monkeypatch.setattr(confirmation, "OpenAIHTTPStandardClient", NeverCalledClient)
    result = execute_run(run, export, rights_decisions_path=rights_path)
    assert result["execution_status"] == "blocked_by_source_rights"
    assert result["blocked_attempt_count"] == 1
    assert result["provider_calls"] == 0
    with sqlite3.connect(run / "tickets.sqlite3") as db:
        assert db.execute("select state,provider_posts from tickets").fetchall() == [("prepared", 0)]
