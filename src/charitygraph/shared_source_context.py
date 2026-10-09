"""Mechanical construction of CG354's one-copy shared evidence registry.

This module deliberately has no language rules.  It joins the two frozen
section packets on their already-selected source representations and exposes
each representation once to the semantic provider.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


CONTEXT_VERSION = "cg354-shared-source-context-v1"


def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def build_registry(section_packets: tuple[Mapping[str, Any], Mapping[str, Any]], representations_root: str) -> dict[str, Any]:
    """Return a stable registry, rejecting ambiguity before any provider call.

    Identity is the immutable representation hash, not prose or a semantic
    similarity judgement.  The two section packets must bind the same case and
    subject.  Repeated evidence fragments are retained as bindings on the one
    transmitted representation.
    """
    first, second = section_packets
    if first["case_id"] != second["case_id"] or first["subject_id"] != second["subject_id"]:
        raise ValueError("section_packets_do_not_share_case_and_subject")
    import pathlib
    root = pathlib.Path(representations_root)
    registry: dict[str, dict[str, Any]] = {}
    for packet in section_packets:
        for evidence in packet.get("evidence", ()):
            key = evidence["representation_sha256"]
            locator = evidence["representation_locator"]
            path = root / locator
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != key:
                raise ValueError("missing_or_changed_representation:" + locator)
            item = registry.setdefault(key, {
                "evidence_id": "S%03d" % (len(registry) + 1),
                "representation_id": evidence["representation_id"],
                "representation_sha256": key,
                "representation_locator": locator,
                "source_record_id": evidence.get("source_record_id", evidence["raw_blob_id"]),
                "raw_blob_id": evidence["raw_blob_id"], "raw_sha256": evidence["raw_sha256"],
                "source_family": evidence.get("source_family"), "source_role": evidence.get("source_role"),
                "source_version": evidence.get("source_version"), "retrieved_at": evidence.get("retrieved_at"),
                "resolved_locator": evidence.get("resolved_locator"), "bindings": [],
            })
            # Different claimed provenance for identical retained bytes is not
            # safe to silently merge.
            if item["representation_id"] != evidence["representation_id"] or item["raw_sha256"] != evidence["raw_sha256"]:
                raise ValueError("ambiguous_representation_identity:" + key)
            binding = {"section": packet["section"], "evidence_fragment_id": evidence["evidence_fragment_id"], "fragment_locator": evidence["fragment_locator"], "fragment_sha256": evidence["fragment_sha256"]}
            if binding not in item["bindings"]:
                item["bindings"].append(binding)
    entries = sorted(registry.values(), key=lambda x: x["evidence_id"])
    result = {"context_version": CONTEXT_VERSION, "case_id": first["case_id"], "subject_id": first["subject_id"], "packet_hashes": {str(p["section"]): p["packet_hash"] for p in section_packets}, "evidence": entries}
    result["registry_sha256"] = canonical_hash(result)
    return result


def validate_no_duplicate_transmission(registry: Mapping[str, Any]) -> None:
    entries = registry.get("evidence", ())
    hashes = [x["representation_sha256"] for x in entries]
    ids = [x["evidence_id"] for x in entries]
    if len(hashes) != len(set(hashes)) or len(ids) != len(set(ids)):
        raise ValueError("duplicate_representation_transmission")
    expected = dict(registry); supplied = expected.pop("registry_sha256", None)
    if supplied != canonical_hash(expected):
        raise ValueError("registry_hash_mismatch")


def provider_evidence_body(registry: Mapping[str, Any], representations_root: str, *, per_representation_char_limit: int = 6000) -> str:
    """Render each validated representation exactly once for the provider."""
    validate_no_duplicate_transmission(registry)
    import pathlib
    root = pathlib.Path(representations_root)
    rows = []
    for item in registry["evidence"]:
        value = json.loads((root / item["representation_locator"]).read_text(encoding="utf-8"))
        text = value.get("text") if isinstance(value, dict) else None
        if not isinstance(text, str):
            text = json.dumps(value.get("json") if isinstance(value, dict) else value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        provenance = {key: item.get(key) for key in ("evidence_id", "source_record_id", "source_family", "source_role", "source_version", "retrieved_at", "resolved_locator", "bindings")}
        rows.append(json.dumps(provenance, sort_keys=True, ensure_ascii=False) + "\n" + text[:per_representation_char_limit])
    return "\n\n".join(rows)
