from datetime import datetime, timezone
from decimal import Decimal

from charitygraph.baseline_corpus import MaterialOrigin
from charitygraph.contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    ProducerRef,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
    canonical_sha256,
    deterministic_id,
)
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_factory_integration import (
    GovernedReference,
    preflight_governed_references,
)
from charitygraph.runtime import SQLiteCatalog


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="g4-p1-fixture", version="1")
AUTHORITY_SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test-authority:1", schema_version="1")


def _subject(subject_id: str) -> SubjectRecord:
    return SubjectRecord(
        record_id="subjectrecord:" + subject_id[-32:],
        created_at=NOW,
        producer=PRODUCER,
        subject_id=subject_id,
        subject_kind="organisation",
        lifecycle_status="active",
        identity_authority_refs=(ArtifactRef(artifact_id="decision:" + subject_id[-32:], content_hash="a" * 64, schema=AUTHORITY_SCHEMA),),
        identity_policy_id="fixture-identity-v1",
        display_name="Fixture organisation",
    )


def _fixture(tmp_path, suffix: str = "1", *, scope: bool = True, catalog=None, store=None):
    catalog = catalog or SQLiteCatalog(tmp_path / f"catalog-{suffix}.sqlite3").open(initialize=True)
    store = store or ContentAddressedArtifactStore(tmp_path / f"objects-{suffix}", catalog=catalog)
    subject_id = "subject:" + suffix * 32
    catalog.register_subject(_subject(subject_id))
    scope_id = None
    if scope:
        scope_id = "scope:" + suffix * 32
        catalog.register_scope(ScopeRecord(
            record_id=scope_id,
            created_at=NOW,
            producer=PRODUCER,
            subject_id=subject_id,
            scope_kind="program",
            label="Fixture program",
        ))
    definition = SourceDefinition(
        record_id="srcdef:g4p1-" + suffix,
        created_at=NOW,
        producer=PRODUCER,
        publisher="Fixture publisher",
        source_class="official_website",
        authority_roles=({"proposition": "source", "role": "source-native"},),
        acquisition_locator="https://example.org/fixture/" + suffix,
        temporal_semantics="retrieval snapshot",
        publication_eligibility="private review only",
        steward="builder",
        rights_policy_id="fixture-rights-v1",
    )
    catalog.register_source_definition(definition)
    raw = store.put(("raw source " + suffix).encode())
    representation = store.put_derived(("represented source " + suffix).encode(), input_artifact_ids=(raw.artifact_id,))
    receipt = AcquisitionReceipt(
        record_id="acq:g4p1-" + suffix,
        created_at=NOW,
        producer=PRODUCER,
        source_definition_id=definition.record_id,
        requested_locator=definition.acquisition_locator,
        resolved_locator=definition.acquisition_locator,
        retrieved_at=NOW,
        outcome="available",
        content_hash=raw.content_hash,
        byte_size=raw.byte_size,
        artifact_id=raw.artifact_id,
    )
    catalog.record_acquisition_receipt(receipt)
    source_record = SourceRecord(
        record_id=deterministic_id("srcrec:", {"source_family": "official_website", "source_version": None, "source_locator": definition.acquisition_locator, "payload_hash": raw.content_hash}),
        created_at=NOW,
        producer=PRODUCER,
        about_subject_ids=(subject_id,),
        source_family="official_website",
        source_role="source-native",
        source_locator=definition.acquisition_locator,
        observed_at=NOW,
        payload_ref=raw.artifact_id,
        payload_hash=raw.content_hash,
        rights_policy_id="fixture-rights-v1",
    )
    catalog.register_source_record(source_record)
    locator = catalog.register_evidence_locator(StructuredFieldLocator(
        artifact_id=representation.artifact_id,
        field_path="fixture.field",
    ))
    reference = GovernedReference(
        reference_id="governed-ref:" + suffix,
        subject_id=subject_id,
        scope_id=scope_id,
        source_family="official_website",
        source_definition_id=definition.record_id,
        acquisition_receipt_ids=(receipt.record_id,),
        source_record_ids=(source_record.record_id,),
        evidence_locator_ids=(locator["evidence_locator_id"],),
        representation_artifact_ids=(representation.artifact_id,),
        representation_hashes={representation.artifact_id: representation.content_hash},
        rights_policy_id="fixture-rights-v1",
        rights_role="provider-input-review",
        claim_family_id="program-service-discovery-v2",
        task_profile="fixture_reference_task",
        difficulty="lower_cost_constrained_semantic",
        physical_bundle_opportunity="fixture-bundle",
    )
    return catalog, store, reference, representation


def _run(catalog, cohort_suffix: str, run_suffix: str):
    cohort_id = "cohort:" + cohort_suffix * 32
    run_id = "run:" + run_suffix * 32
    catalog.register_cohort({
        "record_id": cohort_id,
        "cohort_code": "G4-P1",
        "definition_version": "1",
        "membership_hash": "b" * 64,
        "budget_cap": {"amount": "100", "currency": "AUD"},
        "created_at": NOW,
    })
    catalog.register_run({
        "record_id": run_id,
        "cohort_id": cohort_id,
        "run_kind": "g4_p1_provider_free_rehearsal",
        "status": "planned",
        "configuration_hash": "c" * 64,
        "created_at": NOW,
    })
    return cohort_id, run_id


def test_governed_reference_is_hash_checked_lowered_and_durable(tmp_path):
    catalog, store, reference, representation = _fixture(tmp_path)
    body = ("represented source 1").encode()
    first = preflight_governed_references([reference], catalog=catalog, retained_bytes=lambda artifact_id: body)
    second = preflight_governed_references([reference], catalog=catalog, retained_bytes=lambda artifact_id: body)

    assert first.accepted_count == 1
    assert not first.diagnostics
    assert first.tasks[0]["logical_task_id"] == second.tasks[0]["logical_task_id"]
    assert first.tasks[0]["source_record_ids"] == reference.source_record_ids
    assert first.tasks[0]["representation_artifact_ids"] == (representation.artifact_id,)
    assert first.tasks[0]["rights_roles"] == ("provider-input-review",)

    cohort_id, run_id = _run(catalog, "1", "1")
    runner = ReferenceFactory(catalog, first.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runtime_tasks = runner.seed(NOW)
    row = catalog.get_task(runtime_tasks[0]["record_id"])
    assert row["task_material_json"] is not None
    assert catalog.get_task(runtime_tasks[0]["record_id"])["subject_id"] == reference.subject_id
    with catalog._connection() as conn:
        evidence = conn.execute("SELECT evidence_id FROM model_task_evidence WHERE model_task_id=?", (runtime_tasks[0]["record_id"],)).fetchall()
    assert len(evidence) == 1
    assert runner.run(NOW) == 1
    assert runner.run(NOW) == 0
    position = catalog.budget_position(cohort_id)
    assert position.breach is False
    assert position.actual_spend_aud == Decimal("0.002000")


def test_non_ready_governed_states_are_differentiated_and_never_planned(tmp_path):
    catalog, _store, reference, _representation = _fixture(tmp_path)
    variants = [
        reference.model_copy(update={"reference_id": "missing", "declared_state": "missing"}),
        reference.model_copy(update={"reference_id": "blocked", "declared_state": "blocked"}),
        reference.model_copy(update={"reference_id": "structural", "declared_state": "structurally_invalid"}),
        reference.model_copy(update={"reference_id": "not-applicable", "declared_state": "not_applicable"}),
        reference.model_copy(update={"reference_id": "not-processed", "declared_state": "not_processed"}),
        reference.model_copy(update={"reference_id": "retrieval", "declared_state": "retrieval_failed"}),
        reference.model_copy(update={"reference_id": "mismatch", "representation_hashes": {reference.representation_artifact_ids[0]: "d" * 64}}),
        reference.model_copy(update={"reference_id": "unrecoverable", "acquisition_receipt_ids": ()}),
    ]
    result = preflight_governed_references(variants, catalog=catalog)
    assert result.accepted_count == 0
    assert {item.reference_id: item.state for item in result.diagnostics} == {
        "missing": "missing",
        "blocked": "blocked",
        "structural": "structurally_invalid",
        "not-applicable": "not_applicable",
        "not-processed": "not_processed",
        "retrieval": "retrieval_failed",
        "mismatch": "mismatched",
        "unrecoverable": "unrecoverable",
    }


def test_scope_isolation_failure_visibility_and_ambiguous_restart(tmp_path):
    catalog_a, store_a, reference_a, _ = _fixture(tmp_path, "1")
    # The second fixture is registered in the same catalog as an independent unit.
    _catalog_b, _store_b, reference_b, _ = _fixture(tmp_path, "2", catalog=catalog_a, store=store_a)
    first = preflight_governed_references([reference_a], catalog=catalog_a, retained_bytes=lambda _: b"represented source 1")
    assert first.accepted_count == 1
    isolated = preflight_governed_references([reference_a.model_copy(update={"subject_id": reference_b.subject_id, "scope_id": reference_a.scope_id})], catalog=catalog_a)
    assert isolated.accepted_count == 0
    assert isolated.diagnostics[0].state == "mismatched"

    cohort_id, run_id = _run(catalog_a, "2", "2")
    runner = ReferenceFactory(catalog_a, first.factory_plan, cohort_id=cohort_id, run_id=run_id)
    tasks = runner.seed(NOW)
    package_id = deterministic_id("taskrun:", {"members": [tasks[0]["record_id"]], "mode": runner.delivery_mode})
    physical_id = "physical:" + package_id.split(":", 1)[1]
    try:
        runner.run(NOW, interruptions={physical_id: "send_ambiguous"})
    except RuntimeError as exc:
        assert "simulated loss after send" in str(exc)
    else:
        raise AssertionError("ambiguous send must stop before blind resend")
    assert catalog_a.get_physical_attempt(physical_id)["status"] == "send_started"
    runner.reconcile_ambiguous_package(package_id, now=NOW)
    assert runner.run(NOW) == 1
    assert runner.run(NOW) == 0
    assert catalog_a.budget_position(cohort_id).breach is False


def test_independent_unit_failure_does_not_repeat_successful_unit(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _catalog, _store, reference_b, representation_b = _fixture(tmp_path, "2", catalog=catalog, store=store)
    bodies = {
        representation_a.artifact_id: b"represented source 1",
        representation_b.artifact_id: b"represented source 2",
    }
    result = preflight_governed_references([reference_a, reference_b], catalog=catalog, retained_bytes=bodies.__getitem__)
    assert result.accepted_count == 2
    cohort_id, run_id = _run(catalog, "4", "4")
    runner = ReferenceFactory(catalog, result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    tasks = runner.seed(NOW)
    by_logical = {task["logical_task_id"]: task for task in tasks}
    packages = runner.plan.physical_packages()
    package_ids = [
        deterministic_id("taskrun:", {"members": [by_logical[item["logical_task_id"]]["record_id"] for item in package], "mode": runner.delivery_mode})
        for package in packages
    ]
    failed_physical = "physical:" + package_ids[0].split(":", 1)[1]
    assert runner.run(NOW, failures={failed_physical: "structural"}) == 2
    statuses = {task["subject_id"]: catalog.get_task(task["record_id"])["status"] for task in tasks}
    assert set(statuses.values()) == {"failed_terminal", "succeeded"}
    assert runner.run(NOW) == 0
    assert catalog.budget_position(cohort_id).breach is False
