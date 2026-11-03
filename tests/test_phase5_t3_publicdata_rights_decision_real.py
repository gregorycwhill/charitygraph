from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from charitygraph.phase5_t3_acnc_real_evidence_retention import (
    bind_retained_acnc_source_evidence,
    retain_publicdata_acnc_register_transport,
)
from charitygraph.phase5_t3_source_evidence_binding import bind_acnc_source_evidence


RUNTIME = Path(r"C:\CharityGraph-runtime\g4-o1c-publicdata-acnc-register-20261103")
RAW_PATH = RUNTIME / "raw-response.json"
NORMALIZED_PATH = RUNTIME / "normalized-representation.json"
RIGHTS_PATH = Path("evidence/gate4-t3-five-subject-v1/first-charity-publicdata-provider-rights-20261103.json")
BINDING_PATH = Path("evidence/gate4-t3-five-subject-v1/first-charity-publicdata-api-binding-20261026.json")
SUBJECT_ID = "subject:02649cdcb42049bb8dedd30f2333e150"
SCOPE_ID = "scope:0a10077aee9363200199a815e8198f3807fef97737ad89bfd1e2e17f61d63248"
SOURCE_SHA256 = "07b83ca8f241b23445818c2079883924929ecc5c72dd0aed04b10c3f8b5372fc"
REPRESENTATION_SHA256 = "1405b49e6dcf06b399f2b1e5f3a40b14f17051cdc318a336813159e80d76af82"
SOURCE_DEFINITION_ID = "srcdef:21dbd2bcf09bc1c778964db71f37f6ff57a088a47838dd6168d7be661b562e21"
SOURCE_RECORD_ID = "srcrec:d2025968c8b6c873f3cc83441289e70fc94c98a891f5a9a1f95a56d89ac3188b"
URL = "https://publicdata.au/api/v1/datasets/acnc-register/versions/2026-10-26/rows?abn=eq.52000399744"


def _subject() -> dict:
    return {
        "id": SUBJECT_ID,
        "subject_id": SUBJECT_ID,
        "subject_kind": "legal_entity",
        "display_name": "Guide Dogs NSW/ACT",
        "external_identifiers": [{"scheme": "ABN", "value": "52000399744", "issuing_authority": "Australian Business Register"}],
    }


def _scope() -> dict:
    return {"id": SCOPE_ID, "scope_id": SCOPE_ID, "subject_id": SUBJECT_ID, "scope_kind": "registered_entity"}


def _transport() -> dict:
    body = RAW_PATH.read_text(encoding="utf-8")
    return {
        "schema": "charitygraph.private-source-transport/v1",
        "source_kind": "independent_publicdata_au_api_representation_of_acnc_register",
        "subject_abn": "52000399744",
        "subject_name": "Guide Dogs NSW/ACT",
        "source_row_count": 1,
        "upstream_dataset_version": "2026-10-26",
        "source_url": URL,
        "rights": {"id": "CC-BY-3.0-AU", "title": "CC BY 3.0 AU", "url": "https://creativecommons.org/licenses/by/3.0/au/"},
        "http_body_utf8": body,
        "http_body_sha256": SOURCE_SHA256,
        "upstream_original_csv_claimed_sha256": "1ff76b510e8155d7ab35df4b45b8791315c1f0a15f43f9c3057dff16646f816d",
        "upstream_original_csv_claimed_bytes": 15156962,
        "capture_method": "local retained prior-task API response; no acquisition",
        "captured_at": "2026-11-03T00:33:45.171Z",
    }


def _retained(rights: dict | None = None):
    kwargs = {
        "subject_id": SUBJECT_ID,
        "scope_id": SCOPE_ID,
        "subject": _subject(),
        "scope": _scope(),
        "source_definition_id": SOURCE_DEFINITION_ID,
        "source_record_id": SOURCE_RECORD_ID,
    }
    return retain_publicdata_acnc_register_transport(
        _transport(),
        **kwargs,
        rights_authority=None if rights is None else {"private_provider_processing": rights},
    )


def test_real_retained_source_and_representation_bind_with_exact_rights():
    rights = json.loads(RIGHTS_PATH.read_bytes())["rights_decision"]
    retained = _retained(rights)
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.representation_sha256 == REPRESENTATION_SHA256
    assert retained.representation_bytes == NORMALIZED_PATH.read_bytes()
    assert retained.provider_processing_status == "authorized"
    result = bind_retained_acnc_source_evidence(retained, ordinal=1, as_of=date(2026, 11, 3))
    assert result.bound_count == 1
    assert result.rows[0].status == "BOUND"
    assert result.rows[0].reasons == ()
    assert result.rows[0].governed_reference is not None
    assert result.rows[0].governed_reference.rights_decision_ids == (
        "rights:private-provider:" + REPRESENTATION_SHA256,
    )


def test_real_cohort_is_one_bound_of_ten_and_artifact_has_no_private_bytes():
    rights = json.loads(RIGHTS_PATH.read_bytes())["rights_decision"]
    retained = _retained(rights)
    manifest = json.loads(Path("evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json").read_bytes())
    rows = [retained.binder_row(ordinal=1), *manifest["rows"][1:]]
    result = bind_acnc_source_evidence(
        {"schema": manifest["schema"], "source_universe_version": "v1", "selected_manifest_sha256": manifest["selected_manifest_sha256"], "rows": rows},
        existing=retained.binder_existing(),
        retained_bytes=retained.retained_bytes(),
        as_of=date(2026, 11, 3),
        require_five_subject_ten_rows=True,
    )
    assert len(result.rows) == 10
    assert result.bound_count == 1
    assert result.missing_count == 9
    assert [row.ordinal for row in result.rows if row.status == "BOUND"] == [1]
    artifact = json.loads(BINDING_PATH.read_bytes())
    assert artifact["binding_result"]["canonical_hash"] == result.canonical_hash
    assert artifact["cohort"] == {
        "blocked_count": 0,
        "bound_count": 1,
        "bound_ordinals": [1],
        "denominator": 10,
        "missing_count": 9,
        "missing_ordinals": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "provider_calls": 0,
        "publications": 0,
        "spend_aud": "0.00",
    }
    serialized = BINDING_PATH.read_text(encoding="utf-8")
    assert "source_bytes_base64" not in serialized
    assert "http_body_utf8" not in serialized


def test_provider_rights_remain_exact_and_fail_closed_when_representation_changes():
    rights = json.loads(RIGHTS_PATH.read_bytes())["rights_decision"]
    rights["representation_sha256"] = "0" * 64
    retained = _retained(rights)
    result = bind_retained_acnc_source_evidence(retained, ordinal=1, as_of=date(2026, 11, 3))
    assert result.bound_count == 0
    assert result.rows[0].status == "BLOCKED"
    assert "rights_representation_sha_mismatch" in result.rows[0].reasons

