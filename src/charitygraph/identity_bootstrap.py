"""Bounded exact-ABN subject bootstrap shared by cohort drivers.

This module deliberately implements identity only.  It never creates semantic
tasks and it accepts only exact ACNC Register identity evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from charitygraph.contracts import (
    AcquisitionReceipt, ArtifactRef, ExternalIdentifier, PropositionAuthorityRole,
    SchemaRef, SourceDefinition, SourceRecord, SubjectRecord, canonical_sha256,
)
from charitygraph.contracts.ids import deterministic_id, new_opaque_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.catalog import _canonical_hash


API = "https://www.acnc.gov.au/api/dynamics"
POLICY = "acnc-registered-charity-bootstrap-v1"
SOURCE_VERSION = "acnc-dynamics-v1"
ARCHIVE_SOURCE_ID = "acnc-registered-charities-2026-08-10"
ARCHIVE_SOURCE_URL = "https://data.gov.au/data/dataset/b050b242-4487-4306-abf5-07ca073e5594/resource/8fb32972-24e9-4c95-885e-7140be51be8a/download/datadotgov_main.csv"
ARCHIVE_SOURCE_HASH = "01ceee0645b9f1111a555c65e026c12b04811a682e2cb1fa10edb7d510a7d5c8"


def fetch_register_record(abn: str) -> tuple[str, bytes, str]:
    """Resolve exactly one ACNC entity by exact ABN and return its identity name."""
    def get(url: str) -> tuple[bytes, dict[str, Any]]:
        request = Request(url, headers={"User-Agent": "CharityGraph bounded identity bootstrap/1.0"})
        with urlopen(request, timeout=45) as response:  # nosec B310: fixed ACNC HTTPS endpoint
            body = response.read()
        return body, json.loads(body.decode("utf-8"))

    search_url = f"{API}/search/charity?{urlencode({'search': abn})}"
    _, search = get(search_url)
    matches = [row for row in search.get("results", []) if str(row.get("data", {}).get("Abn", "")) == abn]
    if len(matches) != 1:
        raise RuntimeError(f"ACNC exact ABN resolution expected one result for {abn}, found {len(matches)}")
    entity_id = matches[0].get("uuid")
    if not entity_id:
        raise RuntimeError(f"ACNC result for {abn} has no entity identifier")
    entity_url = f"{API}/entity/{entity_id}"
    body, entity = get(entity_url)
    if str(entity.get("data", {}).get("Abn", "")) != abn:
        raise RuntimeError(f"ACNC entity ABN mismatch for {abn}")
    data = entity.get("data", {})
    name = next((str(data[k]).strip() for k in ("CharityLegalName", "LegalName", "CharityName", "Name") if data.get(k)), None)
    if not name:
        raise RuntimeError(f"ACNC source record for {abn} has no registered name")
    return entity_url, body, name


def _source_definition() -> SourceDefinition:
    now = datetime.now(timezone.utc)
    return SourceDefinition(
        record_id=deterministic_id("srcdef:", {"source_family": "acnc_register", "endpoint": f"{API}/entity", "version": SOURCE_VERSION}),
        created_at=now, producer={"kind": "code", "producer_id": "vnext-bootstrap", "version": "1"},
        definition_version=SOURCE_VERSION, publisher="Australian Charities and Not-for-profits Commission",
        source_class="regulatory",
        authority_roles=(PropositionAuthorityRole(proposition="registered charity identity", role="identity-authority", basis="exact ACNC Register ABN record"),),
        acquisition_locator=f"{API}/entity", temporal_semantics="current_register_record",
        publication_eligibility="private_review_only", steward="CharityGraph identity steward",
    )


def _existing_subject(catalog: SQLiteCatalog, abn: str) -> dict[str, Any] | None:
    with catalog._connection() as conn:
        rows = conn.execute(
            "SELECT s.* FROM subjects s JOIN external_identifiers e ON e.subject_id=s.subject_id "
            "WHERE e.scheme=? AND e.identifier_value=? AND e.issuing_authority=? AND e.status='active'",
            ("ABN", abn, "Australian Business Register"),
        ).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f"more than one active governed subject is bound to ABN {abn}")
    if not rows:
        return None
    result = dict(rows[0])
    with catalog._connection() as conn:
        identifier = conn.execute(
            "SELECT material_json FROM external_identifiers WHERE subject_id=? AND scheme=? AND identifier_value=? AND issuing_authority=?",
            (result["subject_id"], "ABN", abn, "Australian Business Register"),
        ).fetchone()
    if not identifier:
        raise RuntimeError(f"active ABN binding disappeared for {abn}")
    material = json.loads(identifier["material_json"])
    source_ids = material.get("source_record_ids") or []
    if len(source_ids) != 1:
        raise RuntimeError(f"existing ABN binding for {abn} lacks exactly one authority source reference")
    result["acnc_source_record_id"] = source_ids[0]
    return result


def _source_record_hash(catalog: SQLiteCatalog, source_record_id: str) -> str:
    row = catalog.get_source_record(source_record_id)
    if row is None:
        raise RuntimeError(f"governed SourceRecord is missing: {source_record_id}")
    return canonical_sha256(SourceRecord.model_validate(json.loads(row["material_json"])))


def _repair_identity_authority_ref(catalog: SQLiteCatalog, subject_id: str) -> None:
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


def _archive_rows(path: Path, cohort: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    expected = {str(row["abn"]) for row in cohort}
    rows: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            abn = str(row.get("ABN") or row.get("Abn") or "").strip()
            if abn in expected:
                if abn in rows:
                    raise RuntimeError(f"archive has multiple exact ACNC rows for {abn}")
                name = str(row.get("Charity Name") or row.get("CharityLegalName") or row.get("Charity_Legal_Name") or row.get("Name") or "").strip()
                if not name:
                    raise RuntimeError(f"archive ACNC row for {abn} has no registered name")
                rows[abn] = {"name": name}
    return rows


def _register_archive_source(catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, source_bytes: bytes, abn: str, now: datetime) -> tuple[str, str]:
    artifact = store.put(source_bytes, created_at=now)
    if artifact.content_hash != ARCHIVE_SOURCE_HASH:
        raise RuntimeError("archived ACNC Register bytes do not match the governed dataset hash")
    locator = f"{ARCHIVE_SOURCE_URL}#ABN={abn}"
    source_record_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": ARCHIVE_SOURCE_ID, "source_locator": locator, "payload_hash": artifact.content_hash})
    record = SourceRecord(
        record_id=source_record_id, created_at=now, producer={"kind": "code", "producer_id": "phase5-top100-subject-bootstrap", "version": "1"},
        source_family="acnc_register", source_role="register_identity", source_version=ARCHIVE_SOURCE_ID,
        source_locator=locator, retrieved_at=datetime(2026, 8, 10, tzinfo=timezone.utc), observed_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        media_type="text/csv", payload_ref=artifact.artifact_id, payload_hash=artifact.content_hash,
        attribution="Australian Charities and Not-for-profits Commission",
    )
    catalog.register_source_record(record)
    receipt = AcquisitionReceipt(
        record_id=deterministic_id("acq:", {"source_definition_id": _source_definition().record_id, "artifact_id": artifact.artifact_id, "locator": locator}),
        created_at=now, producer={"kind": "code", "producer_id": "phase5-top100-subject-bootstrap", "version": "1"},
        source_definition_id=_source_definition().record_id, requested_locator=locator, resolved_locator=locator,
        retrieved_at=datetime(2026, 8, 10, tzinfo=timezone.utc), outcome="available", response_status=200,
        media_type="text/csv", content_hash=artifact.content_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id,
        tool_id="archive-reuse", tool_version="1", material_parameters={"source_id": ARCHIVE_SOURCE_ID, "abn": abn},
    )
    catalog.record_acquisition_receipt(receipt)
    return source_record_id, artifact.content_hash


def bootstrap_cohort(*, catalog_path: Path, runtime_root: Path, cohort_path: Path, archive_csv: Path, allow_network: bool = False) -> list[dict[str, Any]]:
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))["selected"]
    if len(cohort) != 100 or {row["donation_rank_2024_public"] for row in cohort} != set(range(1, 101)) or len({row["abn"] for row in cohort}) != 100:
        raise RuntimeError("Top-100 cohort is not exactly the frozen ranks 1-100 with unique ABNs")
    archive_bytes = archive_csv.read_bytes()
    if hashlib.sha256(archive_bytes).hexdigest() != ARCHIVE_SOURCE_HASH:
        raise RuntimeError("archive CSV hash does not match governed ACNC source metadata")
    archive = _archive_rows(archive_csv, cohort)
    missing_archive = {str(row["abn"]) for row in cohort} - set(archive)
    if missing_archive and not allow_network:
        raise RuntimeError(f"exact ACNC archive rows missing for {sorted(missing_archive)}")
    catalog = SQLiteCatalog(catalog_path).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,), catalog=catalog)
    now = datetime.now(timezone.utc)
    source_definition = _source_definition()
    if catalog.get_source_definition(source_definition.record_id) is None:
        catalog.register_source_definition(source_definition)
    rows: list[dict[str, Any]] = []
    try:
        for cohort_row in sorted(cohort, key=lambda row: row["donation_rank_2024_public"]):
            abn = str(cohort_row["abn"])
            existing = _existing_subject(catalog, abn)
            if existing:
                _repair_identity_authority_ref(catalog, existing["subject_id"])
                source = catalog.get_source_record(existing["acnc_source_record_id"])
                subject_material = json.loads(existing["material_json"])
                created_by_bootstrap = (subject_material.get("producer") or {}).get("producer_id") == "phase5-top100-subject-bootstrap"
                archive_subject = bool(source and source.get("source_version") == ARCHIVE_SOURCE_ID)
                status = "created_from_reused_acnc_source" if created_by_bootstrap and archive_subject else "created_from_new_acnc_acquisition" if created_by_bootstrap else "reused_existing_subject"
                rows.append({"rank": cohort_row["donation_rank_2024_public"], "abn": abn, "subject_id": existing["subject_id"], "status": status, "acnc_source_record_id": existing["acnc_source_record_id"], "source_artifact_hash": source.get("payload_hash") if source else None, "identity_policy_id": POLICY, "display_name": subject_material.get("display_name"), "acquisition_state": "reused_existing_bootstrap_identity" if created_by_bootstrap else "reused_existing_governed_identity", "blocking_reason": None})
                continue
            if abn in archive:
                name = archive[abn]["name"]
                source_record_id, artifact_hash = _register_archive_source(catalog, store, archive_bytes, abn, now)
                status = "created_from_reused_acnc_source"
                acquisition_state = "reused_archived_acnc_register"
            elif allow_network:
                locator, body, name = fetch_register_record(abn)
                artifact = store.put(body, created_at=now)
                artifact_hash = artifact.content_hash
                source_record_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": SOURCE_VERSION, "source_locator": locator, "payload_hash": artifact_hash})
                catalog.register_source_record(SourceRecord(record_id=source_record_id, created_at=now, producer={"kind": "code", "producer_id": "phase5-top100-subject-bootstrap", "version": "1"}, source_family="acnc_register", source_role="register_identity", source_version=SOURCE_VERSION, source_locator=locator, retrieved_at=now, observed_at=now, media_type="application/json", payload_ref=artifact.artifact_id, payload_hash=artifact_hash, attribution="Australian Charities and Not-for-profits Commission"))
                catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=deterministic_id("acq:", {"source_definition_id": source_definition.record_id, "artifact_id": artifact.artifact_id}), created_at=now, producer={"kind": "code", "producer_id": "phase5-top100-subject-bootstrap", "version": "1"}, source_definition_id=source_definition.record_id, requested_locator=locator, resolved_locator=locator, retrieved_at=now, outcome="available", response_status=200, media_type="application/json", content_hash=artifact_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib"))
                status = "created_from_new_acnc_acquisition"
                acquisition_state = "new_acnc_exact_lookup_and_entity_retrieval"
            else:
                raise RuntimeError(f"no exact ACNC identity material for {abn}")
            subject_id = new_opaque_id("subject:")
            subject = SubjectRecord(record_id=new_opaque_id("subjectrecord:"), created_at=now, producer={"kind": "code", "producer_id": "phase5-top100-subject-bootstrap", "version": "1"}, subject_id=subject_id, subject_kind="unknown", lifecycle_status="active", display_name=name, external_identifiers=(ExternalIdentifier(scheme="ABN", value=abn, issuing_authority="Australian Business Register", source_record_ids=(source_record_id,)),), identity_authority_refs=(ArtifactRef(artifact_id=source_record_id, content_hash=_source_record_hash(catalog, source_record_id), schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),), identity_policy_id=POLICY)
            catalog.register_subject(subject)
            rows.append({"rank": cohort_row["donation_rank_2024_public"], "abn": abn, "subject_id": subject_id, "status": status, "acnc_source_record_id": source_record_id, "source_artifact_hash": artifact_hash, "identity_policy_id": POLICY, "display_name": name, "acquisition_state": acquisition_state, "blocking_reason": None})
        return rows
    finally:
        catalog.close()


def identity_map_hash(rows: list[dict[str, Any]]) -> str:
    return canonical_sha256(sorted(rows, key=lambda row: row["rank"]))
