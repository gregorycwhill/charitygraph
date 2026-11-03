"""Provider-free T4A packet planning for the retained real cohort.

The packet is a no-send control-plane artefact.  T3 material is read only in
the caller-owned disposable runtime; the returned document contains symbolic
identities, hashes, route metadata and forecasts, never source bodies,
prompts, credentials or model output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from .contracts import EvidenceInput, ModelTask, ProducerRef, SchemaRef, VersionedPolicy
from .contracts.canonical import canonical_json_bytes, canonical_sha256
from .contracts.ids import deterministic_id
from .phase5_delivery import DeliveryPlan, DeliveryPolicy, build_delivery_plan
from .phase5_governed_real_cohort_rehearsal import build_real_evidence_factory_plan
from .phase5_governed_source_binding import SELECTED_ROWS
from .phase5_openai_dry_run import (
    DISCOVERY_MAX_OUTPUT_TOKENS,
    PRICING,
    conservative_money_ceiling,
    conservative_standard_hard_max_aud,
)
from .phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
    ProviderConfiguration,
    ProviderProcessingPolicy,
)
from .phase5_semantic_contracts import resolve_contract


PACKET_SCHEMA = "charitygraph.gate4.t4a.real-pilot-preflight/v1"
PACKET_DATE = date(2026, 10, 29)
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_ENDPOINT = "/v1/responses"
DEFAULT_SERVICE = "responses_api"
DEFAULT_MAX_OUTPUT_TOKENS = DISCOVERY_MAX_OUTPUT_TOKENS
DEFAULT_AUD_PER_USD = Decimal("1.52")
PROGRAM_CAP_AUD = Decimal("10.000000")
PREFERRED_CEILING_AUD = Decimal("4.000000")
BATCH_MULTIPLIER = Decimal("0.5")
DEFAULT_RETRY_LIMIT = 0
DEFAULT_CONCURRENCY = 1
DEFAULT_LEASE_SECONDS = 3600


class RealPilotPreflightError(ValueError):
    """The no-send packet inputs are structurally unsafe."""


@dataclass(frozen=True)
class ProviderContractBinding:
    """Caller-supplied, non-secret provider contract identity."""

    contract_id: str
    contract_version: str
    configuration: ProviderConfiguration

    def __post_init__(self) -> None:
        if not self.contract_id.strip() or not self.contract_version.strip():
            raise RealPilotPreflightError("provider contract identity and version are required")

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(canonical_json_bytes({
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "configuration": self.configuration,
        })).hexdigest()


@dataclass(frozen=True)
class RealPilotPreflight:
    """Sanitized packet and its provider-free control results."""

    document: dict[str, Any]
    packet_sha256: str
    provider_binding_ready: bool
    send_ready: bool
    provider_calls: int
    reservations: int

    def as_dict(self) -> dict[str, Any]:
        return dict(self.document)


def _decimal(value: Decimal | str | int | None, name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RealPilotPreflightError(f"{name} is not a Decimal") from exc
    if not result.is_finite():
        raise RealPilotPreflightError(f"{name} must be finite")
    return result


def _contract_identity(contract: Any, evidence_ids: tuple[str, ...]) -> dict[str, Any]:
    """Return registry identity without copying prompt or schema payloads."""

    return {
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "claim_families": list(contract.claim_families),
        "prompt_id": contract.prompt_id,
        "prompt_template_version": contract.contract_version,
        "prompt_sha256": contract.prompt_sha256,
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "schema_sha256": contract.schema_hash_for_evidence(evidence_ids),
        "provider_schema_name": contract.provider_schema_name,
        "route_class": contract.route_class,
        "reasoning_policy": contract.reasoning_policy,
        "authority_state": contract.authority_state,
        "publication_boundary": contract.publication_boundary,
        "planner_prompt_policy_version": contract.planner_prompt_policy_version,
        "planner_schema_version": contract.planner_schema_version,
        "identity_sha256": contract.identity_hash(evidence_ids),
    }


def _provider_contract_dict(binding: ProviderContractBinding | None) -> dict[str, Any]:
    if binding is None:
        return {"status": "missing", "contract_id": None, "contract_version": None, "content_sha256": None}
    config = binding.configuration
    return {
        "status": "supplied",
        "contract_id": binding.contract_id,
        "contract_version": binding.contract_version,
        "content_sha256": binding.content_hash,
        "provider": config.provider,
        "project_id": config.project_id,
        "service": config.service,
        "endpoint": config.endpoint,
        "model": config.model,
        "delivery_mode": config.delivery_mode,
        "reasoning_effort": config.reasoning_effort,
        "retention_posture": config.retention_posture,
        "provider_no_training_default": config.provider_no_training_default,
        "provider_data_sharing_opt_in": config.provider_data_sharing_opt_in,
    }


def _provider_authority(
    policy: ProviderProcessingPolicy | Mapping[str, Any] | None,
    binding: ProviderContractBinding | None,
) -> tuple[bool, tuple[str, ...], ProviderProcessingPolicy | None]:
    reasons: list[str] = []
    if policy is None:
        reasons.append("exact provider-processing policy authority is unavailable")
        current = None
    else:
        try:
            current = policy if isinstance(policy, ProviderProcessingPolicy) else ProviderProcessingPolicy.model_validate(policy)
            current = current.sealed()
        except Exception as exc:
            current = None
            reasons.append(f"provider policy identity/version is invalid: {type(exc).__name__}")
    if current is not None:
        if current.policy_id != PROVIDER_PROCESSING_POLICY_ID or current.policy_version != PROVIDER_PROCESSING_POLICY_VERSION:
            reasons.append("provider policy identity or version is not the exact T4A authority")
        if current.status != "current":
            reasons.append("provider processing policy is revoked")
    if binding is None:
        reasons.append("exact provider contract identity/version is not caller-supplied")
    elif current is not None and binding.configuration != current.provider:
        reasons.append("caller-supplied provider project/service/endpoint/model differs from policy binding")
    return not reasons, tuple(reasons), current


def _metadata_tokens(task: Mapping[str, Any], contract: Any, *, model: str, max_output_tokens: int) -> int:
    """Conservatively estimate the private wire material without source text."""

    material = {
        "logical_task_id": task["logical_task_id"],
        "subject_id": task["subject_id"],
        "scope_id": task["scope_id"],
        "evidence_corpus_hash": task["evidence_corpus_hash"],
        "evidence_locator_ids": list(task["evidence_locator_ids"]),
        "representation_hashes": list(task["representation_hashes"]),
        "semantic_contract": _contract_identity(contract, tuple(task["evidence_locator_ids"])),
        "model": model,
        "reasoning_effort": contract.reasoning_policy,
        "endpoint": DEFAULT_ENDPOINT,
        "store": False,
        "max_output_tokens": max_output_tokens,
    }
    # Include the immutable prompt footprint in the forecast, but never in the
    # returned packet.  The actual text is materialised only by a future send.
    return max(1, (len(canonical_json_bytes(material)) + len(contract.prompt_template.encode("utf-8")) + 3) // 4)


def _plan_identity(plan: DeliveryPlan) -> dict[str, Any]:
    return {
        "policy_id": plan.policy_id,
        "request_items": [
            {
                "request_item_id": item.request_item_id,
                "logical_task_ids": list(item.logical_task_ids),
                "provider_id": item.provider_id,
                "model_route": item.model_route,
                "requested_delivery_mode": item.requested_delivery_mode,
                "effective_service_tier": item.effective_service_tier,
            }
            for item in plan.request_items
        ],
        "delivery_jobs": [
            {
                "delivery_job_id": job.delivery_job_id,
                "delivery_mode": job.delivery_mode,
                "provider_id": job.provider_id,
                "model_route": job.model_route,
                "request_item_ids": list(job.request_item_ids),
            }
            for job in plan.delivery_jobs
        ],
    }


def _forecast(
    tasks: tuple[dict[str, Any], ...],
    contract: Any,
    *,
    model: str,
    aud_per_usd: Decimal | None,
    pricing_snapshot_id: str | None,
    retry_limit: int,
    mode: str,
) -> dict[str, Any]:
    if retry_limit < 0:
        raise RealPilotPreflightError("retry_limit cannot be negative")
    base: list[Decimal] = []
    token_rows: list[dict[str, Any]] = []
    try:
        if model not in PRICING:
            raise KeyError(model)
        for task in tasks:
            tokens = _metadata_tokens(task, contract, model=model, max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS)
            standard_aud = conservative_standard_hard_max_aud(
                tokens, DEFAULT_MAX_OUTPUT_TOKENS, aud_per_usd if aud_per_usd is not None else "NaN", model=model,
            )
            selected_aud = standard_aud if mode == "standard" else conservative_money_ceiling(standard_aud * BATCH_MULTIPLIER)
            base.append(selected_aud)
            token_rows.append({"logical_task_id": task["logical_task_id"], "input_tokens_upper_bound": tokens, "output_tokens_upper_bound": DEFAULT_MAX_OUTPUT_TOKENS, "per_attempt_aud": str(selected_aud)})
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        return {
            "status": "blocked",
            "reason": "known model pricing or FX is unavailable",
            "pricing_snapshot_id": pricing_snapshot_id,
            "fx_aud_per_usd": None if aud_per_usd is None else str(aud_per_usd),
            "retry_limit": retry_limit,
            "attempts_per_task_upper_bound": 1 + retry_limit,
            "task_forecasts": [],
            "upper_bound_aud": None,
            "error_type": type(exc).__name__,
        }
    upper = sum(base, Decimal("0")) * Decimal(1 + retry_limit)
    return {
        "status": "available",
        "pricing_snapshot_id": pricing_snapshot_id,
        "fx_snapshot": {"base": "USD", "quote": "AUD", "aud_per_usd": str(aud_per_usd)},
        "rounding": "each non-negative task ceiling rounds upward to AUD 0.000001 before aggregation",
        "retry_limit": retry_limit,
        "attempts_per_task_upper_bound": 1 + retry_limit,
        "task_forecasts": token_rows,
        "upper_bound_aud": str(conservative_money_ceiling(upper)),
        "batch_multiplier": str(BATCH_MULTIPLIER) if mode == "batch" else "1",
    }


def _semantic_tasks(
    real_plan: Any,
    *,
    model: str,
    provider_id: str,
    contract: Any,
) -> tuple[dict[str, Any], ...]:
    tasks: list[dict[str, Any]] = []
    source_family_by_record = {row.source_record_id: row.source_family for row in SELECTED_ROWS}
    for base in real_plan.factory_plan.logical_tasks:
        evidence_ids = tuple(base["evidence_locator_ids"])
        semantic_hash = canonical_sha256({
            "parent_task": base["logical_task_id"],
            "evidence_corpus_hash": base["evidence_corpus_hash"],
            "contract": contract.identity_hash(evidence_ids),
        })
        logical_id = deterministic_id("semtask:", {
            "parent_task": base["logical_task_id"],
            "contract_hash": contract.identity_hash(evidence_ids),
            "route": "g4-t4a-real-pilot-v1",
        })
        representation_hashes = tuple(base["representation_hashes"])
        evidence_inputs = tuple(
            EvidenceInput(
                evidence_id=evidence_id,
                content_hash=dict(representation_hashes)[base["representation_artifact_ids"][0]],
                selection_hash=canonical_sha256({"evidence_locator_id": evidence_id, "representation_hashes": representation_hashes}),
            )
            for evidence_id in evidence_ids
        )
        task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:model-task:1.0", schema_version="1.0")
        output_schema = SchemaRef(schema_id=contract.schema_id, schema_version=contract.schema_version)
        policy_refs = (
            VersionedPolicy(policy_id=base["rights_policy_ids"][0], version="1.0.0"),
            VersionedPolicy(policy_id=PROVIDER_PROCESSING_POLICY_ID, version=PROVIDER_PROCESSING_POLICY_VERSION),
        )
        parameters = {
            "semantic_contract_id": contract.contract_id,
            "semantic_contract_version": contract.contract_version,
            "semantic_contract_hash": contract.identity_hash(evidence_ids),
            "parent_task_id": base["logical_task_id"],
            "source_definition_ids": list(base["source_definition_ids"]),
            "source_record_ids": list(base["source_record_ids"]),
            "evidence_locator_ids": list(evidence_ids),
            "representation_artifact_ids": list(base["representation_artifact_ids"]),
            "representation_hashes": dict(representation_hashes),
            "rights_policy_ids": list(base["rights_policy_ids"]),
            "rights_roles": list(base["rights_roles"]),
            "provider_processing_policy_id": PROVIDER_PROCESSING_POLICY_ID,
            "provider_processing_policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
        }
        from .contracts.tasks import model_task_cache_key
        cache_key = model_task_cache_key(
            task_type="direct_service_semantics", task_schema=task_schema, output_schema=output_schema,
            evidence_inputs=evidence_inputs, prompt_template_id=contract.prompt_id,
            prompt_template_version=contract.contract_version, policy_refs=policy_refs,
            provider_id=provider_id, model_snapshot=model, parameters=parameters,
            material_tool_versions=(),
        )
        record_id = deterministic_id("modeltask:", {"subject_id": base["subject_id"], "scope_id": base["scope_id"], "task_type": "direct_service_semantics", "cache_key": cache_key, "output_schema": output_schema})
        typed = ModelTask(
            record_id=record_id,
            created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
            producer=ProducerRef(kind="code", producer_id="phase5-t4a-real-pilot-preflight", version="1"),
            subject_id=base["subject_id"], scope_id=base["scope_id"], cohort_id=real_plan.cohort_id,
            task_type="direct_service_semantics", task_schema=task_schema, output_schema=output_schema,
            evidence_inputs=evidence_inputs, prompt_template_id=contract.prompt_id,
            prompt_template_version=contract.contract_version, policy_refs=policy_refs,
            provider_id=provider_id, model_snapshot=model, parameters=parameters,
            material_tool_versions=(), cache_key=cache_key, paid_output_categories=("semantic_judgement",),
        )
        tasks.append({
            "logical_task_id": logical_id,
            "record_id": record_id,
            "subject_id": base["subject_id"], "scope_id": base["scope_id"],
            "difficulty": "lower_cost_constrained_semantic",
            "claim_family_id": contract.claim_families[0],
            "task_profile": contract.task_profile,
            "task_profile_version": contract.task_profile_version,
            "schema_version": contract.planner_schema_version,
            "prompt_policy_version": contract.planner_prompt_policy_version,
            "route_policy_version": "g4-t4a-real-pilot-route-v1",
            "evidence_corpus_hash": semantic_hash,
            "source_definition_ids": base["source_definition_ids"],
            "source_family": source_family_by_record[base["source_record_ids"][0]],
            "acquisition_receipt_ids": base["acquisition_receipt_ids"],
            "source_record_ids": base["source_record_ids"],
            "evidence_locator_ids": evidence_ids,
            "representation_artifact_ids": base["representation_artifact_ids"],
            "representation_hashes": representation_hashes,
            "rights_policy_ids": base["rights_policy_ids"],
            "rights_roles": base["rights_roles"],
            "governed_reference_hash": base["governed_reference_hash"],
            "provider_id": provider_id, "model_route": model,
            "batch_supported": True, "latency_required": False,
            "_model_task": typed,
        })
    return tuple(sorted(tasks, key=lambda item: item["logical_task_id"]))


def _task_row(task: Mapping[str, Any], contract: Any) -> dict[str, Any]:
    return {
        "logical_task_id": task["logical_task_id"], "model_task_id": task["record_id"],
        "subject_id": task["subject_id"], "scope_id": task["scope_id"],
        "source_family": task["source_family"],
        "source_definition_ids": list(task["source_definition_ids"]),
        "acquisition_receipt_ids": list(task["acquisition_receipt_ids"]),
        "source_record_ids": list(task["source_record_ids"]),
        "evidence_locator_ids": list(task["evidence_locator_ids"]),
        "representation_artifact_ids": list(task["representation_artifact_ids"]),
        "representation_hashes": list(task["representation_hashes"]),
        "rights_policy_ids": list(task["rights_policy_ids"]),
        "rights_roles": list(task["rights_roles"]),
        "semantic_contract_id": contract.contract_id,
        "semantic_contract_version": contract.contract_version,
        "semantic_contract_hash": contract.identity_hash(tuple(task["evidence_locator_ids"])),
        "prompt_id": contract.prompt_id,
        "prompt_sha256": contract.prompt_sha256,
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "schema_sha256": contract.schema_hash_for_evidence(tuple(task["evidence_locator_ids"])),
        "cache_key": task["_model_task"].cache_key,
        "model": task["model_route"],
    }


def build_real_pilot_preflight(
    *,
    source_archive_root: str | Path,
    work_root: str | Path,
    execution_context: Mapping[str, str],
    provider_policy: ProviderProcessingPolicy | Mapping[str, Any] | None = None,
    provider_contract: ProviderContractBinding | None = None,
    model: str = DEFAULT_MODEL,
    pricing_snapshot_id: str | None = "openai-model-pages-2026-09-07",
    aud_per_usd: Decimal | str | None = DEFAULT_AUD_PER_USD,
    cumulative_actual_aud: Decimal | str | None = Decimal("0"),
    program_cap_aud: Decimal | str | None = PROGRAM_CAP_AUD,
    preferred_ceiling_aud: Decimal | str | None = PREFERRED_CEILING_AUD,
    retry_limit: int = DEFAULT_RETRY_LIMIT,
    max_concurrency: int = DEFAULT_CONCURRENCY,
    batch_size: int = 100,
) -> RealPilotPreflight:
    """Build a deterministic ten-task packet without a provider crossing."""

    if max_concurrency < 1 or max_concurrency > 32 or batch_size < 1:
        raise RealPilotPreflightError("concurrency and batch size are outside the bounded route")
    if retry_limit < 0:
        raise RealPilotPreflightError("retry_limit cannot be negative")
    root = Path(work_root).resolve()
    real_plan = build_real_evidence_factory_plan(
        source_archive_root=source_archive_root, work_root=root / "t3-real-work",
        execution_context=execution_context,
    )
    contract_probe = {
        "logical_task_id": "probe", "claim_family_id": "direct-service-access-v1",
        "task_profile": "direct_service_semantics", "task_profile_version": "1",
        "prompt_policy_version": "direct-service-access-v1:prompt-policy:v2",
        "schema_version": "urn:charitygraph:phase5:planned:direct_service_semantics:v1",
    }
    contract = resolve_contract(contract_probe)
    contract.assert_complete()
    tasks = _semantic_tasks(real_plan, model=model, provider_id="openai", contract=contract) if real_plan.blocked_reason is None else ()
    standard_tasks = tuple({**task, "delivery_mode": "standard"} for task in tasks)
    batch_tasks = tuple({**task, "delivery_mode": "batch"} for task in tasks)
    standard_plan = build_delivery_plan(standard_tasks, batch_size=batch_size, policy=DeliveryPolicy.production())
    batch_plan = build_delivery_plan(batch_tasks, batch_size=batch_size, policy=DeliveryPolicy.production())
    fx = _decimal(aud_per_usd, "aud_per_usd")
    cumulative = _decimal(cumulative_actual_aud, "cumulative_actual_aud")
    cap = _decimal(program_cap_aud, "program_cap_aud")
    ceiling = _decimal(preferred_ceiling_aud, "preferred_ceiling_aud")
    budget_reasons: list[str] = []
    if fx is None or fx <= 0:
        budget_reasons.append("FX is missing or non-positive")
    if cumulative is None or cumulative < 0:
        budget_reasons.append("cumulative actual spend is missing or invalid")
    if cap is None or cap <= 0:
        budget_reasons.append("cumulative programme cap is missing or invalid")
    if ceiling is None or ceiling <= 0:
        budget_reasons.append("planned ceiling is missing or invalid")
    if cap is not None and cumulative is not None and cumulative > cap:
        budget_reasons.append("cumulative actual spend already exceeds programme cap")
    standard_forecast = _forecast(tasks, contract, model=model, aud_per_usd=fx, pricing_snapshot_id=pricing_snapshot_id, retry_limit=retry_limit, mode="standard")
    batch_forecast = _forecast(tasks, contract, model=model, aud_per_usd=fx, pricing_snapshot_id=pricing_snapshot_id, retry_limit=retry_limit, mode="batch")
    if standard_forecast["status"] != "available" or batch_forecast["status"] != "available":
        budget_reasons.append("known model pricing or FX is unavailable")
    remaining = None if cap is None or cumulative is None else conservative_money_ceiling(cap - cumulative) if cap >= cumulative else Decimal("0")
    selected_upper = None if standard_forecast["upper_bound_aud"] is None else Decimal(standard_forecast["upper_bound_aud"])
    if remaining is not None and selected_upper is not None and selected_upper > remaining:
        budget_reasons.append("conservative Standard exposure exceeds remaining programme budget")
    if ceiling is not None and selected_upper is not None and selected_upper > ceiling:
        budget_reasons.append("conservative Standard exposure exceeds the preferred AUD 4 pilot ceiling")
    provider_ready, provider_reasons, current_policy = _provider_authority(provider_policy, provider_contract)
    if provider_contract is not None:
        if provider_contract.configuration.model != model:
            provider_reasons = provider_reasons + ("selected model does not match the caller-supplied provider contract",)
        if provider_contract.configuration.service != DEFAULT_SERVICE:
            provider_reasons = provider_reasons + ("selected service is not the existing Responses API route",)
    if real_plan.blocked_reason is not None:
        provider_reasons = provider_reasons + ("T3 real-evidence binding is blocked",)
    send_ready = False  # This function is explicitly no-send and creates no execution authority.
    all_rows = [] if real_plan.manifest is None else list(real_plan.manifest.get("rows", ()))
    packet_core: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "as_of": PACKET_DATE.isoformat(),
        "mode": "no_send",
        "t3_selected_manifest": {
            "schema": None if real_plan.manifest is None else real_plan.manifest.get("schema"),
            "selected_manifest_sha256": None if real_plan.manifest is None else real_plan.manifest.get("selected_manifest_sha256"),
            "manifest_identity_sha256": None if real_plan.manifest is None else real_plan.manifest.get("manifest_identity_sha256"),
            "source_evidence_provenance": None if real_plan.manifest is None else real_plan.manifest.get("source_evidence_provenance"),
        },
        "cohort": {
            "cohort_id": real_plan.cohort_id, "cohort_plan_sha256": real_plan.cohort_plan_sha256,
            "subject_count": len({row.get("subject_id") for row in all_rows}),
            "source_row_count": len(all_rows),
            "eligible_row_count": sum(row.get("status") == "eligible_private_local_retention" for row in all_rows),
            "missingness": {"missing": sum(row.get("status") == "missing" for row in all_rows), "mismatched": sum(row.get("status") == "mismatched" for row in all_rows), "excluded": sum(row.get("status") == "excluded" for row in all_rows), "not_task_eligible": sum(row.get("status") == "bound_not_task_eligible" for row in all_rows)},
        },
        "rights": {"policy_id": "CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1", "policy_version": "1.0.0", "source_families": ["acnc_register", "acnc_ais_bundle"], "public_redistribution": "not_assessed"},
        "provider_processing_policy": {"policy_id": PROVIDER_PROCESSING_POLICY_ID, "policy_version": PROVIDER_PROCESSING_POLICY_VERSION, "content_sha256": None if current_policy is None else current_policy.computed_hash, "status": "current" if current_policy is not None and current_policy.status == "current" else "unresolved"},
        "provider_contract": _provider_contract_dict(provider_contract),
        "semantic_contract": _contract_identity(contract, ()),
        "tasks": [_task_row(task, contract) for task in tasks],
        "routes": {
            "standard": {**_plan_identity(standard_plan), "plan_sha256": canonical_sha256(_plan_identity(standard_plan)), "forecast": standard_forecast},
            "batch": {**_plan_identity(batch_plan), "plan_sha256": canonical_sha256(_plan_identity(batch_plan)), "forecast": batch_forecast},
            "selected_initial_route": "standard",
        },
        "budget": {
            "programme_cap_aud": None if cap is None else str(cap),
            "cumulative_actual_aud": None if cumulative is None else str(cumulative),
            "remaining_aud": None if remaining is None else str(remaining),
            "preferred_planned_ceiling_aud": None if ceiling is None else str(ceiling),
            "selected_route_upper_bound_aud": None if selected_upper is None else str(selected_upper),
            "reservation_aud": "0.000000",
            "reservation_count": 0,
            "status": "available" if not budget_reasons else "blocked",
            "reasons": budget_reasons,
        },
        "execution_policy": {
            "max_concurrency": max_concurrency, "lease_seconds": DEFAULT_LEASE_SECONDS,
            "retry_limit": retry_limit, "ambiguity_rule": "stop_and_reconcile; never_automatic_resend",
            "restart_rule": "reuse content-addressed logical/request identities; no duplicate send",
            "provider_calls": 0, "model_outputs": 0, "reservations": 0, "cost_entries": 0,
        },
        "authority": {
            "provider_binding_ready": provider_ready and not provider_reasons,
            "send_ready": send_ready,
            "reasons": list(provider_reasons),
            "no_send_guard": "active",
        },
        "health_snapshot": {
            "task_count": len(tasks), "standard_request_items": len(standard_plan.request_items), "batch_request_items": len(batch_plan.request_items),
            "standard_jobs": len(standard_plan.delivery_jobs), "batch_jobs": len(batch_plan.delivery_jobs),
            "provider_calls": 0, "reservations": 0, "cost_entries": 0, "retry_count": 0,
            "route_plan_sha256": canonical_sha256({"standard": _plan_identity(standard_plan), "batch": _plan_identity(batch_plan)}),
        },
        "blocked_reason": real_plan.blocked_reason,
    }
    packet_sha = canonical_sha256(packet_core)
    document = {**packet_core, "packet_identity_sha256": packet_sha}
    return RealPilotPreflight(document=document, packet_sha256=packet_sha, provider_binding_ready=provider_ready and not provider_reasons, send_ready=False, provider_calls=0, reservations=0)


__all__ = ["PACKET_SCHEMA", "ProviderContractBinding", "RealPilotPreflight", "RealPilotPreflightError", "build_real_pilot_preflight"]
