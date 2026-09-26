"""Destructive checks for migration-22 concrete S0 source authority."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from charitygraph.runtime import CatalogError, ConflictError, SQLiteCatalog
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from charitygraph.runtime.migrations import SUPPORTED_VERSION
from charitygraph.s0_acquisition_bridge import GovernedAcquisition, OfflineResponse, SourcePlan
from charitygraph.s0_governed_transport import GovernedSourceTransport, GovernedTransportError
from charitygraph.scale_s0 import DocumentRepresentation, ExecutionAttemptIdentity, ScalePreflightError, ScaleS0Preflight, SourceAuthorisation
from runtime.test_scale_s0_durability import REGISTRY, authority


NOW = datetime(2026, 9, 21, tzinfo=timezone.utc).isoformat()


def _attempt(mandate, *, attempt_id="attempt:source-authority", run_id="run:source-authority"):
    values = {
        "attempt_id": attempt_id, "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash,
        "slice_id": mandate.slice_id, "run_id": run_id, "builder_repository": "builder:test",
        "builder_commit_sha": "b" * 40, "data_repository": "data:test", "data_commit_sha": "d" * 40,
        "bridge_certification": "S0_SOURCE_AUTHORITY_RUNTIME_CERTIFIED", "bridge_version": "2",
        "schema_version": 22, "recovery_authority_ref": "recovery:source-authority", "status": "prepared",
        "created_at": NOW,
    }
    values["configuration_hash"] = canonical_execution_configuration_hash(**{
        key: values[key] for key in (
            "mandate_hash", "slice_id", "run_id", "builder_repository", "builder_commit_sha",
            "data_repository", "data_commit_sha", "bridge_certification", "bridge_version",
            "schema_version", "recovery_authority_ref",
        )
    })
    return ExecutionAttemptIdentity(**values)


def _catalog(tmp_path):
    mandate, routing, policies, source, _packet, _economics = authority()
    catalog = SQLiteCatalog(tmp_path / "source-authority.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {})
    attempt = _attempt(mandate)
    catalog.register_cohort({"record_id": "cohort:source-authority", "cohort_code": "S0-AUTHORITY", "definition_version": "1", "membership_hash": "e" * 64, "budget_cap": {"amount": "8", "currency": "AUD"}, "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:source-authority", "run_kind": "s0", "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    return catalog, mandate, routing, policies, source, attempt


def _source_authority(mandate, policies, source, attempt, **changes):
    values = {
        "source_id": source.source_id, "source_family": source.source_family,
        "url_or_identity": source.url_or_identity, "authority_role": source.authority_role,
        "rights_transmission_status": "permitted", "acquisition_state": "authorised",
        "parsing_state": "not_processed", "snapshot_hash": "", "claim_families": source.claim_families,
        "source_record_id": "", "rights_policy_version": policies["rights_transmission"].version,
        "specialist_authorisation_id": None, "access_classification": "OPEN_WEB_PUBLIC",
        "technical_access_state": "accessible", "source_authority_id": "source-authority:one",
        "mandate_id": mandate.mandate_id, "mandate_hash": mandate.identity_hash, "slice_id": mandate.slice_id,
        "execution_attempt_id": attempt.attempt_id, "subject_id": "subject:a",
        "exact_resource_id": "resource:annual-report:2026", "rights_policy_id": mandate.rights_transmission_policy_id,
        "rights_decision_id": "rights-decision:one", "authority_material": {"record": "rights:one", "resource_version": "2026"},
        "created_at": NOW,
    }
    values.update(changes)
    return SourceAuthorisation(**values)


def test_migration_22_separates_policy_mandate_from_concrete_resource_authority(tmp_path):
    catalog, mandate, routing, policies, source, attempt = _catalog(tmp_path)
    assert SUPPORTED_VERSION == 27
    with pytest.raises(ScalePreflightError, match="separately"):
        ScaleS0Preflight.register_durable_mandate(catalog, mandate, REGISTRY, routing, policies, {source.source_id: source})
    stored = catalog.get_scale_s0_mandate(mandate.mandate_id)
    assert "sources" not in stored["authority"]
    concrete = _source_authority(mandate, policies, source, attempt)
    recorded = ScaleS0Preflight.register_durable_source_authority(catalog, concrete)
    assert recorded["execution_attempt_id"] == attempt.attempt_id
    assert recorded["authority_material_hash"]
    assert catalog.get_scale_s0_source_authority_for_source(execution_attempt_id=attempt.attempt_id, source_id=source.source_id)["source_authority_id"] == concrete.source_authority_id


def test_concrete_source_authority_is_append_only_idempotent_and_substitution_resistant(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    concrete = _source_authority(mandate, policies, source, attempt)
    first = ScaleS0Preflight.register_durable_source_authority(catalog, concrete)
    assert ScaleS0Preflight.register_durable_source_authority(catalog, concrete)["material_hash"] == first["material_hash"]
    for changed in (
        replace(concrete, url_or_identity="https://example.invalid/substituted"),
        replace(concrete, exact_resource_id="resource:substituted"),
        replace(concrete, rights_decision_id="rights-decision:substituted"),
        replace(concrete, rights_policy_version="substituted"),
        replace(concrete, access_classification="SEPARATELY_LICENSED_OR_CONTROLLED",
                specialist_authorisation_id=mandate.specialist_source_policy_id,
                authority_material={
                    "resource_id": concrete.exact_resource_id, "resource_version": "2026",
                    "licence_id": "licence:controlled:substitution", "licence_version": "2026-09",
                    "rights_authority_id": "rights-authority:substitution",
                }),
        replace(concrete, technical_access_state="login_required"),
        replace(concrete, authority_material={"record": "substituted"}),
        replace(concrete, source_family="outside-source-family"),
        replace(concrete, subject_id="subject:outside"),
    ):
        with pytest.raises(ConflictError):
            ScaleS0Preflight.register_durable_source_authority(catalog, changed)
    with pytest.raises(ConflictError, match="competing source authorities"):
        ScaleS0Preflight.register_durable_source_authority(catalog, replace(concrete, source_authority_id="source-authority:two"))
    with pytest.raises(ConflictError, match="exact source rights decision"):
        ScaleS0Preflight.register_durable_source_authority(catalog, replace(concrete, source_authority_id="source-authority:three", source_id="source:three"))


def test_concrete_source_authority_requires_every_runtime_binding_and_detects_tampering(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    concrete = _source_authority(mandate, policies, source, attempt)
    for incomplete in (
        replace(concrete, source_authority_id=""),
        replace(concrete, exact_resource_id=""),
        replace(concrete, rights_policy_id=""),
        replace(concrete, rights_decision_id=""),
        replace(concrete, authority_material={}),
        replace(concrete, created_at="2026-09-21"),
    ):
        with pytest.raises((CatalogError, ConflictError)):
            ScaleS0Preflight.register_durable_source_authority(catalog, incomplete)
    ScaleS0Preflight.register_durable_source_authority(catalog, concrete)
    with catalog._connection(immediate=True) as conn:
        conn.execute("UPDATE scale_s0_source_authorities SET locator=? WHERE source_authority_id=?", ("https://example.invalid/tampered", concrete.source_authority_id))
        catalog._commit(conn)
    plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, "subject:a", "scope:a", source.source_family,
        "governed_http", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", source.url_or_identity,
        mandate.policy_hashes["source_universe"], NOW)
    catalog.register_scale_s0_source_plan({**plan.__dict__, "plan_id": plan.plan_id}, execution_attempt_id=attempt.attempt_id)
    from unittest.mock import Mock
    transport = GovernedSourceTransport(); transport._opener = Mock()
    with pytest.raises(GovernedTransportError, match="integrity"):
        transport.fetch(plan, concrete, mandate, catalog=catalog, execution_attempt_id=attempt.attempt_id)
    transport._opener.open.assert_not_called()


def test_live_transport_and_acquisition_resolve_only_durable_concrete_authority(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, "subject:a", "scope:a", source.source_family,
        "governed_http", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", source.url_or_identity,
        mandate.policy_hashes["source_universe"], NOW)
    catalog.register_scale_s0_source_plan({**plan.__dict__, "plan_id": plan.plan_id}, execution_attempt_id=attempt.attempt_id)
    concrete = _source_authority(mandate, policies, source, attempt)
    ScaleS0Preflight.register_durable_source_authority(catalog, concrete)
    transport = GovernedSourceTransport()
    response = type("Response", (), {})()
    response.status = 200; response.getcode = lambda: 200; response.headers = {"Content-Type": "text/html"}
    chunks = iter((b"fixture", b""))
    response.read = lambda _size: next(chunks); response.close = lambda: None
    from unittest.mock import Mock
    transport._opener = Mock(); transport._opener.open.return_value = response
    caller_spoof = replace(concrete, source_id="source:caller-spoof", url_or_identity="https://example.invalid/spoof", technical_access_state="login_required")
    snapshot = GovernedAcquisition(mandate).acquire_transport(plan, caller_spoof, transport,
        representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only",
        catalog=catalog, execution_attempt_id=attempt.attempt_id, now=datetime.fromisoformat(NOW))
    assert snapshot.source_id == concrete.source_id
    assert catalog.get_scale_s0_source_snapshot(concrete.source_id)["execution_attempt_id"] == attempt.attempt_id
    assert transport._opener.open.call_count == 1
    transport._opener.reset_mock()
    with pytest.raises(GovernedTransportError, match="authority"):
        transport.fetch(plan, replace(concrete, source_authority_id=""), mandate, catalog=catalog, execution_attempt_id=attempt.attempt_id)
    transport._opener.open.assert_not_called()


def test_live_transport_rejects_caller_authority_without_durable_catalogue_before_socket(tmp_path):
    _catalogue, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, "subject:a", "scope:a", source.source_family,
        "governed_http", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", source.url_or_identity,
        mandate.policy_hashes["source_universe"], NOW)
    concrete = _source_authority(mandate, policies, source, attempt)
    from unittest.mock import Mock
    transport = GovernedSourceTransport(); transport._opener = Mock()
    with pytest.raises(GovernedTransportError, match="durable catalogue"):
        transport.fetch(plan, concrete, mandate)
    transport._opener.open.assert_not_called()


def test_cross_attempt_and_cross_mandate_authority_substitution_fail_before_socket(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    alternate = _attempt(mandate, attempt_id="attempt:source-authority:alternate", run_id="run:source-authority:alternate")
    catalog.register_run({"record_id": alternate.run_id, "cohort_id": "cohort:source-authority", "run_kind": "s0", "status": "planned", "configuration_hash": alternate.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, alternate)
    concrete = _source_authority(mandate, policies, source, attempt)
    alternate_authority = replace(concrete, source_authority_id="source-authority:alternate", execution_attempt_id=alternate.attempt_id)
    ScaleS0Preflight.register_durable_source_authority(catalog, concrete)
    ScaleS0Preflight.register_durable_source_authority(catalog, alternate_authority)
    with pytest.raises(ConflictError, match="mandate or attempt binding"):
        ScaleS0Preflight.register_durable_source_authority(catalog, replace(
            concrete, source_authority_id="source-authority:stale-mandate", mandate_hash="f" * 64,
        ))
    plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, "subject:a", "scope:a", source.source_family,
        "governed_http", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", source.url_or_identity,
        mandate.policy_hashes["source_universe"], NOW)
    catalog.register_scale_s0_source_plan({**plan.__dict__, "plan_id": plan.plan_id}, execution_attempt_id=attempt.attempt_id)
    from unittest.mock import Mock
    transport = GovernedSourceTransport(); transport._opener = Mock()
    with pytest.raises(GovernedTransportError, match="live plan binding"):
        transport.fetch(plan, alternate_authority, mandate, catalog=catalog, execution_attempt_id=attempt.attempt_id)
    transport._opener.open.assert_not_called()


def test_controlled_authority_requires_exact_resource_and_licence_material(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    controlled = _source_authority(
        mandate, policies, source, attempt, source_authority_id="source-authority:controlled",
        access_classification="SEPARATELY_LICENSED_OR_CONTROLLED",
        specialist_authorisation_id=mandate.specialist_source_policy_id,
        authority_material={
            "resource_id": "resource:annual-report:2026", "resource_version": "2026",
            "licence_id": "licence:controlled:one", "licence_version": "2026-09",
            "rights_authority_id": "rights-authority:one",
        },
    )
    with pytest.raises(CatalogError, match="licence"):
        ScaleS0Preflight.register_durable_source_authority(catalog, replace(controlled, authority_material={"record": "unbound"}))
    with pytest.raises(ConflictError, match="exact resource"):
        ScaleS0Preflight.register_durable_source_authority(catalog, replace(controlled, authority_material={
            **controlled.authority_material, "resource_id": "resource:sibling:2026",
        }))
    assert ScaleS0Preflight.register_durable_source_authority(catalog, controlled)["source_authority_id"] == controlled.source_authority_id


def test_catalogue_fixture_acquisition_is_explicitly_offline_or_fails_before_writes(tmp_path):
    catalog, mandate, _routing, policies, source, attempt = _catalog(tmp_path)
    plan = SourcePlan(mandate.mandate_id, mandate.identity_hash, mandate.slice_id, "subject:a", "scope:a", source.source_family,
        "fixture", "OPEN_WEB_PUBLIC", "annual_report", "official", "mandatory", source.url_or_identity,
        mandate.policy_hashes["source_universe"], NOW)
    concrete = _source_authority(mandate, policies, source, attempt)
    response = OfflineResponse(b"fixture", "text/plain", plan.locator)
    with pytest.raises(ScalePreflightError, match="durable concrete"):
        GovernedAcquisition(mandate).acquire(plan, concrete, response,
            representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", catalog=catalog, now=datetime.fromisoformat(NOW))
    with catalog._connection() as conn:
        assert conn.execute("SELECT count(*) FROM source_records").fetchone()[0] == 0
    offline = GovernedAcquisition(mandate).acquire(plan, concrete, response,
        representation=DocumentRepresentation.RELIABLE_TEXT, representation_mode="text_extraction_only", catalog=catalog,
        now=datetime.fromisoformat(NOW), offline=True)
    assert offline.source_id != concrete.source_id
