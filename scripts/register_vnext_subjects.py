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

from charitygraph.contracts import ArtifactRef, ExternalIdentifier, SchemaRef, SourceDefinition, SourceRecord, AcquisitionReceipt, SubjectRecord, PropositionAuthorityRole, canonical_sha256
from charitygraph.contracts.ids import deterministic_id, new_opaque_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.catalog import _canonical_hash


ABNS = ("28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642", "67649417658", "45146631843", "15101252171")
API = "https://www.acnc.gov.au/api/dynamics"
SOURCE_VERSION = "acnc-dynamics-v1"
POLICY = "acnc-registered-charity-bootstrap-v1"
PRESERVED_IDS = {
    "28000030179": "subject:f284a1e0e31a4e04b7d9f8ae8863ef10",
    "50169561394": "subject:d10dfad31cb04c5fb27ada0a81f36b69",
    "20077830347": "subject:cd39c657e7df48f28a6e7b1df9ef33fe",
    "22007498482": "subject:c5773029e25241248fdb15edd7440275",
    "15000002522": "subject:67db77d503aa4689a78c685704cc8a96",
    "28004778081": "subject:cf042745edd84e58bce4e1c60704c472",
    "46070556642": "subject:ca20920c8c074a268f09b7a57866479a",
    "67649417658": "subject:0c24bf13cc114a1f8fc9251f303f1b19",
    "45146631843": "subject:c8815cbf7b0c48f28b2a49466a0bd653",
    "15101252171": "subject:ca2a7205d6de410c85cb2a08196206dc",
}


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
            ("ABN", abn, "Australian Business Register"),
        ).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f"more than one active vNext subject is bound to ABN {abn}")
    if not rows:
        return None
    result = dict(rows[0])
    with catalog._connection() as conn:
        identifier = conn.execute(
            "SELECT material_json FROM external_identifiers WHERE subject_id=? AND scheme=? AND identifier_value=? AND issuing_authority=?",
            (result["subject_id"], "ABN", abn, "Australian Business Register"),
        ).fetchone()
    if identifier:
        result["acnc_source_record_id"] = (json.loads(identifier["material_json"]).get("source_record_ids") or [None])[0]
    return result


def _source_record_hash(catalog: SQLiteCatalog, source_record_id: str) -> str:
    with catalog._connection() as conn:
        row = conn.execute("SELECT material_json FROM source_records WHERE source_record_id=?", (source_record_id,)).fetchone()
    if row is None:
        raise RuntimeError(f"governed SourceRecord is missing: {source_record_id}")
    return canonical_sha256(SourceRecord.model_validate(json.loads(row["material_json"])))


def _repair_identity_authority_ref(catalog: SQLiteCatalog, subject_id: str) -> None:
    """Repair existing refs to the canonical SourceRecord hash."""
    with catalog._connection(immediate=True) as conn:
        row = conn.execute("SELECT material_json FROM subjects WHERE subject_id=?", (subject_id,)).fetchone()
        if row is None:
            return
        material = json.loads(row["material_json"])
        changed = False
        for ref in material.get("identity_authority_refs") or []:
            source = conn.execute("SELECT material_json FROM source_records WHERE source_record_id=?", (ref.get("artifact_id"),)).fetchone()
            if source is not None:
                source_hash = canonical_sha256(SourceRecord.model_validate(json.loads(source["material_json"])))
                if ref.get("content_hash") != source_hash:
                    ref["content_hash"] = source_hash
                    changed = True
        if changed:
            encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            conn.execute("UPDATE subjects SET material_json=?, material_hash=? WHERE subject_id=?", (encoded, _canonical_hash(material), subject_id))
            conn.commit()


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
                _repair_identity_authority_ref(catalog, existing["subject_id"])
                rows.append({"abn": abn, "subject_id": existing["subject_id"], "acnc_source_record_id": existing.get("acnc_source_record_id"), "status": "reused", "subject_kind": existing["subject_kind"], "identity_policy": POLICY})
                continue
            locator, body, entity = fetch_register_record(abn)
            artifact = store.put(body, created_at=now)
            payload_hash = artifact.content_hash
            source_record_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": None, "source_locator": locator, "payload_hash": payload_hash})
            receipt_id = deterministic_id("acq:", {"source_definition_id": source_definition.record_id, "artifact_id": artifact.artifact_id})
            receipt = AcquisitionReceipt(record_id=receipt_id, created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, source_definition_id=source_definition.record_id, requested_locator=locator, resolved_locator=locator, retrieved_at=now, outcome="available", response_status=200, media_type="application/json", content_hash=payload_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib")
            catalog.record_acquisition_receipt(receipt)
            record = SourceRecord(record_id=source_record_id, created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, source_family="acnc_register", source_role="register_identity", source_version=None, source_locator=locator, retrieved_at=now, observed_at=now, media_type="application/json", payload_ref=artifact.artifact_id, payload_hash=payload_hash, attribution="Australian Charities and Not-for-profits Commission")
            catalog.register_source_record(record)
            subject_id = PRESERVED_IDS[abn]
            subject = SubjectRecord(record_id=new_opaque_id("subjectrecord:"), created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"}, subject_id=subject_id, subject_kind="unknown", lifecycle_status="active", display_name=_name(entity, abn), external_identifiers=(ExternalIdentifier(scheme="ABN", value=abn, issuing_authority="Australian Business Register", source_record_ids=(source_record_id,)),), identity_authority_refs=(ArtifactRef(artifact_id=source_record_id, content_hash=_source_record_hash(catalog, source_record_id), schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),), identity_policy_id=POLICY)
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
