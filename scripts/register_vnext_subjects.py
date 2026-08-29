"""Bootstrap ten Reality Slice subjects in the stable vNext catalogue.

This script binds only the exact ACNC Register record identified by ABN.  Subject
IDs are UUID4 opaque values and are never derived from the ABN or source data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from charitygraph.contracts import ArtifactRef, ExternalIdentifier, SchemaRef, SourceDefinition, SourceRecord, AcquisitionReceipt, SubjectRecord, PropositionAuthorityRole
from charitygraph.contracts.ids import deterministic_id, new_opaque_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog


ABNS = ("28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642", "67649417658", "45146631843", "15101252171")
API = "https://www.acnc.gov.au/api/dynamics"
SOURCE_VERSION = "api-2026-08-29"
POLICY = "acnc-registered-charity-bootstrap-v1"


def _fetch_json(url: str) -> tuple[bytes, dict]:
    request = Request(url, headers={"User-Agent": "CharityGraph vNext bootstrap/1.0"})
    with urlopen(request, timeout=45) as response:  # nosec B310: fixed public HTTPS API
        body = response.read()
    return body, json.loads(body.decode("utf-8"))


def fetch_register_record(abn: str) -> tuple[str, bytes, dict]:
    search_url = f"{API}/search/charity?{urlencode({'search': abn})}"
    _, search = _fetch_json(search_url)
    matches = [row for row in search.get("results", []) if str(row.get("data", {}).get("Abn", "")) == abn]
    if len(matches) != 1:
        raise RuntimeError(f"ACNC exact ABN resolution expected one result for {abn}, found {len(matches)}")
    uuid = matches[0].get("uuid")
    if not uuid:
        raise RuntimeError(f"ACNC result for {abn} has no entity identifier")
    entity_url = f"{API}/entity/{uuid}"
    body, entity = _fetch_json(entity_url)
    if str(entity.get("data", {}).get("Abn", "")) != abn:
        raise RuntimeError(f"ACNC entity ABN mismatch for {abn}")
    return entity_url, body, entity


def _existing_subject(catalog: SQLiteCatalog, abn: str) -> dict | None:
    with catalog._connection() as conn:  # catalogue has no global identifier lookup API
        rows = conn.execute(
            "SELECT s.* FROM subjects s JOIN external_identifiers e ON e.subject_id=s.subject_id "
            "WHERE e.scheme=? AND e.identifier_value=? AND e.issuing_authority=? AND e.status='active'",
            ("ABN", abn, "ACNC"),
        ).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f"more than one active vNext subject is bound to ABN {abn}")
    if not rows:
        return None
    result = dict(rows[0])
    with catalog._connection() as conn:
        identifier = conn.execute(
            "SELECT material_json FROM external_identifiers WHERE subject_id=? AND scheme=? AND identifier_value=? AND issuing_authority=?",
            (result["subject_id"], "ABN", abn, "ACNC"),
        ).fetchone()
    if identifier:
        result["acnc_source_record_id"] = (json.loads(identifier["material_json"]).get("source_record_ids") or [None])[0]
    return result


def _name(entity: dict, abn: str) -> str:
    data = entity.get("data", {})
    for key in ("CharityLegalName", "LegalName", "CharityName", "Name"):
        value = data.get(key)
        if value and str(value).strip():
            return str(value).strip()
    raise RuntimeError(f"ACNC source record for {abn} has no registered name")


def bootstrap(catalog_path: Path, runtime_root: Path) -> list[dict]:
    catalog = SQLiteCatalog(catalog_path).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,), catalog=catalog)
    now = datetime.now(timezone.utc)
    source_definition = SourceDefinition(
        record_id=deterministic_id("srcdef:", {"source_family": "acnc_register", "endpoint": f"{API}/entity", "version": SOURCE_VERSION}),
        created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"},
        definition_version=SOURCE_VERSION, publisher="Australian Charities and Not-for-profits Commission",
        source_class="regulatory", authority_roles=(PropositionAuthorityRole(proposition="registered charity identity", role="identity-authority", basis="exact ACNC Register ABN record"),),
        acquisition_locator=f"{API}/entity", temporal_semantics="current_register_record",
        publication_eligibility="private_review_only", steward="CharityGraph identity steward",
    )
    if catalog.get_source_definition(source_definition.record_id) is None:
        catalog.register_source_definition(source_definition)
    rows: list[dict] = []
    try:
        for abn in ABNS:
            existing = _existing_subject(catalog, abn)
            if existing:
                rows.append({"abn": abn, "subject_id": existing["subject_id"], "acnc_source_record_id": existing.get("acnc_source_record_id"), "status": "reused", "subject_kind": existing["subject_kind"], "identity_policy": POLICY})
                continue
            locator, body, entity = fetch_register_record(abn)
            artifact = store.put(body, created_at=now)
            payload_hash = artifact.content_hash
            source_record_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": SOURCE_VERSION, "source_locator": locator, "payload_hash": payload_hash})
            receipt_id = deterministic_id("acq:", {"source_definition_id": source_definition.record_id, "artifact_id": artifact.artifact_id})
            receipt = AcquisitionReceipt(record_id=receipt_id, created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, source_definition_id=source_definition.record_id, requested_locator=locator, resolved_locator=locator, retrieved_at=now, outcome="available", response_status=200, media_type="application/json", content_hash=payload_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib")
            catalog.record_acquisition_receipt(receipt)
            record = SourceRecord(record_id=source_record_id, created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, source_family="acnc_register", source_role="register_identity", source_version=SOURCE_VERSION, source_locator=locator, retrieved_at=now, observed_at=now, media_type="application/json", payload_ref=artifact.artifact_id, payload_hash=payload_hash, attribution="Australian Charities and Not-for-profits Commission")
            catalog.register_source_record(record)
            subject_id = new_opaque_id("subject:")
            subject = SubjectRecord(record_id=new_opaque_id("subjectrecord:"), created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, subject_id=subject_id, subject_kind="unknown", lifecycle_status="active", display_name=_name(entity, abn), external_identifiers=(ExternalIdentifier(scheme="ABN", value=abn, issuing_authority="ACNC", source_record_ids=(source_record_id,)),), identity_authority_refs=(ArtifactRef(artifact_id=artifact.artifact_id, content_hash=payload_hash, schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-artefact:1.0", schema_version="1.0")),), identity_policy_id=POLICY)
            catalog.register_subject(subject)
            rows.append({"abn": abn, "subject_id": subject_id, "acnc_source_record_id": source_record_id, "status": "created", "subject_kind": "unknown", "identity_policy": POLICY})
        return rows
    finally:
        catalog.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3"))
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\state"))
    parser.add_argument("--report", type=Path, default=Path(r"C:\CharityGraph-runtime\vnext-bootstrap-subjects-20260829.json"))
    args = parser.parse_args()
    first = bootstrap(args.catalog, args.runtime)
    second = bootstrap(args.catalog, args.runtime)
    if [row["subject_id"] for row in first] != [row["subject_id"] for row in second]:
        raise RuntimeError("bootstrap is not idempotent")
    report = {"policy": POLICY, "catalog": str(args.catalog), "rows": first, "second_run_idempotent": True, "provider_calls": 0}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.report.read_bytes()).hexdigest()
    args.report.with_suffix(args.report.suffix + ".sha256").write_text(digest + "\n", encoding="ascii")
    print(json.dumps({"report": str(args.report), "sha256": digest, "rows": len(first), "idempotent": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


