from datetime import datetime, timezone
import sqlite3

import pytest

from charitygraph.runtime import MigrationError, SQLiteCatalog
import charitygraph.runtime.catalog as catalog_module
from charitygraph.runtime.migrations import MIGRATIONS, Migration, SUPPORTED_VERSION


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_new_database_migrates_reopens_and_integrity_is_green(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    catalog = SQLiteCatalog(path).open(initialize=True)
    assert catalog.migrate() == SUPPORTED_VERSION
    assert catalog.integrity_check() == "ok"
    catalog.close()
    reopened = SQLiteCatalog(path).open()
    assert reopened.migrate() == SUPPORTED_VERSION
    assert reopened.integrity_check() == "ok"


def test_v24_catalogue_upgrades_locator_subject_identifier_seam_without_rewriting_history(tmp_path, monkeypatch):
    path = tmp_path / "v24.sqlite3"
    original = catalog_module.MIGRATIONS
    monkeypatch.setattr(catalog_module, "MIGRATIONS", tuple(item for item in MIGRATIONS if item.version <= 24))
    SQLiteCatalog(path).open(initialize=True).migrate()
    monkeypatch.setattr(catalog_module, "MIGRATIONS", original)
    upgraded = SQLiteCatalog(path).open()
    assert upgraded.migrate() == SUPPORTED_VERSION
    with upgraded._connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(scale_s0_locator_discoveries)")}
    assert {"locator_subject_ref", "locator_identifier_scheme", "locator_identifier_value"} <= columns
    assert upgraded.integrity_check() == "ok"


def test_checksum_mismatch_and_future_version_fail_loudly(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    SQLiteCatalog(path).open(initialize=True).close()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE schema_migrations SET checksum='bad' WHERE version=1")
    with pytest.raises(MigrationError, match="checksum"):
        SQLiteCatalog(path).open().migrate()

    future = tmp_path / "future.sqlite3"
    SQLiteCatalog(future).open(initialize=True).close()
    with sqlite3.connect(future) as conn:
        conn.execute("INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (99, 'future', 'x', ?)", (NOW.isoformat(),))
    with pytest.raises(MigrationError, match="newer"):
        SQLiteCatalog(future).open().migrate()


def test_failed_migration_rolls_back_without_partial_schema(tmp_path, monkeypatch):
    path = tmp_path / "broken.sqlite3"
    original = catalog_module.MIGRATIONS
    monkeypatch.setattr(catalog_module, "MIGRATIONS", (Migration(1, "broken", "CREATE TABLE broken (id INTEGER); BAD SQL;"),))
    with pytest.raises(MigrationError):
        SQLiteCatalog(path).open().migrate()
    monkeypatch.setattr(catalog_module, "MIGRATIONS", original)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
