"""Certification-aware S0 routing for the bounded v0.3 section 15/17 path."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CertificationStatus = Literal["CERTIFIED_BOUNDED", "CERTIFIED_WITH_REVIEW", "UNCERTIFIED"]
Disposition = Literal["PRIVATE_PROJECTION", "REVIEW_REQUIRED", "DISABLED"]


@dataclass(frozen=True)
class DomainRoute:
    section_id: Literal[15, 17]
    owner: Literal["ethos", "notable_history"]
    contract_id: Literal["ethos-v1", "notable-event-v1"]
    certification_id: str
    certification_status: CertificationStatus
    disposition: Disposition
    risk_family: str
    reason: str


_ROUTES = {
    "ethos": DomainRoute(15, "ethos", "ethos-v1", "CG-ETHOS-NOTABILITY-CERTIFICATION-344-TERRA", "CERTIFIED_WITH_REVIEW", "REVIEW_REQUIRED", "self_described", "Positive ethos semantics are synthetic-only in 344."),
    "notable_history": DomainRoute(17, "notable_history", "notable-event-v1", "CG-ETHOS-NOTABILITY-CERTIFICATION-344-TERRA", "CERTIFIED_WITH_REVIEW", "REVIEW_REQUIRED", "historical_temporal", "Positive history semantics are synthetic-only in 344."),
    "source_native_ethos": DomainRoute(15, "ethos", "ethos-v1", "CG-ETHOS-NOTABILITY-CERTIFICATION-344-TERRA", "CERTIFIED_BOUNDED", "PRIVATE_PROJECTION", "missingness", "Source-native governed observations may project privately."),
    "source_native_notable_history": DomainRoute(17, "notable_history", "notable-event-v1", "CG-ETHOS-NOTABILITY-CERTIFICATION-344-TERRA", "CERTIFIED_BOUNDED", "PRIVATE_PROJECTION", "beneficiary_non_transfer", "Source-native governed observations may project privately without scope transfer."),
}


def route_domain(*, section_id: int, risk_family: str, source_native: bool = False, unresolved: bool = False) -> DomainRoute:
    """Select an executable route; unresolved or uncertified surfaces fail closed."""
    if section_id == 16:
        raise ValueError("section 16 owns findings, allegations, sanctions and remediation")
    if section_id not in (15, 17):
        raise ValueError("ethos/notability routing only supports sections 15 and 17")
    key = ("source_native_" if source_native else "") + ("ethos" if section_id == 15 else "notable_history")
    route = _ROUTES[key]
    if unresolved or risk_family in {"external_characterisation", "political_ideological", "religious", "sensitive_person", "adverse_legal", "identity_scope_lineage"}:
        return DomainRoute(route.section_id, route.owner, route.contract_id, route.certification_id, "UNCERTIFIED", "DISABLED", risk_family, "344 does not justify autonomous extraction or ambiguous transfer.")
    return route


def route_task_metadata(*, section_id: int, risk_family: str, source_native: bool = False, unresolved: bool = False) -> dict[str, str | int]:
    route = route_domain(section_id=section_id, risk_family=risk_family, source_native=source_native, unresolved=unresolved)
    return {"section_id": route.section_id, "domain_owner": route.owner, "contract_id": route.contract_id, "certification_id": route.certification_id, "certification_status": route.certification_status, "disposition": route.disposition, "risk_family": route.risk_family, "routing_reason": route.reason}
