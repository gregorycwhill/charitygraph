from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from charitygraph.phase5_t3_acnc_real_evidence_retention import (
    PUBLICDATA_REGISTER_BATCH_EXPECTATIONS,
    RetentionInputError,
    bind_retained_acnc_source_evidence,
    retain_publicdata_acnc_register_batch_entry,
)


TRANSPORT_PATH = Path(
    "C:\\Users\\grego\\My Drive\\CharityGraph Agent Bridge\\artifacts\\"
    "cg-g4-source-transport-publicdata-acnc-register-20261026-remaining-four-20261103.json"
)
TRANSPORT_SHA256 = "5cd5fc916d6356f147f7218cb9ade9c167bedff4a760a7d8fb08ddafcec92f73"
MANIFEST_PATH = Path("evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json")


def _transport() -> dict:
    if not TRANSPORT_PATH.exists():
        pytest.fail(f"verified local transport artifact is missing: {TRANSPORT_PATH}")
    raw = TRANSPORT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == TRANSPORT_SHA256
    return json.loads(raw)


def _targets() -> dict[str, dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {row["abn"]: row for row in manifest["rows"] if row["source_family"] == "acnc_register"}


def _subject_scope(row: dict, name: str, abn: str) -> tuple[dict, dict]:
    subject_id = row["subject_id"]
    scope_id = row["scope_id"]
    return (
        {
            "id": subject_id,
            "subject_id": subject_id,
            "subject_kind": "legal_entity",
            "display_name": name,
            "external_identifiers": [{"scheme": "ABN", "value": abn, "issuing_authority": "Australian Business Register"}],
        },
        {"id": scope_id, "scope_id": scope_id, "subject_id": subject_id, "scope_kind": "registered_entity"},
    )


def _provider_decision(retained) -> dict:
    return {
        "axis": "private_provider_processing",
        "decision_id": f"rights:private-provider:{retained.representation_sha256}",
        "source_artifact_id": retained.source_artifact_id,
        "source_record_id": retained.source_record_id,
        "representation_artifact_id": retained.representation_artifact_id,
        "representation_sha256": retained.representation_sha256,
        "scope_id": retained.scope_id,
        "acquisition_receipt_id": retained.acquisition_receipt_id,
        "acquisition_lineage_ids": [retained.acquisition_receipt_id],
        "decision_version": "1",
        "status": "authorized",
        "assessed_on": "2026-11-03",
        "review_deadline": "2027-11-03",
        "lawful_public_access": True,
        "circumvention_used": False,
        "explicit_prohibition_found": False,
        "authority_kind": "governed_policy",
        "policy_id": "CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1",
        "policy_version": "1.0.0",
        "provider_policy_id": "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
        "provider_policy_version": "1",
        "provider_no_training_default": True,
        "provider_data_sharing_opt_in": False,
        "provider_call_authorized": False,
        "public_redistribution_allowed": False,
        "rights_basis": "public_source_private_processing",
        "licence_identifier": "CC-BY-3.0-AU",
        "licence_or_terms_url": "https://creativecommons.org/licenses/by/3.0/au/",
    }


def test_four_real_batch_entries_hash_and_bind_through_existing_t3():
    transport = _transport()
    targets = _targets()
    assert len(transport["entries"]) == 4
    assert set(targets) >= set(PUBLICDATA_REGISTER_BATCH_EXPECTATIONS)

    for entry in transport["entries"]:
        body = json.loads(entry["response_raw_utf8"])
        row = targets[entry["abn"]]
        subject, scope = _subject_scope(row, body["rows"][0]["charity_legal_name"], entry["abn"])
        retained = retain_publicdata_acnc_register_batch_entry(
            transport,
            entry,
            subject_id=row["subject_id"],
            scope_id=row["scope_id"],
            subject=subject,
            scope=scope,
        )
        provider = _provider_decision(retained)
        retained = retain_publicdata_acnc_register_batch_entry(
            transport,
            entry,
            subject_id=row["subject_id"],
            scope_id=row["scope_id"],
            subject=subject,
            scope=scope,
            rights_authority={"private_provider_processing": provider},
        )
        expected_bytes, expected_sha = PUBLICDATA_REGISTER_BATCH_EXPECTATIONS[entry["abn"]]
        assert len(retained.source_bytes) == expected_bytes
        assert retained.source_sha256 == expected_sha
        assert retained.source_sha256 != retained.representation_sha256
        assert retained.representation["source_provenance"]["publisher_original_bytes"] is False
        assert retained.representation["source_provenance"]["response_fields"] == 69
        result = bind_retained_acnc_source_evidence(retained, ordinal=row["ordinal"], as_of=date(2026, 11, 3))
        assert result.bound_count == 1
        assert result.rows[0].status == "BOUND"


def test_batch_response_tampering_fails_closed_before_retention():
    transport = _transport()
    entry = copy.deepcopy(transport["entries"][0])
    entry["response_raw_utf8"] = entry["response_raw_utf8"].replace("Human Appeal", "Human Appeal X", 1)
    target = _targets()[entry["abn"]]
    with pytest.raises(RetentionInputError, match="length or independently observed SHA-256"):
        retain_publicdata_acnc_register_batch_entry(
            transport,
            entry,
            subject_id=target["subject_id"],
            scope_id=target["scope_id"],
            subject={"id": target["subject_id"], "subject_id": target["subject_id"], "external_identifiers": [{"scheme": "ABN", "value": entry["abn"]}]},
            scope={"id": target["scope_id"], "scope_id": target["scope_id"], "subject_id": target["subject_id"], "scope_kind": "registered_entity"},
        )
