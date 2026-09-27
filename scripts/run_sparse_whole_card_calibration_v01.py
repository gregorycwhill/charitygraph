"""Private Luna-vs-Terra sparse-card calibration experiment (no acquisition)."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from charitygraph.openai_client import estimate_response_cost, responses_create  # noqa: E402
from charitygraph.whole_card_calibration import STRICT_SCHEMA, WholeCardExtractionOutput, locator_resolves, visible_html  # noqa: E402

REPORT = Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-final-correction2-20260830\baseline-corpus-v1-report.json")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
PROMPT_FILE = ROOT / "scripts" / "whole_card_semantic_calibration_v01_prompt.txt"
MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")
PRICES = {"gpt-5.6-luna": (0.20, 1.20), "gpt-5.6-terra": (2.00, 12.00)}
MAX_OUTPUT_TOKENS = 24_000
SPEND_CAP_USD = 3.00
ABNS = {"28000030179": "The Smith Family", "50169561394": "Australian Red Cross Society", "20077830347": "Australian Communities Foundation", "22007498482": "Australian Conservation Foundation", "15000002522": "Mission Australia", "28004778081": "World Vision Australia"}
_ARTIFACT_ROOTS: list[Path] | None = None


def artifact(report_root: Path, artifact_id: str) -> bytes:
    global _ARTIFACT_ROOTS
    digest = artifact_id.split(":", 1)[1]
    if _ARTIFACT_ROOTS is None:
        runtime = Path(r"C:\CharityGraph-runtime")
        _ARTIFACT_ROOTS = [report_root / "objects" / "objects" / "sha256"] + [child / "objects" / "objects" / "sha256" for child in runtime.iterdir() if (child / "objects" / "objects" / "sha256").is_dir()]
    for root in _ARTIFACT_ROOTS:
        path = root / digest[:2] / digest
        if path.is_file(): return path.read_bytes()
    raise FileNotFoundError(artifact_id)


def lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines() or [""]


def program_count(value: object) -> int:
    if isinstance(value, dict):
        return sum((len(v) if isinstance(v, list) and k.casefold() in {"programs", "program_records", "programs_services"} else 0) + program_count(v) for k, v in value.items())
    if isinstance(value, list): return sum(program_count(item) for item in value)
    return 0


def material_content(report_root: Path, payload_ref: str, material_json: str | None, representation_ids: list[str]) -> tuple[str, str, int, int, int]:
    if representation_ids:
        value = json.loads(artifact(report_root, representation_ids[0]).decode("utf-8")); pages = value.get("representation", {}).get("pages", [])
        text = "\n".join(f"Page {p.get('page')}:\n{p.get('text', '')}" for p in pages)
        return text, "derived_pdf_text", len(pages), len(text), 0
    raw = artifact(report_root, payload_ref); media = (json.loads(material_json).get("media_type") if material_json else "") or ""
    if "html" in media or raw.lstrip().lower().startswith((b"<!doctype html", b"<html")): return visible_html(raw.decode("utf-8", "replace")), "visible_html", 0, 0, 0
    if "json" in media or raw.lstrip().startswith((b"{", b"[")):
        try: value = json.loads(raw); return json.dumps(value, ensure_ascii=False, indent=2), "structured_json", 0, 0, program_count(value)
        except json.JSONDecodeError: return raw.decode("utf-8", "replace"), "text", 0, 0, 0
    return raw.decode("utf-8", "replace"), "text", 0, 0, 0


def build_packet(subject: dict[str, Any], corpus: dict[str, Any], report_root: Path, db: sqlite3.Connection) -> tuple[dict[str, Any], dict[str, Any]]:
    sources: list[dict[str, Any]] = []; composition: Counter[str] = Counter(); pdf_pages = pdf_chars = native_programs = 0; gaps: list[str] = []; seq = 0
    for member in corpus["material_members"]:
        for rid in member["source_record_ids"]:
            row = db.execute("select source_record_id,source_family,source_role,source_version,source_locator,payload_ref,material_json from source_records where source_record_id=?", (rid,)).fetchone()
            if row is None: raise RuntimeError(f"source record unavailable: {rid}")
            record_id, family, role, revision, locator, payload_ref, material_json = row
            if role in {"robots", "sitemap"}: continue
            seq += 1; text, kind, pages, chars, programs = material_content(report_root, payload_ref, material_json, member.get("representation_artifact_ids") or [])
            locs = [{"locator": f"[S{seq:03d}:L{i:04d}]", "text": value} for i, value in enumerate(lines(text), 1)]
            sources.append({"source_record_id": record_id, "source_family": family, "source_role": role, "source_locator": locator, "source_revision": revision, "effective_period": member.get("effective_period"), "binding_context": member.get("binding_context"), "representation_readiness": member.get("representation_readiness"), "representation_gaps": member.get("representation_gaps", []), "content_kind": kind, "locators": locs})
            composition[f"{family}/{role}"] += 1; pdf_pages += pages; pdf_chars += chars; native_programs += programs; gaps.extend(member.get("representation_gaps", []))
    packet = {"packet_version": "whole-card-semantic-calibration-v0.1", "subject": {"name": subject["registered_name"], "abn": subject["abn"], "subject_id": subject["subject_id"]}, "corpus_id": corpus["corpus_id"], "material_identity_hash": corpus["material_identity_hash"], "sources": sources}
    coverage = subject["coverage"]; valid = all(coverage[k].get("acquisition") == "available" and coverage[k].get("binding") == "bound" for k in ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr")) and not any(v.get("acquisition") == "failed" for v in coverage.values()) and not coverage["acnc_ais_bundle"].get("reporting_group_error")
    metrics = {"abn": subject["abn"], "registered_name": subject["registered_name"], "subject_id": subject["subject_id"], "acquisition_valid": valid, "packet_bytes": 0, "estimated_input_tokens": 0, "substantive_source_records": len(sources), "source_family_role_composition": dict(sorted(composition.items())), "derived_pdf_text_pages": pdf_pages, "derived_pdf_text_characters": pdf_chars, "source_native_acnc_programs": native_programs, "official_site_substantive_members": sum(1 for m in corpus["material_members"] if m["source_family"] == "official_website" and any(r not in {"robots", "sitemap"} for r in [next((db.execute("select source_role from source_records where source_record_id=?", (x,)).fetchone() or [None])[0] for x in m["source_record_ids"])])), "wikipedia_substantive_member": any(m["source_family"] == "wikipedia_wikimedia" and any(db.execute("select source_role from source_records where source_record_id=?", (x,)).fetchone()[0] not in {"robots", "sitemap"} for x in m["source_record_ids"]) for m in corpus["material_members"]), "reporting_group_binding_contexts": [m.get("binding_context") for m in corpus["material_members"] if m.get("binding_context")], "representation_gaps": sorted(set(gaps)), "coverage": coverage}
    return packet, metrics


def prompt_bytes() -> bytes:
    data = PROMPT_FILE.read_bytes(); return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def projected_exposure(packet_bytes: bytes, prompt: bytes) -> dict[str, float]:
    tokens = (len(packet_bytes) + len(prompt)) // 4
    return {model: (2 * (tokens * PRICES[model][0] + MAX_OUTPUT_TOKENS * PRICES[model][1])) / 1_000_000 for model in MODELS}


def balanced(text: str, start: int) -> int | None:
    depth = 0; quoted = False; escaped = False
    for i in range(start, len(text)):
        c = text[i]
        if quoted:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c == "{": depth += 1
        elif c == "}" and (depth := depth - 1) == 0: return i + 1
    return None


def complete_observations(text: str) -> list[dict[str, Any]]:
    marker = text.find('"observations"'); opening = text.find("[", marker); pos = opening + 1; rows = []
    while opening >= 0 and pos < len(text):
        while pos < len(text) and text[pos].isspace(): pos += 1
        if pos >= len(text) or text[pos] == "]": break
        if text[pos] != "{": break
        end = balanced(text, pos)
        if end is None: break
        try: rows.append(json.loads(text[pos:end]))
        except json.JSONDecodeError: break
        pos = end
        while pos < len(text) and text[pos].isspace(): pos += 1
        if pos < len(text) and text[pos] == ",": pos += 1
    return rows


def validate_result(parsed: object, packet: dict[str, Any], parse_error: str | None) -> dict[str, Any]:
    schema_ok = parse_error is None and isinstance(parsed, dict) and set(parsed) == {"section_assessments", "observations"}
    cross_ok = False; cross_error = None
    if schema_ok:
        try: WholeCardExtractionOutput.model_validate(parsed); cross_ok = len(parsed["section_assessments"]) == 20 and {x["section_id"] for x in parsed["section_assessments"]} == set(range(1, 21))
        except Exception as exc: cross_error = str(exc)[:500]
    source_map = {s["source_record_id"]: s for s in packet["sources"]}; invalid = []; excerpts = []
    for oi, obs in enumerate(parsed.get("observations", []) if isinstance(parsed, dict) else []):
        for ev in obs.get("evidence", []):
            src = source_map.get(ev.get("source_record_id")); locs = {x["locator"] for x in src["locators"]} if src else set(); locator_ok = bool(src and locator_resolves(ev.get("packet_locator", ""), locs)); excerpt = ev.get("excerpt"); excerpt_ok = excerpt is None or locator_ok
            row = {"observation_index": oi, "section_id": obs.get("section_id"), "proposition": obs.get("proposition"), "source_record_id": ev.get("source_record_id"), "packet_locator": ev.get("packet_locator"), "locator_valid": locator_ok, "excerpt_verbatim_after_normalisation": excerpt_ok}; excerpts.append(row)
            if not locator_ok: row["failure_reason"] = "source record or locator does not resolve"; invalid.append(row)
    partial = complete_observations(json.dumps(parsed, separators=(",", ":")) if isinstance(parsed, dict) else "") if parse_error is None else []
    return {"json_schema_valid": schema_ok, "json_schema_error": parse_error, "twenty_section_cross_field_valid": cross_ok, "cross_field_error": cross_error, "citation_source_record_valid": not any(not x["locator_valid"] for x in excerpts), "exact_excerpt_valid": not any(not x["excerpt_verbatim_after_normalisation"] for x in excerpts), "invalid_evidence_references": invalid, "excerpt_checks": excerpts, "truncation": {"truncated": parse_error is not None, "complete_observation_count": len(partial)}}


def run_model(model: str, packet: dict[str, Any], packet_bytes: bytes, prompt: bytes, out: Path, prefix: str) -> dict[str, Any]:
    started = time.perf_counter(); result = None; failure = None
    try: result = responses_create(model=model, input_text=prompt.decode() + "\n\nFROZEN PACKET BYTES:\n" + packet_bytes.decode(), text_format={"type": "json_schema", "name": "whole_card_extraction_v01", "strict": True, "schema": STRICT_SCHEMA}, max_output_tokens=MAX_OUTPUT_TOKENS, max_attempts=2, timeout_seconds=300, reasoning={"effort": "high"})
    except Exception as exc: failure = {"error_class": type(exc).__name__, "error_detail": str(exc)[:240], "transport_attempts": getattr(exc, "attempts_made", 0)}
    latency = round((time.perf_counter() - started) * 1000, 3); raw = result.output_text if result else ""; parsed = None; parse_error = None
    row = {"model": model, "packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "prompt_sha256": hashlib.sha256(prompt).hexdigest(), "max_output_tokens": MAX_OUTPUT_TOKENS, "timeout_seconds": 300, "max_attempts": 2, "reasoning": {"effort": "high"}, "latency_ms": latency}
    if result is not None:
        row.update({"response_id": result.response_id, "transport_attempts": result.transport_requests, "usage": result.usage.__dict__, "cost_usd": str(estimate_response_cost(model, result.usage) or 0), "raw_output": raw})
        try: parsed = json.loads(raw)
        except Exception as exc: parse_error = f"{type(exc).__name__}: {exc}"
    else: row.update({"cost_usd": "0", **(failure or {})})
    row["diagnostics"] = validate_result(parsed, packet, parse_error)
    if parsed is not None: (out / f"{prefix}-{model}-returned-output.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / f"{prefix}-{model}-raw.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return row


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8")); report_root = REPORT.parent; db = sqlite3.connect(CATALOG); prompt = prompt_bytes(); candidates = []
    for subject in report["subjects"]:
        if subject["abn"] not in ABNS: continue
        corpus = next(c for c in report["corpora"] if c["subject_id"] == subject["subject_id"]); packet, metrics = build_packet(subject, corpus, report_root, db); packet_bytes = (json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(); metrics.update({"packet_bytes": len(packet_bytes), "estimated_input_tokens": (len(packet_bytes) + len(prompt)) // 4}); candidates.append({"subject": subject, "corpus": corpus, "packet": packet, "packet_bytes": packet_bytes, "metrics": metrics})
    db.close(); ranking = sorted(candidates, key=lambda x: (not x["metrics"]["acquisition_valid"], x["metrics"]["estimated_input_tokens"], x["metrics"]["abn"])); selected = [x for x in ranking if x["metrics"]["acquisition_valid"]][:2]
    exposure = {item["metrics"]["abn"]: projected_exposure(item["packet_bytes"], prompt) for item in selected}; total_projected = sum(sum(v.values()) for v in exposure.values())
    if len(selected) != 2: raise RuntimeError("fewer than two acquisition-valid sparse candidates")
    if total_projected > SPEND_CAP_USD: raise RuntimeError(f"projected four-call exposure USD {total_projected:.6f} exceeds cap")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); out = Path(r"C:\CharityGraph-runtime") / f"sparse-whole-card-calibration-v01-{stamp}"; out.mkdir(parents=True)
    (out / "candidate-ranking.json").write_text(json.dumps({"candidates": [x["metrics"] for x in ranking], "selected_abns": [x["metrics"]["abn"] for x in selected], "projected_exposure_usd": exposure, "total_projected_exposure_usd": total_projected}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for item in selected:
        abn = item["metrics"]["abn"]; (out / f"{abn}-packet.json").write_bytes(item["packet_bytes"]); (out / f"{abn}-packet.sha256").write_text(hashlib.sha256(item["packet_bytes"]).hexdigest() + "\n", encoding="ascii"); (out / f"{abn}-prompt.txt").write_bytes(prompt); (out / f"{abn}-packet-manifest.json").write_text(json.dumps({"packet_sha256": hashlib.sha256(item["packet_bytes"]).hexdigest(), "prompt_sha256": hashlib.sha256(prompt).hexdigest(), "schema_sha256": hashlib.sha256(json.dumps(STRICT_SCHEMA, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "corpus_id": item["corpus"]["corpus_id"], "material_identity_hash": item["corpus"]["material_identity_hash"]}, indent=2) + "\n", encoding="utf-8"); results = [run_model(model, item["packet"], item["packet_bytes"], prompt, out, abn) for model in MODELS]; labels = ["A", "B"]; secrets.SystemRandom().shuffle(labels); mapping = {labels[i]: results[i]["model"] for i in range(2)}; (out / f"{abn}-model-mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8"); blinded = []
        for label, result in zip(labels, results):
            payload = {"output": json.loads(result["raw_output"]) if result.get("raw_output") and result["diagnostics"]["json_schema_valid"] else None, "validation": result["diagnostics"]}; path = out / f"{abn}-blinded-{label}.json"; path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); blinded.append(str(path))
        rows.append({"abn": abn, "models": [{"model": r["model"], "json_schema_valid": r["diagnostics"]["json_schema_valid"], "observation_count": len(json.loads(r["raw_output"]).get("observations", [])) if r.get("raw_output") and r["diagnostics"]["json_schema_valid"] else r["diagnostics"]["truncation"]["complete_observation_count"], "input_tokens": (r.get("usage") or {}).get("input_tokens"), "output_tokens": (r.get("usage") or {}).get("output_tokens"), "latency_ms": r["latency_ms"], "cost_usd": r["cost_usd"], "citation_failures": len(r["diagnostics"]["invalid_evidence_references"]), "excerpt_failures": sum(not x["excerpt_verbatim_after_normalisation"] for x in r["diagnostics"]["excerpt_checks"]), "truncated": r["diagnostics"]["truncation"]["truncated"]} for r in results], "blinded_outputs": blinded})
    fred_terra = json.loads((Path(r"C:\CharityGraph-runtime\whole-card-calibration-v01-20260830T024044Z") / "gpt-5.6-terra-raw.json").read_text(encoding="utf-8")); fred_luna = json.loads((Path(r"C:\CharityGraph-runtime\whole-card-calibration-v01-luna-retry-20260830T") / "luna-raw.json").read_text(encoding="utf-8")); cross = [{"case": "Fred Hollows Terra v0.1", "packet_input_tokens": fred_terra.get("usage", {}).get("input_tokens"), "output_tokens": fred_terra.get("usage", {}).get("output_tokens"), "observation_count": 36}, {"case": "Fred Hollows Luna v0.1 retry", "packet_input_tokens": fred_luna.get("usage", {}).get("input_tokens"), "output_tokens": fred_luna.get("usage", {}).get("output_tokens"), "observation_count": 63}]
    for row in rows:
        cross.extend({"case": f"{row['abn']} {m['model']}", "packet_input_tokens": m["input_tokens"], "output_tokens": m["output_tokens"], "observation_count": m["observation_count"]} for m in row["models"])
    (out / "per-charity-structural-comparisons.json").write_text(json.dumps(rows, indent=2) + "\n"); (out / "fred-plus-sparse-structural-comparison.json").write_text(json.dumps(cross, indent=2) + "\n"); print(json.dumps({"output_root": str(out), "selected": [x["metrics"] for x in selected], "projected_exposure_usd": exposure, "total_projected_exposure_usd": total_projected, "comparisons": rows}, indent=2))


if __name__ == "__main__": main()
