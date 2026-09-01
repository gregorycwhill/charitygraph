"""Narrow recovery adapter for the terminal v2 Section 16 owner-wire defect."""

from __future__ import annotations

import copy
import json
from datetime import date, datetime
from typing import Any

from .contracts.conduct_compliance import ConductComplianceWireOutput, wire_to_domain

RECOVERY_POLICY_VERSION = "section16-v2-owner-label-recovery-v1"


def recover_historical_wire(raw_output: str | bytes | dict[str, Any]) -> tuple[ConductComplianceWireOutput, dict[str, Any]]:
    """Recover only the known old flat-owner defect; never mutate raw input.

    The adapter is intentionally opt-in for historical v2 payloads.  It accepts
    the old flat owner fields, records any redundant label, and converts them to
    the tagged provider shape without interpreting the label text.
    """
    value = json.loads(raw_output) if isinstance(raw_output, (str, bytes)) else copy.deepcopy(raw_output)
    if not isinstance(value, dict) or not isinstance(value.get("propositions"), list):
        raise ValueError("historical response must contain propositions")
    recovered = copy.deepcopy(value)
    diagnostics: list[dict[str, Any]] = []
    for index, item in enumerate(recovered["propositions"]):
        if not isinstance(item, dict):
            raise ValueError(f"proposition {index} is not an object")
        if "owner" in item:
            raise ValueError("recovery adapter is restricted to old flat-owner responses")
        kind = item.pop("proposition_owner_kind", None)
        if kind not in {"source_publisher", "target_subject", "other_named_party", "unknown"}:
            raise ValueError(f"unsupported historical owner kind at proposition {index}")
        label = item.pop("proposition_owner_label", None)
        diagnostics.append({"observation_index": index, "owner_kind": kind, "redundant_label": label, "removed": label is not None})
        item["owner"] = {"kind": kind, **({"label": label} if kind == "other_named_party" and label is not None else {})}
        temporal = item.get("temporal")
        if isinstance(temporal, dict) and "observed_at" in temporal:
            if temporal["observed_at"] is not None:
                raise ValueError("historical non-null temporal.observed_at cannot be recovered")
            temporal.pop("observed_at")
            diagnostics[-1]["removed_temporal_observed_at"] = True
    wire = ConductComplianceWireOutput.model_validate(recovered)
    return wire, {"policy_version": RECOVERY_POLICY_VERSION, "removed_owner_labels": diagnostics}


def recover_historical_domain(raw_output: str | bytes | dict[str, Any], *, observed_at: datetime | date | str, allowed_scope_ids: set[str] | None = None, evidence_key_map: dict[str, str] | None = None):
    wire, diagnostics = recover_historical_wire(raw_output)
    return wire_to_domain(wire, allowed_scope_ids=allowed_scope_ids, evidence_key_map=evidence_key_map, observed_at=observed_at), diagnostics


__all__ = ["RECOVERY_POLICY_VERSION", "recover_historical_wire", "recover_historical_domain"]
