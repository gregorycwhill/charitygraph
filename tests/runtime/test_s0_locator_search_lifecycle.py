from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.catalog import (
    CatalogError,
    ConflictError,
    S0_LIVE_SEND_ATTESTER,
    S0_LIVE_SEND_OBSERVED_VALUE,
    S0_LIVE_SEND_SETTING_NAME,
    canonical_execution_configuration_hash,
)
from charitygraph.s0_acquisition_bridge import bundle_packets
from charitygraph.s0_locator_discovery import (
    LocatorSearchPrice,
    OpenAIResponsesWebSearchProvider,
    S0LocatorSearchExecutionGate,
    freeze_locator_search_packet,
    prepare_locator_search_request,
)
from charitygraph.phase5_standard_transport import (
    OpenAIHTTPStandardClient,
    OpenAIResponsesWebSearchTransport,
    StandardSystemic,
)
from charitygraph.scale_s0 import (
    EconomicState,
    ExecutionAttemptIdentity,
    PolicyArtifact,
    RoutingClass,
    RoutingPolicy,
    ScaleMandate,
    ScalePreflightError,
    ScaleS0Preflight,
    default_s0_registry,
    packet_task_key,
)


# Keep durable test fixtures beyond wall-clock expiry because the catalog
# deliberately validates a reservation against the real clock before a send.
NOW = datetime(2099, 9, 22, tzinfo=timezone.utc)
SUBJECT = "11111111111"
AUTHORITY = "SCALE_S0_LIVE_LOCATOR_ACTIVATION_2026-09-22.md#CG-S0-PO-LIVE-LOCATOR-2026-09-22"
PROJECT = "proj:synthetic-locator"


def _authority():
    registry = default_s0_registry()
    routing = RoutingPolicy("routing:locator", "1", frozenset(RoutingClass), {})
    ids = {
        "sampling": ("sampling:locator", "1"), "review": ("review:locator", "1"),
        "promotion": ("promotion:locator", "1"), "halt": ("halt:locator", "1"),
        "reservation": ("reservation:locator", "1"), "source_universe": ("sources:locator", "1"),
        "specialist_source": ("specialist:locator", "1"), "rights_transmission": ("rights:locator", "1"),
    }
    policies = {name: PolicyArtifact(policy_id, version, name[0] * 64) for name, (policy_id, version) in ids.items()}
    policies["routing"] = PolicyArtifact(routing.policy_id, routing.version, routing.immutable_hash)
    mandate = ScaleMandate(
        mandate_id="mandate:locator", mandate_version="1", slice_id="slice:locator", created_at=NOW.isoformat(),
        authorizing_actor_ref="actor:synthetic", population_ref="population:synthetic", subject_ids=(SUBJECT,),
        snapshot_as_of="2026-09-22", ranking_policy_id="ranking:synthetic", group_entity_policy_id="group:synthetic",
        source_universe_policy_id="sources:locator", source_universe_policy_version="1",
        mandatory_source_families=("official_website",), applicable_source_families=("official_website",),
        specialist_source_policy_id="specialist:locator", rights_transmission_policy_id="rights:locator",
        task_registry_version=registry.version, enabled_task_ids=tuple(task.task_id for task in registry.contracts),
        disabled_task_ids=(), routing_policy_id="routing:locator", routing_policy_version="1",
        provider_spend_ceiling="8.00", strong_model_spend_ceiling="4.00", provider_call_ceiling=150,
        reservation_policy_id="reservation:locator", currency_basis="USD", review_policy_id="review:locator",
        review_policy_version="1", promotion_policy_id="promotion:locator", promotion_policy_version="1",
        sampling_policy_id="sampling:locator", sampling_policy_version="1", halt_policy_id="halt:locator",
        halt_policy_version="1", allowed_outputs=("execution_accounting_artifacts",),
        policy_hashes={**{name: item.content_hash for name, item in policies.items()}, "logical_task_registry": registry.immutable_hash},
        per_request_reservation_cap="0.25",
    )
    return mandate, registry, routing, policies


def _attempt(mandate):
    value = dict(
        attempt_id="attempt:locator", mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash,
        slice_id=mandate.slice_id, run_id="run:locator", builder_repository="builder:test",
        builder_commit_sha="a" * 40, data_repository="data:test", data_commit_sha="b" * 40,
        bridge_certification="S0_ACQUISITION_PACKET_BRIDGE_CERTIFIED", bridge_version="1", schema_version=23,
        recovery_authority_ref=AUTHORITY, status="prepared", created_at=NOW.isoformat(),
    )
    value["configuration_hash"] = canonical_execution_configuration_hash(**{
        key: value[key] for key in (
            "mandate_hash", "slice_id", "run_id", "builder_repository", "builder_commit_sha",
            "data_repository", "data_commit_sha", "bridge_certification", "bridge_version",
            "schema_version", "recovery_authority_ref",
        )
    })
    return ExecutionAttemptIdentity(**value)


def _prepared_catalog(tmp_path):
    mandate, registry, routing, policies = _authority()
    attempt = _attempt(mandate)
    catalog = SQLiteCatalog(tmp_path / "locator.sqlite3").open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies, {})
    catalog.register_cohort({"record_id": "cohort:locator", "cohort_code": "LOCATOR", "definition_version": "1",
                             "membership_hash": "c" * 64, "budget_cap": {"amount": "8.00", "currency": "USD"},
                             "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:locator", "run_kind": "s0",
                          "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    packet = freeze_locator_search_packet(
        mandate=mandate, execution_attempt=attempt, subject_abn=SUBJECT, query='"Locator Foundation"',
        query_index=0, pricing=LocatorSearchPrice("pricing:locator-v1", "0.10", "USD"),
        frozen_at=NOW.isoformat(), provider_account_project=PROJECT, execution_authority=AUTHORITY,
    )
    assert ScaleS0Preflight.register_durable_packet(catalog, mandate, packet, execution_attempt_id=attempt.attempt_id)["packet_id"] == packet.packet_id
    for bundle in bundle_packets(mandate, (packet,), now=NOW, execution_attempt_id=attempt.attempt_id):
        catalog.register_scale_s0_physical_bundle(bundle.__dict__, execution_attempt_id=attempt.attempt_id)
    prepared = prepare_locator_search_request(packet=packet, reservation_id="reservation:locator",
                                               provider_account_project=PROJECT, execution_authority=AUTHORITY)
    task_key = packet_task_key(packet)
    catalog.register_task({"record_id": task_key, "subject_id": SUBJECT, "scope_id": packet.scope_id,
                           "cohort_id": "cohort:locator", "task_type": "locator_search",
                           "task_schema": packet.input_profile_id, "cache_key": packet.content_hash,
                           "provider_id": "openai", "model_snapshot": "synthetic"}, run_id=attempt.run_id, now=NOW)
    catalog.reserve_cost({"record_id": "reservation:locator", "cohort_id": "cohort:locator", "run_id": attempt.run_id,
                          "reserved_amount": {"amount": "0.10", "currency": "USD"}, "model_task_ids": (task_key,),
                          "expires_at": NOW + timedelta(minutes=30)}, now=NOW)
    economics = EconomicState(0, Decimal("0"), Decimal("0"), "reservation:locator", True,
                              mandate.mandate_id, mandate.slice_id, task_key, Decimal("0.10"), "USD",
                              Decimal("0.10"), Decimal("0"), "pricing:locator-v1")
    ScaleS0Preflight.record_durable_reservation(catalog, economics, recorded_at=NOW.isoformat(), execution_attempt_id=attempt.attempt_id)
    catalog.register_scale_s0_attestation_window({
        "window_id": "window:locator", "execution_attempt_id": attempt.attempt_id,
        "mandate_id": mandate.mandate_id, "slice_id": mandate.slice_id, "run_id": attempt.run_id,
        "attested_by": S0_LIVE_SEND_ATTESTER, "setting_name": S0_LIVE_SEND_SETTING_NAME,
        "observed_value": S0_LIVE_SEND_OBSERVED_VALUE, "provider_account_project": PROJECT,
        "execution_authority": AUTHORITY, "observed_at": NOW, "valid_until": NOW + timedelta(minutes=60),
    })
    catalog.create_delivery_job(delivery_job_id="deliveryjob:locator", run_id=attempt.run_id, provider_id="openai",
                                model_route="synthetic", delivery_mode="standard", pricing_snapshot_id="pricing:locator-v1", now=NOW)
    catalog.prepare_physical_attempt(physical_attempt_id=prepared.request.physical_attempt_id, run_id=attempt.run_id,
                                     subject_id=SUBJECT, delivery_mode="standard", provider_request_id=packet.provider_request_identity,
                                     model_task_ids=(task_key,), reservation_id="reservation:locator", now=NOW)
    catalog.create_provider_request_item(provider_request_item_id=packet.provider_request_identity, run_id=attempt.run_id,
                                         model_task_id=task_key, provider_id="openai", model_route="synthetic",
                                         requested_delivery_mode="standard", effective_service_tier="standard",
                                         delivery_job_id="deliveryjob:locator", physical_attempt_id=prepared.request.physical_attempt_id, now=NOW)
    catalog.create_provider_request_attempt(delivery_attempt_id=prepared.delivery_attempt_id,
                                            provider_request_item_id=packet.provider_request_identity,
                                            physical_attempt_id=prepared.request.physical_attempt_id,
                                            delivery_job_id="deliveryjob:locator", attempt_ordinal=1,
                                            authorization_id="window:locator", attempt_class="initial",
                                            predecessor_attempt_id=None, now=NOW)
    catalog.prepare_standard_transport_trace(prepared.delivery_attempt_id, client_request_id=prepared.client_request_id,
                                             endpoint="https://api.openai.com/v1/responses",
                                             request_body_sha256=packet.content_hash, now=NOW)
    return catalog, mandate, packet, prepared


def test_real_locator_packet_lifecycle_is_durable_priced_source_free_and_exactly_once(tmp_path):
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    live = ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)
    gate = S0LocatorSearchExecutionGate(preflight=live, request=prepared.request, catalog=catalog,
                                        delivery_attempt_id=prepared.delivery_attempt_id,
                                        client_request_id=prepared.client_request_id,
                                        request_identity=packet.provider_request_identity, now=NOW)
    assert packet.source_ids == packet.source_snapshot_hashes == () and not packet.corpus_id
    with pytest.raises(ScalePreflightError, match="query is not bound"):
        gate.begin(request_identity=packet.provider_request_identity, subject_abn=SUBJECT, query='"other query"')
    assert catalog.get_physical_attempt(prepared.request.physical_attempt_id)["status"] == "prepared"
    gate.begin(request_identity=packet.provider_request_identity, subject_abn=SUBJECT, query=packet.locator_query)
    gate.complete(provider_receipt_id="response:locator", result_ref="provider-response:locator", usage={"total_tokens": 1})
    assert catalog.get_provider_request_item(packet.provider_request_identity)["status"] == "completed"
    assert catalog.get_physical_receipt(prepared.request.physical_attempt_id)["provider_receipt_id"] == "response:locator"
    with pytest.raises(ScalePreflightError, match="already exists"):
        live.provider_send(prepared.request, now=NOW)


def test_header_received_response_without_identity_keeps_locator_exposure_outstanding(tmp_path):
    """An unidentifiable decoded response may be billable and cannot release."""
    catalog, mandate, packet, prepared = _prepared_catalog(tmp_path)
    live = ScaleS0Preflight.from_catalog(catalog, mandate_id=mandate.mandate_id, packet_id=packet.packet_id)
    gate = S0LocatorSearchExecutionGate(preflight=live, request=prepared.request, catalog=catalog,
                                        delivery_attempt_id=prepared.delivery_attempt_id,
                                        client_request_id=prepared.client_request_id,
                                        request_identity=packet.provider_request_identity, now=NOW)

    class HeaderButNoIdentity(OpenAIHTTPStandardClient):
        def create_response_once(self, *_args, **_kwargs):
            raise StandardSystemic("provider response did not contain a trustworthy response ID",
                                  response_headers_received=True)

    client = HeaderButNoIdentity(provider_account_project=PROJECT)
    provider = OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client),
                                                 model="gpt-5.6-luna", execution_gate=gate)
    with pytest.raises(StandardSystemic):
        provider.search(query=packet.locator_query, subject_abn=packet.subject_id,
                        request_identity=packet.provider_request_identity)
    assert catalog.get_physical_attempt(prepared.request.physical_attempt_id)["status"] == "held"
    assert catalog.accounting_reservation_position("reservation:locator")["released"] == Decimal("0")


def test_locator_packet_rejects_missing_pricing_and_cap_overrun_without_a_send(tmp_path):
    mandate, _, _, _ = _authority()
    attempt = _attempt(mandate)
    with pytest.raises(ScalePreflightError, match="positive immutable pricing"):
        freeze_locator_search_packet(mandate=mandate, execution_attempt=attempt, subject_abn=SUBJECT,
                                     query='"Locator Foundation"', query_index=0,
                                     pricing=LocatorSearchPrice("", "0.10", "USD"), frozen_at=NOW.isoformat(),
                                     provider_account_project=PROJECT, execution_authority=AUTHORITY)
    with pytest.raises(ScalePreflightError, match="bounded query index"):
        freeze_locator_search_packet(mandate=mandate, execution_attempt=attempt, subject_abn=SUBJECT,
                                     query='"Locator Foundation"', query_index=5,
                                     pricing=LocatorSearchPrice("pricing:locator-v1", "0.10", "USD"),
                                     frozen_at=NOW.isoformat(), provider_account_project=PROJECT,
                                     execution_authority=AUTHORITY)
    catalog = SQLiteCatalog(tmp_path / "cap.sqlite3").open(initialize=True)
    registry = default_s0_registry()
    routing = RoutingPolicy("routing:locator", "1", frozenset(RoutingClass), {})
    _, _, _, policies = _authority()
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies, {})
    catalog.register_cohort({"record_id": "cohort:cap", "cohort_code": "LOCATOR", "definition_version": "1",
                             "membership_hash": "d" * 64, "budget_cap": {"amount": "8.00", "currency": "USD"}, "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:cap", "run_kind": "s0", "status": "planned",
                          "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    over_cap = freeze_locator_search_packet(mandate=mandate, execution_attempt=attempt, subject_abn=SUBJECT,
                                            query='"Locator Foundation"', query_index=0,
                                            pricing=LocatorSearchPrice("pricing:locator-v1", "0.26", "USD"), frozen_at=NOW.isoformat(),
                                            provider_account_project=PROJECT, execution_authority=AUTHORITY)
    with pytest.raises(ScalePreflightError, match="per-request reservation cap"):
        ScaleS0Preflight.register_durable_packet(catalog, mandate, over_cap, execution_attempt_id=attempt.attempt_id)


def test_catalog_rejects_unknown_operational_kinds_and_locator_candidates(tmp_path):
    catalog, mandate, packet, _ = _prepared_catalog(tmp_path)
    unknown_packet = {
        "packet_id": "packet:unknown-operation", "mandate_id": mandate.mandate_id,
        "slice_id": mandate.slice_id, "task_key": "task:unknown-operation",
        "subject_id": SUBJECT, "scope_id": "scope:organisation", "content_hash": "a" * 64,
        "frozen_at": NOW.isoformat(), "binding_hash": "b" * 64,
        "task_id": "urn:charitygraph:scale-s0:unknown", "task_version": "1.0",
        "input_profile_id": "profile:unknown:1", "output_schema_id": "schema:unknown:1",
        "routing_class": "low_cost_semantic", "provider_request_identity": "unknown:request",
        "operation_kind": "unknown_operation",
    }
    with pytest.raises(CatalogError, match="unknown operation kind"):
        catalog.register_scale_s0_frozen_packet(unknown_packet)
    with pytest.raises(ConflictError, match="cannot create candidates"):
        catalog.register_scale_s0_candidate({
            "candidate_id": "candidate:locator-operation", "mandate_id": mandate.mandate_id,
            "packet_id": packet.packet_id, "subject_id": SUBJECT, "scope_id": packet.scope_id,
            "task_key": packet_task_key(packet), "created_at": NOW.isoformat(), "material_hash": "c" * 64,
        })
