"""Deterministic compatibility recovery for the first direct-service run."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts.direct_service_wire import DirectServiceWireOutput


RECOVERY_ADAPTER_VERSION = "direct-service-wire-schema-strip-v1"
_WIRE_FIELDS = frozenset({"section", "propositions", "relationships"})


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


__all__ = ["RECOVERY_ADAPTER_VERSION", "recover_historical_wire", "recovery_identity"]
