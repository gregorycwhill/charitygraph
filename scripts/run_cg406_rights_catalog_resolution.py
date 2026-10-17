"""Provider-free CG406 catalog, representation and rights replay.

The script consumes only previously acquired Phase-5 objects and CG406's
frozen manifests.  It never contacts a source or a provider.  It constructs a
fresh development runtime, so frozen CG406 evidence remains read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from charitygraph.baseline_corpus import CorpusManifest, CorpusMember, build_corpus_manifest, compile_provider_evidence_corpus, extract_pfra_members, resolve_wikipedia_candidate
from charitygraph.contracts import AcquisitionReceipt, SourceRecord
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.frozen_experiment import prepare_frozen_experiment
from charitygraph.phase5_baseline_corpus import native_pdf_representation, source_definition
from charitygraph.runtime import SQLiteCatalog
from charitygraph.source_rights import PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID
from charitygraph.source_transmission import payload_selection, render_complete_workbook


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()


def text(value):
    return re.sub(r"\s+", " ", unescape(value)).strip()


class TableFacts(HTMLParser):
    """Capture source-native HTML header/value rows without interpreting prose."""
    def __init__(self):
        super().__init__(); self.rows=[]; self._tag=None; self._value=[]; self._header=None
    def handle_starttag(self, tag, attrs):
        if tag in {"th", "td"}: self._tag, self._value = tag, []
    def handle_data(self, data):
        if self._tag: self._value.append(data)
    def handle_endtag(self, tag):
        if tag not in {"th", "td"} or self._tag != tag: return
        value = text("".join(self._value))
        if tag == "th": self._header = value
        elif self._header and value: self.rows.append({"label": self._header, "value": value}); self._header = None
        self._tag = None


def abr_facts(body: bytes):
    parser = TableFacts(); parser.feed(body.decode("utf-8", "replace")); parser.close()
    return {"representation_kind": "source_native_structured_facts", "source_format": "html_table", "rows": parser.rows}


def report_excerpt(source_path: Path, source_artifact_id: str):
    report = native_pdf_representation(source_path)
    page_count = len(report["pages"])
    count = min(5, page_count // 5)
    if count < 1: count = 1
    return {"representation_kind": "bounded_pdf_excerpt", "source_artifact_id": source_artifact_id,
            "source_page_count": page_count, "selected_page_count": count,
            "pages": report["pages"][:count]}


def source_path(objects: Path, artifact_id: str) -> Path:
    digest = artifact_id.split(":", 1)[1]
    return objects / "objects" / "sha256" / digest[:2] / digest


def network_events(network_cache: Path):
    result = {}
    for path in network_cache.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8")); event = raw.get("event", {})
        if event.get("content_hash"):
            result[event["content_hash"]] = event
    return result


def frozen_catalog_records(path: Path):
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return [json.loads(row[0]) for row in conn.execute("select material_json from source_records")]
    finally:
        conn.close()


def main(args):
    frozen = args.frozen.resolve(); phase5 = args.phase5.resolve(); output = args.output.resolve()
    if output.exists() and (output / "catalog.sqlite3").exists(): raise RuntimeError("output must be a new development runtime")
    output.mkdir(parents=True, exist_ok=True)
    objects = phase5 / "objects"; events = network_events(phase5 / "network-cache")
    corpus = json.loads((frozen / "governed-provider-corpus.json").read_text(encoding="utf-8"))
    subjects = json.loads(args.subject_manifest.read_text(encoding="utf-8"))["subjects"]
    subject_by_id = {item["subject_id"]: item for item in subjects}
    old_records = {row["record_id"]: row for row in frozen_catalog_records(frozen / "catalog.sqlite3")}
    catalog_path = output / "catalog.sqlite3"; authority = output / "authorization.sqlite3"
    catalog = SQLiteCatalog(catalog_path, authorization_path=authority).open(initialize=True)
    store = ContentAddressedArtifactStore(output / "objects", allowed_roots=(output,))
    now = datetime.now(UTC)
    classifications=[]; decisions=[]; corpora=[]; copied=set()

    def put_existing(artifact_id):
        if artifact_id in copied: return
        origin = (frozen / "objects" if (frozen / "objects" / "objects" / "sha256" / artifact_id.split(":",1)[1][:2] / artifact_id.split(":",1)[1]).exists() else objects)
        body = source_path(origin, artifact_id).read_bytes(); stored = store.put(body, created_at=now)
        if stored.artifact_id != artifact_id: raise RuntimeError("source artifact hash drift")
        copied.add(artifact_id)

    def record(row, family, role, receipt_id):
        artifact = row["artifact_ids"][0]; digest = artifact.split(":",1)[1]; event = events.get(digest)
        if event is None: raise RuntimeError(f"missing retained acquisition metadata: {artifact}")
        definition = source_definition(family, now); catalog.register_source_definition(definition); put_existing(artifact)
        catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=receipt_id, created_at=now, producer={"kind":"code","producer_id":"cg406-rights-catalog-resolution","version":"1"}, source_definition_id=definition.record_id, requested_locator=event["requested_url"], resolved_locator=event.get("resolved_url") or event["requested_url"], retrieved_at=now, outcome="available", response_status=event.get("response_status") or 200, media_type=event.get("media_type") or "application/octet-stream", content_hash=digest, byte_size=len(source_path(objects, artifact).read_bytes()), artifact_id=artifact, tool_id="reconstructed_from_governed_receipt", tool_version="1"))
        catalog.register_source_record(SourceRecord(record_id=row["source_record_ids"][0], created_at=now, producer={"kind":"code","producer_id":"cg406-rights-catalog-resolution","version":"1"}, source_family=family, source_role=role, source_version=row.get("effective_period"), source_locator=event.get("resolved_url") or event["requested_url"], observed_at=now, retrieved_at=now, media_type=event.get("media_type") or "application/octet-stream", payload_ref=artifact, payload_hash=digest, attribution=definition.publisher))
        return event, artifact

    def derived(value, artifact):
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode(); result = store.put_derived(encoded, input_artifact_ids=(artifact,), created_at=now)
        if isinstance(value.get("pages"), list):
            rendered = "\n\n".join(str(page["text"]) for page in value["pages"] if isinstance(page, dict) and isinstance(page.get("text"), str))
            if not rendered: raise RuntimeError("bounded representation has no deterministic text")
            return result.artifact_id, rendered
        return result.artifact_id, encoded.decode()

    def decision(*, artifact, record_id, event, role, receipt, rendered, policy, basis, cls, factual):
        value={"decision_id":"rights:"+sha({"artifact":artifact,"representation":hashlib.sha256(rendered.encode()).hexdigest(),"policy":policy}),"source_artifact_id":artifact,"source_record_id":record_id,"source_origin_url":event.get("resolved_url") or event["requested_url"],"source_role":role,"acquisition_lineage_ids":[receipt],"transmitted_representation_sha256":hashlib.sha256(rendered.encode()).hexdigest(),"rights_policy_id":policy,"provider_processing_policy_id":"OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1","rights_basis":basis,"evidence_locator":"policy://"+policy+"/v1#deterministic-replay-assessment","evidence_sha256":sha({"source_artifact_id":artifact,"representation_sha256":hashlib.sha256(rendered.encode()).hexdigest(),"source_origin":event.get("resolved_url") or event["requested_url"],"policy":policy}),"assessed_on":now.date().isoformat(),"assessment_scope":"private bounded analytical processing","local_retention_allowed":False,"provider_transmission_allowed":True,"public_redistribution_allowed":False,"factual_representation_only":factual,"representation_class":cls,"publicly_accessible_without_circumvention":True,"access_controls_bypassed":False,"lawfully_acquired":True,"analytical_purpose":"semantic_analysis","explicit_prohibition_found":False,"provider_no_training_default":True,"provider_data_sharing_opt_in":False}
        decisions.append(value)

    # Reconstruct old ACNC source records and preserve their exact existing decisions.
    old_rights=json.loads((frozen / "artifact-rights-decisions.json").read_text(encoding="utf-8"))["decisions"]
    for row in old_records.values():
        put_existing(row["payload_ref"]); catalog.register_source_record(SourceRecord.model_validate(row))
    decisions.extend(old_rights)

    for corpus_row in corpus["corpora"]:
        subject_id=corpus_row["subject_id"]; member_rows=[]
        for item in corpus_row["material_members"]: member_rows.append(item)
        for row in corpus_row["source_universe_assessment"]:
            family=row["source_family"]
            if family in {"acnc_register","acnc_ais_bundle","official_website"} or row["acquisition"] not in {"available","partial"} or row["subject_binding"] != "bound": continue
            receipt=row["acquisition_receipt_ids"][0]; role={"ato_abr_dgr":"abr_entity","annual_report":"annual_report","wikipedia_wikimedia":"wikipedia_search_context","pfra":"registry_membership"}[family]
            event, artifact=record(row, family, role, receipt); body=source_path(objects,artifact).read_bytes()
            if family == "annual_report":
                if body.startswith(b"%PDF-"):
                    # The excerpt is selected for payload economy, not because
                    # the full public report lacks transmission permission.
                    value=report_excerpt(source_path(objects,artifact),artifact)
                    payload_reason="economic_optimization"
                else:
                    # Complete source-native workbook transport rendering: no
                    # sheet, range, or cell limit is imposed by rights policy.
                    value=render_complete_workbook(body, artifact)
                    payload_reason="transport_rendering"
                policy,basis,cls,factual=PUBLIC_SOURCE_PRIVATE_PROVIDER_POLICY_ID,"public_source_private_processing","complete_or_near_complete_work",False
            elif family == "ato_abr_dgr": value=abr_facts(body); policy,basis,cls,factual="PUBLIC_FACTS_ONLY_V1","public_facts_only","structured_factual",True
            elif family == "wikipedia_wikimedia":
                candidates=json.loads(body).get("query",{}).get("search",[]); subject=subject_by_id[subject_id]; chosen=resolve_wikipedia_candidate([subject["display_name"]],candidates)
                value={"representation_kind":"source_native_structured_facts","source_format":"wikipedia_search_result","record":chosen}; policy,basis,cls,factual="PUBLIC_FACTS_ONLY_V1","public_facts_only","structured_factual",True
            else:
                subject=subject_by_id[subject_id]; acnc=next(x for x in corpus_row["material_members"] if x["source_family"]=="acnc_register"); acnc_body=source_path(frozen / "objects",acnc["artifact_ids"][0]).read_text(encoding="utf-8"); acnc_payload=json.loads(acnc_body); acnc_fields=acnc_payload.get("data", acnc_payload); domain=(urlsplit(str(acnc_fields.get("Website") or "")).hostname or "").casefold().removeprefix("www.")
                matches=[x for x in extract_pfra_members(body.decode("utf-8","replace"),page_role="current_charity_membership") if domain in {str(y).casefold().removeprefix("www.") for y in x.get("linked_domains",[])}]
                if len(matches)!=1: raise RuntimeError(f"PFRA frozen binding no longer resolves exactly: subject={subject_id} domain={domain!r} matches={len(matches)}")
                value={"representation_kind":"source_native_structured_facts","source_format":"pfra_member_card","record":matches[0]}; policy,basis,cls,factual="PUBLIC_FACTS_ONLY_V1","public_facts_only","structured_factual",True
            representation, rendered=derived(value,artifact)
            decision(artifact=artifact,record_id=row["source_record_ids"][0],event=event,role=role,receipt=receipt,rendered=rendered,policy=policy,basis=basis,cls=cls,factual=factual)
            member_rows.append({**row,"representation_artifact_ids":[representation],"representation_readiness":"partial" if family=="annual_report" else "ready"})
            entry={"subject_id":subject_id,"source_family":family,"source_record_id":row["source_record_ids"][0],"source_artifact_id":artifact,"catalog_classification":"CATALOG_MECHANICAL_GAP","rights_classification":"RIGHTS_ALREADY_DETERMINED_ALLOW","proposed_representation":value["representation_kind"],"rights_policy_id":policy,"result":"ALLOW"}
            if family == "annual_report":
                entry["payload_selection"] = payload_selection(candidate_representation_artifact_id=representation, selection_reason=payload_reason)
                entry["payload_classification"] = "ECONOMIC_PROVIDER_PAYLOAD_CHOICE" if payload_reason == "economic_optimization" else "FULL_PUBLIC_SOURCE_TRANSPORT_RENDERING"
            else:
                entry["payload_classification"] = "SOURCE_NATIVE_STRUCTURED_FACTUAL_PAYLOAD"
            classifications.append(entry)
        manifests=[CorpusMember.model_validate(x) for x in member_rows]
        corpora.append(build_corpus_manifest(subject_id=subject_id,profile_version="cg406-development-rights-resolution-v1",members=manifests).model_dump(mode="json"))
    catalog.close()
    governed=compile_provider_evidence_corpus([CorpusManifest.model_validate(item) for item in corpora])
    (output / "governed-provider-corpus.json").write_text(json.dumps(governed,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (output / "artifact-rights-decisions.json").write_text(json.dumps({"schema":"charitygraph.artifact-rights-decisions/v1","decisions":decisions},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (output / "row-classification.json").write_text(json.dumps(classifications,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    shutil.copy2(frozen / "frozen-pricing-snapshot.json", output / "frozen-pricing-snapshot.json")
    shutil.copy2(frozen / "cg406-execution-authorization.txt", output / "cg406-execution-authorization.txt")
    prepared=prepare_frozen_experiment(subject_manifest=args.subject_manifest,demand_manifest=args.demand_manifest,corpus_manifest=output / "governed-provider-corpus.json",rights_decisions=output / "artifact-rights-decisions.json",pricing_snapshot=output / "frozen-pricing-snapshot.json",runtime_root=output,catalog_path=catalog_path,authorization_catalog_path=authority,authorization_text_hash=hashlib.sha256((output / "cg406-execution-authorization.txt").read_bytes()).hexdigest(),provider_account_project="cg406-development-replay")
    (output / "prepared-run.json").write_text(json.dumps(prepared,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(classifications),"families":{k:sum(x["source_family"]==k for x in classifications) for k in sorted({x["source_family"] for x in classifications})},"prepared_requests":len(prepared["rows"]),"provider_calls":0},sort_keys=True))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--frozen",type=Path,required=True); parser.add_argument("--phase5",type=Path,required=True); parser.add_argument("--subject-manifest",type=Path,required=True); parser.add_argument("--demand-manifest",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); main(parser.parse_args())
