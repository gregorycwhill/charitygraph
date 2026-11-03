import json
import importlib.util
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from charitygraph.contracts import AcquisitionReceipt
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_factory_integration import preflight_governed_references
from charitygraph.runtime import SQLiteCatalog
from charitygraph.source_rights import ArtifactRightsDecision

_integration_path = Path(__file__).with_name("test_phase5_governed_factory_integration.py")
_integration_spec = importlib.util.spec_from_file_location("g4_p3_integration_fixture", _integration_path)
assert _integration_spec is not None and _integration_spec.loader is not None
_integration_module = importlib.util.module_from_spec(_integration_spec)
_integration_spec.loader.exec_module(_integration_module)
NOW = _integration_module.NOW
_fixture = _integration_module._fixture
_run = _integration_module._run


def _stored_decision(catalog, decision_id: str) -> ArtifactRightsDecision:
    row = catalog.get_artifact_rights_decision(decision_id)
    assert row is not None
    return ArtifactRightsDecision.model_validate(json.loads(row["material_json"])["decision"])


def _record_variant(catalog, decision: ArtifactRightsDecision, decision_id: str, **changes) -> ArtifactRightsDecision:
    variant = decision.model_copy(update={"decision_id": decision_id, **changes})
    catalog.record_artifact_rights_decision(variant, now=NOW)
    return variant


def _work_counts(catalog) -> dict[str, int]:
    with catalog._connection() as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "tasks", "physical_attempts", "provider_receipts", "budget_reservations",
                "cost_entries", "provider_request_attempts",
            )
        }


def _assert_blocked_without_work(catalog, reference, *, planned_processing_at=NOW):
    result = preflight_governed_references(
        [reference], catalog=catalog, retained_bytes=lambda _: b"represented source 1",
        planned_processing_at=planned_processing_at,
    )
    assert result.accepted_count == 0
    cohort_id, run_id = _run(catalog, "8", "8")
    runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    assert runner.seed(NOW) == ()
    assert runner.run(NOW) == 0
    assert _work_counts(catalog) == {
        "tasks": 0, "physical_attempts": 0, "provider_receipts": 0,
        "budget_reservations": 0, "cost_entries": 0, "provider_request_attempts": 0,
    }
    position = catalog.budget_position(cohort_id)
    assert position.actual_spend_aud == Decimal("0")
    assert position.outstanding_reserved_exposure_aud == Decimal("0")
    return result


def test_positive_rights_preflight_runs_real_factory_and_is_restart_idempotent(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    first = preflight_governed_references(
        [reference], catalog=catalog, retained_bytes=lambda _: b"represented source 1",
        planned_processing_at=NOW,
    )
    assert first.accepted_count == 1
    assert not first.diagnostics
    assert first.tasks[0]["_model_task"].parameters["rights_decision_ids"] == [reference.rights_decision_ids[0]]

    cohort_id, run_id = _run(catalog, "6", "6")
    runner = ReferenceFactory(catalog, first.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    assert runner.run(NOW) == 1
    counts = _work_counts(catalog)
    assert counts["physical_attempts"] == counts["provider_receipts"] == 1
    assert counts["budget_reservations"] == 1
    assert counts["cost_entries"] == 2
    assert catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")

    catalog.close()
    reopened = SQLiteCatalog(catalog.path).open()
    rerun = ReferenceFactory(reopened, first.factory_plan, cohort_id=cohort_id, run_id=run_id)
    rerun.seed(NOW)
    assert rerun.run(NOW) == 0
    assert _work_counts(reopened) == counts


@pytest.mark.parametrize(
    ("name", "update", "state"),
    [
        ("missing-decision", {"rights_decision_ids": ()}, "rights_missing"),
        ("role-mismatch", {"rights_role": "different-source-role"}, "rights_mismatched"),
        ("policy-mismatch", {"provider_processing_policy_id": "different-provider-policy"}, "rights_mismatched"),
        ("rights-policy-mismatch", {"rights_policy_id": "different-rights-policy"}, "rights_mismatched"),
        ("representation-mismatch", {"representation_hashes": {"repr:missing": "d" * 64}}, "mismatched"),
    ],
)
def test_rights_mismatches_are_durable_and_create_no_factory_work(tmp_path, name, update, state):
    catalog, _store, reference, representation = _fixture(tmp_path, "1")
    if name == "representation-mismatch":
        update = {"representation_hashes": {representation.artifact_id: "d" * 64}}
    variant = reference.model_copy(update={"reference_id": "rights-" + name, **update})
    result = _assert_blocked_without_work(catalog, variant)
    assert result.diagnostics[0].state == state
    if state.startswith("rights_"):
        diagnostics = catalog.get_provider_rights_diagnostics(variant.reference_id)
        assert diagnostics and diagnostics[-1]["state"] == state


def test_duplicate_current_decisions_fail_closed_without_arbitrary_choice(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    duplicate = _record_variant(catalog, original, "rights:g4p1-duplicate")
    variant = reference.model_copy(update={
        "reference_id": "rights-conflict",
        "rights_decision_ids": (original.decision_id, duplicate.decision_id),
    })
    result = _assert_blocked_without_work(catalog, variant)
    assert result.diagnostics[0].state == "rights_conflict"
    assert "multiple current" in result.diagnostics[0].reason


@pytest.mark.parametrize("status", ["blocked", "revoked"])
def test_explicit_deny_and_revocation_supersede_prior_allow(tmp_path, status):
    catalog, _store, reference, _representation = _fixture(tmp_path, "1")
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    denied = _record_variant(
        catalog, original, "rights:g4p1-" + status,
        status=status, provider_transmission_allowed=False,
        supersedes_decision_id=original.decision_id,
    )
    variant = reference.model_copy(update={
        "reference_id": "rights-" + status,
        "rights_decision_ids": (original.decision_id, denied.decision_id),
    })
    result = _assert_blocked_without_work(catalog, variant)
    assert result.diagnostics[0].state == "rights_denied"


def test_optional_expiry_absent_is_valid_and_expiry_boundary_is_inclusive(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    valid = preflight_governed_references(
        [reference], catalog=catalog, retained_bytes=lambda _: b"represented source 1",
        planned_processing_at=NOW,
    )
    assert valid.accepted_count == 1

    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    bounded = _record_variant(
        catalog, original, "rights:g4p1-boundary", expires_on=NOW.date(),
        supersedes_decision_id=original.decision_id,
    )
    boundary = reference.model_copy(update={
        "reference_id": "rights-boundary",
        "rights_decision_ids": (original.decision_id, bounded.decision_id),
    })
    at_boundary = preflight_governed_references(
        [boundary], catalog=catalog, retained_bytes=lambda _: b"represented source 1",
        planned_processing_at=NOW,
    )
    assert at_boundary.accepted_count == 1


def test_expired_decision_blocks_at_later_planned_processing_time(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    original = _stored_decision(catalog, reference.rights_decision_ids[0])
    expired = _record_variant(
        catalog, original, "rights:g4p1-expired", expires_on=NOW.date(),
        supersedes_decision_id=original.decision_id,
    )
    variant = reference.model_copy(update={
        "reference_id": "rights-expired",
        "rights_decision_ids": (original.decision_id, expired.decision_id),
    })
    result = _assert_blocked_without_work(catalog, variant, planned_processing_at=NOW + timedelta(days=1))
    assert result.diagnostics[0].state == "rights_expired"


def test_acquisition_lineage_mismatch_blocks_while_independent_peer_runs(tmp_path):
    catalog, store, reference_a, _representation_a = _fixture(tmp_path, "1")
    _catalog_b, _store_b, reference_b, _representation_b = _fixture(tmp_path, "2", catalog=catalog, store=store)
    original_receipt = catalog.get_acquisition_receipt(reference_a.acquisition_receipt_ids[0])
    assert original_receipt is not None
    receipt_model = AcquisitionReceipt.model_validate(json.loads(original_receipt["material_json"])).model_copy(update={"record_id": "acq:g4p1-alt"})
    catalog.record_acquisition_receipt(receipt_model, now=NOW)
    mismatched = reference_a.model_copy(update={"reference_id": "rights-lineage", "acquisition_receipt_ids": (receipt_model.record_id,)})
    result = preflight_governed_references(
        [mismatched, reference_b], catalog=catalog,
        retained_bytes=lambda artifact_id: b"represented source 1" if artifact_id == reference_a.representation_artifact_ids[0] else b"represented source 2",
        planned_processing_at=NOW,
    )
    assert result.accepted_count == 1
    assert result.tasks[0]["subject_id"] == reference_b.subject_id
    assert result.diagnostics[0].state == "rights_mismatched"

    cohort_id, run_id = _run(catalog, "7", "7")
    runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    assert runner.run(NOW) == 1
    assert catalog.budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")
