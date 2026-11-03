"""Offline, deterministic packetisation of retained semantic evidence.

This module deliberately contains no language or network logic.  It only
normalises retained evidence, deduplicates by representation identity, and
builds domain packets containing references into one shared registry.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _identity(evidence: dict[str, Any]) -> str:
    return str(evidence.get("representation_id") or evidence.get("raw_blob_id") or evidence.get("evidence_fragment_id"))


DEFAULT_CONTEXT_LIMIT = 32_000
DEFAULT_SAFETY_MARGIN = 0.20
DEFAULT_OUTPUT_RESERVE = 4_000


def estimate_tokens(value: Any) -> int:
    """Deterministic upper-bound estimate: UTF-8 bytes / 3, rounded up."""
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, math.ceil(len(raw.encode("utf-8")) / 3))


def _text(record: dict[str, Any]) -> str:
    for key in ("text", "content", "body", "extracted_text"):
        if isinstance(record.get(key), str):
            return record[key]
    return ""


def _split_record(record: dict[str, Any], *, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    text = _text(record)
    if not text or not chunk_size or len(text) <= chunk_size:
        return [dict(record)]
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    identity = _identity(record)
    out = []
    start = 0
    ordinal = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        # Prefer a mechanical whitespace boundary, without inspecting meaning.
        if end < len(text):
            boundary = text.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        row = dict(record)
        row.update({"registry_key": f"{identity}:span:{ordinal:06d}", "parent_representation_id": identity,
                    "span_start": start, "span_end": end, "chunk_ordinal": ordinal,
                    "overlap_from_previous": max(0, (start + chunk_size) - end),
                    "text": text[start:end]})
        out.append(row)
        ordinal += 1
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return out


def preflight_read_units(units: list[dict[str, Any]], *, context_limit: int = DEFAULT_CONTEXT_LIMIT,
                         safety_margin: float = DEFAULT_SAFETY_MARGIN, output_reserve: int = DEFAULT_OUTPUT_RESERVE,
                         envelope_tokens: int = 512) -> dict[str, Any]:
    if context_limit <= 0 or not 0 <= safety_margin < 1 or output_reserve < 0:
        raise ValueError("invalid token budget configuration")
    budget = math.floor(context_limit * (1 - safety_margin)) - output_reserve
    rows = []
    for unit in units:
        estimated = estimate_tokens(unit.get("payload", unit)) + envelope_tokens
        rows.append({"unit_id": unit["unit_id"], "estimated_input_tokens": estimated,
                     "budget_tokens": budget, "within_budget": estimated <= budget})
    if any(not row["within_budget"] for row in rows):
        raise ValueError("read-unit preflight exceeds conservative Luna budget")
    return {"context_limit": context_limit, "safety_margin": safety_margin, "output_reserve": output_reserve,
            "budget_tokens": budget, "units": rows}


def build_packets(corpus: dict[str, Any], *, chunk_size: int = 6000, overlap: int = 64,
                  context_limit: int = DEFAULT_CONTEXT_LIMIT, safety_margin: float = DEFAULT_SAFETY_MARGIN,
                  output_reserve: int = DEFAULT_OUTPUT_RESERVE) -> dict[str, Any]:
    """Build shared registry and replayable section packets from frozen corpus.

    ``chunk_size`` is character-based; splitting is mechanical only and
    preserves parent identity and source metadata.
    """
    if chunk_size < 0:
        raise ValueError("chunk_size must be non-negative")
    registry: dict[str, dict[str, Any]] = {}
    refs: dict[str, list[str]] = {}
    for packet in corpus.get("packets", []):
        packet_key = f"{packet['case_id']}:{packet['section']}"
        ids: list[str] = []
        for evidence in sorted(packet.get("evidence", []), key=lambda x: (_identity(x), x.get("fragment_locator", ""))):
            identity = _identity(evidence)
            if not identity or identity == "None":
                raise ValueError("retained evidence lacks a stable representation identity")
            for record in _split_record(dict(evidence), chunk_size=chunk_size, overlap=overlap):
                key = record.get("registry_key", identity)
                existing = registry.get(key)
                if existing is not None and canonical(existing) != canonical(record):
                    raise ValueError(f"identity collision with divergent provenance: {key}")
                registry[key] = record
                ids.append(key)
        refs[packet_key] = sorted(set(ids))

    registry_items = [registry[key] for key in sorted(registry)]
    packet_rows = []
    for packet in sorted(corpus.get("packets", []), key=lambda x: (x["case_id"], x["section"])):
        key = f"{packet['case_id']}:{packet['section']}"
        body = {"case_id": packet["case_id"], "subject_id": packet["subject_id"], "section": packet["section"],
                "selection_version": "shared-registry-packetisation-v1", "evidence_registry_keys": refs[key],
                "coverage_state": packet.get("coverage_state", "coverage_gap")}
        packet_rows.append({**body, "packet_id": "packet:" + digest(body), "packet_hash": digest(body)})
    units = []
    # A read unit is deliberately bounded below the section packet: one
    # source span plus its stable packet context. This keeps source boundaries
    # intact while allowing a section to have arbitrarily many documents.
    for row in packet_rows:
        for ordinal, key in enumerate(row["evidence_registry_keys"]):
            payload = {"packet": {k: v for k, v in row.items() if k != "evidence_registry_keys"},
                       "evidence_registry_key": key, "evidence": registry[key]}
            units.append({"unit_id": f"{row['packet_id']}:unit:{ordinal:06d}", "payload": payload})
    preflight = preflight_read_units(units, context_limit=context_limit, safety_margin=safety_margin,
                                    output_reserve=output_reserve)
    result = {"format": "charitygraph.semantic-input.v1", "corpus_id": corpus.get("corpus_id"),
              "cohort_sha256": corpus.get("cohort_sha256"), "source_corpus_sha256": corpus.get("corpus_sha256"),
              "registry": registry_items, "packets": packet_rows, "read_units": units,
              "preflight": preflight, "network": {"allowed": False}}
    result["packetisation_sha256"] = digest(result)
    return result


def replay_hash(corpus: dict[str, Any], *, chunk_size: int = 0) -> str:
    return build_packets(corpus, chunk_size=chunk_size)["packetisation_sha256"]
