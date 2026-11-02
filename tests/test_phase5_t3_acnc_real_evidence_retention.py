from __future__ import annotations

import base64
from datetime import date

import pytest

from charitygraph.phase5_t3_acnc_real_evidence_retention import (
    RetentionInputError,
    bind_retained_acnc_source_evidence,
    retain_acnc_source_evidence,
)


def _fixture() -> dict:
    subject_id = "subject:" + "1" * 32
    scope_id = "scope:" + "2" * 32
    return {
        "subject_id": subject_id,
        "scope_id": scope_id,
        "subject": {"id": subject_id, "subject_id": subject_id, "subject_kind": "charity"},
        "scope": {"id": scope_id, "scope_id": scope_id, "subject_id": subject_id, "scope_kind": "organisation"},
        "source_family": "acnc_register",
        "source_role": "register_identity",
        "source_url": "https://www.acnc.gov.au/for-charities/manage-your-charity/charity-register",
        "raw_bytes": b"offline ACNC register source-native bytes",
        "representation": {"registered_name": "Offline Fixture Charity", "abn": "52000399744"},
        "acquired_at": "2026-11-02T11:30:00+11:00",
        "source_definition_id": "srcdef:" + "3" * 64,
        "source_record_id": "srcrec:" + "4" * 64,
    }


def test_positive_local_retention_preserves_exact_bytes_and_explicit_rights_states():
    fixture = _fixture()
    retained = retain_acnc_source_evidence(**fixture)

    assert retained.source_bytes == fixture["raw_bytes"]
    assert base64.b64decode(retained.as_dict()["source_bytes_base64"]) == fixture["raw_bytes"]
    assert retained.source_sha256 != retained.representation_sha256
    assert retained.acquisition_receipt["outcome"] == "available"
    assert retained.acquired_at_utc == "2026-11-02T00:30:00Z"
    assert retained.provider_processing_status == "blocked"
    assert retained.public_redistribution_status == "not_assessed"

    result = bind_retained_acnc_source_evidence(retained, as_of=date(2026, 11, 2))
    assert result.bound_count == 0
    assert "private_provider_processing_rights_decision_not_observed" in result.rows[0].reasons


def test_source_and_representation_have_independent_content_identities():
    retained = retain_acnc_source_evidence(**_fixture())

    assert retained.source_artifact_id.startswith("srcblob:")
    assert retained.representation_artifact_id.startswith("artifact:")
    assert retained.source_artifact_id != retained.representation_artifact_id
    assert retained.source_sha256 == retained.source_artifact_id.removeprefix("srcblob:")
    assert retained.representation_sha256 == retained.representation_artifact_id.removeprefix("artifact:")

    same_bytes = _fixture()
    same_bytes["representation"] = same_bytes["raw_bytes"]
    with pytest.raises(RetentionInputError, match="identities must remain distinct"):
        retain_acnc_source_evidence(**same_bytes)


def test_wrong_subject_or_scope_fails_closed_before_retention():
    wrong_subject = _fixture()
    wrong_subject["subject"] = {**wrong_subject["subject"], "subject_id": "subject:" + "f" * 32, "id": "subject:" + "f" * 32}
    with pytest.raises(RetentionInputError, match="does not match"):
        retain_acnc_source_evidence(**wrong_subject)

    wrong_scope = _fixture()
    wrong_scope["scope"] = {**wrong_scope["scope"], "subject_id": "subject:" + "f" * 32}
    with pytest.raises(RetentionInputError, match="different durable subject"):
        retain_acnc_source_evidence(**wrong_scope)


def test_missing_acquisition_receipt_never_binds():
    retained = retain_acnc_source_evidence(**_fixture())
    result = bind_retained_acnc_source_evidence(
        retained,
        existing={"acquisition_receipts": []},
    )

    row = result.rows[0]
    assert row.status == "MISSING"
    assert "acquisition_receipt_not_observed" in row.reasons
    assert row.governed_reference is None


def test_missing_provider_and_public_rights_are_explicit_and_never_inferred():
    retained = retain_acnc_source_evidence(**_fixture())
    existing = retained.binder_existing()
    assert len(existing["rights_decisions"]) == 1
    assert existing["rights_decisions"][0]["axis"] == "local_retention"

    result = bind_retained_acnc_source_evidence(retained)
    row = result.rows[0]
    assert "private_provider_processing_rights_decision_not_observed" in row.reasons
    assert row.governed_reference is None

