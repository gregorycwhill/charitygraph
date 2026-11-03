"""Build and run the private Whole-Card Semantic Calibration v0.1 packet."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from charitygraph.openai_client import estimate_response_cost, responses_create  # noqa: E402
from charitygraph.whole_card_calibration import STRICT_SCHEMA, packet_sha, validate_output, visible_html  # noqa: E402

REPORT = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
MODEL_NAMES = ("gpt-5.6-luna", "gpt-5.6-terra")
MODEL_PRICES = {"gpt-5.6-luna": (0.20, 1.20), "gpt-5.6-terra": (2.00, 12.00)}
MAX_TOKENS = 24_000
SPEND_CAP_USD = 3.00


def _prompt() -> str:
    # The frozen prompt is versioned beside this harness so completed runs
    # remain reproducible without depending on a local Codex attachment.
    prompt_bytes = Path(__file__).with_name("whole_card_semantic_calibration_v01_prompt.txt").read_bytes()
    # The completed run used the frozen attachment's CRLF bytes; canonicalise
    # line endings before transmission so checkout settings cannot change it.
    return prompt_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n").decode("utf-8")


def _artifact(root: Path, artifact_id: str) -> bytes:
    digest = artifact_id.split(":", 1)[1]
    candidates = [root / "objects" / "objects" / "sha256" / digest[:2] / digest]
    candidates += [p for p in Path(r"C:\CharityGraph-runtime").glob("**/objects/objects/sha256") for p in [p / digest[:2] / digest]]
    for path in candidates:
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(f"persisted artifact unavailable: {artifact_id}")


def _lines(content: str) -> list[str]:
    return content.replace("\r\n", "\n").replace("\r", "\n").splitlines() or [""]


def build_packet(report_path: Path = REPORT, catalog_path: Path = CATALOG) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    fred = next((item for item in report["subjects"] if item["abn"] == "46070556642"), None)
    if fred is None:
        raise RuntimeError("Fred Hollows subject is absent from the completed corpus report")
    corpus = next(item for item in report["corpora"] if item["subject_id"] == fred["subject_id"])
    db = sqlite3.connect(catalog_path)
    sources: list[dict[str, Any]] = []
    sequence = 0
    for member in corpus["material_members"]:
        role = None
        for source_record_id in member["source_record_ids"]:
            row = db.execute("select source_record_id,source_family,source_role,source_version,source_locator,payload_ref,material_json from source_records where source_record_id=?", (source_record_id,)).fetchone()
            if row is None:
                raise RuntimeError(f"source record unavailable: {source_record_id}")
            (record_id, family, role, revision, locator, payload_ref, material_json) = row
            if role in {"robots", "sitemap"}:
                continue
            sequence += 1
            representation_ids = member.get("representation_artifact_ids") or []
            if representation_ids:
                representation = json.loads(_artifact(report_path.parent, representation_ids[0]).decode("utf-8"))
                pages = representation.get("representation", {}).get("pages", [])
                content = "\n".join(f"Page {page.get('page')}:\n{page.get('text','')}" for page in pages)
                content_kind = "derived_pdf_text"
            else:
                raw = _artifact(report_path.parent, payload_ref)
                media = (json.loads(material_json).get("media_type") if material_json else "") or ""
                if "html" in media or raw.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    content = visible_html(raw.decode("utf-8", "replace")); content_kind = "visible_html"
                elif "json" in media or raw.lstrip().startswith((b"{", b"[")):
                    try: content = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
                    except json.JSONDecodeError: content = raw.decode("utf-8", "replace")
                    content_kind = "structured_json"
                else:
                    content = raw.decode("utf-8", "replace"); content_kind = "text"
            line_values = _lines(content)
            locators = [{"locator": f"[S{sequence:03d}:L{index:04d}]", "text": line} for index, line in enumerate(line_values, 1)]
            sources.append({"source_record_id": record_id, "source_family": family, "source_role": role, "source_locator": locator, "source_revision": revision, "effective_period": member.get("effective_period"), "binding_context": member.get("binding_context"), "representation_readiness": member.get("representation_readiness"), "representation_gaps": member.get("representation_gaps", []), "content_kind": content_kind, "locators": locators})
    db.close()
    packet = {"packet_version": "whole-card-semantic-calibration-v0.1", "subject": {"name": "The Fred Hollows Foundation", "abn": "46070556642", "subject_id": fred["subject_id"]}, "corpus_id": next(item["corpus_id"] for item in report["corpora"] if item["subject_id"] == fred["subject_id"]), "material_identity_hash": next(item["material_identity_hash"] for item in report["corpora"] if item["subject_id"] == fred["subject_id"]), "sources": sources}
    return packet


def _estimate(packet_bytes: bytes, prompt: str) -> tuple[int, Any]:
    tokens = (len(packet_bytes) + len(prompt.encode("utf-8"))) // 4
    # Each call has one permitted transport retry; price each model separately.
    projected = {model: (2 * (tokens * MODEL_PRICES[model][0] + MAX_TOKENS * MODEL_PRICES[model][1])) / 1_000_000 for model in MODEL_NAMES}
    return tokens, projected


def run(output_root: Path | None = None) -> int:
    packet = build_packet()
    prompt = _prompt()
    packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    estimated_tokens, projected_usd = _estimate(packet_bytes, prompt)
    if estimated_tokens > 200_000:
        raise RuntimeError(f"packet exceeds 200000 estimated input tokens: {estimated_tokens}")
    if sum(projected_usd.values()) > SPEND_CAP_USD:
        raise RuntimeError(f"projected experiment spend exceeds USD {SPEND_CAP_USD:.2f}: {sum(projected_usd.values()):.6f}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = output_root or Path(r"C:\CharityGraph-runtime") / f"whole-card-calibration-v01-{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    (root / "packet.json").write_bytes(packet_bytes)
    (root / "packet.sha256").write_text(hashlib.sha256(packet_bytes).hexdigest() + "\n", encoding="ascii")
    (root / "prompt.txt").write_text(prompt, encoding="utf-8")
    (root / "packet-manifest.json").write_text(json.dumps({"packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "corpus_id": packet["corpus_id"], "material_identity_hash": packet["material_identity_hash"], "ordered_source_record_ids": [s["source_record_id"] for s in packet["sources"]], "estimated_input_tokens": estimated_tokens, "per_source": [{"source_record_id": s["source_record_id"], "line_count": len(s["locators"]), "estimated_tokens": sum(len(x["text"]) for x in s["locators"]) // 4} for s in packet["sources"]]}, indent=2) + "\n", encoding="utf-8")
    input_text = prompt + "\n\nFROZEN PACKET BYTES:\n" + packet_bytes.decode("utf-8")
    results: list[dict[str, Any]] = []
    for model in MODEL_NAMES:
        row: dict[str, Any] = {"model": model, "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "projected_exposure_usd": projected_usd[model]}
        try:
            response = responses_create(model=model, input_text=input_text, text_format={"type": "json_schema", "name": "whole_card_extraction_v01", "strict": True, "schema": STRICT_SCHEMA}, max_output_tokens=MAX_TOKENS, max_attempts=2, reasoning={"effort": "high"})
            row.update({"response_id": response.response_id, "transport_requests": response.transport_requests, "usage": response.usage.__dict__, "cost_usd": str(estimate_response_cost(model, response.usage) or 0), "raw_output": response.output_text})
            try:
                parsed = json.loads(response.output_text); row["json_valid"] = True; row["parsed_output"] = parsed
            except Exception as exc:
                row.update({"json_valid": False, "valid": False, "validation_error": type(exc).__name__, "validation_error_detail": str(exc)[:240]})
            if row.get("json_valid"):
                try:
                    validated = validate_output(row["parsed_output"], packet); row.update({"valid": True, "output": validated.model_dump(mode="json")})
                except Exception as exc:
                    row.update({"valid": False, "validation_error": type(exc).__name__, "validation_error_detail": str(exc)[:240]})
        except Exception as exc:
            row.update({"valid": False, "error": type(exc).__name__, "error_detail": str(exc)[:240], "transport_requests": getattr(exc, "attempts_made", 0), "cost_usd": "0"})
        (root / f"{model}-raw.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(row)
    labels = ["A", "B"]; secrets.SystemRandom().shuffle(labels)
    mapping = {labels[i]: results[i]["model"] for i in range(2)}
    for label, row in zip(labels, results):
        (root / f"blinded_{label}.json").write_text(json.dumps({"output": row.get("parsed_output", row.get("output", {})), "validation": {"json_valid": row.get("json_valid", False), "valid": row.get("valid", False), "error": row.get("validation_error"), "error_detail": row.get("validation_error_detail")}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "model_mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    comparison = {"packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "models": [{"valid": r.get("valid", False), "observation_count": len(r.get("parsed_output", {}).get("observations", [])), "section_statuses": [x.get("status") for x in r.get("parsed_output", {}).get("section_assessments", [])], "provider_calls": 1 if r.get("response_id") else 0, "transport_requests": r.get("transport_requests", 0), "usage": r.get("usage"), "cost_usd": r.get("cost_usd", "0")} for r in results]}
    (root / "structural-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"root": str(root), "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "estimated_input_tokens": estimated_tokens, "projected_exposure_usd": projected_usd, "models": [{"model": r["model"], "valid": r.get("valid", False), "cost_usd": r.get("cost_usd", "0"), "transport_requests": r.get("transport_requests", 0)} for r in results]}, indent=2))
    return 0


if __name__ == "__main__":
    run()
