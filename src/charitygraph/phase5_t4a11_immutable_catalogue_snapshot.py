"""Provider-free preflight for one immutable SQLite catalogue main file.

This is deliberately a file preflight, not a catalogue reader or accounting
authority.  The caller supplies the source identity and expected bytes hash.
Only an explicitly closed, immutable main-file snapshot is eligible for the
read-only SQLite inspection; WAL, SHM and journal state fail closed.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SnapshotStatus = Literal["CANDIDATE_NOT_ATTESTED", "NOT_ATTESTABLE"]
_SQLITE_HEADER = b"SQLite format 3\x00"
_REQUIRED_IDENTITY = (
    "source_id",
    "source_kind",
    "source_version",
    "snapshot_id",
    "snapshot_kind",
    "source_status",
    "active",
    "mutable",
    "content_sha256",
)
_SIDE_CAR_SUFFIXES = ("-wal", "-shm", "-journal")
_SAFE_JOURNAL_MODES = {"delete", "truncate", "persist"}
_NOT_ATTESTED_COVERAGE = {
    "project_completeness": "NOT_ATTESTED",
    "pricing": "NOT_ATTESTED",
    "fx": "NOT_ATTESTED",
    "route": "NOT_ATTESTED",
    "aud_spend": "NOT_ATTESTED",
}


@dataclass(frozen=True)
class ImmutableCatalogueSnapshot:
    """Deterministic inspection metadata; never an independent attestation."""

    status: SnapshotStatus
    main_file: str
    source_identity: Mapping[str, object] | None = None
    sha256: str | None = None
    schema_header: Mapping[str, object] | None = None
    schema_version: int | None = None
    table_row_counts: Mapping[str, int] = field(default_factory=dict)
    table_row_count_coverage: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    coverage: Mapping[str, str] = field(default_factory=dict)
    sidecars_present: tuple[str, ...] = ()
    query_only: bool = False
    sqlite_uri: str | None = None
    diagnostics: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a stable, JSON-friendly diagnostic representation."""

        return {
            "status": self.status,
            "main_file": self.main_file,
            "source_identity": None if self.source_identity is None else dict(self.source_identity),
            "sha256": self.sha256,
            "schema_header": None if self.schema_header is None else dict(self.schema_header),
            "schema_version": self.schema_version,
            "table_row_counts": dict(self.table_row_counts or {}),
            "table_row_count_coverage": {
                name: dict(value) for name, value in (self.table_row_count_coverage or {}).items()
            },
            "coverage": dict(self.coverage or {}),
            "sidecars_present": list(self.sidecars_present),
            "query_only": self.query_only,
            "sqlite_uri": self.sqlite_uri,
            "diagnostics": list(self.diagnostics),
        }


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        char in "0123456789abcdef" for char in value
    )


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sidecars(path: Path) -> tuple[str, ...]:
    return tuple(str(candidate) for candidate in (Path(str(path) + suffix) for suffix in _SIDE_CAR_SUFFIXES) if candidate.exists())


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _header_metadata(data: bytes, reasons: list[str]) -> dict[str, object] | None:
    if len(data) < 100:
        reasons.append("sqlite_header_truncated")
        return None
    if data[:16] != _SQLITE_HEADER:
        reasons.append("sqlite_header_magic_invalid")
        return None
    page_size = int.from_bytes(data[16:18], "big")
    page_size = 65536 if page_size == 1 else page_size
    schema_format = int.from_bytes(data[44:48], "big")
    if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
        reasons.append("sqlite_header_page_size_invalid")
    if data[18] not in (1, 2) or data[19] not in (1, 2):
        reasons.append("sqlite_header_format_version_invalid")
    if data[18] == 2 or data[19] == 2:
        reasons.append("sqlite_header_wal_format_not_allowed")
    if schema_format not in (1, 2, 3, 4):
        reasons.append("sqlite_header_schema_format_invalid")
    return {
        "magic": _SQLITE_HEADER.decode("ascii", errors="strict"),
        "page_size": page_size,
        "write_format": data[18],
        "read_format": data[19],
        "schema_format": schema_format,
        "user_version": int.from_bytes(data[92:96], "big"),
    }


def _identity_diagnostics(identity: object, expected_sha256: str) -> tuple[dict[str, object] | None, list[str]]:
    if not isinstance(identity, Mapping):
        return None, ["source_identity_missing_or_invalid"]
    value = dict(identity)
    reasons = [f"source_identity_field_missing:{name}" for name in _REQUIRED_IDENTITY if name not in value]
    for name in ("source_id", "source_kind", "source_version", "snapshot_id"):
        if name in value and not _non_empty_text(value[name]):
            reasons.append(f"source_identity_{name}_invalid")
    if value.get("snapshot_kind") != "immutable_sqlite_main_file":
        reasons.append("source_snapshot_kind_not_immutable_sqlite_main_file")
    if value.get("source_status") != "closed":
        reasons.append("source_status_not_closed")
    if value.get("active") is not False:
        reasons.append("active_source_indicator_present")
    if value.get("mutable") is not False:
        reasons.append("mutable_source_indicator_present")
    if not _valid_sha256(value.get("content_sha256")):
        reasons.append("source_identity_content_sha256_invalid")
    elif value.get("content_sha256") != expected_sha256:
        reasons.append("source_identity_content_sha256_mismatch")
    for name in ("writable", "write_in_progress", "in_progress", "source_active", "source_mutable"):
        if name in value and value[name] is not False:
            reasons.append(f"{name}_indicator_present")
    return value, reasons


def _migration_schema_version(
    conn: sqlite3.Connection,
    expected: int,
    reasons: list[str],
) -> int | None:
    tables = {
        str(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT name, type FROM sqlite_master WHERE name = 'schema_migrations'"
        ).fetchall()
    }
    if tables.get("schema_migrations") != "table":
        reasons.append("schema_version_authority_missing")
        return None
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(\"schema_migrations\")").fetchall()}
    if not {"version", "name", "checksum"}.issubset(columns):
        reasons.append("schema_version_authority_invalid")
        return None
    rows = conn.execute("SELECT version FROM \"schema_migrations\" ORDER BY version").fetchall()
    versions = [row[0] for row in rows]
    if not versions or any(not isinstance(version, int) or version < 1 for version in versions):
        reasons.append("schema_version_rows_missing_or_invalid")
        return None
    if versions != list(range(1, max(versions) + 1)):
        reasons.append("schema_version_sequence_invalid")
    version = max(versions)
    if version != expected:
        reasons.append(f"schema_version_mismatch:expected={expected}:observed={version}")
    return version


def _row_counts(conn: sqlite3.Connection, reasons: list[str]) -> tuple[dict[str, int], dict[str, Mapping[str, object]]]:
    counts: dict[str, int] = {}
    coverage: dict[str, Mapping[str, object]] = {}
    objects = conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for row in objects:
        name = str(row[0])
        quoted = '"' + name.replace('"', '""') + '"'
        try:
            count = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
        except sqlite3.Error:
            reasons.append(f"table_row_count_unavailable:{name}")
            continue
        counts[name] = count
        coverage[name] = {"state": "OBSERVED", "row_count": count, "object_type": str(row[1])}
    return counts, coverage


def _result(
    path: Path,
    *,
    status: SnapshotStatus,
    identity: Mapping[str, object] | None,
    sha256: str | None,
    header: Mapping[str, object] | None,
    schema_version: int | None,
    table_row_counts: Mapping[str, int] | None = None,
    table_row_count_coverage: Mapping[str, Mapping[str, object]] | None = None,
    sidecars: tuple[str, ...] = (),
    query_only: bool = False,
    uri: str | None = None,
    reasons: list[str] | None = None,
) -> ImmutableCatalogueSnapshot:
    return ImmutableCatalogueSnapshot(
        status=status,
        main_file=str(path),
        source_identity=identity,
        sha256=sha256,
        schema_header=header,
        schema_version=schema_version,
        table_row_counts=table_row_counts or {},
        table_row_count_coverage=table_row_count_coverage or {},
        coverage={
            "enumerated_table_rows": "OBSERVED",
            "missing_or_empty_views": "NOT_ATTESTED",
            **_NOT_ATTESTED_COVERAGE,
        },
        sidecars_present=sidecars,
        query_only=query_only,
        sqlite_uri=uri,
        diagnostics=_unique(reasons or []),
    )


def preflight_immutable_catalogue_snapshot(
    main_file: str | Path,
    *,
    expected_sha256: str,
    source_identity: Mapping[str, object],
    expected_schema_version: int,
) -> ImmutableCatalogueSnapshot:
    """Inspect one caller-pinned SQLite main file without mutating it.

    A successful result is only ``CANDIDATE_NOT_ATTESTED``.  It describes the
    bytes and rows observed in this one file; it does not establish project
    completeness, pricing, FX, route authority or AUD spend.
    """

    path = Path(main_file)
    reasons: list[str] = []
    identity, identity_reasons = _identity_diagnostics(source_identity, expected_sha256)
    reasons.extend(identity_reasons)
    if not _valid_sha256(expected_sha256):
        reasons.append("expected_sha256_invalid")
    if isinstance(expected_schema_version, bool) or not isinstance(expected_schema_version, int) or expected_schema_version < 1:
        reasons.append("expected_schema_version_invalid")

    if not path.exists():
        reasons.append("main_file_missing")
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=None, header=None, schema_version=None, reasons=reasons)
    if not path.is_file():
        reasons.append("main_file_not_regular_file")
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=None, header=None, schema_version=None, reasons=reasons)
    if path.is_symlink():
        reasons.append("main_file_symlink_not_allowed")
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=None, header=None, schema_version=None, reasons=reasons)

    before_sidecars = _sidecars(path)
    if before_sidecars:
        reasons.append("mutable_sidecar_present")
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=None, header=None, schema_version=None, sidecars=before_sidecars, reasons=reasons)

    try:
        before_hash, _ = _hash_file(path)
        header = _header_metadata(path.read_bytes()[:100], reasons)
    except OSError:
        reasons.append("main_file_unreadable")
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=None, header=None, schema_version=None, reasons=reasons)
    if before_hash != expected_sha256:
        reasons.append("main_file_sha256_mismatch")
    if reasons:
        return _result(path, status="NOT_ATTESTABLE", identity=identity, sha256=before_hash, header=header, schema_version=None, reasons=reasons)

    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    conn: sqlite3.Connection | None = None
    query_only = False
    schema_version: int | None = None
    table_row_counts: dict[str, int] = {}
    table_coverage: dict[str, Mapping[str, object]] = {}
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("PRAGMA query_only = ON")
        query_only = conn.execute("PRAGMA query_only").fetchone()[0] == 1
        if not query_only:
            reasons.append("query_only_not_enabled")
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal_mode not in _SAFE_JOURNAL_MODES:
            reasons.append(f"mutable_journal_mode:{journal_mode}")
        schema_version = _migration_schema_version(conn, expected_schema_version, reasons)
        table_row_counts, table_coverage = _row_counts(conn, reasons)
    except (sqlite3.Error, OSError) as exc:
        reasons.append(f"sqlite_read_failed:{type(exc).__name__}")
    finally:
        if conn is not None:
            conn.close()

    try:
        after_hash, _ = _hash_file(path)
    except OSError:
        after_hash = None
        reasons.append("main_file_missing_after_read")
    after_sidecars = _sidecars(path)
    if after_hash != before_hash:
        reasons.append("main_file_changed_during_preflight")
    if after_sidecars:
        reasons.append("mutable_sidecar_created_during_preflight")
    all_sidecars = tuple(sorted(set(before_sidecars + after_sidecars)))
    status: SnapshotStatus = "CANDIDATE_NOT_ATTESTED" if not reasons else "NOT_ATTESTABLE"
    return _result(
        path,
        status=status,
        identity=identity,
        sha256=after_hash or before_hash,
        header=header,
        schema_version=schema_version,
        table_row_counts=table_row_counts,
        table_row_count_coverage=table_coverage,
        sidecars=all_sidecars,
        query_only=query_only,
        uri=uri,
        reasons=reasons,
    )


__all__ = ["ImmutableCatalogueSnapshot", "preflight_immutable_catalogue_snapshot"]
