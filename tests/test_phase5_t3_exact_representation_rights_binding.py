from __future__ import annotations

import copy
import hashlib
import json
from datetime import date

import pytest

from charitygraph.phase5_governed_factory_integration import preflight_governed_references
from charitygraph.phase5_t3_exact_representation_rights_binding import (
    LOCAL_RETENTION_POLICY_ID,
    LOCAL_RETENTION_POLICY_VERSION,
    OPENAI_PROVIDER_POLICY_ID,
    SELECTED_MANIFEST_SHA256,
    bind_selected_manifest,
)
from charitygraph.source_rights import ArtifactRightsDecision


MANIFEST_PATH = "evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json"
NOW = date(2026, 11, 1)


def _manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _synthetic_inputs(manifest: dict, *, row_index: int = 0) -> tuple[dict, dict]:
    row = dict(manifest["rows"][row_index])
    source_bytes = b"synthetic source object; not committed"
    representation_bytes = b"synthetic structured representation; not committed"
    representation_sha = hashlib.sha256(representation_bytes).hexdigest()
    representation_id = "artifact:" + representation_sha
    row["representation_artifact_id"] = representation_id
    row["representation_sha256"] = representation_sha
    source_id = row["source_artifact_id"]
    source_record = {
        "id": row["source_record_id"],
        "source_family": row["source_family"],
        "source_role": row["source_role"],
        "about_subject_ids": [row["subject_id"]],
        "payload_ref": source_id,
        "payload_hash": row["source_sha256"],
        "source_locator": "https://example.invalid/acnc-fixture",
    }
    receipt = {
        "id": row["acquisition_receipt_id"],
        "source_definition_id": row["source_definition_id"],
        "artifact_id": source_id,
        "content_hash": row["source_sha256"],
        "outcome": "available",
    }
    representation = {
        "id": representation_id,
        "artifact_id": representation_id,
        "content_hash": representation_sha,
        "content": representation_bytes,
        "source_artifact_id": source_id,
        "subject_id": row["subject_id"],
        "scope_id": row["scope_id"],
        "representation_class": "structured_factual",
        "evidence_locator_ids": ("evidence:synthetic",),
    }
    rights = {
        "representation_artifact_id": representation_id,
        "axes": {
            "local_retention": {
                "status": "authorized",
                "decision_id": "rights:synthetic:local",
                "representation_sha256": representation_sha,
                "policy_id": LOCAL_RETENTION_POLICY_ID,
                "policy_version": LOCAL_RETENTION_POLICY_VERSION,
                "assessed_authority": "synthetic-governed-authority-v1",
                "assessed_on": "2026-10-01",
                "review_deadline": "2027-10-01",
                "lawful_public_access": True,
                "circumvention_used": False,
                "explicit_prohibition_found": False,
                "authority_kind": "governed_policy",
            },
            "private_provider_processing": {
                "status": "authorized",
                "decision_id": "rights:synthetic:provider",
                "representation_sha256": representation_sha,
                "policy_id": "CC_BY_4_0_V1",
                "policy_version": "1.0.0",
                "assessed_authority": "synthetic-source-rights-authority-v1",
                "assessed_on": "2026-10-01",
                "review_deadline": "2027-01-01",
                "lawful_public_access": True,
                "circumvention_used": False,
                "explicit_prohibition_found": False,
                "provider_policy_id": OPENAI_PROVIDER_POLICY_ID,
                "provider_policy_version": "1",
                "provider_no_training_default": True,
                "provider_data_sharing_opt_in": False,
                "authority_kind": "governed_policy",
            },
            "public_redistribution": {"status": "not_assessed"},
        },
    }
    existing = {
        "source_records": [source_record],
        "acquisition_receipts": [receipt],
        "representations": [representation],
        "scopes": [{"id": row["scope_id"], "subject_id": row["subject_id"]}],
        "rights_decisions": [rights],
    }
    return row, existing


def test_real_selected_manifest_is_preserved_and_fail_closed():
    result = bind_selected_manifest(MANIFEST_PATH)

    assert result.selected_manifest_sha256 == SELECTED_MANIFEST_SHA256
    assert len(result.rows) == 10
    assert len({row.subject_id for row in result.rows}) == 5
    assert result.eligible_count == 0
    assert all(row.status == "NOT_OBSERVED" for row in result.rows)
    assert all("exact_representation_not_observed" in row.reasons for row in result.rows)
    assert all(row.local_retention.status == "not_observed" for row in result.rows)
    assert all(row.private_provider_processing.status == "not_observed" for row in result.rows)
    assert all(row.public_redistribution.status == "not_observed" for row in result.rows)
    assert b"synthetic structured representation" not in result.canonical_bytes()


def test_canonical_hash_is_stable_under_manifest_and_coverage_permutation():
    manifest = _manifest()
    _, existing = _synthetic_inputs(manifest)
    coverage = [
        {"subject_id": manifest["rows"][0]["subject_id"], "section_id": "section-03", "status": "source_silent"},
        {"subject_id": manifest["rows"][0]["subject_id"], "section_id": "section-01", "status": "source_silent"},
    ]
    first = bind_selected_manifest(manifest, existing=existing, coverage_records=coverage, require_selected_cohort=False)
    permuted = copy.deepcopy(manifest)
    permuted["rows"] = list(reversed(permuted["rows"]))
    second = bind_selected_manifest(permuted, existing=existing, coverage_records=list(reversed(coverage)), require_selected_cohort=False)

    assert first.canonical_hash == second.canonical_hash
    assert first.coverage_records == second.coverage_records


def test_synthetic_positive_lowers_to_existing_preflight_contract():
    manifest = _manifest()
    row, existing = _synthetic_inputs(manifest)
    result = bind_selected_manifest(
        {**manifest, "rows": [row]},
        existing=existing,
        require_selected_cohort=False,
    )

    assert result.bound_count == 1
    reference = result.rows[0].governed_reference
    assert reference is not None
    assert reference.representation_hashes[reference.representation_artifact_ids[0]] != row["source_sha256"]
    preflight = preflight_governed_references((reference,), catalog=_PreflightCatalog(row, existing), retained_bytes=lambda _: b"synthetic structured representation; not committed")
    assert preflight.accepted_count == 1
    assert not preflight.diagnostics


@pytest.mark.parametrize(
    "change, expected",
    [
        ("source_sha", "source_sha_substituted_for_representation"),
        ("subject", "representation_lineage_or_subject_mismatch"),
        ("scope", "representation_scope_mismatch"),
        ("policy_version", "policy_version_mismatch"),
        ("revoked", "provider_decision_revoked"),
        ("provider_conditions", "provider_data_sharing_condition_missing"),
        ("public_overreach", "public_redistribution_not_authorized_by_internal_policy"),
        ("prohibition", "explicit_prohibition_not_excluded"),
        ("fake_provider", "provider_owned_rights_metadata_not_authority"),
    ],
)
def test_negative_rights_and_identity_cases_are_not_bound(change, expected):
    manifest = _manifest()
    row, existing = _synthetic_inputs(manifest)
    if change == "source_sha":
        existing["representations"][0]["content_hash"] = row["source_sha256"]
    elif change == "subject":
        existing["representations"][0]["subject_id"] = "subject:" + "f" * 32
    elif change == "scope":
        existing["representations"][0]["scope_id"] = "scope:" + "f" * 32
    elif change == "policy_version":
        existing["rights_decisions"][0]["axes"]["local_retention"]["policy_version"] = "9.9.9"
    elif change == "revoked":
        existing["rights_decisions"][0]["axes"]["private_provider_processing"]["status"] = "revoked"
    elif change == "provider_conditions":
        existing["rights_decisions"][0]["axes"]["private_provider_processing"]["provider_data_sharing_opt_in"] = None
    elif change == "public_overreach":
        existing["rights_decisions"][0]["axes"]["public_redistribution"] = {
            "status": "authorized",
            "decision_id": "rights:synthetic:public",
            "representation_sha256": existing["representations"][0]["content_hash"],
            "policy_id": "CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1",
            "policy_version": "1.0.0",
            "assessed_authority": "internal-only-authority",
            "assessed_on": "2026-10-01",
            "review_deadline": "2027-01-01",
            "lawful_public_access": True,
            "circumvention_used": False,
            "explicit_prohibition_found": False,
        }
    elif change == "prohibition":
        existing["rights_decisions"][0]["axes"]["local_retention"]["explicit_prohibition_found"] = True
    elif change == "fake_provider":
        existing["rights_decisions"][0]["axes"]["private_provider_processing"]["authority_kind"] = "provider_owned"
    result = bind_selected_manifest({**manifest, "rows": [row]}, existing=existing, require_selected_cohort=False)

    assert result.rows[0].governed_reference is None
    assert expected in result.rows[0].reasons or any(expected in reason for reason in result.rows[0].reasons)


def test_invalid_review_date_and_duplicate_receipts_fail_closed():
    manifest = _manifest()
    row, existing = _synthetic_inputs(manifest)
    existing["rights_decisions"][0]["axes"]["local_retention"]["review_deadline"] = "not-a-date"
    with pytest.raises(ValueError, match="review_deadline"):
        bind_selected_manifest({**manifest, "rows": [row]}, existing=existing, require_selected_cohort=False)

    _, existing = _synthetic_inputs(manifest)
    existing["acquisition_receipts"] = [existing["acquisition_receipts"][0], existing["acquisition_receipts"][0]]
    with pytest.raises(ValueError, match="duplicate acquisition receipt"):
        bind_selected_manifest({**manifest, "rows": [row]}, existing=existing, require_selected_cohort=False)


class _PreflightCatalog:
    def __init__(self, row: dict, existing: dict):
        self.row = row
        self.existing = existing
        self.rep = existing["representations"][0]
        self.receipt = existing["acquisition_receipts"][0]
        self.source = existing["source_records"][0]
        self.decision = ArtifactRightsDecision(
            decision_id="rights:synthetic:provider",
            source_artifact_id=row["source_artifact_id"],
            representation_artifact_id=self.rep["artifact_id"],
            source_record_id=row["source_record_id"],
            source_origin_url=self.source["source_locator"],
            source_role=row["source_role"],
            acquisition_lineage_ids=(row["acquisition_receipt_id"],),
            transmitted_representation_sha256=self.rep["content_hash"],
            rights_policy_id="CC_BY_4_0_V1",
            rights_policy_version="1.0.0",
            provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
            provider_processing_policy_version="1",
            rights_basis="explicit_open_license",
            evidence_locator=self.source["source_locator"],
            evidence_sha256=row["source_sha256"],
            assessed_on=NOW,
            assessment_scope="synthetic fixture",
            assessment_authority="synthetic-source-rights-authority-v1",
            licence_identifier="CC-BY-4.0",
            licence_or_terms_url="https://example.invalid/licence",
            local_retention_allowed=False,
            provider_transmission_allowed=True,
            public_redistribution_allowed=False,
            factual_representation_only=True,
            representation_class="structured_factual",
            publicly_accessible_without_circumvention=True,
            access_controls_bypassed=False,
            lawfully_acquired=True,
            analytical_purpose="semantic_analysis",
            provider_no_training_default=True,
            provider_data_sharing_opt_in=False,
        )

    def get_subject(self, _):
        return {"subject_id": self.row["subject_id"]}

    def get_scope(self, _):
        return {"scope_id": self.row["scope_id"], "subject_id": self.row["subject_id"]}

    def get_source_definition(self, _):
        return {"source_definition_id": self.row["source_definition_id"]}

    def get_acquisition_receipt(self, _):
        return {**self.receipt, "requested_locator": self.source["source_locator"]}

    def get_source_record(self, _):
        return {**self.source, "material": {"about_subject_ids": [self.row["subject_id"]]}}

    def get_artifact(self, artifact_id):
        if artifact_id == self.rep["artifact_id"]:
            return {"artifact_id": artifact_id, "content_hash": self.rep["content_hash"], "availability": "available"}
        if artifact_id == self.row["source_artifact_id"]:
            return {"artifact_id": artifact_id, "content_hash": self.row["source_sha256"], "availability": "available"}
        return None

    def get_artifact_lineage(self, _):
        return [{"input_artifact_id": self.row["source_artifact_id"]}]

    def get_evidence_locator(self, _):
        return {"artifact_id": self.rep["artifact_id"], "material_hash": self.rep["content_hash"]}

    def get_artifact_rights_decisions(self, _):
        return [{"decision_id": self.decision.decision_id}]

    def list_artifact_rights_decisions(self, representation_artifact_id=None):
        if representation_artifact_id == self.rep["artifact_id"]:
            return [{
                "decision_id": self.decision.decision_id,
                "rights_policy_id": self.decision.rights_policy_id,
                "rights_policy_version": self.decision.rights_policy_version,
                "material_json": json.dumps({"decision": self.decision.model_dump(mode="json")}),
            }]
        return []

    def record_provider_rights_diagnostic(self, **_):
        return None
