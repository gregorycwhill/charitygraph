import hashlib
import sqlite3

import pytest

from charitygraph.contracts import EvidenceLocator
from charitygraph.native_program_discovery import build_discovery_task_v2
from charitygraph.phase5_evidence_addressing import canonical_discovery_proof_task, canonical_locator, direct_service_scope_candidates
from charitygraph.phase5_semantic_contracts import executable_contract_for
from charitygraph.runtime.catalog import CatalogError, SQLiteCatalog


def _db(path, *, source=True, payload_hash="a" * 64):
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE source_records (source_record_id TEXT PRIMARY KEY, source_family TEXT, source_role TEXT, source_locator TEXT, payload_ref TEXT, payload_hash TEXT);
    CREATE TABLE evidence_locators (evidence_locator_id TEXT PRIMARY KEY, artifact_id TEXT, source_record_id TEXT, kind TEXT, locator_json TEXT, material_hash TEXT);
    CREATE TABLE artifact_index (artifact_id TEXT PRIMARY KEY, content_hash TEXT, schema_id TEXT, schema_version TEXT, storage_path TEXT, availability TEXT, created_at TEXT, indexed_at TEXT);
    CREATE TABLE subject_scopes (scope_id TEXT, subject_id TEXT, scope_kind TEXT, label TEXT, lifecycle_status TEXT);
    """)
    if source:
        c.execute("INSERT INTO source_records VALUES (?,?,?,?,?,?)", ("srcrec:acnc", "acnc_register", "register_identity", "https://example.test/acnc", "srcblob:" + (payload_hash or "a" * 64), payload_hash))
    c.commit(); c.close()


def test_source_record_locator_requires_no_artifact_index_and_builds_task(tmp_path):
    content = b"retained ACNC payload"
    digest = hashlib.sha256(content).hexdigest()
    db = tmp_path / "catalog.sqlite3"; _db(db, payload_hash=digest)
    locator = EvidenceLocator(kind="document", source_record_id="srcrec:acnc", locator="https://example.test/acnc")
    c = sqlite3.connect(db)
    c.execute("INSERT INTO evidence_locators VALUES (?,?,?,?,?,?)", ("locator:acnc", None, "srcrec:acnc", "document", locator.model_dump_json(), "c" * 64)); c.commit(); c.close()
    catalog = SQLiteCatalog(db).open()
    task = build_discovery_task_v2(catalog, subject_id="subject:" + "a" * 32, evidence_ids=["locator:acnc"], prompt_template_id="p", prompt_template_version="1", provider_id="openai", model_snapshot="gpt-5.6-luna")
    assert task.evidence_inputs[0].content_hash == digest
    assert catalog.get_artifact("srcblob:" + digest) is None


def test_source_record_locator_identity_ignores_optional_artifact_index(tmp_path):
    row = {"source_record_id": "srcrec:acnc", "artifact_id": "srcblob:" + "a" * 64, "source_locator": "https://example.test/acnc"}
    first = canonical_locator(row).model_dump()
    second = canonical_locator({**row, "artifact_id": "srcblob:" + "b" * 64}).model_dump()
    assert first == second
    assert first["artifact_id"] is None


def test_missing_source_record_fails_closed(tmp_path):
    db = tmp_path / "catalog.sqlite3"; _db(db, source=False)
    c = SQLiteCatalog(db).open()
    with pytest.raises(CatalogError, match="unknown evidence"):
        build_discovery_task_v2(c, subject_id="subject:" + "a" * 32, evidence_ids=["missing"], prompt_template_id="p", prompt_template_version="1", provider_id="openai", model_snapshot="gpt-5.6-luna")


def test_missing_payload_hash_fails_closed(tmp_path):
    db = tmp_path / "catalog.sqlite3"; _db(db, payload_hash=None)
    c = sqlite3.connect(db); c.execute("UPDATE source_records SET payload_hash=NULL"); c.execute("INSERT INTO evidence_locators VALUES (?,?,?,?,?,?)", ("locator:acnc", None, "srcrec:acnc", "document", "{}", "c" * 64)); c.commit(); c.close()
    catalog = SQLiteCatalog(db).open()
    with pytest.raises(CatalogError, match="no recoverable content hash"):
        build_discovery_task_v2(catalog, subject_id="subject:" + "a" * 32, evidence_ids=["locator:acnc"], prompt_template_id="p", prompt_template_version="1", provider_id="openai", model_snapshot="gpt-5.6-luna")


def test_readiness_uses_canonical_production_discovery_identity():
    task = canonical_discovery_proof_task(subject_id="subject:" + "a" * 32, evidence_corpus_hash="a" * 64, logical_task_id="semtask:proof")
    contract = executable_contract_for(task)
    assert (task["task_profile"], task["task_profile_version"]) == ("program_service_discovery", "1")
    assert contract.provider_schema_name == "program_service_discovery_v2"
    invalid = dict(task, task_profile_version="2")
    with pytest.raises(ValueError, match="no semantic contract"):
        executable_contract_for(invalid)


def test_direct_service_scope_candidates_require_both_governed_source_families():
    rows = [
        {"subject_id": "subject:a", "status": "eligible", "source_family": "acnc_ais_bundle"},
        {"subject_id": "subject:a", "status": "eligible", "source_family": "official_website"},
        {"subject_id": "subject:b", "status": "eligible", "source_family": "acnc_ais_bundle"},
        {"subject_id": "subject:c", "status": "not_available", "source_family": "official_website"},
    ]
    candidates = direct_service_scope_candidates(rows)
    assert [row["subject_id"] for row in candidates] == ["subject:a"]
