"""Read-only validation for immutable Data Scale S0 authority packages."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from charitygraph.scale_s0 import (
    LogicalTaskRegistry, PolicyArtifact, RoutingClass, RoutingPolicy,
    SamplingPolicy, ScaleMandate, ScalePreflightError, ScaleS0Preflight,
    HaltController, default_s0_registry,
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return sha256(canonical_bytes(value)).hexdigest().upper()


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScalePreflightError(f"package artifact is not canonical JSON-compatible YAML: {path}") from error
    if not isinstance(value, dict):
        raise ScalePreflightError(f"package artifact is not an object: {path}")
    return value


def _policy_artifacts(root: Path, manifest: dict[str, Any]) -> tuple[dict[str, PolicyArtifact], dict[str, dict[str, Any]]]:
    artifacts: dict[str, PolicyArtifact] = {}
    bodies: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for entry in manifest["policies"]:
        path = root / entry["artifact_path"]
        body = load_json_yaml(path)
        actual = canonical_hash(body)
        identity = (entry["policy_id"], str(entry["policy_version"]))
        if identity in seen:
            raise ScalePreflightError("duplicate policy ID/version")
        seen.add(identity)
        if body.get("policy_id") != identity[0] or str(body.get("policy_version")) != identity[1] or actual != entry["canonical_content_hash"]:
            raise ScalePreflightError("policy identity or canonical content hash mismatch")
        artifacts[entry["manifest_key"]] = PolicyArtifact(*identity, actual)
        bodies[entry["manifest_key"]] = body
    aggregate = canonical_hash([{"key": key, "policy_id": artifacts[key].policy_id, "version": artifacts[key].version, "hash": artifacts[key].content_hash} for key in sorted(artifacts)])
    if aggregate != manifest["aggregate_bundle_hash"]:
        raise ScalePreflightError("aggregate policy bundle hash mismatch")
    return artifacts, bodies


def load_authorisation_package(package_root: str | Path) -> tuple[ScaleMandate, LogicalTaskRegistry, RoutingPolicy, SamplingPolicy, dict[str, PolicyArtifact]]:
    root = Path(package_root)
    manifest = load_json_yaml(root / "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml")
    artifacts, bodies = _policy_artifacts(root, manifest)
    mandate_data = load_json_yaml(root / "SCALE_S0_SHADOW_MANDATE_V2.yaml")
    if mandate_data.get("aggregate_policy_bundle_hash") != manifest["aggregate_bundle_hash"]:
        raise ScalePreflightError("mandate bundle hash mismatch")
    if mandate_data.get("policy_hashes") != {key: artifact.content_hash for key, artifact in artifacts.items()}:
        raise ScalePreflightError("mandate individual policy binding mismatch")
    artifacts["reservation"] = artifacts["economics_reservation"]
    registry = default_s0_registry()
    if mandate_data.get("task_registry_hash") != registry.immutable_hash.upper():
        raise ScalePreflightError("task registry hash mismatch")
    population = bodies["population"]
    if mandate_data.get("population_hash") != artifacts["population"].content_hash or tuple(x["abn"] for x in population["entities"]) != tuple(mandate_data["subject_ids"]):
        raise ScalePreflightError("population binding mismatch")
    routing_body, sampling_body, economics_body = bodies["routing"], bodies["sampling"], bodies["economics_reservation"]
    routing = RoutingPolicy(routing_body["policy_id"], str(routing_body["policy_version"]), frozenset(RoutingClass(v) for v in ("deterministic", "low_cost_semantic", "low_cost_then_escalate", "strong_reasoning", "human_decision")), {key: RoutingClass(value) for key, value in routing_body["allowed_escalations"].items()}, artifacts["routing"].content_hash)
    sampling = SamplingPolicy(sampling_body["policy_id"], str(sampling_body["policy_version"]), sampling_body["seed"], tuple(sampling_body["strata"]), {"default": sampling_body["strata"]["ordinary_semantic"]}, artifacts["sampling"].content_hash)
    allowed = tuple(bodies["output_boundary"]["allowed_outputs"])
    mandate = ScaleMandate(
        mandate_id=mandate_data["mandate_id"], mandate_version=str(mandate_data["mandate_version"]), slice_id=mandate_data["slice_id"], created_at=mandate_data["created_at"], authorizing_actor_ref=mandate_data["authorizing_actor_ref"], population_ref=population["ranking_artifact"], subject_ids=tuple(mandate_data["subject_ids"]), snapshot_as_of=population["snapshot_reporting_vintage"], ranking_policy_id="acnc-2024-ais-donations-desc-abn-asc-v1", group_entity_policy_id=artifacts["entity_group"].policy_id, source_universe_policy_id=artifacts["source_universe"].policy_id, source_universe_policy_version=artifacts["source_universe"].version, mandatory_source_families=tuple(bodies["source_universe"]["mandatory_families"]), applicable_source_families=tuple(bodies["source_universe"]["mandatory_families"] + bodies["source_universe"]["conditional_families"] + [bodies["source_universe"]["specialist_triggered_family"]]), specialist_source_policy_id=artifacts["specialist_source"].policy_id, rights_transmission_policy_id=artifacts["rights_transmission"].policy_id, task_registry_version=registry.version, enabled_task_ids=tuple(c.task_id for c in registry.contracts), disabled_task_ids=(), routing_policy_id=artifacts["routing"].policy_id, routing_policy_version=artifacts["routing"].version, provider_spend_ceiling=economics_body["total_provider_ceiling"], strong_model_spend_ceiling=economics_body["strong_model_ceiling"], provider_call_ceiling=economics_body["provider_call_ceiling"], reservation_policy_id=artifacts["economics_reservation"].policy_id, currency_basis=economics_body["currency"], review_policy_id=artifacts["review"].policy_id, review_policy_version=artifacts["review"].version, promotion_policy_id=artifacts["promotion"].policy_id, promotion_policy_version=artifacts["promotion"].version, sampling_policy_id=artifacts["sampling"].policy_id, sampling_policy_version=artifacts["sampling"].version, halt_policy_id=artifacts["halt"].policy_id, halt_policy_version=artifacts["halt"].version, allowed_outputs=allowed, automatically_publishable=False, policy_hashes={key: artifact.content_hash for key, artifact in artifacts.items()} | {"logical_task_registry": registry.immutable_hash}, per_request_reservation_cap=economics_body["per_request_reservation_cap"],
    )
    return mandate, registry, routing, sampling, artifacts


def validate_authorisation_package(package_root: str | Path, *, synthetic_approval: bool = False) -> ScaleMandate:
    mandate, registry, routing, _sampling, policies = load_authorisation_package(package_root)
    if synthetic_approval:
        mandate = replace(mandate, authorizing_actor_ref="TEST_ONLY_SYNTHETIC_APPROVAL")
    mandate.validate()
    ScaleS0Preflight(mandate, registry, routing, {}, HaltController(), packets={}, policies=policies, economics=None)
    return mandate
