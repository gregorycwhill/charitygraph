"""Deterministic Section 16 bundle, task and economics preflight.

This module performs source-structural representation only.  It never selects
legal phrases or decides which statements matter; semantic interpretation is
reserved for the provider contract in :mod:`charitygraph.contracts.conduct_compliance`.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .baseline_corpus import sha256_json
from .contracts.conduct_compliance import ConductComplianceWireOutput
from .contracts.ids import deterministic_id
from .sources.web_v2 import normalize_snapshot
from .strict_schema import strictify_schema, validate_strict_schema


SOURCE_BUNDLES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("2020_compliance_action", ("srcrec:898766af7c3624fced893a04b550059c87fe1be45871be0259eef07eee3b6b21",), False),
    ("2023_enforceable_undertaking", ("srcrec:dd8c70b78cc766a8ba66cf74575547233e004199b67e36063b661e24d27e8ec9", "srcrec:4c1d129b170866bb55d7013c38417a17c5866ab499b3694b3bbeb775b22b7be1"), False),
    ("2025_compliance_action", ("srcrec:8c39eaf19d794611ce4c81a8fb1011e05ae3fa6e4c963d938cb46cd7f47fa6aa",), False),
    ("current_registration_section_boundary_control", ("srcrec:61d455442ae83a77b885408397436f90e3391611c69a0edfde33de2e34c57144",), True),
)

SUBJECT_ID = "subject:ca2a7205d6de410c85cb2a08196206dc"
MODEL = "gpt-5.6-luna"
REASONING = "high"
OUTPUT_CEILING = 24000


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_path(store_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.split(":", 1)[1]
    candidates = (
        store_root / "objects" / "sha256" / digest[:2] / digest,
        store_root / "objects" / "objects" / "sha256" / digest[:2] / digest,
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"private artefact is unavailable: {artifact_id}")


def _html_representation(raw: bytes, *, source_record: dict[str, Any], source_number: int) -> dict[str, Any]:
    html = raw.decode("utf-8", errors="replace")
    page = normalize_snapshot(html, requested_url=source_record["url"], final_url=source_record["url"])
    lines = [block["text"] for block in page["substantive_blocks"] if block.get("text")]
    if not lines:
        lines = [" ".join(html.split())]
    return {
        "source_record_id": source_record["source_record_id"],
        "source_key": f"S{source_number:03d}",
        "source_url": source_record["url"],
        "role": source_record["role"],
        "publisher_authority": "NDIS Quality and Safeguards Commission",
        "representation_type": "generic_visible_main_content",
        "lines": [{"evidence_key": f"E{i:06d}", "canonical_locator": f"[S{source_number:03d}:L{i:04d}]", "text": line} for i, line in enumerate(lines, 1)],
    }


def _pdf_representation(store_root: Path, source_record: dict[str, Any], source_number: int) -> dict[str, Any]:
    # The packet's representation points at the existing native PDF derived
    # artefact.  Every represented page is retained; no semantic page filter is
    # applied.
    representation = source_record.get("representation") or {}
    artifact_id = representation.get("artifact_id")
    if not artifact_id:
        raise ValueError("PDF source record lacks native representation artefact")
    data = json.loads(_artifact_path(store_root, artifact_id).read_text(encoding="utf-8"))
    lines: list[dict[str, str]] = []
    line_number = 1
    for page in data.get("pages", []):
        text = page.get("text") or ""
        for line in text.splitlines() or [""]:
            lines.append({"locator": f"[S{source_number:03d}:L{line_number:04d}]", "text": line})
            line_number += 1
    return {
        "source_record_id": source_record["source_record_id"],
        "source_key": f"S{source_number:03d}",
        "source_url": source_record["url"],
        "role": source_record["role"],
        "publisher_authority": "NDIS Quality and Safeguards Commission",
        "representation_type": "native_pdf_all_pages",
        "pages": data.get("pages", []),
        "lines": [{"evidence_key": f"E{i:06d}", "canonical_locator": line["locator"], "text": line["text"]} for i, line in enumerate(lines, 1)],
    }


def _bundle_hash(bundle: dict[str, Any]) -> str:
    return sha256_json({key: value for key, value in bundle.items() if key != "bundle_sha256"})


def _assign_evidence_keys(representations: list[dict[str, Any]]) -> None:
    """Assign one deterministic provider key namespace across a bundle."""
    key_number = 1
    for representation in representations:
        for line in representation.get("lines", []):
            line["evidence_key"] = f"E{key_number:06d}"
            key_number += 1


def persist_prompt_artifact(prompt: str, output_dir: str | Path) -> dict[str, str]:
    """Persist exact prompt bytes privately and return its content identity."""
    data = prompt.encode("utf-8")
    digest = _sha_bytes(data)
    path = Path(output_dir) / "prompts" / f"{digest}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("prompt artefact hash collision or mutation")
    if not path.exists():
        path.write_bytes(data)
    return {"prompt_sha256": digest, "prompt_artifact_id": f"prompt:{digest}", "prompt_artifact_path": str(path)}


def load_prompt_artifact(path: str | Path, expected_sha256: str) -> str:
    """Load a frozen prompt and fail closed if its bytes do not match."""
    data = Path(path).read_bytes()
    if _sha_bytes(data) != expected_sha256:
        raise ValueError("frozen prompt artefact SHA mismatch")
    return data.decode("utf-8")


def build_pressure_case_bundles(packet_path: str | Path, store_root: str | Path, output_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Build four deterministic bundles from the frozen packet."""
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    if packet.get("packet_sha256") != "35a44dde214ec360394e39aa15917230865fff8c99b80cdce636a8937506d994":
        raise ValueError("frozen pressure-case packet hash mismatch")
    records = {item["source_record_id"]: item for item in packet["source_records"]}
    store = Path(store_root)
    bundles: list[dict[str, Any]] = []
    for bundle_name, source_ids, is_boundary_control in SOURCE_BUNDLES:
        representations = []
        for index, source_id in enumerate(source_ids, 1):
            record = records[source_id]
            raw_path = _artifact_path(store, record["artifact_id"])
            if record["media_type"] == "text/html":
                rep = _html_representation(raw_path.read_bytes(), source_record=record, source_number=index)
            elif record["media_type"] == "application/pdf":
                rep = _pdf_representation(store, record, index)
            else:
                raise ValueError(f"unsupported pressure-case media type: {record['media_type']}")
            representations.append(rep)
        _assign_evidence_keys(representations)
        bundle = {
            "version": "section16-pressure-bundle-v1",
            "bundle_name": bundle_name,
            "control_kind": "current_registration_section_boundary_control" if is_boundary_control else None,
            "subject_id": packet["subject_id"],
            "allowed_scope_ids": [packet["subject_id"]],
            "source_record_ids": list(source_ids),
            "representations": representations,
            "representation_method": "generic_source_structural_v1",
            "representation_gaps": [],
            "bundle_sha256": None,
        }
        bundle["bundle_sha256"] = _bundle_hash(bundle)
        if output_dir is not None:
            out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
            (out / f"{bundle_name}.json").write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        bundles.append(bundle)
    return bundles


def bundle_locators(bundle: dict[str, Any]) -> set[str]:
    return {line["evidence_key"] for source in bundle["representations"] for line in source.get("lines", [])}


def bundle_evidence_map(bundle: dict[str, Any]) -> dict[str, str]:
    """Map provider evidence keys to canonical durable line locators."""
    return {line["evidence_key"]: line["canonical_locator"] for source in bundle["representations"] for line in source.get("lines", [])}


def bundle_prompt(bundle: dict[str, Any]) -> str:
    boundary = bundle.get("control_kind") == "current_registration_section_boundary_control"
    sparse = " This is a regulator registration/status record. It may contain registration conditions, variations, audit conditions or other regulatory-status facts. Do not classify those as Section 16 enforcement_action, finding or another conduct/adverse/compliance proposition merely because a condition was imposed. Emit a proposition only where the supplied evidence itself establishes a Section 16 matter. If it contains only registration/status conditions outside Section 16, return an empty proposition collection." if boundary else ""
    evidence = "\n".join(f"SOURCE_KEY: {source['source_key']}\nSOURCE_RECORD_ID: {source['source_record_id']}\nSOURCE_ROLE: {source['role']}\nPUBLISHER/AUTHORITY: {source['publisher_authority']}\n" + "\n".join(f"{line['evidence_key']} {line['text']}" for line in source.get("lines", [])) for source in bundle["representations"])
    return (
        "Extract only Section 16 conduct/adverse/compliance propositions supported by this supplied bundle. "
        "Sparse output is correct when evidence is sparse. Do not infer moral or reputational character, present "
        "non-compliance from historical action, or treat current registration as exoneration or general compliance "
        "endorsement. Distinguish source publisher authority from proposition owner: owner means who makes or holds "
        "the proposition/commitment, not who is affected by a condition. Do not absorb adjacent registration status, "
        "accreditation, governance or service-description facts unless the evidence supports a Section 16 proposition. "
        "Use only supplied subject, scope and evidence keys; use no outside knowledge. Provider evidence references "
        "must use the supplied E###### evidence keys, never durable locator syntax or source-record IDs. "
        f"Subject scope: {bundle['subject_id']}.{sparse}\n" + evidence
    )


def wire_schema() -> dict[str, Any]:
    schema = strictify_schema(ConductComplianceWireOutput.model_json_schema())
    validate_strict_schema(schema)
    return schema


def wire_schema_sha() -> str:
    return _sha_bytes(json.dumps(wire_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def plan_pressure_case(packet_path: str | Path, store_root: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    bundles = build_pressure_case_bundles(packet_path, store_root, output_dir)
    schema_sha = wire_schema_sha()
    planned: list[dict[str, Any]] = []
    for bundle in bundles:
        prompt = bundle_prompt(bundle)
        packet_bytes = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        prompt_bytes = prompt.encode()
        bundle_sha = bundle["bundle_sha256"]
        prompt_sha = _sha_bytes(prompt_bytes)
        task_identity = {"kind": "conduct_compliance_section16", "bundle_sha": bundle_sha, "prompt_sha": prompt_sha, "schema_sha": schema_sha, "model": MODEL, "reasoning": REASONING}
        task_id = deterministic_id("modeltask:", task_identity)
        run_id = deterministic_id("run:", {"task_id": task_id, "kind": "section16_preflight"})
        task_run_id = deterministic_id("taskrun:", {"task_id": task_id, "run_id": run_id, "attempt": 1})
        estimated_input = (len(packet_bytes) + len(prompt_bytes) + 3) // 4
        costs = {str(ceiling): str((Decimal(estimated_input) * Decimal("0.20") + Decimal(ceiling) * Decimal("1.20")) / Decimal(1_000_000)) for ceiling in (12000, 16000, 24000)}
        prompt_artifact = persist_prompt_artifact(prompt, output_dir) if output_dir is not None else {}
        planned.append({
            "bundle_name": bundle["bundle_name"], "control_kind": bundle["control_kind"], "source_record_ids": bundle["source_record_ids"], "bundle_sha256": bundle_sha,
            "represented_characters": sum(len(line["text"]) for rep in bundle["representations"] for line in rep.get("lines", [])),
            "packet_bytes": len(packet_bytes), "prompt_bytes": len(prompt_bytes), "estimated_input_tokens": estimated_input,
            "prompt_sha256": prompt_sha, "prompt_artifact_id": prompt_artifact.get("prompt_artifact_id"), "prompt_artifact_path": prompt_artifact.get("prompt_artifact_path"), "wire_schema_sha256": schema_sha, "evidence_map_sha256": _sha_bytes(json.dumps(bundle_evidence_map(bundle), sort_keys=True, separators=(",", ":")).encode()), "task_id": task_id, "run_id": run_id, "task_run_id": task_run_id,
            "authorization_identity": deterministic_id("decision:", {"task_id": task_id, "state": "not_authorized"}),
            "cache_key": _sha_bytes(json.dumps(task_identity, sort_keys=True, separators=(",", ":")).encode()),
            "accounting_identity": deterministic_id("costledger:", {"task_id": task_id}), "max_output_tokens": OUTPUT_CEILING,
            "projected_usd": costs, "authorization_state": "not_authorized",
        })
    total = sum((Decimal(item["projected_usd"][str(OUTPUT_CEILING)]) for item in planned), Decimal("0"))
    report = {"version": "section16-provider-preflight-v1", "subject_id": SUBJECT_ID, "model": MODEL, "reasoning_effort": REASONING, "wire_schema_sha256": schema_sha, "bundles": planned, "aggregate_projected_max_usd": str(total.quantize(Decimal("0.000001"))), "aggregate_projected_max_aud": None, "fx_note": "No FX snapshot used; AUD projection intentionally not asserted.", "provider_calls": 0, "authorization_state": "not_authorized"}
    if output_dir is not None:
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        (out / "section16-provider-preflight.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


__all__ = ["SOURCE_BUNDLES", "build_pressure_case_bundles", "bundle_locators", "bundle_evidence_map", "bundle_prompt", "wire_schema", "wire_schema_sha", "plan_pressure_case"]
