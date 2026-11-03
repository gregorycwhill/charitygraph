import json
import importlib.util
from decimal import Decimal
from pathlib import Path

from charitygraph.contracts import SourceRecord
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_factory_integration import preflight_governed_references
from charitygraph.runtime import SQLiteCatalog
from charitygraph.source_rights import ArtifactRightsDecision


_integration_path = Path(__file__).with_name("test_phase5_governed_factory_integration.py")
_integration_spec = importlib.util.spec_from_file_location("g4_p3b1_integration_fixture", _integration_path)
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


def _rebind_source(catalog, reference, *, about_subject_ids, suffix, supersedes=False):
    source_row = catalog.get_source_record(reference.source_record_ids[0])
    assert source_row is not None
    source = SourceRecord.model_validate(json.loads(source_row["material_json"])).model_copy(
        update={
            "record_id": "srcrec:g4p3b1-" + suffix,
            "about_subject_ids": tuple(about_subject_ids),
        }
    )
    catalog.register_source_record(source)

    rights_row = catalog.get_artifact_rights_decision(reference.rights_decision_ids[0])
    assert rights_row is not None
    rights = ArtifactRightsDecision.model_validate(json.loads(rights_row["material_json"])["decision"])
    rights = rights.model_copy(update={
        "decision_id": "rights:g4p3b1-" + suffix,
        "source_record_id": source.record_id,
        "supersedes_decision_id": rights.decision_id if supersedes else None,
    })
    catalog.record_artifact_rights_decision(rights, now=NOW)
    return reference.model_copy(update={
        "reference_id": "governed-ref:g4p3b1-" + suffix,
        "source_record_ids": (source.record_id,),
        "rights_decision_ids": (rights.decision_id,),
    })


def test_unscoped_source_record_fails_closed_while_independent_peer_runs_and_reenters(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _catalog_b, _store_b, reference_b, representation_b = _fixture(
        tmp_path, "2", catalog=catalog, store=store
    )
    unscoped = _rebind_source(catalog, reference_a, about_subject_ids=(), suffix="unscoped")
    cross_subject = reference_a.model_copy(update={
        "reference_id": "governed-ref:g4p3b1-cross-subject",
        "subject_id": reference_b.subject_id,
        "scope_id": reference_b.scope_id,
    })
    bodies = {
        representation_a.artifact_id: b"represented source 1",
        representation_b.artifact_id: b"represented source 2",
    }
    blocked = preflight_governed_references(
        [unscoped, cross_subject], catalog=catalog, retained_bytes=bodies.__getitem__, planned_processing_at=NOW
    )
    assert blocked.accepted_count == 0
    assert {item.reference_id: item.state for item in blocked.diagnostics} == {
        unscoped.reference_id: "mismatched",
        cross_subject.reference_id: "mismatched",
    }
    assert "no explicit durable subject binding" in blocked.diagnostics[0].reason
    assert "different subject" in blocked.diagnostics[1].reason
    assert _work_counts(catalog) == {
        "tasks": 0, "physical_attempts": 0, "provider_receipts": 0,
        "budget_reservations": 0, "cost_entries": 0, "provider_request_attempts": 0,
    }

    accepted = preflight_governed_references(
        [reference_b], catalog=catalog, retained_bytes=bodies.__getitem__, planned_processing_at=NOW
    )
    assert accepted.accepted_count == 1
    assert not accepted.diagnostics
    cohort_id, run_id = _run(catalog, "p3b1", "p3b1")
    runner = ReferenceFactory(catalog, accepted.factory_plan, cohort_id=cohort_id, run_id=run_id)
    assert len(runner.seed(NOW)) == 1
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
    rerun = ReferenceFactory(reopened, accepted.factory_plan, cohort_id=cohort_id, run_id=run_id)
    rerun.seed(NOW)
    assert rerun.run(NOW) == 0
    assert _work_counts(reopened) == counts


def test_explicit_multi_subject_source_binding_is_accepted_for_each_bound_subject(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _catalog_b, _store_b, reference_b, _representation_b = _fixture(
        tmp_path, "2", catalog=catalog, store=store
    )
    multi = _rebind_source(
        catalog,
        reference_a,
        about_subject_ids=(reference_a.subject_id, reference_b.subject_id),
        suffix="multi",
        supersedes=True,
    )
    multi_for_a = multi
    multi_for_b = multi.model_copy(update={
        "reference_id": "governed-ref:g4p3b1-multi-b",
        "subject_id": reference_b.subject_id,
        "scope_id": reference_b.scope_id,
    })
    result = preflight_governed_references(
        [multi_for_a, multi_for_b],
        catalog=catalog,
        retained_bytes=lambda artifact_id: b"represented source 1" if artifact_id == representation_a.artifact_id else b"",
        planned_processing_at=NOW,
    )
    assert result.accepted_count == 2
    assert not result.diagnostics
    assert {task["subject_id"] for task in result.tasks} == {
        reference_a.subject_id, reference_b.subject_id,
    }
