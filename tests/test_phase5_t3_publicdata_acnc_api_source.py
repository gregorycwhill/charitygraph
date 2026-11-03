from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from charitygraph.phase5_t3_acnc_real_evidence_retention import (
    PUBLICDATA_REGISTER_BODY_BYTES,
    PUBLICDATA_REGISTER_BODY_SHA256,
    PUBLICDATA_REGISTER_SOURCE_KIND,
    PUBLICDATA_REGISTER_URL,
    PUBLICDATA_REGISTER_VERSION,
    PUBLICDATA_TRANSPORT_SCHEMA,
    RetentionInputError,
    bind_retained_acnc_source_evidence,
    retain_publicdata_acnc_register_transport,
)


TRANSPORT_PATH = Path(
    "C:\\Users\\grego\\My Drive\\CharityGraph Agent Bridge\\artifacts\\"
    "cg-g4-source-transport-publicdata-acnc-register-20261026-abn52000399744-07b83ca8f241.json"
)
SUBJECT_ID = "subject:02649cdcb42049bb8dedd30f2333e150"
SCOPE_ID = "scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248"


def _subject() -> dict:
    return {
        "id": SUBJECT_ID,
        "subject_id": SUBJECT_ID,
        "subject_kind": "legal_entity",
        "display_name": "Guide Dogs NSW/ACT",
        "external_identifiers": [
            {"scheme": "ABN", "value": "52000399744", "issuing_authority": "Australian Business Register"}
        ],
    }


def _scope() -> dict:
    return {
        "id": SCOPE_ID,
        "scope_id": SCOPE_ID,
        "subject_id": SUBJECT_ID,
        "scope_kind": "registered_entity",
    }


def _transport() -> dict:
    if not TRANSPORT_PATH.exists():
        pytest.fail(f"verified local transport artifact is missing: {TRANSPORT_PATH}")
    return json.loads(TRANSPORT_PATH.read_bytes())


def test_verified_publicdata_transport_reaches_existing_t3_binder_without_source_substitution():
    transport = _transport()
    retained = retain_publicdata_acnc_register_transport(
        transport,
        subject_id=SUBJECT_ID,
        scope_id=SCOPE_ID,
        subject=_subject(),
        scope=_scope(),
    )

    assert retained.source_family == "acnc_register"
    assert retained.source_role == "register_identity"
    assert retained.source_sha256 == PUBLICDATA_REGISTER_BODY_SHA256
    assert len(retained.source_bytes) == PUBLICDATA_REGISTER_BODY_BYTES
    assert retained.source_bytes == transport["http_body_utf8"].encode("utf-8")
    assert retained.source_sha256 != retained.representation_sha256
    assert retained.acquisition_receipt["method"] == "caller_supplied_publicdata_api_transport"
    assert retained.acquisition_receipt["source_provenance"]["publisher_original_bytes"] is False
    assert retained.representation["source_provenance"]["currentness"]["source_version"] == PUBLICDATA_REGISTER_VERSION
    assert retained.rights_status["private_provider_processing"]["status"] == "blocked"
    assert retained.rights_status["public_redistribution"]["status"] == "not_assessed"

    result = bind_retained_acnc_source_evidence(retained, ordinal=1, as_of=date(2026, 11, 3))
    row = result.rows[0]
    assert result.bound_count == 0
    assert row.status == "MISSING"
    assert row.subject_id == SUBJECT_ID
    assert row.scope_id == SCOPE_ID
    assert row.source_sha256 == PUBLICDATA_REGISTER_BODY_SHA256
    assert row.representation_sha256 == retained.representation_sha256
    assert "private_provider_processing_rights_decision_not_observed" in row.reasons
    assert row.governed_reference is None


def test_transport_contract_preserves_third_party_lineage_and_mirror_claim_boundary():
    transport = _transport()
    assert transport["schema"] == PUBLICDATA_TRANSPORT_SCHEMA
    assert transport["source_kind"] == PUBLICDATA_REGISTER_SOURCE_KIND
    assert transport["source_url"] == PUBLICDATA_REGISTER_URL
    assert transport["upstream_dataset_version"] == PUBLICDATA_REGISTER_VERSION
    assert transport["source_row_count"] == 1
    assert transport["rights"]["id"] == "CC-BY-3.0-AU"
    body = json.loads(transport["http_body_utf8"])
    assert body["rows"][0]["abn"] == "52000399744"
    assert body["rows"][0]["charity_legal_name"] == "Guide Dogs NSW/ACT"
    assert body["publicdata"]["source"]["sha256"] == transport["upstream_original_csv_claimed_sha256"]

    retained = retain_publicdata_acnc_register_transport(
        transport,
        subject_id=SUBJECT_ID,
        scope_id=SCOPE_ID,
        subject=_subject(),
        scope=_scope(),
    )
    provenance = retained.representation["source_provenance"]
    assert provenance["publisher_original_bytes"] is False
    assert provenance["upstream_original_csv_verification"] == "mirror_claim_not_locally_verified"
    assert retained.representation["content_hash"] != retained.source_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "charitygraph.private-source-transport/v0"),
        ("source_row_count", 2),
        ("upstream_dataset_version", "2024-01-01"),
        ("subject_abn", "52000399745"),
    ],
)
def test_transport_identity_and_currentness_mismatches_fail_closed(field, value):
    transport = _transport()
    transport[field] = value
    with pytest.raises(RetentionInputError):
        retain_publicdata_acnc_register_transport(
            transport,
            subject_id=SUBJECT_ID,
            scope_id=SCOPE_ID,
            subject=_subject(),
            scope=_scope(),
        )


def test_transport_rights_mismatch_fails_closed():
    transport = _transport()
    transport["rights"] = {"id": "CC-BY-4.0", "title": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}
    with pytest.raises(RetentionInputError, match="rights"):
        retain_publicdata_acnc_register_transport(
            transport,
            subject_id=SUBJECT_ID,
            scope_id=SCOPE_ID,
            subject=_subject(),
            scope=_scope(),
        )
