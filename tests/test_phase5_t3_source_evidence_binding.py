from __future__ import annotations

import copy
import hashlib
import json
from datetime import date

from charitygraph.phase5_t3_source_evidence_binding import (
    LOCAL_RETENTION_POLICY_ID,
    LOCAL_RETENTION_POLICY_VERSION,
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
    bind_acnc_source_evidence,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture(index: int = 1) -> tuple[dict, dict, dict[str, bytes]]:
    subject = f"subject:{index:032x}"
    scope = f"scope:{index:032x}"
    source_artifact = f"srcblob:{index:032x}"
    source_record = f"srcrec:{index:032x}"
    source_definition = f"srcdef:{index:032x}"
    receipt = f"acq:{index:032x}"
    source_body = f"ACNC source-native record {index}".encode()
    representation_body = f"ACNC structured factual representation {index}".encode()
    representation_artifact = f"artifact:{_sha(representation_body)}"
    row = {
        "ordinal": index,
        "subject_id": subject,
        "scope_id": scope,
        "evidence_scope": {"scope_id": scope, "scope_kind": "organisation", "subject_id": subject},
        "source_family": "acnc_register",
        "source_role": "register_identity",
        "source_definition_id": source_definition,
        "source_record_id": source_record,
        "source_artifact_id": source_artifact,
        "source_sha256": _sha(source_body),
        "acquisition_receipt_id": receipt,
        "representation_artifact_id": representation_artifact,
        "observation_kind": "observation",
    }
    source = {
        "id": source_record,
        "source_family": "acnc_register",
        "source_role": "register_identity",
        "about_subject_ids": [subject],
        "payload_ref": source_artifact,
        "payload_hash": row["source_sha256"],
        "source_locator": "https://example.invalid/acnc/register/record",
        "evidence_scope": row["evidence_scope"],
        "date_or_period": "2026-10-01",
    }
    representation = {
        "id": representation_artifact,
        "artifact_id": representation_artifact,
        "content_hash": _sha(representation_body),
        "source_artifact_id": source_artifact,
        "source_record_id": source_record,
        "subject_id": subject,
        "scope_id": scope,
        "representation_class": "structured_factual",
        "evidence_locator_ids": [f"locator:{index:032x}"],
        "citation_locator": "https://example.invalid/acnc/register/record#name",
        "date_or_period": "2026-10-01",
    }
    common = {
        "source_artifact_id": source_artifact,
        "source_record_id": source_record,
        "representation_artifact_id": representation_artifact,
        "representation_sha256": representation["content_hash"],
        "scope_id": scope,
        "decision_version": "1",
        "decision_id": None,
        "status": "authorized",
        "assessed_on": "2026-10-01",
        "review_deadline": "2027-10-01",
        "lawful_public_access": True,
        "circumvention_used": False,
        "explicit_prohibition_found": False,
        "authority_kind": "governed_policy",
    }
    local = {
        **common,
        "axis": "local_retention",
        "decision_id": f"rights:local:{index}",
        "policy_id": LOCAL_RETENTION_POLICY_ID,
        "policy_version": LOCAL_RETENTION_POLICY_VERSION,
    }
    provider = {
        **common,
        "axis": "private_provider_processing",
        "decision_id": f"rights:provider:{index}",
        "policy_id": PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,
        "policy_version": "1.0.0",
        "provider_policy_id": OPENAI_PROVIDER_POLICY_ID,
        "provider_policy_version": "1",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
    }
    existing = {
        "subjects": [{"id": subject, "subject_id": subject, "subject_kind": "charity"}],
        "scopes": [{"id": scope, "scope_id": scope, "subject_id": subject, "scope_kind": "organisation"}],
        "source_definitions": [{"id": source_definition, "source_definition_id": source_definition}],
        "source_records": [source],
        "acquisition_receipts": [{
            "id": receipt,
            "source_definition_id": source_definition,
            "artifact_id": source_artifact,
            "content_hash": row["source_sha256"],
            "outcome": "available",
            "acquired_on": "2026-10-01",
        }],
        "representations": [{**representation, "content": representation_body}],
        "rights_decisions": [local, provider],
    }
    return row, existing, {source_artifact: source_body, representation_artifact: representation_body}


def test_confirmed_binding_contains_durable_identity_scope_receipt_rights_and_factory_reference():
    row, existing, retained = _fixture()
    result = bind_acnc_source_evidence([row], existing=existing, retained_bytes=retained, as_of=date(2026, 11, 1))

    bound = result.rows[0]
    assert result.bound_count == 1
    assert bound.status == "BOUND"
    assert bound.governed_reference is not None
    assert bound.governed_reference.subject_id == row["subject_id"]
    assert bound.governed_reference.scope_id == row["scope_id"]
    assert bound.representation_sha256 != row["source_sha256"]
    assert bound.citation_locator.endswith("#name")
    assert bound.date_or_period == "2026-10-01"
    assert bound.observation_kind == "observation"


def test_no_source_or_body_is_missingness_and_never_factory_work():
    row, existing, _ = _fixture()
    existing["source_records"] = []
    existing["acquisition_receipts"] = []
    existing["rights_decisions"] = []
    existing["representations"][0].pop("content")
    result = bind_acnc_source_evidence([row], existing=existing)

    item = result.rows[0]
    assert item.status == "MISSING"
    assert item.observation_kind == "missingness"
    assert item.governed_reference is None
    assert "source_record_not_observed" in item.reasons
    assert "representation_bytes_not_observed" in item.reasons


def test_stale_receipt_mismatched_sha_wrong_subject_and_ambiguous_destination_fail_closed():
    row, existing, _ = _fixture()
    stale = copy.deepcopy(existing)
    stale["acquisition_receipts"][0]["status"] = "stale"
    assert "acquisition_receipt_stale" in bind_acnc_source_evidence([row], existing=stale).rows[0].reasons

    altered = copy.deepcopy(existing)
    altered["representations"][0]["content"] = b"altered bytes"
    assert "representation_bytes_sha_mismatch" in bind_acnc_source_evidence([row], existing=altered).rows[0].reasons

    wrong_subject = copy.deepcopy(existing)
    wrong_subject["source_records"][0]["about_subject_ids"] = ["subject:" + "f" * 32]
    assert "source_record_wrong_subject" in bind_acnc_source_evidence([row], existing=wrong_subject).rows[0].reasons

    ambiguous = copy.deepcopy(existing)
    ambiguous["source_records"][0]["about_subject_ids"] = [row["subject_id"], "subject:" + "e" * 32]
    assert "ambiguous_destination" in bind_acnc_source_evidence([row], existing=ambiguous).rows[0].reasons


def test_rights_block_version_mismatch_and_cross_scope_do_not_bind():
    row, existing, _ = _fixture()
    version = copy.deepcopy(existing)
    version["rights_decisions"][1]["provider_policy_version"] = "9"
    assert "private_provider_processing_rights_policy_version_mismatch" in bind_acnc_source_evidence([row], existing=version).rows[0].reasons

    blocked = copy.deepcopy(existing)
    blocked["rights_decisions"][1]["status"] = "blocked"
    assert "private_provider_processing_rights_blocked" in bind_acnc_source_evidence([row], existing=blocked).rows[0].reasons

    cross_scope = copy.deepcopy(existing)
    cross_scope["representations"][0]["scope_id"] = "scope:" + "f" * 32
    assert "representation_scope_mismatch" in bind_acnc_source_evidence([row], existing=cross_scope).rows[0].reasons


def test_duplicate_source_and_rights_reuse_are_rejected():
    row, existing, _ = _fixture()
    second = copy.deepcopy(row)
    second["ordinal"] = 2
    duplicate = bind_acnc_source_evidence([row, second], existing=existing)
    assert all(item.governed_reference is None for item in duplicate.rows)
    assert all("duplicate_source" in item.reasons for item in duplicate.rows)

    reused = copy.deepcopy(existing)
    reused["rights_decisions"].append(copy.deepcopy(reused["rights_decisions"][1]))
    reused["rights_decisions"][2]["representation_artifact_id"] = "artifact:" + "f" * 64
    try:
        bind_acnc_source_evidence([row], existing=reused)
    except ValueError as exc:
        assert "duplicate rights decision identity" in str(exc)
    else:
        raise AssertionError("cross-representation rights reuse was accepted")


def test_candidate_and_explicit_missingness_are_not_observations():
    row, existing, _ = _fixture()
    candidate = copy.deepcopy(row)
    candidate["observation_kind"] = "candidate"
    candidate_result = bind_acnc_source_evidence([candidate], existing=existing)
    assert candidate_result.candidate_count == 1
    assert candidate_result.rows[0].status == "BLOCKED"
    assert "candidate_requires_governance" in candidate_result.rows[0].reasons

    missing = copy.deepcopy(row)
    missing["observation_kind"] = "missingness"
    missing_result = bind_acnc_source_evidence([missing], existing=existing)
    assert missing_result.missing_count == 1
    assert missing_result.rows[0].status == "MISSING"
    assert missing_result.rows[0].governed_reference is None


def test_deterministic_replay_is_stable_under_row_permutation():
    row_one, existing_one, _ = _fixture(1)
    row_two, existing_two, _ = _fixture(2)
    merged = {key: existing_one[key] + existing_two[key] for key in existing_one}
    first = bind_acnc_source_evidence([row_one, row_two], existing=merged)
    second = bind_acnc_source_evidence([row_two, row_one], existing=merged)

    assert first.canonical_hash == second.canonical_hash
    assert first.canonical_bytes() == second.canonical_bytes()


def test_selected_five_subject_ten_row_manifest_is_honestly_all_missing():
    manifest_path = "evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json"
    result = bind_acnc_source_evidence(
        manifest_path,
        existing={},
        require_five_subject_ten_rows=True,
    )

    assert result.all_ten_missing
    assert result.bound_count == 0
    assert len(result.rows) == 10
    assert len({row.subject_id for row in result.rows}) == 5
    assert all(row.observation_kind == "missingness" for row in result.rows)
    assert all(row.status == "MISSING" for row in result.rows)
    assert all(row.governed_reference is None for row in result.rows)
    assert all("source_record_not_observed" in row.reasons for row in result.rows)
    assert b"ACNC structured factual representation" not in result.canonical_bytes()


def test_changed_source_policy_fails_closed():
    row, existing, _ = _fixture()
    result = bind_acnc_source_evidence(
        {"source_universe_version": "v2", "rows": [row]},
        existing=existing,
    )
    assert result.rows[0].governed_reference is None
    assert "source_policy_version_mismatch" in result.rows[0].reasons
