"""Run the private World Vision Luna Knowledge Production v0.2 experiment."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charitygraph.openai_client import estimate_response_cost, responses_create  # noqa: E402
from charitygraph.whole_card_calibration import visible_html  # noqa: E402
from charitygraph.whole_card_semantic_v02 import (  # noqa: E402
    STRICT_SCHEMA,
    WholeCardExtractionOutputV02,
    duplicate_count,
    validate_output,
)

REPORT = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
MODEL = "gpt-5.6-luna"
MAX_OUTPUT_TOKENS = 48_000
MAX_ATTEMPTS = 2
SPEND_CAP_USD = Decimal("1.00")
SECTION_COUNT = 20


def _artifact(artifact_id: str) -> bytes:
    digest = artifact_id.split(":", 1)[1]
    roots = [Path(r"C:\CharityGraph-runtime\state"), REPORT.parent]
    roots.extend(Path(r"C:\CharityGraph-runtime").glob("**/objects"))
    for root in roots:
        path = root / "objects" / "sha256" / digest[:2] / digest
        if path.is_file():
            return path.read_bytes()
        path = root / "objects" / "objects" / "sha256" / digest[:2] / digest
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(f"persisted artifact unavailable: {artifact_id}")


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines() or [""]


def _content(row: tuple[Any, ...], member: dict[str, Any]) -> tuple[str, str]:
    record_id, family, role, revision, locator, payload_ref, material_json = row
    raw = _artifact(payload_ref)
    media = (json.loads(material_json).get("media_type") if material_json else "") or ""
    representations = member.get("representation_artifact_ids") or []
    if representations:
        rep = json.loads(_artifact(representations[0]).decode("utf-8"))
        pages = rep.get("representation", {}).get("pages", [])
        return "\n".join(f"Page {page.get('page')}:\n{page.get('text', '')}" for page in pages), "derived_pdf_text"
    if "html" in media or raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        return visible_html(raw.decode("utf-8", "replace")), "visible_html"
    if "json" in media or raw.lstrip().startswith((b"{", b"[")):
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False, indent=2), "structured_json"
        except json.JSONDecodeError:
            return raw.decode("utf-8", "replace"), "text"
    return raw.decode("utf-8", "replace"), "text"


def build_packet(report_path: Path = REPORT, catalog_path: Path = CATALOG) -> tuple[dict[str, Any], dict[str, str]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    subject = next(item for item in report["subjects"] if item["abn"] == "28004778081")
    corpus = next(item for item in report["corpora"] if item["subject_id"] == subject["subject_id"])
    db = sqlite3.connect(catalog_path)
    sources: list[dict[str, Any]] = []
    source_map: dict[str, str] = {}
    sequence = 0
    for member in corpus["material_members"]:
        for record_id in member["source_record_ids"]:
            row = db.execute(
                "select source_record_id,source_family,source_role,source_version,source_locator,payload_ref,material_json from source_records where source_record_id=?",
                (record_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"source record unavailable: {record_id}")
            if row[2] in {"robots", "sitemap"}:
                continue
            sequence += 1
            key = f"S{sequence:03d}"
            content, content_kind = _content(row, member)
            locators = [{"locator": f"{key}:L{index:04d}", "text": line} for index, line in enumerate(_lines(content), 1)]
            source_map[key] = row[0]
            sources.append({
                "source_key": key,
                "source_record_id": row[0],
                "source_family": row[1],
                "source_role": row[2],
                "source_locator": row[4],
                "source_revision": row[3],
                "effective_period": member.get("effective_period"),
                "binding_context": member.get("binding_context"),
                "representation_readiness": member.get("representation_readiness"),
                "representation_gaps": member.get("representation_gaps", []),
                "content_kind": content_kind,
                "locators": locators,
            })
    db.close()
    packet = {
        "packet_version": "whole-card-semantic-knowledge-production-v0.2",
        "subject": {"name": subject["registered_name"], "abn": subject["abn"], "subject_id": subject["subject_id"]},
        "corpus_id": corpus["corpus_id"],
        "material_identity_hash": corpus["material_identity_hash"],
        "sources": sources,
    }
    return packet, source_map


def _prompt() -> str:
    return (Path(__file__).with_name("whole_card_semantic_calibration_v02_prompt.txt").read_text(encoding="utf-8")).replace("\r\n", "\n")


def _estimate(packet_bytes: bytes, prompt: str) -> tuple[int, Decimal]:
    tokens = (len(packet_bytes) + len(prompt.encode("utf-8")) + 3) // 4
    projected = (Decimal(tokens) * Decimal("0.20") + Decimal(MAX_OUTPUT_TOKENS) * Decimal("1.20")) * MAX_ATTEMPTS / Decimal(1_000_000)
    return tokens, projected.quantize(Decimal("0.000001"))


def _context_metrics() -> dict[str, Any]:
    result: dict[str, Any] = {}
    candidates = {
        "fred_luna": Path(r"C:\CharityGraph-runtime\whole-card-calibration-v01-luna-retry-20260830T\luna-raw.json"),
        "acf_luna": Path(r"C:\CharityGraph-runtime\sparse-whole-card-calibration-v01-20260830T043851Z\gpt-5.6-luna-returned-output.json"),
    }
    for name, path in candidates.items():
        if not path.is_file():
            result[name] = {"available": False}
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            text = raw.get("output_text") or raw.get("raw_output") or ""
            parsed = raw.get("parsed_output") or raw.get("output")
            result[name] = {"available": True, "path": str(path), "output_characters": len(text), "observation_count": len((parsed or {}).get("observations", [])) if isinstance(parsed, dict) else None}
        except Exception as exc:
            result[name] = {"available": True, "path": str(path), "read_error": type(exc).__name__}
    return result


def _structural(result: WholeCardExtractionOutputV02 | None, packet: dict[str, Any], source_map: dict[str, str], *, truncation: bool = False) -> dict[str, Any]:
    if result is None:
        return {"observations": 0, "observations_by_section": {str(i): 0 for i in range(1, SECTION_COUNT + 1)}, "scope_counts": {}, "source_family_counts": {}, "relationships": 0, "cross_source_issues": 0, "assignments_by_scheme_and_scope": {}, "citation_resolution_failures": [], "duplicate_counts": {}, "truncated": truncation}
    by_section = {str(i): 0 for i in range(1, SECTION_COUNT + 1)}
    scopes: dict[str, int] = {}; families: dict[str, int] = {}
    family_by_key = {s["source_key"]: s["source_family"] for s in packet["sources"]}
    for item in result.observations:
        by_section[str(item.section_id)] += 1; scopes[item.scope.kind] = scopes.get(item.scope.kind, 0) + 1
        for evidence in item.evidence:
            family = family_by_key.get(evidence.source, "unresolved"); families[family] = families.get(family, 0) + 1
    assignments: dict[str, int] = {}
    for item in result.assignments:
        key = f"{item.scheme}:{item.target_scope.kind}"; assignments[key] = assignments.get(key, 0) + 1
    return {"observations": len(result.observations), "observations_by_section": by_section, "scope_counts": scopes, "source_family_counts": families, "relationships": len(result.relationships), "cross_source_issues": len(result.cross_source_issues), "assignments_by_scheme_and_scope": assignments, "citation_resolution_failures": [], "duplicate_counts": {"observations": duplicate_count(result.observations), "assignments": duplicate_count(result.assignments), "relationships": duplicate_count(result.relationships)}, "truncated": truncation}


def _structural_unvalidated(value: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    """Count recoverable structure even when cross-field validation rejects it."""
    by_section = {str(i): 0 for i in range(1, SECTION_COUNT + 1)}; scopes: dict[str, int] = {}; families: dict[str, int] = {}
    family_by_key = {s["source_key"]: s["source_family"] for s in packet["sources"]}
    valid = {s["source_key"]: {x["locator"].split(":", 1)[-1] for x in s["locators"]} for s in packet["sources"]}
    failures: list[dict[str, Any]] = []
    for index, item in enumerate(value.get("observations", [])):
        section = item.get("section_id")
        if isinstance(section, int) and 1 <= section <= SECTION_COUNT: by_section[str(section)] += 1
        kind = (item.get("scope") or {}).get("kind")
        if kind: scopes[kind] = scopes.get(kind, 0) + 1
        refs = item.get("evidence") or []
        for ref in refs:
            key, loc = ref.get("source"), ref.get("locator")
            if key in family_by_key: families[family_by_key[key]] = families.get(family_by_key[key], 0) + 1
            if key not in valid:
                failures.append({"collection": "observations", "index": index, "source": key, "locator": loc, "reason": "unknown source key"})
            elif not isinstance(loc, str):
                failures.append({"collection": "observations", "index": index, "source": key, "locator": loc, "reason": "invalid locator"})
            else:
                match = __import__("re").fullmatch(r"L(\d{4})(?:-L(\d{4}))?", loc)
                if not match or int(match.group(1)) > int(match.group(2) or match.group(1)) or any(f"L{n:04d}" not in valid[key] for n in range(int(match.group(1)), int(match.group(2) or match.group(1)) + 1)):
                    failures.append({"collection": "observations", "index": index, "source": key, "locator": loc, "reason": "locator does not resolve"})
    def dups(items: list[Any]) -> int:
        encoded = [json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for x in items]
        return len(encoded) - len(set(encoded))
    assignments = value.get("assignments", []) or []
    assignment_counts: dict[str, int] = {}
    for item in assignments:
        key = f"{item.get('scheme')}:{(item.get('target_scope') or {}).get('kind')}"; assignment_counts[key] = assignment_counts.get(key, 0) + 1
    return {"observations": len(value.get("observations", []) or []), "observations_by_section": by_section, "scope_counts": scopes, "source_family_counts": families, "relationships": len(value.get("relationships", []) or []), "cross_source_issues": len(value.get("cross_source_issues", []) or []), "assignments_by_scheme_and_scope": assignment_counts, "citation_resolution_failures": failures, "duplicate_counts": {"observations": dups(value.get("observations", []) or []), "assignments": dups(assignments), "relationships": dups(value.get("relationships", []) or [])}, "truncated": False}


def run(output_root: Path | None = None) -> dict[str, Any]:
    packet, source_map = build_packet()
    prompt = _prompt()
    packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    packet_hash = hashlib.sha256(packet_bytes).hexdigest()
    estimated_tokens, projected = _estimate(packet_bytes, prompt)
    if estimated_tokens > 200_000:
        raise RuntimeError(f"packet exceeds 200000 estimated input tokens: {estimated_tokens}")
    if projected > SPEND_CAP_USD:
        raise RuntimeError(f"projected Luna exposure exceeds USD {SPEND_CAP_USD}: {projected}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = output_root or Path(r"C:\CharityGraph-runtime") / f"worldvision-luna-knowledge-v02-{stamp}"
    root.mkdir(parents=False, exist_ok=False)
    (root / "packet.json").write_bytes(packet_bytes)
    (root / "packet.sha256").write_text(packet_hash + "\n", encoding="ascii")
    (root / "prompt.txt").write_text(prompt, encoding="utf-8")
    manifest = {"packet_sha256": packet_hash, "corpus_id": packet["corpus_id"], "material_identity_hash": packet["material_identity_hash"], "ordered_source_record_ids": [source_map[s["source_key"]] for s in packet["sources"]], "source_keys": list(source_map), "estimated_input_tokens": estimated_tokens, "substantive_source_count": len(packet["sources"]), "excluded_roles": ["robots", "sitemap"]}
    (root / "packet-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    input_text = prompt + "\n\nFROZEN PACKET BYTES:\n" + packet_bytes.decode("utf-8")
    started = time.perf_counter(); row: dict[str, Any] = {"model": MODEL, "packet_sha256": packet_hash, "projected_exposure_usd": str(projected), "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": 300, "max_attempts": MAX_ATTEMPTS}
    parsed: dict[str, Any] | None = None; validated: WholeCardExtractionOutputV02 | None = None
    try:
        response = responses_create(model=MODEL, input_text=input_text, text_format={"type": "json_schema", "name": "whole_card_extraction_v02", "strict": True, "schema": STRICT_SCHEMA}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=MAX_ATTEMPTS, timeout_seconds=300, reasoning={"effort": "high"})
        row.update({"response_id": response.response_id, "status": response.status, "transport_requests": response.transport_requests, "usage": response.usage.__dict__, "cost_usd": str(estimate_response_cost(MODEL, response.usage) or 0), "output_text": response.output_text})
        # Persist the raw provider response before JSON or semantic validation.
        (root / "gpt-5.6-luna-raw.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            parsed = json.loads(response.output_text); row["json_valid"] = True
            (root / "parsed-output.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            row.update({"json_valid": False, "parse_error": type(exc).__name__, "parse_error_detail": str(exc)[:240]})
        if parsed is not None:
            try:
                validated = validate_output(parsed, packet); row["schema_valid"] = True
            except Exception as exc:
                row.update({"schema_valid": False, "validation_error": type(exc).__name__, "validation_error_detail": str(exc)[:240]})
    except Exception as exc:
        row.update({"provider_error": type(exc).__name__, "provider_error_detail": str(exc)[:240], "transport_requests": getattr(exc, "attempts_made", 0), "cost_usd": "0"})
        (root / "gpt-5.6-luna-raw.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    row["latency_seconds"] = round(time.perf_counter() - started, 3)
    if validated is not None:
        (root / "validated-output.json").write_text(json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    structural = _structural(validated, packet, source_map, truncation=False) if validated is not None else (_structural_unvalidated(parsed, packet) if parsed is not None else _structural(None, packet, source_map))
    schema_shape = isinstance(parsed, dict) and set(parsed) == {"section_assessments", "observations", "assignments", "relationships", "cross_source_issues"}
    report = {"experiment": "world-vision-luna-knowledge-production-v0.2", "subject": packet["subject"], "corpus_id": packet["corpus_id"], "packet_sha256": packet_hash, "packet_bytes": len(packet_bytes), "estimated_input_tokens": estimated_tokens, "actual_input_tokens": (row.get("usage") or {}).get("input_tokens"), "output_tokens": (row.get("usage") or {}).get("output_tokens"), "latency_seconds": row["latency_seconds"], "cost_usd": row.get("cost_usd", "0"), "max_output_tokens": MAX_OUTPUT_TOKENS, "transport_requests": row.get("transport_requests", 0), "completion_validity": {"json": row.get("json_valid", False), "schema_shape": schema_shape, "cross_field": row.get("schema_valid", False), "citations": not structural.get("citation_resolution_failures")}, "structural": structural, "representation_gaps": [{"source_record_id": s["source_record_id"], "gaps": s["representation_gaps"]} for s in packet["sources"] if s["representation_gaps"]], "comparative_context": _context_metrics(), "provider_calls": 1 if row.get("response_id") else 0, "source_acquisition": 0}
    (root / "structural-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"root": str(root), "packet_sha256": packet_hash, "estimated_input_tokens": estimated_tokens, "projected_exposure_usd": str(projected), "actual_cost_usd": row.get("cost_usd", "0"), "provider_calls": report["provider_calls"], "json_valid": row.get("json_valid", False), "schema_valid": row.get("schema_valid", False)}, indent=2))
    return report


if __name__ == "__main__":
    run()
