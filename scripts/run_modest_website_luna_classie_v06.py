"""Bounded private Modest-Website Luna + CLASSIE v0.6 experiment.

Acquisition reuses the governed Baseline Corpus v1 machinery.  Only generic
experiment mechanics are committed; source material, prompts, taxonomy and
responses are written to the private runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from charitygraph.baseline_corpus import (  # noqa: E402
    CorpusMember, build_corpus_manifest, enumerate_site_candidates,
)
from charitygraph.evidence_store import ContentAddressedArtifactStore  # noqa: E402
from charitygraph.openai_client import estimate_response_cost, responses_create  # noqa: E402
from charitygraph.runtime import SQLiteCatalog  # noqa: E402
from charitygraph.whole_card_semantic_v02 import STRICT_SCHEMA, validate_output  # noqa: E402

from scripts import run_baseline_charity_corpus_v1 as base  # noqa: E402
from scripts.run_sparse_luna_classie_v05 import (  # noqa: E402
    build_classie_schema, build_taxonomy_blind_view, source_packet,
)

ABN = "93650312636"  # Local Buying Foundation (WA), rank 2009
RANK = 2009
MODEL = "gpt-5.6-luna"
CAP = Decimal("0.50")
IN_PRICE = Decimal("0.20")
OUT_PRICE = Decimal("1.20")
RANK_MAX = 8000
WHOLE_MAX = 24000
CLASSIE_MAX = 12000


def now() -> datetime:
    return datetime.now(timezone.utc)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return sha(data)


def register_subject_if_needed(catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, runtime: Path) -> str:
    with catalog._connection() as conn:
        row = conn.execute(
            "SELECT subject_id FROM external_identifiers WHERE scheme='ABN' AND identifier_value=? "
            "AND issuing_authority='Australian Business Register' AND status='active'", (ABN,)
        ).fetchone()
    if row:
        return str(row[0])
    from charitygraph.contracts import ArtifactRef, ExternalIdentifier, SchemaRef, SubjectRecord
    from charitygraph.contracts.ids import new_opaque_id
    url, body, resolved, entity = base.acnc_fetch(ABN)
    lineage = base.source_lineage(catalog, store, family="acnc_register", endpoint=f"{base.API}/entity", url=url, body=body, resolved=resolved, media="application/json", role="register_identity")
    data = entity.get("data", {})
    sid = new_opaque_id("subject:")
    source = catalog.get_source_record(lineage["source_record_id"]) or {}
    subject = SubjectRecord(
        record_id=new_opaque_id("subjectrecord:"), created_at=now(),
        producer={"kind": "code", "producer_id": "modest-website-v06", "version": "0.1"},
        subject_id=sid, subject_kind="unknown", lifecycle_status="active",
        display_name=str(data.get("Name") or "Local Buying Foundation (WA)"),
        external_identifiers=(ExternalIdentifier(scheme="ABN", value=ABN, issuing_authority="Australian Business Register", source_record_ids=(lineage["source_record_id"],)),),
        identity_authority_refs=(ArtifactRef(artifact_id=lineage["source_record_id"], content_hash=source.get("payload_hash") or "0" * 64, schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),),
        identity_policy_id="acnc-registered-charity-bootstrap-v1",
    )
    catalog.register_subject(subject)
    write_json(runtime / "subject-registration.json", {"subject_id": sid, "abn": ABN, "display_name": subject.display_name, "source_record_id": lineage["source_record_id"]})
    return sid


def projected(input_text: str, max_output: int) -> Decimal:
    tokens = max(1, len(input_text.encode("utf-8")) // 4)
    return (Decimal(tokens) * IN_PRICE + Decimal(max_output * 2) * OUT_PRICE) / Decimal(1_000_000)


def call_luna(input_text: str, schema: dict, name: str, max_output: int, spent: Decimal, events: list[dict], runtime: Path) -> tuple[dict, Decimal]:
    estimate = projected(input_text, max_output)
    if spent + estimate > CAP:
        raise RuntimeError(f"provider cap would be exceeded before {name}: {spent + estimate:.6f} > {CAP}")
    event = {"phase": name, "model": MODEL, "projected_max_usd": f"{estimate:.6f}", "max_output_tokens": max_output, "started_at": now().isoformat(), "status": "started"}
    write_json(runtime / f"{name}-start.json", event)
    started = now()
    result = responses_create(model=MODEL, input_text=input_text, text_format={"type": "json_schema", "name": name, "strict": True, "schema": schema}, max_output_tokens=max_output, max_attempts=2, timeout_seconds=300, reasoning={"effort": "high"})
    usage = result.usage.__dict__
    actual = estimate_response_cost(result.model, result.usage) or Decimal("0")
    raw = {"output_text": result.output_text, "model": result.model, "usage": usage, "transport_requests": result.transport_requests, "status": result.status}
    write_json(runtime / f"{name}-raw.json", raw)
    event.update({"status": "response_received", "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "transport_requests": result.transport_requests, "actual_cost_usd": f"{actual:.6f}", "latency_seconds": (now() - started).total_seconds()})
    events.append(event)
    return json.loads(result.output_text), actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\modest-website-luna-classie-v06-20260831T"))
    args = parser.parse_args()
    runtime = args.runtime.resolve(); runtime.mkdir(parents=True, exist_ok=True)
    # Baseline runner is reused in skip-Luna mode for all six bounded source families.
    catalog = SQLiteCatalog(Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,), catalog=catalog)
    subject_id = register_subject_if_needed(catalog, store, runtime)
    base.ABNS = (ABN,); base.DEV = set(); base.WEBSITES = {ABN: "https://localbuyingfoundation.com.au"}
    base.subject_registry = lambda _catalog: {ABN: subject_id}
    base_report_rc = base.run(argparse.Namespace(runtime=runtime, skip_luna=True, subject_abn=ABN))
    if base_report_rc != 0:
        raise RuntimeError("bounded baseline acquisition failed")
    report_path = runtime / "baseline-corpus-v1-report.json"
    acquisition = json.loads(report_path.read_text(encoding="utf-8"))
    corpus_json = acquisition["corpora"][0]
    members = [CorpusMember.model_validate(m) for m in corpus_json["material_members"]]
    # Website ranking is the only optional acquisition-stage model call.
    site = acquisition.get("official_site_rankings", {}).get(ABN, {})
    candidates = site.get("mechanical_candidates") or []
    events: list[dict] = []; spent = Decimal("0")
    if candidates:
        rank_input = "Rank these official-site URL candidates by information value. Return every ordinal exactly once. Subject: Local Buying Foundation (WA)\n" + json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
        rank_schema = {"type": "object", "additionalProperties": False, "properties": {"ranked_ordinals": {"type": "array", "items": {"type": "integer"}}}, "required": ["ranked_ordinals"]}
        ranking, cost = call_luna(rank_input, rank_schema, "website-ranking", RANK_MAX, spent, events, runtime); spent += cost
        allowed = {int(c["ordinal"]) for c in candidates}; ranked = [int(x) for x in ranking.get("ranked_ordinals", [])]
        if set(ranked) != allowed or len(ranked) != len(allowed):
            raise RuntimeError("website ranking did not return every candidate ordinal exactly once")
        chosen = [next(c for c in candidates if int(c["ordinal"]) == ordinal) for ordinal in ranked[:10]]
        for c in chosen:
            try:
                body, resolved, _, media = base.fetch(c["url"])
                lineage = base.source_lineage(catalog, store, family="official_website", endpoint="https://localbuyingfoundation.com.au", url=c["url"], body=body, resolved=resolved, media=media, role="official_page")
                members.append(base._member_from_lineage(lineage, family="official_website"))
            except Exception:
                continue
        site["v06_ranking"] = {"candidate_count": len(candidates), "batch_count": 1, "selected_count": len(chosen), "selected_urls": [c["url"] for c in chosen]}
    corpus = build_corpus_manifest(subject_id=subject_id, profile_version="modest-website-corpus-v06", members=members, retrieval_timestamps=(now().isoformat(),), builder_commit=None)
    corpus_sha = write_json(runtime / "corpus-manifest-v06.json", corpus.model_dump(mode="json"))
    diagnostics: list[dict] = []
    packet = source_packet(catalog, store, members, diagnostics); packet["subject"] = {"subject_id": subject_id, "display_name": "Local Buying Foundation (WA)", "abn": ABN}
    packet_sha = write_json(runtime / "whole-card-packet-v06.json", packet)
    write_json(runtime / "representation-diagnostics.json", diagnostics)
    prompt_path = Path(__file__).with_name("whole_card_semantic_calibration_v02_prompt.txt")
    whole_prompt = prompt_path.read_text(encoding="utf-8") + "\n\nFROZEN PACKET:\n" + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    whole, cost = call_luna(whole_prompt, STRICT_SCHEMA, "whole-card-v06", WHOLE_MAX, spent, events, runtime); spent += cost
    try:
        parsed = validate_output(whole, packet); whole_valid = True; validation = {"json_schema": "passed", "citation": "passed"}; write_json(runtime / "whole-card-parsed.json", parsed.model_dump(mode="json"))
    except Exception as exc:
        whole_valid = False; validation = {"json_schema_or_citation": "failed", "error": str(exc)}; write_json(runtime / "whole-card-parsed.json", whole)
    write_json(runtime / "whole-card-validation.json", validation)
    blind = build_taxonomy_blind_view(whole); blind_sha = write_json(runtime / "classie-blind-knowledge-view-v06.json", blind)
    taxonomy_path = Path(r"C:\CharityGraph-runtime\classie-4.2\classie-subject-4.2-private.json")
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    classie_input = "Infer CharityGraph CLASSIE assignments from taxonomy-blind knowledge and the supplied private taxonomy only. Do not use outside knowledge, source documents, ACNC CLASSIE, SDG or CharityGraph Native.\n" + json.dumps({"knowledge": blind, "taxonomy": taxonomy}, ensure_ascii=False, separators=(",", ":"))
    classie, cost = call_luna(classie_input, build_classie_schema(), "classie-v06", CLASSIE_MAX, spent, events, runtime); spent += cost
    concept_ids = {str(c.get("external_concept_id") or c.get("concept_id") or c.get("id")) for c in taxonomy.get("concepts", [])}
    valid_refs = set(blind.get("observation_refs", {})); unknown = sorted(set(str(a.get("concept_id")) for a in classie.get("assignments", [])) - concept_ids); bad_refs = sorted({str(ref.get("observation_ref")) for a in classie.get("assignments", []) for ref in a.get("supporting_observations", []) if ref.get("observation_ref") not in valid_refs})
    write_json(runtime / "classie-parsed.json", classie); write_json(runtime / "classie-validation.json", {"unknown_concepts": unknown, "unresolved_observation_refs": bad_refs, "json_schema": "passed"})
    write_json(runtime / "run-report-v06.json", {"version": "modest-website-luna-classie-v06", "private": True, "selected": {"abn": ABN, "rank": RANK, "name": "Local Buying Foundation (WA)"}, "subject_id": subject_id, "corpus_sha256": corpus_sha, "packet_sha256": packet_sha, "representation": diagnostics, "whole_card": {"valid": whole_valid, "observations": len(whole.get("observations", [])), "sections": sorted({o.get("section_id") for o in whole.get("observations", [])})}, "classie_blind_sha256": blind_sha, "classie_assignments": len(classie.get("assignments", [])), "acnc_classie_comparison": "unavailable from frozen source-native records", "provider_events": events, "provider_calls": len(events), "total_cost_usd": f"{spent:.6f}", "source_acquisition": "bounded public sources only", "website": site})
    catalog.close()
    print(json.dumps({"runtime": str(runtime), "selected": "Local Buying Foundation (WA)", "rank": RANK, "corpus_sha256": corpus_sha, "whole_valid": whole_valid, "whole_observations": len(whole.get("observations", [])), "classie_assignments": len(classie.get("assignments", [])), "provider_calls": len(events), "cost_usd": f"{spent:.6f}"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
