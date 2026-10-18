"""Reusable execution seam for an already-frozen private experiment cohort.

It does not acquire or interpret sources itself.  Callers supply only normal
Builder corpus manifests produced by governed acquisition/representation and
artifact-bound transmission-rights decisions.  This module pins those inputs
into the ordinary Standard delivery lifecycle without promotion.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from .phase5_execution_mandate import manifest_hash
from .phase5_execution_packet import ExecutionPacketUnready, materialize_execution_packet
from .phase5_openai_dry_run import PRICING, standard_actual_cost, serialize_execution_packet_request
from .phase5_semantic_contracts import executable_contract_for
from .phase5_pre_send_certification import certify_standard_execution_row
from .phase5_standard_transport import StandardCampaignCoordinator, body_sha256, canonical_standard_body_bytes
from .runtime import SQLiteCatalog
from .source_rights import ArtifactRightsDecision, require_provider_rights
from .contracts.semantic import EvidenceSelectionOutput


class FrozenExperimentError(RuntimeError):
    """Frozen input, rights, pricing, or lifecycle identity is not exact."""


def _frozen_signature(signature: str | None) -> dict[str, Any]:
    """Load the frozen structured demand without interpreting its prose."""
    if signature is None:
        raise ValueError("frozen demand signature is absent")
    try:
        value = json.loads(signature)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen demand signature must be structured JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("frozen demand signature must be an object")
    return value


def demand_propositions(signature: str | None) -> tuple[dict[str, str], ...]:
    """Assign packet-stable identities to the exact frozen proposition bytes.

    The provider sees an identifier and its frozen text, but returns only the
    identifier.  This deliberately does not infer, normalize, or paraphrase
    natural language.
    """
    value = _frozen_signature(signature)
    propositions = value.get("propositions") if isinstance(value, dict) else None
    if not isinstance(propositions, list) or not propositions or any(not isinstance(item, str) or not item.strip() for item in propositions):
        raise ValueError("frozen demand signature has no concrete proposition set")
    if len(propositions) != len(set(propositions)):
        raise ValueError("frozen demand signature repeats a proposition")
    return tuple({"proposition_id": "proposition:" + hashlib.sha256(item.encode("utf-8")).hexdigest(), "proposition": item} for item in propositions)


def demand_requirements(signature: str | None) -> tuple[dict[str, str], ...]:
    """Assign stable IDs to the exact typed dimensions of a frozen demand.

    This is intentionally a structural compiler.  It neither classifies nor
    normalises natural language: every emitted value is an exact value from a
    named field in the frozen signature.  A future provider must account for
    these requirements alongside the proposition labels.
    """
    value = _frozen_signature(signature)
    specifications: list[tuple[str, str, str]] = []
    for field, kind in (("subjects", "referent"), ("joins", "relation"), ("operations", "operation"), ("forbidden", "non_inference")):
        entries = value.get(field)
        if not isinstance(entries, list) or not entries or any(not isinstance(item, str) or not item.strip() for item in entries):
            raise ValueError(f"frozen demand signature has no concrete {field}")
        specifications.extend((kind, field, item) for item in entries)
    for field, kind in (("evidence", "evidence_standard"), ("intent", "intent"), ("temporal", "temporal")):
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"frozen demand signature has no concrete {field}")
        specifications.append((kind, field, item))
    result = []
    for kind, field, requirement in specifications:
        material = {"kind": kind, "field": field, "requirement": requirement}
        result.append({
            "requirement_id": "requirement:" + _sha(material),
            "kind": kind,
            "field": field,
            "requirement": requirement,
        })
    return tuple(result)


def validate_evidence_selection(output: Mapping[str, Any], *, allowed_evidence_ids: set[str], demand_signature: str | None = None) -> EvidenceSelectionOutput:
    """Validate only the existing typed output and its packet-local references.

    This deliberately makes no judgement about whether a conclusion is
    persuasive.  It enforces the mechanical boundary required to retain a
    provider response as an experiment result.
    """
    parsed = EvidenceSelectionOutput.model_validate(output)
    referenced = set(parsed.selected_evidence_ids) | set(parsed.rejected_evidence_ids)
    referenced |= {item.evidence_id for item in parsed.conclusion.evidence}
    if not referenced.issubset(allowed_evidence_ids):
        raise ValueError("evidence-selection output references evidence outside its packet")
    required = {item["proposition_id"] for item in demand_propositions(demand_signature)}
    requirements = {item["requirement_id"]: item for item in demand_requirements(demand_signature)}
    required_requirements = set(requirements)
    if required:
        support = {item.proposition_id: item for item in parsed.proposition_support}
        if len(support) != len(parsed.proposition_support):
            raise ValueError("evidence-selection output repeats a frozen demand proposition")
        if set(support) != required:
            raise ValueError("evidence-selection output must account for every frozen demand proposition exactly once")
        for item in support.values():
            if not set(item.evidence_ids).issubset(allowed_evidence_ids):
                raise ValueError("proposition support references evidence outside its packet")
        requirement_support = {item.requirement_id: item for item in parsed.demand_requirement_support}
        if len(requirement_support) != len(parsed.demand_requirement_support):
            raise ValueError("evidence-selection output repeats a frozen demand requirement")
        if set(requirement_support) != required_requirements:
            raise ValueError("evidence-selection output must account for every frozen demand requirement exactly once")
        for item in requirement_support.values():
            if not set(item.evidence_ids).issubset(allowed_evidence_ids):
                raise ValueError("demand requirement support references evidence outside its packet")
            kind = requirements[item.requirement_id]["kind"]
            if item.support_state == "guarded" and kind != "non_inference":
                raise ValueError("only frozen non-inference requirements may be marked guarded")
        if parsed.conclusion.outcome in {"resolved", "supported"} and any(item.support_state != "supported" for item in support.values()):
            raise ValueError("positive evidence-selection conclusion has unresolved material proposition scope")
        if parsed.conclusion.outcome in {"resolved", "supported"} and any(
            item.support_state != "supported"
            and not (requirements[item.requirement_id]["kind"] == "non_inference" and item.support_state == "guarded")
            for item in requirement_support.values()
        ):
            raise ValueError("positive evidence-selection conclusion has unresolved frozen demand requirements")
    return parsed


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _id(prefix: str, value: Any) -> str:
    return prefix + _sha(value)


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(timezone.utc)


def load_frozen_instances(*, subject_manifest: Path, demand_manifest: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    subjects = json.loads(subject_manifest.read_text(encoding="utf-8"))
    demands = json.loads(demand_manifest.read_text(encoding="utf-8"))
    if subjects.get("selection_state") != "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION" or demands.get("selection_state") != "FROZEN_BEFORE_SEMANTIC_RESULT_INSPECTION":
        raise FrozenExperimentError("experiment manifests are not frozen")
    members, instances = subjects.get("subjects"), demands.get("instances")
    if not isinstance(members, list) or not isinstance(instances, list) or len(members) != len(instances) or not members:
        raise FrozenExperimentError("subject/demand manifests do not form a non-empty exact cohort")
    by_subject = {item.get("subject_id"): item for item in members}
    if len(by_subject) != len(members) or {item.get("subject_id") for item in instances} != set(by_subject):
        raise FrozenExperimentError("demand instances do not exactly cover frozen subjects")
    ids = [item.get("instance_id") for item in instances]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise FrozenExperimentError("frozen instance IDs are absent or non-unique")
    return subjects, demands, sorted(instances, key=lambda item: item["instance_id"])


def _contract() -> Any:
    return executable_contract_for({
        "task_profile": "evidence_selection", "task_profile_version": "3",
        "claim_family_id": "evidence-selection-v1",
        "prompt_policy_version": "evidence-selection-v1:prompt-policy:v5-evidence-claim-interface",
        "schema_version": "urn:charitygraph:frozen-experiment:evidence-selection:v5",
    })


def _corpora(path: Path, subject_ids: set[str]) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    values = raw.get("corpora") if isinstance(raw, dict) else raw
    if not isinstance(values, list):
        raise FrozenExperimentError("corpus input must be a list or a corpora object")
    result = {item.get("subject_id"): item for item in values if isinstance(item, dict)}
    if set(result) != subject_ids:
        raise FrozenExperimentError("normal governed corpus manifests do not exactly cover frozen subjects")
    return result


def _rights(path: Path, units: tuple[Any, ...]) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    values = raw.get("decisions") if isinstance(raw, dict) else raw
    if not isinstance(values, list):
        raise FrozenExperimentError("rights input must be a decision list")
    try:
        decisions = [ArtifactRightsDecision.model_validate(item) for item in values]
    except Exception as exc:
        raise FrozenExperimentError("rights decisions are invalid") from exc
    blockers = require_provider_rights(decisions, [{
        "source_artifact_id": unit.source_artifact_id, "source_record_id": unit.source_record_id,
        "source_locator": unit.source_locator, "source_role": unit.source_role,
        "exact_transmitted_representation": unit.content,
    } for unit in units])
    if blockers:
        raise FrozenExperimentError("provider rights are blocked: " + "; ".join(sorted(blockers)))


def _pricing(path: Path, expected_ids: set[str]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("requests")
    if value.get("provider") != "openai" or value.get("model") != "gpt-5.6-luna" or not isinstance(rows, list):
        raise FrozenExperimentError("frozen pricing snapshot does not bind the canonical route")
    by_id = {row.get("instance_id"): row for row in rows if isinstance(row, dict)}
    if set(by_id) != expected_ids:
        raise FrozenExperimentError("pricing snapshot does not exactly cover frozen instances")
    total_usd = sum((Decimal(str(row.get("hard_max_usd"))) for row in by_id.values()), Decimal("0"))
    if total_usd > Decimal("1.00"):
        raise FrozenExperimentError("frozen experiment exceeds its USD 1.00 aggregate ceiling")
    values: dict[str, dict[str, str]] = {}
    for key, row in by_id.items():
        usd, aud = Decimal(str(row.get("hard_max_usd"))), Decimal(str(row.get("hard_max_aud")))
        if usd <= 0 or aud <= 0:
            raise FrozenExperimentError("pricing request bounds must be positive")
        values[str(key)] = {"usd": str(usd), "aud": str(aud)}
    return value, values


def prepare_frozen_experiment(*, subject_manifest: Path, demand_manifest: Path, corpus_manifest: Path,
                              rights_decisions: Path, pricing_snapshot: Path, runtime_root: Path,
                              catalog_path: Path, authorization_catalog_path: Path,
                              authorization_text_hash: str, provider_account_project: str,
                              now: datetime | None = None) -> dict[str, Any]:
    """Pin a frozen cohort into normal Standard rows; never sends a provider request."""
    timestamp = _now(now)
    if not isinstance(provider_account_project, str) or not provider_account_project.strip():
        raise FrozenExperimentError("frozen experiment requires an exact provider project binding")
    subjects, demands, instances = load_frozen_instances(subject_manifest=subject_manifest, demand_manifest=demand_manifest)
    subject_hash, demand_hash = _file_sha(subject_manifest), _file_sha(demand_manifest)
    corpus_by_subject = _corpora(corpus_manifest, {item["subject_id"] for item in instances})
    pricing, cost_by_instance = _pricing(pricing_snapshot, {item["instance_id"] for item in instances})
    contract = _contract()
    cohort_identity = {"subject_manifest_sha256": subject_hash, "demand_manifest_sha256": demand_hash, "corpus_manifest_sha256": _file_sha(corpus_manifest), "rights_decisions_sha256": _file_sha(rights_decisions), "pricing_snapshot_sha256": _file_sha(pricing_snapshot), "contract_identity_hash": contract.identity_hash(), "provider_account_project": provider_account_project}
    cohort_id, run_id = _id("cohort:", cohort_identity), _id("run:", cohort_identity)
    aggregate_aud = sum((Decimal(cost_by_instance[item["instance_id"]]["aud"]) for item in instances), Decimal("0"))
    mandate_id = _id("mandate:", {"kind": "frozen-experiment-standard-luna-v1", **cohort_identity})
    allowed_contract = {"contract_key": contract.contract_id + ":" + contract.contract_version, **contract.identity_payload(), "claim_families": list(contract.claim_families), "provider_schema_name": contract.provider_schema_name, "schema_factory_id": contract.schema_factory_id, "schema_hash_rule": "packet-bound governed schema factory"}
    allowed_contract["contract_identity_hash"] = contract.identity_hash()
    mandate = {"manifest_version": "execution-mandate-v1", "mandate_id": mandate_id, "purpose": "private frozen experiment", "phase_scope": "frozen-experiment", "frozen_input_identity": cohort_identity, "provider": "openai", "provider_account_project": provider_account_project, "delivery_mode": "standard", "model": "gpt-5.6-luna", "reasoning_effort": "low", "max_concurrency": 1, "automatic_retries": 0, "semantic_retries": 0, "fallbacks": [], "ambiguous_resend": False, "aggregate_hard_aud": str(aggregate_aud), "per_request_hard_aud": str(max(Decimal(v["aud"]) for v in cost_by_instance.values())), "allowed_contracts": [allowed_contract], "excluded_authorities": ["governed_promotion", "adjudication", "card_projection", "public_release", "source_acquisition"], "termination": ["aggregate_authority_exhausted", "explicit_revocation", "identity_or_rights_drift"]}
    catalog = SQLiteCatalog(catalog_path, authorization_path=authorization_catalog_path).open(initialize=True)
    rows: list[dict[str, Any]] = []
    try:
        # A preparation can be interrupted after durable registration. Reuse
        # that immutable identity instead of treating its operational timestamp
        # as changed semantic material on resume.
        if catalog.get_cohort(cohort_id) is None:
            catalog.register_cohort({"record_id": cohort_id, "cohort_code": "FROZEN_EXPERIMENT", "definition_version": "1", "membership_hash": _sha([item["instance_id"] for item in instances]), "budget_cap": {"amount": str(aggregate_aud), "currency": "AUD"}, "created_at": timestamp})
        if catalog.get_run(run_id) is None:
            catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "frozen-experiment-standard", "status": "planned", "configuration_hash": _sha({"cohort": cohort_identity, "mandate": mandate}), "created_at": timestamp})
        catalog.register_execution_mandate(mandate_id=mandate_id, manifest_hash=manifest_hash(mandate), authorization_text_hash=authorization_text_hash, scope=mandate, contract_allowlist=tuple(mandate["allowed_contracts"]), aggregate_hard_aud=mandate["aggregate_hard_aud"], per_request_hard_aud=mandate["per_request_hard_aud"], phase_scope=mandate["phase_scope"], now=timestamp)
        existing_mandate = catalog.get_execution_mandate(mandate_id)
        if existing_mandate is None:
            raise FrozenExperimentError("prepared mandate did not persist")
        if existing_mandate["status"] == "proposed":
            catalog.activate_execution_mandate(mandate_id=mandate_id, authorization_text_hash=authorization_text_hash, authorized_by="product-owner", now=timestamp)
        elif existing_mandate["status"] != "active":
            raise FrozenExperimentError("prepared mandate is not active")
        job_id = _id("deliveryjob:", {"run_id": run_id, "pricing_snapshot_sha256": cohort_identity["pricing_snapshot_sha256"]})
        catalog.create_delivery_job(delivery_job_id=job_id, run_id=run_id, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id="pricing:" + cohort_identity["pricing_snapshot_sha256"], now=timestamp)
        for instance in instances:
            corpus = corpus_by_subject[instance["subject_id"]]
            task = {"logical_task_id": _id("modeltask:", {"instance_id": instance["instance_id"], **cohort_identity}), "subject_id": instance["subject_id"], "task_profile": contract.task_profile, "task_profile_version": contract.task_profile_version, "claim_family_id": contract.claim_families[0], "prompt_policy_version": contract.planner_prompt_policy_version, "schema_version": contract.planner_schema_version, "evidence_corpus_hash": _sha(corpus), "difficulty": contract.route_class, "demand": {"demand_id": instance["demand_id"], "semantic_signature": instance["semantic_signature"]}}
            packet = materialize_execution_packet(task=task, corpus=corpus, contract=contract, runtime_root=runtime_root, catalog_path=catalog_path, model="gpt-5.6-luna", reasoning_effort="low", service_tier="default")
            _rights(rights_decisions, packet.evidence_units)
            compiled = serialize_execution_packet_request(task, packet, delivery_job_id=job_id, delivery_mode="standard")
            # Persist only a JSON round-trippable body, then hash that exact
            # durable material.  This makes the pre-send hash invariant hold
            # even when a provider schema/prompt contains Unicode edge cases.
            frozen_body = json.loads(_canonical(compiled.body).decode("utf-8"))
            bound = cost_by_instance[instance["instance_id"]]
            reservation_id = _id("reservation:", {"request": compiled.provider_request_item_id, "aud": bound["aud"]})
            physical_id, delivery_id = _id("physical:", compiled.provider_request_item_id), _id("deliveryattempt:", compiled.provider_request_item_id)
            catalog.register_task({"record_id": task["logical_task_id"], "subject_id": task["subject_id"], "cohort_id": cohort_id, "task_type": "evidence_selection", "task_schema": {"schema_id": contract.schema_id}, "cache_key": packet.packet_hash, "provider_id": "openai", "model_snapshot": "gpt-5.6-luna"}, run_id=run_id, now=timestamp)
            catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": bound["aud"], "currency": "AUD"}, "model_task_ids": (task["logical_task_id"],)}, now=timestamp)
            catalog.reserve_execution_mandate(mandate_id=mandate_id, reservation_id=reservation_id, amount_aud=bound["aud"], now=timestamp)
            catalog.prepare_physical_attempt(physical_attempt_id=physical_id, run_id=run_id, subject_id=task["subject_id"], delivery_mode="standard", provider_request_id=compiled.provider_request_item_id, model_task_ids=(task["logical_task_id"],), reservation_id=reservation_id, now=timestamp)
            catalog.create_provider_request_item(provider_request_item_id=compiled.provider_request_item_id, run_id=run_id, model_task_id=task["logical_task_id"], provider_id="openai", model_route="gpt-5.6-luna", requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=job_id, physical_attempt_id=physical_id, now=timestamp)
            catalog.create_provider_request_attempt(delivery_attempt_id=delivery_id, provider_request_item_id=compiled.provider_request_item_id, physical_attempt_id=physical_id, delivery_job_id=job_id, attempt_ordinal=1, authorization_id=mandate_id, attempt_class="initial", predecessor_attempt_id=None, now=timestamp)
            schema = frozen_body["text"]["format"]["schema"]
            rows.append({"instance_id": instance["instance_id"], "provider": "openai", "provider_account_project": provider_account_project, "provider_request_item_id": compiled.provider_request_item_id, "logical_task_id": task["logical_task_id"], "contract_id": contract.contract_id, "contract_version": contract.contract_version, "contract_identity_hash": contract.identity_hash(), "schema_factory_id": contract.schema_factory_id, "task_profile": contract.task_profile, "task_profile_version": contract.task_profile_version, "prompt_sha256": contract.prompt_sha256, "schema_id": contract.schema_id, "schema_version": contract.schema_version, "schema_hash": _sha(schema), "provider_schema_name": compiled.schema_name, "model": compiled.model, "reasoning_effort": "low", "delivery_mode": "standard", "provider_service_tier": None, "max_output_tokens": 8000, "request_body": frozen_body, "request_body_sha256": body_sha256(canonical_standard_body_bytes(frozen_body)), "hard_max_aud": bound["aud"], "hard_max_usd": bound["usd"], "reservation_id": reservation_id, "mandate_reservation_id": reservation_id, "physical_attempt_id": physical_id, "delivery_attempt_id": delivery_id, "scope_id": None, "evidence_ids": [unit.evidence_id for unit in packet.evidence_units], "packet_hash": packet.packet_hash})
    finally:
        catalog.close()
    # Packet compilation may share schema internals across rows. Recompute the
    # body identity after the complete materialization loop so every pinned
    # hash covers the exact final durable body rather than a transient object.
    for row in rows:
        row["request_body_sha256"] = body_sha256(canonical_standard_body_bytes(row["request_body"]))
    return {"schema": "charitygraph.frozen-experiment-prepared-run/v1", "cohort_id": cohort_id, "run_id": run_id, "mandate_id": mandate_id, "provider_account_project": provider_account_project, "pricing_snapshot_sha256": cohort_identity["pricing_snapshot_sha256"], "aggregate_hard_usd": str(sum((Decimal(item["hard_max_usd"]) for item in rows), Decimal("0"))), "aggregate_hard_aud": str(aggregate_aud), "rows": rows, "prepared_run_hash": _sha(rows)}


def execute_prepared_standard(*, prepared: Mapping[str, Any], catalog_path: Path, authorization_catalog_path: Path, runtime_root: Path, provider: Any, now: datetime | None = None) -> dict[str, Any]:
    """Execute only pre-pinned rows through the existing exactly-once transport."""
    execution_time = _now(now)
    catalog = SQLiteCatalog(catalog_path, authorization_path=authorization_catalog_path).open()
    try:
        if getattr(provider, "provider_account_project", None) != prepared.get("provider_account_project"):
            raise FrozenExperimentError("provider project does not match the prepared frozen run")
        pricing_path = Path(runtime_root) / "frozen-pricing-snapshot.json"
        if _file_sha(pricing_path) != prepared.get("pricing_snapshot_sha256"):
            raise FrozenExperimentError("frozen pricing snapshot is missing or differs from prepared identity")
        pricing, _ = _pricing(pricing_path, {str(row["instance_id"]) for row in prepared["rows"]})
        expected_rates = {key: str(value) for key, value in PRICING["gpt-5.6-luna"].items()}
        if pricing.get("provider_rates_usd_per_million_tokens") != expected_rates:
            raise FrozenExperimentError("frozen pricing rates differ from established Luna pricing mechanism")

        def reconcile(row: Mapping[str, Any], usage: Any, provider_receipt_id: str) -> dict[str, Any]:
            if not isinstance(usage, Mapping):
                raise FrozenExperimentError("completed provider receipt lacks usage accounting")
            item = catalog.get_provider_request_item(str(row["provider_request_item_id"]))
            physical = catalog.get_physical_attempt(str(row["physical_attempt_id"]))
            receipt = catalog.get_physical_receipt(str(row["physical_attempt_id"]))
            if (item is None or item.get("status") != "completed" or item.get("provider_receipt_id") != provider_receipt_id
                    or physical is None or physical.get("status") != "validated"
                    or receipt is None or receipt.get("provider_receipt_id") != provider_receipt_id
                    or receipt.get("provider_request_id") != row["provider_request_item_id"]):
                raise FrozenExperimentError("actual-cost reconciliation is not bound to a completed durable provider receipt")
            durable_usage = receipt.get("usage_json")
            if isinstance(durable_usage, str):
                durable_usage = json.loads(durable_usage)
            if dict(durable_usage or {}) != dict(usage):
                raise FrozenExperimentError("provider usage differs from durable receipt")
            usd, aud = standard_actual_cost(dict(usage), Decimal(str(pricing["aud_per_usd"])), model="gpt-5.6-luna")
            if usd > Decimal(str(row["hard_max_usd"])) or aud > Decimal(str(row["hard_max_aud"])):
                raise FrozenExperimentError("actual provider cost exceeds its pinned per-request exposure")
            reservation_id = str(row["reservation_id"])
            fx_identity = "fxsnapshot:" + _sha({"pricing_snapshot_sha256": prepared["pricing_snapshot_sha256"], "aud_per_usd": str(pricing["aud_per_usd"])})
            entry_key = "actual:frozen:" + str(row["provider_request_item_id"])
            catalog.record_accounting_actual(
                entry_key=entry_key, provider_request_item_id=str(row["provider_request_item_id"]),
                provider_receipt_id=provider_receipt_id, reservation_id=reservation_id,
                provider_amount=usd, provider_currency="USD", accounting_amount=aud,
                accounting_currency="AUD", pricing_snapshot_id=str(pricing["snapshot_id"]),
                fx_snapshot_id=fx_identity, usage=usage, recorded_at=execution_time,
            )
            release_key = "release:frozen:" + str(row["provider_request_item_id"])
            if catalog.get_cost_entry(release_key) is None:
                position = catalog.accounting_reservation_position(reservation_id)
                if Decimal(position["outstanding"]) > 0:
                    catalog.release_reservation(reservation_id, {"amount": str(position["outstanding"]), "currency": "AUD"}, now=execution_time, entry_key=release_key)
            catalog.settle_execution_mandate_reservation(
                mandate_id=str(prepared["mandate_id"]), reservation_id=str(row["mandate_reservation_id"]),
                actual_aud=aud, ambiguous=False, now=execution_time,
            )
            return {"entry_key": entry_key, "actual_usd": str(usd), "actual_aud": str(aud), "pricing_snapshot_id": str(pricing["snapshot_id"])}

        # This is deliberately immediately before the coordinator: it checks the
        # durable request/physical/delivery rows and active budget authority that
        # the coordinator will consume, without crossing a provider boundary.
        for row in prepared["rows"]:
            durable = catalog.get_provider_request_item(str(row["provider_request_item_id"]))
            if durable is not None and durable.get("status") == "completed":
                receipt = catalog.get_physical_receipt(str(row["physical_attempt_id"]))
                if receipt is None:
                    raise FrozenExperimentError("completed provider item lacks a durable receipt")
                usage = receipt.get("usage_json")
                if isinstance(usage, str):
                    usage = json.loads(usage)
                reconcile(row, usage, str(receipt["provider_receipt_id"]))
            else:
                certify_standard_execution_row(catalog, row, mandate_id=prepared["mandate_id"])
        return StandardCampaignCoordinator(
            catalog=catalog, provider=provider, runtime_root=runtime_root, max_concurrency=1,
            now=execution_time,
            on_reconciled=lambda row, response, usage: reconcile(
                row, usage,
                "standard-receipt:" + hashlib.sha256((str(row["provider_request_item_id"]) + ":" + str(response.body["id"])).encode()).hexdigest(),
            ),
            mandate_evaluator=lambda row: __import__("charitygraph.phase5_execution_mandate", fromlist=["evaluate_execution_against_mandate"]).evaluate_execution_against_mandate(catalog, prepared["mandate_id"], row, now=execution_time),
        ).run(list(prepared["rows"]))
    finally:
        catalog.close()


__all__ = ["FrozenExperimentError", "demand_propositions", "load_frozen_instances", "validate_evidence_selection", "prepare_frozen_experiment", "execute_prepared_standard"]
