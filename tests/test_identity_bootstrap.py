from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from charitygraph.contracts import ArtifactRef, SchemaRef, SourceRecord, SubjectRecord, deterministic_id
from charitygraph.identity_bootstrap import _archive_rows, _verify_identity_authority_ref, identity_map_hash
from charitygraph.runtime import SQLiteCatalog


def test_archive_identity_rows_require_exact_abn_and_name(tmp_path: Path) -> None:
    path = tmp_path / "register.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ABN", "Charity_Legal_Name"])
        writer.writeheader()
        writer.writerow({"ABN": "12345678901", "Charity_Legal_Name": "Exact Charity"})
    assert _archive_rows(path, [{"abn": "12345678901"}]) == {"12345678901": {"name": "Exact Charity"}}


def test_archive_identity_rows_reject_missing_exact_match(tmp_path: Path) -> None:
    path = tmp_path / "register.csv"
    path.write_text("ABN,Charity_Legal_Name\n12345678901,\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no registered name"):
        _archive_rows(path, [{"abn": "12345678901"}])


def test_identity_map_hash_is_order_independent_and_subject_ids_are_opaque() -> None:
    rows = [
        {"rank": 2, "abn": "22345678901", "subject_id": "subject:bbbb", "status": "created_from_reused_acnc_source"},
        {"rank": 1, "abn": "12345678901", "subject_id": "subject:aaaa", "status": "reused_existing_subject"},
    ]
    assert identity_map_hash(rows) == identity_map_hash(list(reversed(rows)))
    assert all(row["subject_id"] != f"subject:{row['abn']}" for row in rows)


def test_bootstrap_module_has_no_semantic_task_or_provider_entrypoint() -> None:
    text = Path("src/charitygraph/identity_bootstrap.py").read_text(encoding="utf-8")
    assert "responses.create" not in text
    assert "model_task" not in text
    assert "provider_calls" not in text


def test_reused_subject_identity_authority_mismatch_fails_without_rewriting_subject(tmp_path: Path) -> None:
    """The bootstrap reuse path must not mutate governed subject identity evidence."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    source = SourceRecord(
        record_id=deterministic_id("srcrec:", {
            "source_family": "registry", "source_version": None,
            "source_locator": "fixture://identity", "payload_hash": "3" * 64,
        }), created_at=now,
        producer={"kind": "code", "producer_id": "fixture"}, source_family="registry",
        source_role="identity", source_locator="fixture://identity", observed_at=now,
        payload_ref="artifact:" + "2" * 32, payload_hash="3" * 64,
    )
    catalog.register_source_record(source)
    subject = SubjectRecord(
        record_id="subjectrecord:" + "4" * 32, created_at=now,
        producer={"kind": "human", "producer_id": "reviewer"}, subject_id="subject:" + "5" * 32,
        subject_kind="organisation", lifecycle_status="active", identity_policy_id="identity-v1",
        identity_authority_refs=(ArtifactRef(
            artifact_id=source.record_id, content_hash="0" * 64,
            schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0"),
        ),),
    )
    catalog.register_subject(subject)
    before = catalog.get_subject(subject.subject_id)
    with pytest.raises(RuntimeError, match="explicit identity correction"):
        _verify_identity_authority_ref(catalog, subject.subject_id)
    assert catalog.get_subject(subject.subject_id) == before
