"""Deterministic compatibility recovery for the first direct-service run."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .contracts.direct_service_wire import (
    DirectServiceWireOutput,
    DirectServiceWireProposition,
    DirectServiceWireRelationship,
    wire_to_domain,
)


RECOVERY_ADAPTER_VERSION = "direct-service-wire-schema-strip-v1"
DIRECT_SERVICE_RESULT_RECOVERY_VERSION = "direct-service-result-recovery-v1"
_WIRE_FIELDS = frozenset({"section", "propositions", "relationships"})
_BARE_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RecoveredDirectServiceResult:
    """A derived, append-only interpretation of an immutable provider result.

    The adapter has intentionally narrow authority: it can restore the literal
    ``locator:`` prefix only when that exact reconstructed value occurs in the
    frozen packet, and can retain an independently valid entry from a mixed
    output.  It never changes a proposition's meaning or supplies evidence.
    """

    wire: DirectServiceWireOutput
    recovery_identity: str
    normalized_locator_count: int
    discarded_propositions: tuple[dict[str, Any], ...]
    discarded_relationships: tuple[dict[str, Any], ...]

    @property
    def is_direct(self) -> bool:
        return not self.normalized_locator_count and not self.discarded_propositions and not self.discarded_relationships

    @property
    def is_usable(self) -> bool:
        return bool(self.wire.propositions or self.wire.relationships)


def recover_historical_wire(raw_output: str | bytes) -> DirectServiceWireOutput:
    """Drop only the known historical provider-owned ``schema`` field.

    This is deliberately not a generic extra-field tolerance policy: all other
    unexpected keys remain strict failures.
    """

    parsed = json.loads(raw_output)
    if not isinstance(parsed, dict) or "schema" not in parsed:
        raise ValueError("historical response must contain the obsolete top-level schema field")
    unexpected = set(parsed) - (_WIRE_FIELDS | {"schema"})
    if unexpected:
        raise ValueError(f"unexpected historical wire fields: {sorted(unexpected)}")
    return DirectServiceWireOutput.model_validate({key: value for key, value in parsed.items() if key != "schema"})


def recovery_identity(*, response_id: str, old_wire_schema_sha: str, domain_schema_id: str, policy_version: str = RECOVERY_ADAPTER_VERSION) -> str:
    material: dict[str, Any] = {"response_id": response_id, "old_wire_schema_sha": old_wire_schema_sha, "domain_schema_id": domain_schema_id, "policy_version": policy_version}
    return "modelresult:" + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _normalize_locator(locator: str, evidence_locators: set[str]) -> tuple[str, bool]:
    """Restore only the exact, packet-authorized locator namespace prefix."""

    if locator in evidence_locators:
        return locator, False
    candidate = "locator:" + locator
    if _BARE_SHA256.fullmatch(locator) and candidate in evidence_locators:
        return candidate, True
    raise ValueError("wire evidence locator is not present in the frozen packet")


def _normalize_evidence(items: tuple[Any, ...], evidence_locators: set[str]) -> tuple[tuple[Any, ...], int]:
    normalized = []
    count = 0
    for item in items:
        locator, changed = _normalize_locator(item.locator, evidence_locators)
        normalized.append(item.model_copy(update={"locator": locator}))
        count += int(changed)
    return tuple(normalized), count


def _entry_reason(kind: str, index: int, exc: Exception) -> dict[str, Any]:
    return {"kind": kind, "index": index, "reason": str(exc)[:500]}


def recover_direct_service_result(
    raw_output: str | bytes,
    *,
    response_id: str,
    allowed_scope_ids: set[str],
    evidence_locators: set[str],
) -> RecoveredDirectServiceResult:
    """Recover a provider result only through exact packet-bound mechanics.

    Validation is deliberately performed per entry.  A malformed or
    semantically disallowed entry cannot invalidate a different, complete,
    evidence-bound entry, but remains recorded as discarded in the resulting
    lineage.  An unrecognized evidence locator is never normalized or guessed.
    """

    raw_text = raw_output.decode("utf-8") if isinstance(raw_output, bytes) else raw_output
    original = DirectServiceWireOutput.model_validate_json(raw_text)
    normalized_count = 0
    kept_propositions: list[DirectServiceWireProposition] = []
    kept_relationships: list[DirectServiceWireRelationship] = []
    discarded_propositions: list[dict[str, Any]] = []
    discarded_relationships: list[dict[str, Any]] = []

    for index, item in enumerate(original.propositions):
        try:
            evidence, count = _normalize_evidence(item.evidence, evidence_locators)
            candidate = item.model_copy(update={"evidence": evidence})
            wire_to_domain(
                DirectServiceWireOutput(section=original.section, propositions=(candidate,)),
                allowed_scope_ids=allowed_scope_ids,
                evidence_locators=evidence_locators,
            )
            kept_propositions.append(candidate)
            normalized_count += count
        except Exception as exc:
            discarded_propositions.append(_entry_reason("proposition", index, exc))

    for index, item in enumerate(original.relationships):
        try:
            evidence, count = _normalize_evidence(item.evidence, evidence_locators)
            candidate = item.model_copy(update={"evidence": evidence})
            wire_to_domain(
                DirectServiceWireOutput(section=original.section, relationships=(candidate,)),
                allowed_scope_ids=allowed_scope_ids,
                evidence_locators=evidence_locators,
            )
            kept_relationships.append(candidate)
            normalized_count += count
        except Exception as exc:
            discarded_relationships.append(_entry_reason("relationship", index, exc))

    recovered = DirectServiceWireOutput(
        section=original.section,
        propositions=tuple(kept_propositions),
        relationships=tuple(kept_relationships),
    )
    # Verify the assembled output with the production domain boundary too.
    wire_to_domain(recovered, allowed_scope_ids=allowed_scope_ids, evidence_locators=evidence_locators)
    material = {
        "response_id": response_id,
        "raw_output_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "allowed_scope_ids": sorted(allowed_scope_ids),
        "evidence_locators": sorted(evidence_locators),
        "policy_version": DIRECT_SERVICE_RESULT_RECOVERY_VERSION,
    }
    identity = "modelresult:" + hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RecoveredDirectServiceResult(
        wire=recovered,
        recovery_identity=identity,
        normalized_locator_count=normalized_count,
        discarded_propositions=tuple(discarded_propositions),
        discarded_relationships=tuple(discarded_relationships),
    )


__all__ = [
    "RECOVERY_ADAPTER_VERSION", "DIRECT_SERVICE_RESULT_RECOVERY_VERSION",
    "RecoveredDirectServiceResult", "recover_historical_wire",
    "recover_direct_service_result", "recovery_identity",
]
