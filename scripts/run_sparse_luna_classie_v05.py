"""Bounded sparse-charity Luna knowledge + private CLASSIE experiment.

The runner keeps all acquired material, prompts, taxonomy and model responses in
the private runtime.  Only generic mechanics belong in Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

from charitygraph.baseline_corpus import (
    BindingState, CorpusMember, DiscoveryState, AcquisitionState, MaterialOrigin,
    RepresentationReadiness, build_corpus_manifest, enumerate_site_candidates,
    extract_pfra_members, normalise_host, resolve_wikipedia_candidate,
    select_filing_documents, sha256_json,
)
from charitygraph.contracts import ArtifactRef, ExternalIdentifier, SchemaRef, SubjectRecord
from charitygraph.contracts.ids import new_opaque_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.openai_client import responses_create, estimate_response_cost
from charitygraph.runtime import SQLiteCatalog
from charitygraph.whole_card_semantic_v02 import STRICT_SCHEMA, WholeCardExtractionOutputV02, validate_output
from charitygraph.whole_card_calibration import visible_html
from charitygraph.baseline_corpus import represent_pdf

# Imported private baseline helpers intentionally: they already implement the
# governed source registry, HTTP and ACNC filing mechanics.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_baseline_charity_corpus_v1 import (
    API, PFRA_AGENCY, PFRA_CHARITY, WIKI, acnc_fetch, fetch, fetch_website_homepage,
    source_lineage, _member_from_lineage,
)

RANKING = Path(r"C:\Users\grego\OneDrive\Documents\GitHub\CharityGraph\charitygraph-data\rankings\acnc-2024-ais-donation-ranking-top10000.json")
MODEL = "gpt-5.6-luna"
CAP_USD = Decimal("0.50")
IN_PRICE = Decimal("0.20")
OUT_PRICE = Decimal("1.20")
WHOLE_MAX = 24000
CLASSIE_MAX = 12000


def now() -> datetime:
    return datetime.now(timezone.utc)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value: Any) -> str:
    data = json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    path.write_bytes(data)
    return sha_bytes(data)


def estimated_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // 4)


def projected_cost(input_text: str, output_tokens: int) -> Decimal:
    # At most two transport attempts can consume the configured output ceiling.
    return ((Decimal(estimated_tokens(input_text)) * IN_PRICE) +
            (Decimal(output_tokens * 2) * OUT_PRICE)) / Decimal(1_000_000)


def call_luna(input_text: str, schema: dict[str, Any], name: str, max_output: int,
              spent: Decimal, events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, Decimal, str]:
    projected = projected_cost(input_text, max_output)
    if spent + projected > CAP_USD:
        raise RuntimeError(f"provider cap would be exceeded before {name}: {spent + projected:.6f} > {CAP_USD}")
    started = now()
    result = responses_create(
        model=MODEL, input_text=input_text,
        text_format={"type": "json_schema", "name": name, "strict": True, "schema": schema},
        max_output_tokens=max_output, max_attempts=2, timeout_seconds=300,
        reasoning={"effort": "high"},
    )
    usage = result.usage.__dict__
    actual = estimate_response_cost(result.model, result.usage) or Decimal("0")
    event = {"phase": name, "model": result.model, "projected_max_usd": f"{projected:.6f}",
             "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
             "transport_requests": result.transport_requests, "actual_cost_usd": f"{actual:.6f}",
             "latency_seconds": (now() - started).total_seconds(), "status": result.status}
    events.append(event)
    return json.loads(result.output_text), actual, result.output_text


def build_taxonomy_blind_view(value: dict[str, Any]) -> dict[str, Any]:
    """Remove classification material without rewriting retained observations."""
    blind = dict(value)
    blind["assignments"] = []
    blind["observations"] = [o for o in value.get("observations", []) if o.get("section_id") != 19]
    blind["observation_refs"] = {f"O{i:03d}": o for i, o in enumerate(blind["observations"], 1)}
    return blind


def register_subject(catalog: SQLiteCatalog, abn: str, name: str, source_record_id: str) -> tuple[str, bool]:
    with catalog._connection() as conn:
        row = conn.execute("SELECT subject_id FROM external_identifiers WHERE scheme='ABN' AND identifier_value=? AND issuing_authority='Australian Business Register' AND status='active'", (abn,)).fetchone()
    if row:
        return str(row[0]), False
    subject_id = new_opaque_id("subject:")
    subject_record_id = new_opaque_id("subjectrecord:")
    source = catalog.get_source_record(source_record_id) or {}
    ref = ArtifactRef(
        artifact_id=source_record_id,
        content_hash=source.get("payload_hash") or "0" * 64,
        schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0"),
    )
    subject = SubjectRecord(
        record_id=subject_record_id, created_at=now(), producer={"kind": "code", "producer_id": "sparse-luna-classie-v05", "version": "0.1"},
        subject_id=subject_id, subject_kind="unknown", lifecycle_status="active", display_name=name,
        external_identifiers=(ExternalIdentifier(scheme="ABN", value=abn, issuing_authority="Australian Business Register", source_record_ids=(source_record_id,)),),
        identity_authority_refs=(ref,), identity_policy_id="acnc-registered-charity-bootstrap-v1",
    )
    catalog.register_subject(subject)
    return subject_id, True


def text_for(body: bytes, media: str) -> str:
    if media in {"application/json", "text/html", "text/plain", "application/xml", "text/xml"}:
        raw = body.decode("utf-8", "replace")
        if media == "text/html":
            raw = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
            raw = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", raw).strip()
    return "[binary source material; native representation recorded separately]"


def source_packet(catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, members: list[CorpusMember], diagnostics_out: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = []
    for idx, member in enumerate(members, 1):
        if not member.artifact_ids or not member.source_record_ids:
            continue
        artifact_id = member.artifact_ids[0]
        try:
            body = store.read(artifact_id)
        except Exception:
            continue
        rec = catalog.get_source_record(member.source_record_ids[0]) or {}
        media = rec.get("media_type") or "text/plain"
        representation_type = "text"
        representation_gap = None
        derived_artifact_id = None
        if member.representation_artifact_ids:
            try:
                rep = json.loads(store.read(member.representation_artifact_ids[0]).decode("utf-8"))
                pages = rep.get("representation", {}).get("pages", [])
                material = "\n".join(f"Page {p.get('page')}:\n{p.get('text', '')}" for p in pages)
                representation_type = "derived_pdf_native"
            except Exception:
                material = ""; representation_gap = "derived_representation_unavailable"
        elif "pdf" in media or body.startswith(b"%PDF-"):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
                handle.write(body); pdf_path = Path(handle.name)
            try:
                rep = represent_pdf(pdf_path)
                rep_bytes = json.dumps({"representation": rep}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                derived = store.put_derived(rep_bytes, input_artifact_ids=(artifact_id,), created_at=now())
                derived_artifact_id = derived.artifact_id
                material = "\n".join(f"Page {p.get('page')}:\n{p.get('text', '')}" for p in rep.get("pages", []))
                representation_type = "derived_pdf_native"
                gaps = rep.get("page_gaps") or []
                representation_gap = (";".join(f"{k}:{v}" for k, v in rep.get("gap_reasons", {}).items() if v) or None)
            except Exception as exc:
                material = ""; representation_type = "pdf_placeholder"; representation_gap = f"native_pdf_representation_failed:{type(exc).__name__}"
            finally:
                pdf_path.unlink(missing_ok=True)
        elif "json" in media or body.lstrip().startswith((b"{", b"[")):
            try:
                material = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
                representation_type = "structured_json"
            except json.JSONDecodeError:
                material = body.decode("utf-8", "replace"); representation_type = "text"
        elif "html" in media or body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            material = visible_html(body.decode("utf-8", "replace")); representation_type = "visible_html"
        else:
            material = body.decode("utf-8", "replace")
        complete = representation_gap is None
        bounded = len(material) <= 120000
        if not bounded:
            material = material[:120000]; representation_gap = representation_gap or "representation_bounded_to_120000_chars"; complete = False
        diagnostics = {"source_key": f"S{idx:03d}", "source_record_id": member.source_record_ids[0], "media_type": media, "acquired_bytes": len(body), "representation_type": representation_type, "represented_characters": len(material), "estimated_tokens": estimated_tokens(material), "locator_count": len(material.splitlines() or [""]), "complete": complete, "bounded": bounded, "placeholder": representation_type.endswith("placeholder"), "representation_gap": representation_gap, "derived_artifact_id": derived_artifact_id}
        if diagnostics_out is not None: diagnostics_out.append(diagnostics)
        lines = material.splitlines() or [material]
        locators = []
        for line_no, line in enumerate(lines, 1):
            locators.append({"locator": f"L{line_no:04d}", "text": line})
        sources.append({"source_key": f"S{idx:03d}", "source_record_id": member.source_record_ids[0],
                        "source_family": member.source_family, "source_role": rec.get("source_role"),
                        "source_locator": rec.get("source_locator"), "locators": locators})
    return {"sources": sources}


def build_classie_schema() -> dict[str, Any]:
    scope = {"type": "object", "additionalProperties": False,
             "properties": {"kind": {"type": "string"}, "label": {"type": ["string", "null"]}},
             "required": ["kind", "label"]}
    target = {"type": "object", "additionalProperties": False,
              "properties": {"kind": {"type": "string"}, "label": {"type": ["string", "null"]}},
              "required": ["kind", "label"]}
    assessment = {"type": "object", "additionalProperties": False,
                  "properties": {"target_scope": target, "status": {"type": "string", "enum": ["assignments_found", "no_supported_assignment", "insufficient_evidence"]}, "note": {"type": ["string", "null"]}},
                  "required": ["target_scope", "status", "note"]}
    evidence = {"type": "object", "additionalProperties": False,
                "properties": {"observation_ref": {"type": "string", "pattern": "^O[0-9]{3,}$"}, "role": {"type": "string", "enum": ["supporting", "corroborating", "context"]}},
                "required": ["observation_ref", "role"]}
    assignment = {"type": "object", "additionalProperties": False,
                  "properties": {"target_scope": target, "concept_id": {"type": "string"}, "supporting_observations": {"type": "array", "items": evidence}, "rationale": {"type": "string"}, "qualifications": {"type": "array", "items": {"type": "string"}}},
                  "required": ["target_scope", "concept_id", "supporting_observations", "rationale", "qualifications"]}
    return {"type": "object", "additionalProperties": False,
            "properties": {"target_assessments": {"type": "array", "items": assessment}, "assignments": {"type": "array", "items": assignment}},
            "required": ["target_assessments", "assignments"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\sparse-luna-classie-v05-20260830T"))
    args = parser.parse_args()
    runtime = args.runtime.resolve(); runtime.mkdir(parents=True, exist_ok=True)
    catalog = SQLiteCatalog(Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,), catalog=catalog)
    ranking = json.loads(RANKING.read_text(encoding="utf-8"))
    inspected = ranking["records"][2000:2010]
    chosen = inspected[0]  # first clear sparse-footprint fit in the bounded inspection
    abn = chosen["abn"]
    selection = {"inspected": inspected, "selected": {**chosen, "selection_reason": "registered operating charity; recent submitted AIS; source-native ACNC activity summary; only a support-page website; no exact Wikipedia title; not Basic Religious Charity"}}
    dump(runtime / "candidate-selection.json", selection)

    # ACNC register first, then register the new opaque governed subject.
    register_url, register_body, register_resolved, entity = acnc_fetch(abn)
    reg_lineage = source_lineage(catalog, store, family="acnc_register", endpoint=f"{API}/entity", url=register_url, body=register_body, resolved=register_resolved, media="application/json", role="register_identity")
    subject_id, newly_created = register_subject(catalog, abn, entity.get("data", {}).get("Name") or chosen["charity_name"], reg_lineage["source_record_id"])
    members = [_member_from_lineage(reg_lineage, family="acnc_register")]
    coverage: dict[str, Any] = {"acnc_register": {"state": "source_acquired", "binding": "bound"}}
    data = entity.get("data", {})

    # Latest submitted AIS plus same-period attached documents.
    reports = [r for r in data.get("AnnualReports", []) if r.get("IsAIS") and r.get("Status") == "Submitted" and r.get("AISId")]
    latest = max(reports, key=lambda r: (int(r.get("Year") or 0), r.get("DateReceived") or ""), default=None)
    filing_count = 0
    if latest:
        ais_url = f"{API}/entity/{latest['AISId']}"; body, resolved, _, media = fetch(ais_url)
        line = source_lineage(catalog, store, family="acnc_ais_bundle", endpoint=f"{API}/entity/{{AISId}}", url=ais_url, body=body, resolved=resolved, media=media, role="annual_information_statement", revision=str(latest["Year"]))
        members.append(_member_from_lineage(line, family="acnc_ais_bundle", revision=str(latest["Year"]), period=str(latest["Year"]))); filing_count += 1
        for doc in select_filing_documents(data.get("Documents") or [], str(latest["Year"])):
            try:
                db, dr, _, dm = fetch(str(doc["Url"]))
                dl = source_lineage(catalog, store, family="acnc_ais_bundle", endpoint=f"{API}/filing-documents", url=str(doc["Url"]), body=db, resolved=dr, media=dm, role=str(doc.get("role") or "attached_document"), revision=str(latest["Year"]))
                members.append(_member_from_lineage(dl, family="acnc_ais_bundle", revision=str(latest["Year"]), period=str(latest["Year"]))); filing_count += 1
            except Exception:
                continue
    coverage["acnc_ais_bundle"] = {"state": "source_acquired" if latest else "source_absent", "period": latest.get("Year") if latest else None, "member_count": filing_count}

    # ABR/ATO source is retained; structured DGR interpretation remains deferred.
    abr_url = f"https://abr.business.gov.au/ABN/View?id={abn}"
    try:
        body, resolved, _, media = fetch(abr_url); line = source_lineage(catalog, store, family="abr_dgr", endpoint="https://abr.business.gov.au/", url=abr_url, body=body, resolved=resolved, media=media, role="abr_entity")
        members.append(_member_from_lineage(line, family="abr_dgr")); coverage["abr_dgr"] = {"state": "source_acquired", "dgr_extraction": "deferred"}
    except Exception as exc:
        coverage["abr_dgr"] = {"state": "inaccessible_through_supported_acquisition", "error": type(exc).__name__}

    # Official website: homepage and mechanical navigation/sitemap evidence only.
    website = data.get("Website")
    if website:
        base = website if str(website).startswith("http") else "https://" + str(website)
        try:
            hb, hr, _, hm, attempts = fetch_website_homepage(base)
            hl = source_lineage(catalog, store, family="official_website", endpoint=base, url=base, body=hb, resolved=hr, media=hm, role="official_homepage")
            members.append(_member_from_lineage(hl, family="official_website"))
            nav = enumerate_site_candidates(hb.decode("utf-8", "replace"), hr)
            coverage["official_website"] = {"state": "source_acquired", "homepage": True, "candidate_count": len(nav), "ranking": "not_attempted_sparse_experiment", "transport_attempts": attempts}
        except Exception as exc:
            coverage["official_website"] = {"state": "inaccessible_through_supported_acquisition", "error": type(exc).__name__}
    else:
        coverage["official_website"] = {"state": "source_absent"}

    # Wikipedia exact source-native title path only; no model identity call in this two-call experiment.
    names = [str(data.get("Name") or chosen["charity_name"])] + [str(x) for x in (data.get("OtherNames") or []) if x]
    wiki_report: dict[str, Any]
    try:
        q = WIKI + "?" + urlencode({"action": "query", "list": "search", "srsearch": names[0], "srlimit": 10, "format": "json", "formatversion": "2"})
        wb, wr, _, _ = fetch(q); rows = (json.loads(wb).get("query") or {}).get("search") or []
        resolution = resolve_wikipedia_candidate(names, rows)
        wiki_report = {"status": resolution["status"], "basis": resolution["basis"], "candidate_count": len(rows)}
        coverage["wikipedia_wikimedia"] = {"state": "source_absent" if resolution["status"] == "no_bound_record" else "source_acquired", **wiki_report}
    except Exception as exc:
        wiki_report = {"status": "inaccessible_through_supported_acquisition", "error": type(exc).__name__}; coverage["wikipedia_wikimedia"] = wiki_report

    # PFRA directory, exact linked-domain binding only.
    domain = normalise_host(website)
    pfra_rows: list[dict[str, Any]] = []
    for url, role in ((PFRA_CHARITY, "current_charity_membership"), (PFRA_AGENCY, "agency_membership")):
        try:
            pb, pr, _, _ = fetch(url)
            for row in extract_pfra_members(pb.decode("utf-8", "replace"), page_role=role, base_url=PFRA_CHARITY):
                if domain and domain in {normalise_host(x) for x in row.get("linked_domains", [])}:
                    pl = source_lineage(catalog, store, family="pfra", endpoint=url, url=url, body=pb, resolved=pr, media="text/html", role=role)
                    members.append(_member_from_lineage(pl, family="pfra")); pfra_rows.append({"role": role, "label": row.get("label"), "linked_domains": row.get("linked_domains")})
        except Exception:
            continue
    coverage["pfra"] = {"state": "source_acquired", "binding": "bound" if pfra_rows else "no_bound_record", "records": pfra_rows}

    corpus = build_corpus_manifest(subject_id=subject_id, profile_version="sparse-charity-corpus-v05", members=members, retrieval_timestamps=(now().isoformat(),), builder_commit=None)
    corpus_json = corpus.model_dump(mode="json")
    corpus_sha = dump(runtime / "corpus-manifest.json", corpus_json)
    dump(runtime / "coverage.json", coverage)
    packet = source_packet(catalog, store, members); packet["subject"] = {"subject_id": subject_id, "display_name": data.get("Name"), "abn": abn}
    packet_sha = dump(runtime / "whole-card-packet.json", packet)

    events: list[dict[str, Any]] = []; spent = Decimal("0")
    whole_prompt = (Path(__file__).with_name("whole_card_semantic_calibration_v02_prompt.txt").read_text(encoding="utf-8") +
                    "\n\nFROZEN PACKET:\n" + json.dumps(packet, ensure_ascii=False, separators=(",", ":")))
    whole_value, actual, whole_text = call_luna(whole_prompt, STRICT_SCHEMA, "sparse_whole_card_v05", WHOLE_MAX, spent, events); spent += actual
    dump(runtime / "whole-card-raw.json", whole_value)
    (runtime / "whole-card-output-text.txt").write_text(whole_text, encoding="utf-8")
    whole_valid = True; whole_diag: dict[str, Any] = {}
    try:
        parsed = validate_output(whole_value, packet); dump(runtime / "whole-card-parsed.json", parsed.model_dump(mode="json")); whole_diag = {"json_schema": "passed"}
    except Exception as exc:
        whole_valid = False; whole_diag = {"json_schema_or_citation": "failed", "error": str(exc)}; dump(runtime / "whole-card-parsed.json", whole_value)
    dump(runtime / "whole-card-validation.json", whole_diag)

    # Taxonomy-blind view: remove all assignments and section 19; preserve retained observations verbatim.
    blind = build_taxonomy_blind_view(whole_value)
    blind_sha = dump(runtime / "classie-blind-knowledge-view.json", blind)
    tax_path = Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json")
    if not tax_path.is_file():
        raise RuntimeError("permitted private CLASSIE taxonomy material is unavailable; failed closed")
    taxonomy = json.loads(tax_path.read_text(encoding="utf-8"))
    concept_ids = {str(c.get("concept_id") or c.get("id")) for c in taxonomy.get("concepts", [])}
    classie_packet = {"knowledge": blind, "taxonomy": taxonomy}
    classie_prompt = ("Infer CharityGraph CLASSIE assignments from the supplied taxonomy-blind CharityGraph knowledge. "
                      "Use only supplied observations and taxonomy; return the strict schema. Do not use outside knowledge, ACNC CLASSIE, SDG or CharityGraph Native.\n" +
                      json.dumps(classie_packet, ensure_ascii=False, separators=(",", ":")))
    classie_value, actual, classie_text = call_luna(classie_prompt, build_classie_schema(), "sparse_classie_v05", CLASSIE_MAX, spent, events); spent += actual
    dump(runtime / "classie-raw.json", classie_value)
    (runtime / "classie-output-text.txt").write_text(classie_text, encoding="utf-8")
    classie_diag: dict[str, Any] = {"json_schema": "passed", "unknown_concepts": sorted(set(str(a.get("concept_id")) for a in classie_value.get("assignments", [])) - concept_ids), "unresolved_observation_refs": []}
    valid_refs = set(blind["observation_refs"])
    for assignment in classie_value.get("assignments", []):
        for ref in assignment.get("supporting_observations", []):
            if ref.get("observation_ref") not in valid_refs: classie_diag["unresolved_observation_refs"].append(ref.get("observation_ref"))
    dump(runtime / "classie-parsed.json", classie_value); dump(runtime / "classie-validation.json", classie_diag)
    # ACNC assignments are preserved mechanically in source material; exact ID comparison only.
    acnc_ids: set[str] = set()
    for member in members:
        if member.source_family == "acnc_register" and member.artifact_ids:
            try:
                raw = json.loads(store.read(member.artifact_ids[0])); vals = raw.get("data", {}).get("Classifications") or raw.get("data", {}).get("CLASSIE") or []
                if isinstance(vals, list): acnc_ids.update(str(x.get("concept_id") or x.get("id")) for x in vals if isinstance(x, dict))
            except Exception: pass
    cg_ids = {str(a.get("concept_id")) for a in classie_value.get("assignments", [])}
    dump(runtime / "comparison.json", {"exact_agreement": sorted(cg_ids & acnc_ids), "cg_only": sorted(cg_ids - acnc_ids), "acnc_only": sorted(acnc_ids - cg_ids), "comparison_basis": "exact concept IDs only"})
    dump(runtime / "run-report.json", {"version": "sparse-luna-classie-v05", "private": True, "selected": selection["selected"], "subject_id": subject_id, "newly_created": newly_created, "corpus_id": corpus.corpus_id, "corpus_sha256": corpus_sha, "packet_sha256": packet_sha, "coverage": coverage, "whole_card": {"valid": whole_valid, "observations": len(whole_value.get("observations", [])), "sections": sorted({o.get("section_id") for o in whole_value.get("observations", [])})}, "classie_blind_sha256": blind_sha, "classie_assignments": len(classie_value.get("assignments", [])), "acnc_assignments": len(acnc_ids), "provider_events": events, "total_cost_usd": f"{spent:.6f}", "provider_calls": 2, "source_acquisition": "bounded public sources only"})
    catalog.close()
    print(json.dumps({"runtime": str(runtime), "subject_id": subject_id, "corpus_sha256": corpus_sha, "whole_observations": len(whole_value.get("observations", [])), "classie_assignments": len(classie_value.get("assignments", [])), "total_cost_usd": f"{spent:.6f}", "provider_calls": 2}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
