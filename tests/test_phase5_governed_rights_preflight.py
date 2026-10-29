from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    ProducerRef,
    PropositionAuthorityRole,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
    deterministic_id,
)
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.phase5_factory import ReferenceFactory
from charitygraph.phase5_governed_rights_preflight import (
    RightsPreflightReference,
    preflight_governed_rights,
)
from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.rights_governance_projection import RightsGovernanceProjection
from charitygraph.runtime.rights_governance_record import (
    INTERNAL_PRIVATE_USE_POLICY_ID,
    INTERNAL_PRIVATE_USE_POLICY_VERSION,
    RightsAxis,
    RightsGovernanceEvent,
    RightsGovernanceRecord,
    RightsGovernanceStore,
)


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="g4-t1-clean-fixture", version="1")
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test-authority:1", schema_version="1")


def _counts(catalog: SQLiteCatalog) -> tuple[int, ...]:
    with catalog._connection() as conn:
        return tuple(
            int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("tasks", "physical_attempts", "budget_reservations", "provider_receipts", "cost_entries")
        )


def _fixture(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    artifacts = ContentAddressedArtifactStore(tmp_path / "objects", catalog=catalog)
    subject_id = "subject:" + "a" * 32
    scope_id = "scope:" + "b" * 32
    definition_id = "srcdef:g4-t1-clean"
    source_url = "https://example.invalid/g4-t1-clean"

    catalog.register_subject(SubjectRecord(
        record_id="subjectrecord:" + subject_id.removeprefix("subject:"),
        created_at=NOW,
        producer=PRODUCER,
        subject_id=subject_id,
        subject_kind="organisation",
        lifecycle_status="active",
        identity_authority_refs=(ArtifactRef(artifact_id="authority:g4-t1-clean", content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="fixture-identity-v1",
        display_name="Clean fixture organisation",
    ))
    catalog.register_scope(ScopeRecord(
        record_id=scope_id,
        created_at=NOW,
        producer=PRODUCER,
        subject_id=subject_id,
        scope_kind="program",
        label="Clean fixture scope",
    ))
    definition = SourceDefinition(
        record_id=definition_id,
        created_at=NOW,
        producer=PRODUCER,
        publisher="Fixture publisher",
        source_class="official_website",
        authority_roles=(PropositionAuthorityRole(proposition="source", role="source-native"),),
        acquisition_locator=source_url,
        temporal_semantics="retrieval snapshot",
        publication_eligibility="private review only",
        steward="builder",
        rights_policy_id="CC_BY_4_0_V1",
    )
    catalog.register_source_definition(definition)
    source_bytes = b"clean governed source bytes"
    representation_bytes = b"clean governed representation bytes"
    source_artifact = artifacts.put(source_bytes)
    representation = artifacts.put_derived(representation_bytes, input_artifact_ids=(source_artifact.artifact_id,))
    receipt = AcquisitionReceipt(
        record_id="acq:g4-t1-clean",
        created_at=NOW,
        producer=PRODUCER,
        source_definition_id=definition_id,
        requested_locator=source_url,
        resolved_locator=source_url,
        retrieved_at=NOW,
        outcome="available",
        content_hash=source_artifact.content_hash,
        byte_size=source_artifact.byte_size,
        artifact_id=source_artifact.artifact_id,
    )
    catalog.record_acquisition_receipt(receipt)
    source_record = SourceRecord(
        record_id=deterministic_id("srcrec:", {
            "source_family": "official_website",
            "source_version": None,
            "source_locator": source_url,
            "payload_hash": source_artifact.content_hash,
        }),
        created_at=NOW,
        producer=PRODUCER,
        about_subject_ids=(subject_id,),
        source_family="official_website",
        source_role="source-native",
        source_locator=source_url,
        observed_at=NOW,
        payload_ref=source_artifact.artifact_id,
        payload_hash=source_artifact.content_hash,
        rights_policy_id="CC_BY_4_0_V1",
    )
    catalog.register_source_record(source_record)
    locator = catalog.register_evidence_locator(StructuredFieldLocator(
        artifact_id=representation.artifact_id,
        field_path="fixture.governed_field",
    ))
    record = RightsGovernanceRecord(
        decision_id="rights:g4-t1-clean",
        source_artifact_id=source_artifact.artifact_id,
        source_record_id=source_record.record_id,
        subject_id=subject_id,
        source_origin_url=source_url,
        source_role="source-native",
        acquisition_lineage_ids=(receipt.record_id,),
        representation_artifact_id=representation.artifact_id,
        representation_sha256=representation.content_hash,
        rights_basis="explicit_open_license",
        rights_policy_id="CC_BY_4_0_V1",
        rights_policy_version="1.0.0",
        purpose="semantic_analysis",
        scope=scope_id,
        evidence_locator=source_url,
        evidence_sha256=source_artifact.content_hash,
        assessed_on=NOW.date(),
        local_retention=RightsAxis(
            status="authorized",
            policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
            policy_version="1.0.0",
            decision_id="rights:g4-t1-clean:retention",
        ),
        provider_transmission=RightsAxis(status="blocked"),
        public_redistribution=RightsAxis(status="blocked"),
        status="authorized",
        review_status="current",
        actor_kind="human",
        actor_id="actor:g4-t1-clean",
        recorded_at=NOW,
        representation_class="structured_factual",
        factual_representation_only=True,
        lawful_access_confirmed=True,
        circumvention_used=False,
        one_source_native_entity_record=True,
        retention_lifecycle_status="active_until_review",
        retention_review_due_on=date(2027, 10, 28),
    )
    rights_root = tmp_path / "private-rights"
    rights_store = RightsGovernanceStore(rights_root)
    rights_store.put_record(record)
    projection = RightsGovernanceProjection(catalog.path).open()
    projection.rebuild_from_store(rights_store, as_of=NOW.date())
    request = RightsPreflightReference(
        reference_id="governed-rights-ref:g4-t1-clean",
        rights_record_id=record.content_hash,
        source_family="official_website",
        source_definition_id=definition_id,
        evidence_locator_ids=(locator["evidence_locator_id"],),
        claim_family_id="fixture-claim-family-v1",
        task_profile="fixture-governed-rights-task",
        difficulty="lower_cost_constrained_semantic",
        physical_bundle_opportunity="fixture-governed-rights-bundle",
    )
    return {
        "catalog": catalog,
        "artifacts": artifacts,
        "store": rights_store,
        "projection": projection,
        "record": record,
        "request": request,
        "representation": representation,
        "source_artifact": source_artifact,
        "now": NOW,
    }


def _register_run(catalog: SQLiteCatalog) -> tuple[str, str]:
    cohort_id = "cohort:" + "c" * 32
    run_id = "run:" + "d" * 32
    catalog.register_cohort({
        "record_id": cohort_id,
        "cohort_code": "G4-T1-CLEAN",
        "definition_version": "1",
        "membership_hash": "e" * 64,
        "budget_cap": {"amount": "100", "currency": "AUD"},
        "created_at": NOW,
    })
    catalog.register_run({
        "record_id": run_id,
        "cohort_id": cohort_id,
        "run_kind": "g4_t1_provider_free_fake_rehearsal",
        "status": "planned",
        "configuration_hash": "f" * 64,
        "created_at": NOW,
    })
    return cohort_id, run_id


def test_authority_preflight_lowers_to_factory_and_fake_restart_is_idempotent(tmp_path):
    from charitygraph.phase5_governed_factory_integration import GovernedReference

    if "rights_decision_ids" in GovernedReference.model_fields:
        pytest.skip("clean seam test is isolated from the pre-existing dirty rights prototype")
    fixture = _fixture(tmp_path)
    result = preflight_governed_rights(
        (fixture["request"],),
        store=fixture["store"],
        projection=fixture["projection"],
        catalog=fixture["catalog"],
        as_of=fixture["now"].date(),
        retained_bytes=fixture["artifacts"].read,
    )
    assert result.accepted_count == 1
    assert not result.diagnostics
    task_id = result.tasks[0]["logical_task_id"]
    assert result.tasks[0]["representation_hashes"] == ((fixture["representation"].artifact_id, fixture["representation"].content_hash),)
    assert result.tasks[0]["rights_policy_ids"] == ("CC_BY_4_0_V1",)
    assert task_id == preflight_governed_rights(
        (fixture["request"],), store=fixture["store"], projection=fixture["projection"],
        catalog=fixture["catalog"], as_of=fixture["now"].date(), retained_bytes=fixture["artifacts"].read,
    ).tasks[0]["logical_task_id"]

    cohort_id, run_id = _register_run(fixture["catalog"])
    runner = ReferenceFactory(fixture["catalog"], result.factory_plan, cohort_id=cohort_id, run_id=run_id)
    runner.seed(NOW)
    assert runner.run(NOW) == 1
    assert runner.run(NOW) == 0
    assert fixture["catalog"].budget_position(cohort_id).breach is False
    assert fixture["catalog"].budget_position(cohort_id).actual_spend_aud == Decimal("0.002000")


def test_denied_authority_creates_no_runtime_side_effects(tmp_path):
    fixture = _fixture(tmp_path)
    before = _counts(fixture["catalog"])
    missing = fixture["request"].model_copy(update={"rights_record_id": "f" * 64})
    result = preflight_governed_rights(
        (missing,), store=fixture["store"], projection=fixture["projection"],
        catalog=fixture["catalog"], as_of=fixture["now"].date(), retained_bytes=fixture["artifacts"].read,
    )
    assert result.accepted_count == 0
    assert result.diagnostics[0].state == "blocked"
    assert _counts(fixture["catalog"]) == before

    with fixture["projection"]._catalog._connection(immediate=True) as conn:
        conn.execute("DELETE FROM rights_projection_current")
        fixture["projection"]._catalog._commit(conn)
    result = preflight_governed_rights(
        (fixture["request"],), store=fixture["store"], projection=fixture["projection"],
        catalog=fixture["catalog"], as_of=fixture["now"].date(), retained_bytes=fixture["artifacts"].read,
    )
    assert result.accepted_count == 0
    assert result.diagnostics[0].state == "blocked"
    assert _counts(fixture["catalog"]) == before


def test_provider_authorization_is_not_invented_when_source_registry_is_absent(tmp_path):
    fixture = _fixture(tmp_path)
    record = fixture["record"]
    assert record.provider_transmission.status == "blocked"
    assert not hasattr(__import__("charitygraph.source_rights", fromlist=["x"]), "PROVIDER_POLICY_REGISTRY")


def test_internal_private_use_policy_fails_closed_for_unknown_source_family(tmp_path):
    fixture = _fixture(tmp_path)
    scope_id = "scope:" + "e" * 32
    fixture["catalog"].register_scope(ScopeRecord(
        record_id=scope_id,
        created_at=NOW,
        producer=PRODUCER,
        subject_id=fixture["record"].subject_id,
        scope_kind="organisation",
        label="Internal private-use policy fixture scope",
    ))
    values = fixture["record"].model_dump(mode="python")
    values.pop("record_id", None)
    values.update({
        "decision_id": "rights:g4-t3-unknown-family",
        "scope": scope_id,
        "rights_basis": "public_source_private_processing",
        "rights_policy_id": INTERNAL_PRIVATE_USE_POLICY_ID,
        "rights_policy_version": INTERNAL_PRIVATE_USE_POLICY_VERSION,
        "local_retention": RightsAxis(
            status="authorized",
            policy_id=INTERNAL_PRIVATE_USE_POLICY_ID,
            policy_version=INTERNAL_PRIVATE_USE_POLICY_VERSION,
            decision_id="rights:g4-t3-unknown-family:retention",
        ),
        "public_redistribution": RightsAxis(status="not_assessed"),
    })
    record = RightsGovernanceRecord.model_validate(values)
    fixture["store"].put_record(record)
    fixture["store"].put_event(RightsGovernanceEvent(
        record_id=record.content_hash,
        event_type="created",
        actor_kind="human",
        actor_id="actor:g4-t3-test",
        recorded_at=NOW,
    ))
    fixture["projection"].rebuild_from_store(fixture["store"], as_of=NOW.date())
    request = fixture["request"].model_copy(update={
        "reference_id": "governed-rights-ref:g4-t3-unknown-family",
        "rights_record_id": record.content_hash,
        "source_family": "unknown_family",
    })

    result = preflight_governed_rights(
        (request,),
        store=fixture["store"],
        projection=fixture["projection"],
        catalog=fixture["catalog"],
        as_of=fixture["now"].date(),
        retained_bytes=fixture["artifacts"].read,
    )
    assert result.accepted_count == 0
    assert result.diagnostics[0].state == "mismatched"
    assert "does not cover the source family" in result.diagnostics[0].reason
    assert _counts(fixture["catalog"]) == (0, 0, 0, 0, 0)
