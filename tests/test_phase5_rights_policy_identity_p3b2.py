import json
import importlib.util
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from charitygraph.contracts import SourceRecord
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_factory_integration import preflight_governed_references
from charitygraph.runtime import SQLiteCatalog
from charitygraph.source_rights import ArtifactRightsDecision


_integration_path = Path(__file__).with_name("test_phase5_governed_factory_integration.py")
_integration_spec = importlib.util.spec_from_file_location("g4_p3b2_integration_fixture", _integration_path)
assert _integration_spec is not None and _integration_spec.loader is not None
_integration_module = importlib.util.module_from_spec(_integration_spec)
_integration_spec.loader.exec_module(_integration_module)
NOW = _integration_module.NOW
_fixture = _integration_module._fixture
_run = _integration_module._run


def _work_counts(catalog) -> dict[str, int]:
    with catalog._connection() as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "tasks", "physical_attempts", "provider_receipts", "budget_reservations",
                "cost_entries", "provider_request_attempts",
            )
        }


def _stored_decision(catalog, decision_id: str) -> ArtifactRightsDecision:
    row = catalog.get_artifact_rights_decision(decision_id)
    assert row is not None
    return ArtifactRightsDecision.model_validate(json.loads(row["material_json"])["decision"])


def _record_variant(catalog, decision: ArtifactRightsDecision, decision_id: str, **changes):
    variant = decision.model_copy(update={"decision_id": decision_id, **changes})
    catalog.record_artifact_rights_decision(variant, now=NOW)
    return variant


def _blocked(catalog, reference, *, planned_processing_at=NOW, retained_bytes=None):
    result = preflight_governed_references(
        [reference], catalog=catalog,
        retained_bytes=retained_bytes or (lambda _: b"represented source 1"),
        planned_processing_at=planned_processing_at,
    )
    assert result.accepted_count == 0
    cohort_id, run_id = _run(catalog, "p3b2", "p3b2")
    runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    assert runner.seed(NOW) == ()
    assert runner.run(NOW) == 0
    assert _work_counts(catalog) == {
        "tasks": 0, "physical_attempts": 0, "provider_receipts": 0,
        "budget_reservations": 0, "cost_entries": 0, "provider_request_attempts": 0,
    }
    assert catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0")
    return result


def test_authorised_100_policy_identity_lowers_real_factory_and_restarts_idempotently(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    reference = reference.model_copy(update={"rights_policy_version": "1.0.0"})
    preflight = preflight_governed_references(
        [reference], catalog=catalog, retained_bytes=lambda _: b"represented source 1", planned_processing_at=NOW
    )
    assert preflight.accepted_count == 1
    assert preflight.tasks[0]["_model_task"].parameters["rights_policy_version"] == "1.0.0"

    cohort_id, run_id = _run(catalog, "positive", "positive")
    runner = ReferenceFactory(catalog, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    assert runner.run(NOW) == 1
    assert runner.run(NOW) == 0
    counts = _work_counts(catalog)
    assert counts == {
        "tasks": 1, "physical_attempts": 1, "provider_receipts": 1,
        "budget_reservations": 1, "cost_entries": 2, "provider_request_attempts": 0,
    }
    assert catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")

    catalog.close()
    reopened = SQLiteCatalog(catalog.path).open()
    rerun = ReferenceFactory(reopened, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
    rerun.seed(NOW)
    assert rerun.run(NOW) == 0
    assert _work_counts(reopened) == counts


def test_arbitrary_policy_version_is_durable_but_fails_preflight_closed(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    invalid = _record_variant(
        catalog, original, "rights:p3b2-999", rights_policy_version="999.0.0",
        supersedes_decision_id=original.decision_id,
    )
    variant = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-999",
        "rights_decision_ids": (invalid.decision_id,),
        "rights_policy_version": "999.0.0",
    })
    result = _blocked(catalog, variant)
    assert result.diagnostics[0].state == "rights_mismatched"
    assert "unknown or version-mismatched" in result.diagnostics[0].reason
    diagnostics = catalog.get_provider_rights_diagnostics(variant.reference_id)
    assert diagnostics and "999.0.0" in diagnostics[-1]["details_json"]


def test_reference_version_mismatch_and_absent_durable_record_fail_closed(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    mismatched = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-reference-version",
        "rights_policy_version": "999.0.0",
    })
    result = _blocked(catalog, mismatched)
    assert result.diagnostics[0].state == "rights_mismatched"

    absent = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-absent",
        "rights_decision_ids": ("rights:p3b2-absent",),
    })
    result = _blocked(catalog, absent)
    assert result.diagnostics[0].state == "rights_missing"
    assert "not durable" in result.diagnostics[0].reason


def test_duplicate_and_revoked_current_policy_records_fail_closed(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path, "1")
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    duplicate = _record_variant(catalog, original, "rights:p3b2-duplicate")
    duplicate_ref = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-duplicate",
        "rights_decision_ids": (original.decision_id, duplicate.decision_id),
    })
    result = _blocked(catalog, duplicate_ref)
    assert result.diagnostics[0].state == "rights_conflict"

    catalog, _store, reference, _representation = _fixture(tmp_path, "2")
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    revoked = _record_variant(
        catalog, original, "rights:p3b2-revoked", status="revoked",
        provider_transmission_allowed=False, supersedes_decision_id=original.decision_id,
    )
    revoked_ref = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-revoked",
        "rights_decision_ids": (revoked.decision_id,),
    })
    result = _blocked(catalog, revoked_ref, retained_bytes=lambda _: b"represented source 2")
    assert result.diagnostics[0].state == "rights_denied"

    catalog, _store, reference, _representation = _fixture(tmp_path, "3")
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    superseded = _record_variant(
        catalog, original, "rights:p3b2-superseded", status="superseded",
        provider_transmission_allowed=False, supersedes_decision_id=original.decision_id,
    )
    superseded_ref = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-superseded",
        "rights_decision_ids": (superseded.decision_id,),
    })
    result = _blocked(catalog, superseded_ref, retained_bytes=lambda _: b"represented source 3")
    assert result.diagnostics[0].state == "rights_missing"


def test_optional_expiry_is_valid_and_passed_deadline_blocks(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    reference = reference.model_copy(update={"rights_policy_version": "1.0.0"})
    valid = preflight_governed_references(
        [reference], catalog=catalog, retained_bytes=lambda _: b"represented source 1", planned_processing_at=NOW
    )
    assert valid.accepted_count == 1

    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    expired = _record_variant(
        catalog, original, "rights:p3b2-expired", expires_on=NOW.date(),
        supersedes_decision_id=original.decision_id,
    )
    expired_ref = reference.model_copy(update={
        "reference_id": "governed-ref:p3b2-expired",
        "rights_decision_ids": (expired.decision_id,),
    })
    result = _blocked(catalog, expired_ref, planned_processing_at=NOW + timedelta(days=1))
    assert result.diagnostics[0].state == "rights_expired"


def test_multi_subject_matching_and_mismatched_policy_paths_are_isolated(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _catalog_b, _store_b, reference_b, representation_b = _fixture(tmp_path, "2", catalog=catalog, store=store)
    source_row = catalog.get_source_record(reference_a.source_record_ids[0])
    assert source_row is not None
    source = SourceRecord.model_validate(json.loads(source_row["material_json"])).model_copy(
        update={"record_id": "srcrec:p3b2-multi", "about_subject_ids": (reference_a.subject_id, reference_b.subject_id)}
    )
    catalog.register_source_record(source)
    original = _stored_decision(catalog, reference_a.rights_decision_ids[0])
    rights = _record_variant(
        catalog, original, "rights:p3b2-multi", source_record_id=source.record_id,
        supersedes_decision_id=original.decision_id,
    )
    multi_a = reference_a.model_copy(update={
        "reference_id": "governed-ref:p3b2-multi-a",
        "source_record_ids": (source.record_id,), "rights_decision_ids": (rights.decision_id,),
        "rights_policy_version": "1.0.0",
    })
    multi_b = multi_a.model_copy(update={
        "reference_id": "governed-ref:p3b2-multi-b", "subject_id": reference_b.subject_id,
        "scope_id": reference_b.scope_id,
    })
    subject_c = "subject:" + "3" * 32
    catalog.register_subject(_integration_module._subject(subject_c))
    mismatch = multi_a.model_copy(update={
        "reference_id": "governed-ref:p3b2-multi-mismatch", "subject_id": subject_c,
    })
    result = preflight_governed_references(
        [multi_a, multi_b, mismatch], catalog=catalog,
        retained_bytes=lambda artifact_id: b"represented source 1" if artifact_id == representation_a.artifact_id else b"represented source 2",
        planned_processing_at=NOW,
    )
    assert result.accepted_count == 2
    assert {task["subject_id"] for task in result.tasks} == {reference_a.subject_id, reference_b.subject_id}
    assert result.diagnostics[0].reference_id == mismatch.reference_id
    assert result.diagnostics[0].state == "mismatched"


def test_policy_failure_does_not_suppress_an_unaffected_peer(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _catalog_b, _store_b, reference_b, representation_b = _fixture(tmp_path, "2", catalog=catalog, store=store)
    original = _stored_decision(catalog, reference_a.rights_decision_ids[0])
    invalid = _record_variant(
        catalog, original, "rights:p3b2-peer-invalid", rights_policy_version="999.0.0",
        supersedes_decision_id=original.decision_id,
    )
    invalid_a = reference_a.model_copy(update={
        "reference_id": "governed-ref:p3b2-peer-invalid",
        "rights_decision_ids": (invalid.decision_id,), "rights_policy_version": "999.0.0",
    })
    result = preflight_governed_references(
        [invalid_a, reference_b], catalog=catalog,
        retained_bytes=lambda artifact_id: (
            b"represented source 1" if artifact_id == representation_a.artifact_id
            else b"represented source 2"
        ),
        planned_processing_at=NOW,
    )
    assert result.accepted_count == 1
    assert result.diagnostics[0].reference_id == invalid_a.reference_id
    assert result.tasks[0]["subject_id"] == reference_b.subject_id
    cohort_id, run_id = _run(catalog, "peer", "peer")
    runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    assert runner.run(NOW) == 1
    assert catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")

