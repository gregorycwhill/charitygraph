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
from charitygraph.source_rights import (
    OPENAI_PROVIDER_POLICY_ID,
    PUBLIC_FACTS_ONLY_POLICY_ID,
    ArtifactRightsDecision,
)


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


def _fixture(tmp_path, suffix: str = "1", *, subject_suffix: str | None = None, scope_suffix: str | None = None, scope: bool = True, catalog=None, store=None):
    catalog = catalog or SQLiteCatalog(tmp_path / f"catalog-{suffix}.sqlite3").open(initialize=True)
    store = store or ContentAddressedArtifactStore(tmp_path / f"objects-{suffix}", catalog=catalog)
    subject_suffix = subject_suffix or suffix
    scope_suffix = scope_suffix or suffix
    subject_id = "subject:" + subject_suffix * 32
    catalog.register_subject(_subject(subject_id))
    scope_id = None
    if scope:
        scope_id = "scope:" + scope_suffix * 32
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
        rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
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
        rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
    )
    catalog.register_source_record(source_record)
    locator = catalog.register_evidence_locator(StructuredFieldLocator(
        artifact_id=representation.artifact_id,
        field_path="fixture.field",
    ))
    rights = ArtifactRightsDecision(
        decision_id="rights:g4p1-" + suffix,
        source_artifact_id=raw.artifact_id,
        representation_artifact_id=representation.artifact_id,
        source_record_id=source_record.record_id,
        source_origin_url=definition.acquisition_locator,
        source_role=source_record.source_role,
        acquisition_lineage_ids=(receipt.record_id,),
        transmitted_representation_sha256=representation.content_hash,
        rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
        rights_policy_version="1.0.0",
        provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
        provider_processing_policy_version="1",
        rights_basis="public_facts_only",
        evidence_locator=definition.acquisition_locator,
        evidence_sha256=raw.content_hash,
        assessed_on=NOW.date(),
        assessment_scope="synthetic provider-free fixture",
        assessment_authority="fixture-rights-authority-v1",
        local_retention_allowed=False,
        provider_transmission_allowed=True,
        public_redistribution_allowed=False,
        factual_representation_only=True,
        representation_class="structured_factual",
        publicly_accessible_without_circumvention=True,
        access_controls_bypassed=False,
        lawfully_acquired=True,
        analytical_purpose="evidence_grounded_knowledge_construction",
        provider_no_training_default=True,
        provider_data_sharing_opt_in=False,
    )
    catalog.record_artifact_rights_decision(rights, now=NOW)
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
        rights_decision_ids=(rights.decision_id,),
        rights_policy_id=PUBLIC_FACTS_ONLY_POLICY_ID,
        rights_role=source_record.source_role,
        provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
        provider_processing_policy_version="1",
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
    assert first.tasks[0]["rights_roles"] == ("source-native",)

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
    result = preflight_governed_references([reference, *variants], catalog=catalog, retained_bytes=lambda _: b"represented source 1")
    assert result.accepted_count == 1
    assert len(result.tasks) == 1
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


def test_governed_factory_isolates_scopes_and_subjects_in_durable_physical_work(tmp_path):
    catalog, store, reference_a, representation_a = _fixture(tmp_path, "1")
    _, _, reference_same_scope, representation_same_scope = _fixture(
        tmp_path, "1b", subject_suffix="1", scope_suffix="1", catalog=catalog, store=store
    )
    _, _, reference_other_scope, representation_other_scope = _fixture(
        tmp_path, "1c", subject_suffix="1", scope_suffix="1c", catalog=catalog, store=store
    )
    _, _, reference_other_subject, representation_other_subject = _fixture(
        tmp_path, "2", catalog=catalog, store=store
    )
    references = [reference_a, reference_same_scope, reference_other_scope, reference_other_subject]
    bodies = {
        representation_a.artifact_id: b"represented source 1",
        representation_same_scope.artifact_id: b"represented source 1b",
        representation_other_scope.artifact_id: b"represented source 1c",
        representation_other_subject.artifact_id: b"represented source 2",
    }

    preflight = preflight_governed_references(references, catalog=catalog, retained_bytes=bodies.__getitem__)
    assert preflight.accepted_count == 4
    assert not preflight.diagnostics
    assert {task["scope_id"] for task in preflight.tasks if task["subject_id"] == reference_a.subject_id} == {
        reference_a.scope_id, reference_other_scope.scope_id
    }
    assert len({task["logical_task_id"] for task in preflight.tasks}) == 4

    cohort_id, run_id = _run(catalog, "5", "5")
    runner = ReferenceFactory(catalog, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runtime_tasks = runner.seed(NOW)
    packages = runner.plan.physical_packages()
    assert {(package[0]["subject_id"], package[0]["scope_id"], len(package)) for package in packages} == {
        (reference_a.subject_id, reference_a.scope_id, 2),
        (reference_other_scope.subject_id, reference_other_scope.scope_id, 1),
        (reference_other_subject.subject_id, reference_other_subject.scope_id, 1),
    }
    assert runner.run(NOW) == 4

    with catalog._connection() as conn:
        member_rows = conn.execute(
            """
            SELECT pam.physical_attempt_id, t.subject_id, t.scope_id
            FROM physical_attempt_members pam
            JOIN tasks t ON t.model_task_id = pam.model_task_id
            ORDER BY pam.physical_attempt_id, t.model_task_id
            """
        ).fetchall()
        attempt_count = conn.execute("SELECT COUNT(*) FROM physical_attempts").fetchone()[0]
        receipt_count = conn.execute("SELECT COUNT(*) FROM provider_receipts").fetchone()[0]
        cost_count = conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0]
    members_by_attempt = {}
    for row in member_rows:
        members_by_attempt.setdefault(row[0], []).append((row[1], row[2]))
    assert attempt_count == receipt_count == 3
    assert cost_count == 6  # one actual and one release entry per physical package
    assert all(len({subject_id for subject_id, _ in members}) == 1 for members in members_by_attempt.values())
    assert all(len({scope_id for _, scope_id in members}) == 1 for members in members_by_attempt.values())
    assert any(len(members) == 2 for members in members_by_attempt.values())

    catalog.close()
    reopened = SQLiteCatalog(catalog.path).open()
    rerun = ReferenceFactory(reopened, preflight.factory_plan, cohort_id=cohort_id, run_id=run_id)
    rerun.seed(NOW)
    assert rerun.run(NOW) == 0
    with reopened._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM physical_attempts").fetchone()[0] == attempt_count
        assert conn.execute("SELECT COUNT(*) FROM provider_receipts").fetchone()[0] == receipt_count
        assert conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0] == cost_count
    position = reopened.budget_position(cohort_id)
    assert position.outstanding_reserved_exposure_aud == Decimal("0.000000")
    assert position.actual_spend_aud == Decimal("0.006000")
    assert position.breach is False


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
