"""Durable, bounded standing execution mandates.

Mandates authorize a class of already-governed requests.  They never replace
request identity, delivery attempts, reservations, receipts, or promotion
controls.  This module contains only provider-free policy evaluation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping

from .phase5_semantic_contracts import HISTORICAL_DISCOVERY_V2_CONTRACT, REGISTRY


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(manifest)).hexdigest()


class MandateDecision(StrEnum):
    AUTHORIZED_BY_MANDATE = "AUTHORIZED_BY_MANDATE"
    HUMAN_AUTHORIZATION_REQUIRED = "HUMAN_AUTHORIZATION_REQUIRED"
    MANDATE_EXHAUSTED = "MANDATE_EXHAUSTED"
    MANDATE_REVOKED = "MANDATE_REVOKED"
    CONTRACT_NOT_ALLOWED = "CONTRACT_NOT_ALLOWED"
    DELIVERY_NOT_ALLOWED = "DELIVERY_NOT_ALLOWED"
    MODEL_NOT_ALLOWED = "MODEL_NOT_ALLOWED"
    PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
    REQUEST_COST_EXCEEDS_LIMIT = "REQUEST_COST_EXCEEDS_LIMIT"
    IDENTITY_DRIFT = "IDENTITY_DRIFT"
    RESERVATION_NOT_AUTHORIZED = "RESERVATION_NOT_AUTHORIZED"


@dataclass(frozen=True)
class MandateEvaluation:
    decision: MandateDecision
    reason: str
    remaining_aud: Decimal | None = None
    mandate_id: str | None = None

    @property
    def authorized(self) -> bool:
        return self.decision == MandateDecision.AUTHORIZED_BY_MANDATE


def _allowlisted_contract(contract: Any) -> dict[str, Any]:
    return {
        "contract_key": contract.contract_id + ":" + contract.contract_version,
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "contract_identity_hash": contract.identity_hash(),
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "claim_families": list(contract.claim_families),
        "prompt_sha256": contract.prompt_sha256,
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "schema_factory_id": contract.schema_factory_id,
        "provider_schema_name": contract.provider_schema_name,
        "schema_hash_rule": "exact governed schema factory over exact evidence IDs; request hash remains independently pinned",
    }


def _phase5_standard_luna_manifest(*, mandate_id: str, supersedes_mandate_id: str | None = None, discovery_contract: Any | None = None) -> dict[str, Any]:
    """Build an inactive Phase-5 mandate envelope for the current registry."""
    discovery_contract = discovery_contract or next(item for item in REGISTRY if item.contract_id == "urn:charitygraph:builder:semantic-contract:program-service-discovery-v2")
    direct_contract = next(item for item in REGISTRY if item.contract_id == "urn:charitygraph:builder:semantic-contract:direct-service-v1")
    allowed_contracts = [_allowlisted_contract(discovery_contract), _allowlisted_contract(direct_contract)]
    return {
        "manifest_version": "execution-mandate-v1",
        "mandate_id": mandate_id,
        "purpose": "Phase-5 build/calibration semantic execution",
        "phase_scope": "phase5-build-calibration",
        "provider": "openai",
        "delivery_mode": "standard",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "max_concurrency": 4,
        "automatic_retries": 0,
        "semantic_retries": 0,
        "fallbacks": [],
        "ambiguous_resend": False,
        "aggregate_hard_aud": "100.00",
        "per_request_hard_aud": "0.25",
        "allowed_contracts": allowed_contracts,
        "excluded_authorities": ["governed_promotion", "CanonicalObservations", "adjudication", "card_projection", "git_merge", "public_release", "source_acquisition", "new_provider"],
        "termination": ["phase5_formally_closed", "aggregate_authority_exhausted", "explicit_revocation", "mandate_invalidating_boundary_change"],
        **({"supersedes_mandate_id": supersedes_mandate_id} if supersedes_mandate_id else {}),
    }


def proposed_phase5_standard_luna_manifest() -> dict[str, Any]:
    return _phase5_standard_luna_manifest(mandate_id="mandate:phase5-build-standard-luna-v1")


def proposed_phase5_standard_luna_historical_manifest() -> dict[str, Any]:
    return _phase5_standard_luna_manifest(
        mandate_id="mandate:phase5-build-standard-luna-v1-amendment-1",
        discovery_contract=HISTORICAL_DISCOVERY_V2_CONTRACT,
    )


def proposed_phase5_standard_luna_amendment_manifest() -> dict[str, Any]:
    return _phase5_standard_luna_manifest(
        mandate_id="mandate:phase5-build-standard-luna-v1-amendment-2",
        supersedes_mandate_id="mandate:phase5-build-standard-luna-v1-amendment-1",
    )


def evaluate_execution_against_mandate(catalog: Any, mandate_id: str, request: Mapping[str, Any], *, now: Any = None) -> MandateEvaluation:
    mandate = catalog.get_execution_mandate(mandate_id)
    if mandate is None:
        return MandateEvaluation(MandateDecision.HUMAN_AUTHORIZATION_REQUIRED, "mandate does not exist", mandate_id=mandate_id)
    if mandate["status"] in {"revoked", "terminated"}:
        return MandateEvaluation(MandateDecision.MANDATE_REVOKED, "mandate is no longer active", mandate_id=mandate_id)
    if mandate["status"] == "exhausted":
        return MandateEvaluation(MandateDecision.MANDATE_EXHAUSTED, "mandate authority is exhausted", mandate_id=mandate_id)
    if mandate["status"] != "active":
        return MandateEvaluation(MandateDecision.HUMAN_AUTHORIZATION_REQUIRED, "mandate has not been explicitly activated", mandate_id=mandate_id)
    if request.get("provider") != "openai":
        return MandateEvaluation(MandateDecision.PROVIDER_NOT_ALLOWED, "provider is outside mandate", mandate_id=mandate_id)
    if request.get("delivery_mode") != "standard":
        return MandateEvaluation(MandateDecision.DELIVERY_NOT_ALLOWED, "delivery mode is outside mandate", mandate_id=mandate_id)
    if request.get("model") != "gpt-5.6-luna" or request.get("reasoning_effort") != "low":
        return MandateEvaluation(MandateDecision.MODEL_NOT_ALLOWED, "model/reasoning is outside mandate", mandate_id=mandate_id)
    if request.get("automatic_retries", 0) != 0 or request.get("semantic_retries", 0) != 0 or request.get("fallbacks", []) != [] or request.get("ambiguous_resend", False) is not False:
        return MandateEvaluation(MandateDecision.IDENTITY_DRIFT, "retry/fallback/ambiguity policy differs", mandate_id=mandate_id)
    try:
        hard_cost = Decimal(str(request["hard_max_aud"]))
    except Exception:
        return MandateEvaluation(MandateDecision.IDENTITY_DRIFT, "request hard cost is not a valid Decimal", mandate_id=mandate_id)
    if hard_cost < 0 or hard_cost > Decimal(mandate["per_request_hard_aud"]):
        return MandateEvaluation(MandateDecision.REQUEST_COST_EXCEEDS_LIMIT, "request exceeds per-request mandate ceiling", mandate_id=mandate_id)
    contract_match = False
    for raw in mandate.get("contracts", []):
        item = json.loads(raw["contract_json"]) if isinstance(raw, dict) and "contract_json" in raw else raw
        if all(request.get(key) == item.get(key) for key in ("contract_id", "contract_version", "task_profile", "task_profile_version", "prompt_sha256", "schema_id", "schema_version", "provider_schema_name", "contract_identity_hash")):
            contract_match = True
            break
    if not contract_match:
        return MandateEvaluation(MandateDecision.CONTRACT_NOT_ALLOWED, "semantic contract/prompt/schema identity is not allowlisted", mandate_id=mandate_id)
    remaining = Decimal(mandate["aggregate_hard_aud"]) - Decimal(mandate["actual_spend_aud"]) - Decimal(mandate["unresolved_reserved_aud"])
    if hard_cost > remaining:
        return MandateEvaluation(MandateDecision.MANDATE_EXHAUSTED, "request would exceed remaining aggregate mandate authority", remaining_aud=remaining, mandate_id=mandate_id)
    reservation_id = request.get("mandate_reservation_id")
    if not reservation_id:
        return MandateEvaluation(MandateDecision.RESERVATION_NOT_AUTHORIZED, "exact physical attempt has no mandate reservation", remaining_aud=remaining, mandate_id=mandate_id)
    with catalog._authorization_connection() as conn:
        reservation = conn.execute("SELECT * FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (mandate_id, reservation_id)).fetchone()
    if reservation is None or reservation["status"] != "active" or Decimal(reservation["reserved_aud"]) < hard_cost:
        return MandateEvaluation(MandateDecision.RESERVATION_NOT_AUTHORIZED, "exact physical attempt does not have active sufficient mandate reservation", remaining_aud=remaining, mandate_id=mandate_id)
    return MandateEvaluation(MandateDecision.AUTHORIZED_BY_MANDATE, "request is within the active mandate", remaining_aud=remaining, mandate_id=mandate_id)


__all__ = ["MandateDecision", "MandateEvaluation", "evaluate_execution_against_mandate", "manifest_hash", "proposed_phase5_standard_luna_manifest", "proposed_phase5_standard_luna_historical_manifest", "proposed_phase5_standard_luna_amendment_manifest"]
