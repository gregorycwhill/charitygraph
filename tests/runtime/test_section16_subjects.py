from datetime import datetime, timezone

from charitygraph.contracts import SchemaRef, SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.runtime import SQLiteCatalog
from charitygraph.section16_subjects import ensure_section16_subject


def test_unseen_authoritative_org_registration_is_idempotent(tmp_path):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    catalog = SQLiteCatalog(tmp_path / "catalogue.sqlite3").open(initialize=True)
    source_id = deterministic_id("srcrec:", {"source_family": "acnc_register", "source_version": "1", "source_locator": "fixture:acnc", "payload_hash": "a" * 64})
    catalog.register_source_record(SourceRecord(
        record_id=source_id, created_at=now, producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_family="acnc_register", source_role="identity", source_version="1", source_locator="fixture:acnc",
        observed_at=now, payload_ref="srcblob:" + "a" * 64, payload_hash="a" * 64,
    ))
    first, created = ensure_section16_subject(catalog, abn="20 609 977 764", display_name="Example Australia Ltd", source_record_id=source_id, now=now)
    second, reused = ensure_section16_subject(catalog, abn="20 609 977 764", display_name="Example Australia Ltd", source_record_id=source_id, now=now)
    assert created is True and reused is False and first == second
    with catalog._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM subjects WHERE subject_id=?", (first,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM external_identifiers WHERE subject_id=?", (first,)).fetchone()[0] == 1
    catalog.close()
