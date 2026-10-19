"""Provider wire interface for the generic v1.5 discovery contract.

This is a mechanical adapter: it binds a compiled contract and exact evidence
identity set to a strict JSON Schema and a generic instruction. It does not
interpret question prose, infer missing parameters, or inspect source meaning.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping, Sequence

from .generic_discovery_contract import (
    CONTRACT_SCHEMA,
    GenericDiscoveryContractError,
    UNSPECIFIED,
    validate_discovery_result,
)
from .strict_schema import validate_strict_schema


PROVIDER_INTERFACE = "charitygraph.generic-discovery-provider/v1.5.1"
SCHEMA_NAME = "charitygraph_discovery_v151"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _nonblank(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GenericDiscoveryContractError(f"{label} must be a non-empty string")
    return value


def assert_same_selected_subjects(selection_doc: Mapping[str, Any], packets_doc: Mapping[str, Any]) -> None:
    """Fail closed unless executable rows bind the exact selected subject set."""
    selected = selection_doc.get("instances", [])
    packets = packets_doc.get("packets", [])
    try:
        selected_abns = {str(row["subject"]["abn"]) for row in selected}
        packet_abns = set()
        for packet in packets:
            identifiers = packet["envelope"]["subject"].get("external_authority_identifiers", [])
            values = [str(item["value"]) for item in identifiers
                      if item.get("authority") == "ACNC" and item.get("scheme") == "ABN"]
            if len(values) != 1:
                raise ValueError("frozen packet subject must have exactly one ACNC-scoped ABN")
            packet_abns.add(values[0])
    except (KeyError, TypeError) as exc:
        raise ValueError("selected subjects or packet subject bindings are malformed") from exc
    if len(selected_abns) != 36 or len(packet_abns) != 36 or selected_abns != packet_abns:
        raise ValueError(
            "frozen execution packets are not bound to the exact selected 36-subject manifest; "
            f"selected={len(selected_abns)}, packet={len(packet_abns)}, overlap={len(selected_abns & packet_abns)}"
        )


def response_schema(contract: Mapping[str, Any], evidence_ids: Sequence[str]) -> dict[str, Any]:
    """Build an OpenAI strict schema bound to this contract and packet IDs."""
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise GenericDiscoveryContractError("provider interface requires a compiled v1.5 demand contract")
    if not isinstance(evidence_ids, Sequence) or isinstance(evidence_ids, (str, bytes)):
        raise GenericDiscoveryContractError("packet evidence IDs must be a sequence")
    ids = list(evidence_ids)
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise GenericDiscoveryContractError("packet evidence IDs must be unique non-empty strings")
    variables = contract.get("discoverable_answer_variables")
    if not isinstance(variables, list) or not variables:
        raise GenericDiscoveryContractError("contract has no declared answer variables")
    names = [item.get("name") for item in variables if isinstance(item, Mapping)]
    if len(names) != len(variables) or any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise GenericDiscoveryContractError("contract answer-variable identities are malformed")
    states = contract.get("permitted_states")
    if not isinstance(states, list) or not states or any(not isinstance(item, str) for item in states):
        raise GenericDiscoveryContractError("contract permitted states are malformed")

    evidence_ref = {"type": "string", **({"enum": ids} if ids else {})}
    record = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answer_variable": {"type": "string", "enum": names},
            # v1.5 intentionally does not define variable-specific types or
            # cardinality. Keep values attributed and textual; do not invent
            # a typed/domain projection here.
            "answer_text": {"type": "string"},
            "evidence_ids": {"type": "array", "items": copy.deepcopy(evidence_ref), "minItems": 1},
            "qualification": {"type": ["string", "null"]},
        },
        "required": ["answer_variable", "answer_text", "evidence_ids", "qualification"],
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "state": {"type": "string", "enum": states},
            "records": {"type": "array", "items": record, **({} if ids else {"maxItems": 0})},
            "qualification": {"type": ["string", "null"]},
            "enumeration_state": {"type": "string", "enum": [UNSPECIFIED, "PARTIAL", "EXHAUSTIVE"]},
            "exhaustiveness_evidence_ids": {
                "type": "array",
                "items": copy.deepcopy(evidence_ref),
                **({} if ids else {"maxItems": 0}),
            },
            "negative_conclusion": {"type": "boolean"},
        },
        "required": [
            "state", "records", "qualification", "enumeration_state",
            "exhaustiveness_evidence_ids", "negative_conclusion",
        ],
    }
    validate_strict_schema(schema)
    return schema


def schema_sha256(contract: Mapping[str, Any], evidence_ids: Sequence[str]) -> str:
    return hashlib.sha256(_canonical(response_schema(contract, evidence_ids))).hexdigest()


def render_prompt(
    *,
    contract: Mapping[str, Any],
    question_text: str,
    subject: Mapping[str, Any],
    identity_bindings: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> str:
    """Render one generic provider prompt without deriving semantics from prose."""
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise GenericDiscoveryContractError("prompt requires a compiled v1.5 demand contract")
    _nonblank(question_text, "frozen question text")
    subject_id = _nonblank(subject.get("governed_subject_id"), "opaque governed subject ID")
    if not isinstance(identity_bindings, Sequence) or isinstance(identity_bindings, (str, bytes)):
        raise GenericDiscoveryContractError("identity bindings must be a sequence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        raise GenericDiscoveryContractError("packet evidence must be a sequence")
    ids = [item.get("evidence_id") for item in evidence if isinstance(item, Mapping)]
    if len(ids) != len(evidence) or any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise GenericDiscoveryContractError("packet evidence identities must be unique and explicit")

    # Only the prepared packet is rendered. Source representations are passed
    # in by the caller and remain intact; this function never acquires sources.
    return (
        "You are answering one frozen CharityGraph discovery question using only the supplied governed evidence.\n"
        "Return only JSON matching the supplied strict schema. Do not use outside knowledge, search, or infer facts from names or categories.\n"
        "Follow the supplied demand contract exactly: its operation, answer variables, subject/scope, time, user inputs, evidence obligations, permitted states, and forbidden inferences are authoritative. Do not change the opaque subject identity or turn an answer variable into an input.\n"
        "Each record is an attributed textual value for one declared answer variable. Cite one or more exact packet evidence IDs for every value. Preserve source-native meaning, scope, time, uncertainty, disagreement, and qualifications. A record may be partial or qualified; do not strengthen it beyond its cited evidence.\n"
        "Use a supported state only for answer content actually established by the cited evidence. Use PARTIAL when only a bounded portion is established, and explain the boundary in qualification. Use a permitted missing/abstain state when the answer is not established; lack of evidence is not a negative fact. Do not convert partial evidence into a negative conclusion or unsupported certainty.\n"
        "Enumeration is UNSPECIFIED unless the evidence explicitly establishes its completeness. EXHAUSTIVE and any negative conclusion require explicit packet evidence of coverage; cite it in exhaustiveness_evidence_ids. An empty result does not prove an empty real-world set.\n\n"
        f"FROZEN QUESTION (preserve its exact meaning):\n{question_text}\n\n"
        f"COMPILED V1.5 DEMAND CONTRACT:\n{json.dumps(contract, ensure_ascii=False, sort_keys=True)}\n\n"
        f"OPAQUE GOVERNED SUBJECT ID: {subject_id}\n"
        f"GOVERNED SUBJECT-TO-AUTHORITY BINDINGS:\n{json.dumps(list(identity_bindings), ensure_ascii=False, sort_keys=True)}\n\n"
        f"PACKET EVIDENCE (exact evidence IDs and representations):\n{json.dumps(list(evidence), ensure_ascii=False, sort_keys=True)}"
    )


def validate_provider_result(
    contract: Mapping[str, Any],
    result: Mapping[str, Any],
    evidence_ids: Sequence[str],
) -> None:
    """Validate v1.5 semantics structurally and bind every nested ref to packet IDs."""
    validate_discovery_result(contract, result)
    allowed = set(evidence_ids)
    if len(allowed) != len(list(evidence_ids)):
        raise GenericDiscoveryContractError("packet evidence identity set contains duplicates")
    top_refs = result.get("exhaustiveness_evidence_ids", [])
    if not isinstance(top_refs, list) or any(item not in allowed for item in top_refs):
        raise GenericDiscoveryContractError("exhaustiveness evidence ID is outside this packet")
    for index, record in enumerate(result.get("records", [])):
        refs = record.get("evidence_ids") if isinstance(record, Mapping) else None
        if not isinstance(refs, list) or not refs or any(item not in allowed for item in refs):
            raise GenericDiscoveryContractError(f"record {index} has an evidence ID outside this packet")
        if not isinstance(record.get("answer_variable"), str) or record["answer_variable"] not in {
            item["name"] for item in contract.get("discoverable_answer_variables", [])
        }:
            raise GenericDiscoveryContractError(f"record {index} uses an undeclared answer variable")
        _nonblank(record.get("answer_text"), f"record {index} answer text")
    state = result.get("state")
    if state == "PARTIAL" and not _nonblank(result.get("qualification"), "partial-result qualification"):
        raise GenericDiscoveryContractError("PARTIAL requires an explicit qualification")
    if result.get("negative_conclusion") is True and result.get("enumeration_state") != "EXHAUSTIVE":
        raise GenericDiscoveryContractError("negative conclusions require explicit exhaustive evidence")
