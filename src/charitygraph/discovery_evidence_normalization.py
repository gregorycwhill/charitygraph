"""Deterministic, append-only normalization for Discovery V2 evidence meanings."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any, Mapping


TRANSFORM_ID = "charitygraph.discovery.v2.evidence-meaning-normalization"
TRANSFORM_VERSION = "1"
ROLES = frozenset({"supporting", "competing", "context"})


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _meaning(entry: Mapping[str, Any]) -> tuple[str, str | None]:
    if set(entry) != {"evidence_id", "role", "note"}:
        raise ValueError("historical evidence entry has unexpected fields")
    evidence_id, role, note = entry["evidence_id"], entry["role"], entry["note"]
    if not isinstance(evidence_id, str) or not evidence_id:
        raise ValueError("historical evidence ID is invalid")
    if role not in ROLES:
        raise ValueError("historical evidence role is invalid")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        raise ValueError("historical evidence note is invalid")
    return role, note


def normalize_discovery_output(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Group repeated locator entries without changing semantic proposal fields."""
    if set(raw) != {"proposals"} or not isinstance(raw["proposals"], list):
        raise ValueError("historical Discovery output shape is invalid")
    normalized = {"proposals": []}
    for proposal in raw["proposals"]:
        if not isinstance(proposal, Mapping) or "evidence" not in proposal or not isinstance(proposal["evidence"], list):
            raise ValueError("historical proposal evidence shape is invalid")
        result = dict(proposal)
        grouped: OrderedDict[str, list[tuple[str, str | None]]] = OrderedDict()
        for entry in proposal["evidence"]:
            if not isinstance(entry, Mapping):
                raise ValueError("historical evidence entry is not an object")
            evidence_id = entry.get("evidence_id")
            grouped.setdefault(evidence_id, []).append(_meaning(entry))
        evidence = []
        for evidence_id, meanings in grouped.items():
            distinct = []
            for pair in meanings:
                if pair not in distinct:
                    distinct.append(pair)
            first_role, first_note = distinct[0]
            item = {"evidence_id": evidence_id, "role": first_role, "note": first_note}
            item["additional_meanings"] = [{"role": role, "note": note} for role, note in distinct[1:]]
            evidence.append(item)
        result["evidence"] = evidence
        normalized["proposals"].append(result)
    return normalized


def normalize_with_lineage(*, raw: Mapping[str, Any], provider_response_id: str,
                           provider_request_item_id: str, historical_contract: Mapping[str, Any],
                           corrected_contract: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_discovery_output(raw)
    return {
        "transform_id": TRANSFORM_ID,
        "transform_version": TRANSFORM_VERSION,
        "provider_response_id": provider_response_id,
        "provider_request_item_id": provider_request_item_id,
        "historical_contract": dict(historical_contract),
        "corrected_contract": dict(corrected_contract),
        "input_raw_result_hash": canonical_hash(raw),
        "normalized_result_hash": canonical_hash(normalized),
        "normalized_output": normalized,
    }


__all__ = ["TRANSFORM_ID", "TRANSFORM_VERSION", "canonical_hash", "normalize_discovery_output", "normalize_with_lineage"]
