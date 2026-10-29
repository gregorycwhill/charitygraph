import hashlib
import sqlite3
from pathlib import Path

from charitygraph.phase5_t4a11_immutable_catalogue_snapshot import (
    preflight_immutable_catalogue_snapshot,
)


EXPECTED_SCHEMA = 2


def _identity(file_hash: str, **overrides):
    value = {
        "source_id": "source:synthetic-catalogue",
        "source_kind": "sqlite-main-file-snapshot",
        "source_version": "fixture-v1",
        "snapshot_id": "snapshot:synthetic-1",
        "snapshot_kind": "immutable_sqlite_main_file",
        "source_status": "closed",
        "active": False,
        "mutable": False,
        "content_sha256": file_hash,
    }
    value.update(overrides)
    return value


def _make_database(path: Path, *, with_authority=True) -> str:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")
        if with_authority:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                [(1, "base", "a" * 64), (2, "fixture", "b" * 64)],
            )
        connection.execute("CREATE TABLE source_rows (source_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO source_rows VALUES ('source:one')")
        connection.execute("CREATE TABLE intentionally_empty (value TEXT)")
        connection.commit()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(path: Path, file_hash: str, **identity):
    return preflight_immutable_catalogue_snapshot(
        path,
        expected_sha256=file_hash,
        source_identity=_identity(file_hash, **identity),
        expected_schema_version=EXPECTED_SCHEMA,
    )


def test_successful_snapshot_returns_rows_identity_schema_and_explicit_non_attestation(tmp_path):
    path = tmp_path / "snapshot.sqlite3"
    file_hash = _make_database(path)

    result = _run(path, file_hash)

    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert result.source_identity["source_id"] == "source:synthetic-catalogue"
    assert result.sha256 == file_hash
    assert result.schema_version == EXPECTED_SCHEMA
    assert result.schema_header["magic"] == "SQLite format 3\x00"
    assert result.table_row_counts["source_rows"] == 1
    assert result.table_row_counts["intentionally_empty"] == 0
    assert result.table_row_count_coverage["intentionally_empty"]["state"] == "OBSERVED"
    assert all(result.coverage[key] == "NOT_ATTESTED" for key in ("project_completeness", "pricing", "fx", "route", "aud_spend"))
    assert result.query_only is True
    assert "mode=ro&immutable=1" in result.sqlite_uri


def test_preexisting_wal_and_shm_sidecars_are_rejected_without_opening(tmp_path):
    path = tmp_path / "snapshot.sqlite3"
    file_hash = _make_database(path)
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    wal.write_bytes(b"fixture wal")
    shm.write_bytes(b"fixture shm")

    result = _run(path, file_hash)

    assert result.status == "NOT_ATTESTABLE"
    assert result.sidecars_present == (str(path) + "-wal", str(path) + "-shm")
    assert "mutable_sidecar_present" in result.diagnostics
    assert wal.read_bytes() == b"fixture wal"
    assert shm.read_bytes() == b"fixture shm"


def test_missing_stale_and_changed_hashes_fail_closed(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    result = preflight_immutable_catalogue_snapshot(
        missing,
        expected_sha256="a" * 64,
        source_identity=_identity("a" * 64),
        expected_schema_version=EXPECTED_SCHEMA,
    )
    assert result.status == "NOT_ATTESTABLE"
    assert "main_file_missing" in result.diagnostics

    path = tmp_path / "stale.sqlite3"
    file_hash = _make_database(path)
    result = _run(path, "0" * 64)
    assert result.status == "NOT_ATTESTABLE"
    assert "main_file_sha256_mismatch" in result.diagnostics

    path.write_bytes(path.read_bytes() + b"changed")
    result = _run(path, file_hash)
    assert result.status == "NOT_ATTESTABLE"
    assert "main_file_sha256_mismatch" in result.diagnostics


def test_successful_preflight_leaves_directory_baseline_unchanged(tmp_path):
    path = tmp_path / "snapshot.sqlite3"
    file_hash = _make_database(path)
    before = sorted(item.name for item in tmp_path.iterdir())

    result = _run(path, file_hash)

    after = sorted(item.name for item in tmp_path.iterdir())
    assert result.status == "CANDIDATE_NOT_ATTESTED"
    assert after == before
    assert not Path(str(path) + "-wal").exists()
    assert not Path(str(path) + "-shm").exists()
    assert not Path(str(path) + "-journal").exists()


def test_missing_schema_authority_is_not_zero_or_not_attested(tmp_path):
    path = tmp_path / "without-authority.sqlite3"
    file_hash = _make_database(path, with_authority=False)

    result = _run(path, file_hash)

    assert result.status == "NOT_ATTESTABLE"
    assert result.schema_version is None
    assert "schema_version_authority_missing" in result.diagnostics
    assert result.coverage["project_completeness"] == "NOT_ATTESTED"
    assert result.coverage["aud_spend"] == "NOT_ATTESTED"


def test_active_or_mutable_source_identity_is_rejected_before_sqlite_open(tmp_path):
    path = tmp_path / "active.sqlite3"
    file_hash = _make_database(path)

    result = _run(path, file_hash, active=True)
    assert result.status == "NOT_ATTESTABLE"
    assert "active_source_indicator_present" in result.diagnostics

    result = _run(path, file_hash, mutable=True)
    assert result.status == "NOT_ATTESTABLE"
    assert "mutable_source_indicator_present" in result.diagnostics


def test_wal_journal_mode_is_rejected_as_potentially_incomplete(tmp_path):
    path = tmp_path / "wal.sqlite3"
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL)")
        connection.executemany("INSERT INTO schema_migrations VALUES (?, ?, ?)", [(1, "base", "a" * 64), (2, "fixture", "b" * 64)])
        connection.commit()
    finally:
        connection.close()
    wal = Path(str(path) + "-wal")
    if wal.exists():
        wal.unlink()
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    result = _run(path, file_hash)

    assert result.status == "NOT_ATTESTABLE"
    assert "sqlite_header_wal_format_not_allowed" in result.diagnostics
