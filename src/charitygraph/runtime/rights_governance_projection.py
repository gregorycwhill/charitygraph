"""Private, rebuildable SQLite projection for governed rights records.

The content-addressed files managed by :mod:`rights_governance_record` remain
the authority.  This module stores only record/event identities, hashes,
lifecycle state and safe query metadata.  It never stores private record bodies
and it has no provider or source-acquisition behaviour.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from ..contracts.canonical import canonical_json_bytes
from .catalog import SQLiteCatalog
from .rights_governance_record import (
    RightsGovernanceEvent,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    RightsStorageError,
    resolve_current,
    validate_history,
)


class RightsProjectionError(ValueError):
    """Fail-closed error for projection input or materialization state."""


def _sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _binding_hash(record: RightsGovernanceRecord) -> str:
    return _sha256_json({"binding": record.binding_key, "scope": record.scope})


def _lineage_hash(record: RightsGovernanceRecord) -> str:
    return _sha256_json(record.acquisition_lineage_ids)


class RightsGovernanceProjection:
    """Versioned SQLite projection backed by an explicit private root."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        self._catalog = SQLiteCatalog(database_path, busy_timeout_ms=busy_timeout_ms)
        self._opened = False

    @property
    def database_path(self) -> Path:
        return self._catalog.path

    def open(self, *, initialize: bool = False) -> "RightsGovernanceProjection":
        self._catalog.open(initialize=initialize)
        self._opened = True
        return self

    def close(self) -> None:
        self._catalog.close()
        self._opened = False

    def __enter__(self) -> "RightsGovernanceProjection":
        return self.open()

    def __exit__(self, *_: Any) -> None:
        self.close()

    def migrate(self) -> int:
        self._require_open()
        return self._catalog.migrate()

    def _require_open(self) -> None:
        if not self._opened:
            raise RightsProjectionError("projection is not open; call open() explicitly")

    @staticmethod
    def _restore_events(
        store: RightsGovernanceStore,
        records: dict[str, RightsGovernanceRecord],
    ) -> tuple[RightsGovernanceEvent, ...]:
        """Load every private event and require its record target to exist."""

        events_root = store.root / "events" / "sha256"
        if not events_root.exists():
            return ()
        if events_root.is_symlink() or not events_root.is_dir():
            raise RightsStorageError("rights event tree is not a safe directory")

        loaded: list[RightsGovernanceEvent] = []
        for prefix in sorted(events_root.iterdir(), key=lambda item: item.name):
            if prefix.is_symlink() or not prefix.is_dir() or len(prefix.name) != 2:
                raise RightsStorageError("rights event tree contains an unsafe entry")
            for path in sorted(prefix.iterdir(), key=lambda item: item.name):
                if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                    raise RightsStorageError("rights event tree contains an unsafe entry")
                event = store.load_event(path.stem)
                if event.record_id not in records:
                    raise RightsProjectionError("rights event target record is missing")
                loaded.append(event)
        return tuple(sorted(loaded, key=lambda item: str(item.event_id)))

    @classmethod
    def _authoritative_material(
        cls,
        store: RightsGovernanceStore,
        *,
        as_of: date,
    ) -> tuple[tuple[RightsGovernanceRecord, ...], tuple[RightsGovernanceEvent, ...], tuple[RightsGovernanceRecord, ...]]:
        try:
            records = validate_history(store.restore_records())
            by_id = {record.content_hash: record for record in records}
            events = cls._restore_events(store, by_id)
            current = resolve_current(records, as_of=as_of)
        except RightsProjectionError:
            raise
        except Exception as exc:
            raise RightsProjectionError("private rights authority rejected projection input") from exc
        return records, events, tuple(sorted(current, key=_binding_hash))

    @staticmethod
    def _record_insert_order(records: Iterable[RightsGovernanceRecord]) -> tuple[RightsGovernanceRecord, ...]:
        """Return a deterministic predecessor-before-successor order."""

        remaining = {record.content_hash: record for record in records}
        ordered: list[RightsGovernanceRecord] = []
        while remaining:
            ready = sorted(
                (
                    record
                    for record in remaining.values()
                    if (record.supersedes_record_id is None or record.supersedes_record_id not in remaining)
                    and (record.revokes_record_id is None or record.revokes_record_id not in remaining)
                ),
                key=lambda record: record.content_hash,
            )
            if not ready:
                raise RightsProjectionError("rights lifecycle contains a competing successor or cycle")
            for record in ready:
                ordered.append(record)
                del remaining[record.content_hash]
        return tuple(ordered)

    @staticmethod
    def _insert_record(conn: Any, record: RightsGovernanceRecord) -> None:
        conn.execute(
            """
            INSERT INTO rights_projection_records(
                record_id, decision_id, subject_id, scope, source_artifact_id,
                source_record_id, source_role, representation_artifact_id,
                representation_sha256, acquisition_lineage_hash, binding_hash,
                rights_basis, rights_policy_id, rights_policy_version,
                provider_processing_policy_id, provider_processing_policy_version,
                status, review_status, expires_on, supersedes_record_id,
                revokes_record_id, local_retention_status,
                provider_transmission_status, public_redistribution_status,
                actor_kind, actor_id, recorded_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record.content_hash,
                record.decision_id,
                record.subject_id,
                record.scope,
                record.source_artifact_id,
                record.source_record_id,
                record.source_role,
                record.representation_artifact_id,
                str(record.representation_sha256),
                _lineage_hash(record),
                _binding_hash(record),
                record.rights_basis,
                record.rights_policy_id,
                record.rights_policy_version,
                record.provider_processing_policy_id,
                record.provider_processing_policy_version,
                record.status,
                record.review_status,
                record.expires_on.isoformat() if record.expires_on else None,
                record.supersedes_record_id,
                record.revokes_record_id,
                record.local_retention.status,
                record.provider_transmission.status,
                record.public_redistribution.status,
                record.actor_kind,
                record.actor_id,
                record.recorded_at.isoformat(),
            ),
        )

    @staticmethod
    def _insert_event(conn: Any, event: RightsGovernanceEvent) -> None:
        conn.execute(
            """
            INSERT INTO rights_projection_events(
                event_id, record_id, event_type, actor_kind, actor_id,
                recorded_at, content_hash
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                event.event_id,
                event.record_id,
                event.event_type,
                event.actor_kind,
                event.actor_id,
                event.recorded_at.isoformat(),
                event.event_id,
            ),
        )

    def rebuild_from_store(self, store: RightsGovernanceStore, *, as_of: date) -> str:
        """Wipe and rebuild the projection transactionally from private authority."""

        self._require_open()
        records, events, current = self._authoritative_material(store, as_of=as_of)
        ordered_records = self._record_insert_order(records)

        try:
            with self._catalog._connection(immediate=True) as conn:
                try:
                    conn.execute("DELETE FROM rights_projection_current")
                    conn.execute("DELETE FROM rights_projection_events")
                    conn.execute("DELETE FROM rights_projection_records")
                    for record in ordered_records:
                        self._insert_record(conn, record)
                    for event in events:
                        self._insert_event(conn, event)
                    for record in current:
                        conn.execute(
                            "INSERT INTO rights_projection_current(binding_hash, record_id, as_of) VALUES (?,?,?)",
                            (_binding_hash(record), record.content_hash, as_of.isoformat()),
                        )
                    self._catalog._commit(conn)
                except Exception:
                    conn.rollback()
                    raise
        except Exception as exc:
            if isinstance(exc, RightsProjectionError):
                raise
            raise RightsProjectionError("rights projection rebuild failed and was rolled back") from exc
        return self.snapshot_hash()

    def ingest(self, store: RightsGovernanceStore, *, as_of: date) -> str:
        """Alias for the explicit full authoritative rebuild operation."""

        return self.rebuild_from_store(store, as_of=as_of)

    def _rows(self, table: str, order_by: str) -> tuple[dict[str, Any], ...]:
        self._require_open()
        if table not in {
            "rights_projection_records",
            "rights_projection_events",
            "rights_projection_current",
        }:
            raise RightsProjectionError("unknown rights projection table")
        with self._catalog._connection() as conn:
            return tuple(dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}"))

    def snapshot(self) -> dict[str, tuple[dict[str, Any], ...]]:
        return {
            "records": self._rows("rights_projection_records", "record_id"),
            "events": self._rows("rights_projection_events", "event_id"),
            "current": self._rows("rights_projection_current", "binding_hash"),
        }

    def snapshot_hash(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.snapshot())).hexdigest()

    def current_record(
        self,
        *,
        record_id: str,
        subject_id: str,
        scope: str,
        as_of: date,
    ) -> dict[str, Any] | None:
        """Return one verified v29 current row for an exact authority binding.

        The row is only a lookup index.  Callers must still reload the
        content-addressed record from ``RightsGovernanceStore`` and compare
        its identity fields.  A stale, incomplete, duplicate, or internally
        inconsistent current projection fails closed.
        """

        snapshot = self.snapshot()
        current_rows = snapshot["current"]
        if not current_rows:
            return None
        expected_as_of = as_of.isoformat()
        if any(row.get("as_of") != expected_as_of for row in current_rows):
            raise RightsProjectionError("rights current projection is not materialized for the requested date")

        records = {str(row["record_id"]): row for row in snapshot["records"]}
        for current in current_rows:
            current_record_id = str(current.get("record_id", ""))
            row = records.get(current_record_id)
            if row is None:
                raise RightsProjectionError("rights current projection references a missing record")
            if current.get("binding_hash") != row.get("binding_hash"):
                raise RightsProjectionError("rights current projection binding hash is corrupt")

        matches = [
            row for row in records.values()
            if row.get("record_id") == record_id
            and row.get("subject_id") == subject_id
            and row.get("scope") == scope
            and any(current.get("record_id") == record_id for current in current_rows)
        ]
        current_match_count = sum(1 for current in current_rows if current.get("record_id") == record_id)
        if current_match_count > 1 or len(matches) > 1:
            raise RightsProjectionError("rights current projection contains duplicate current records")
        return matches[0] if matches else None


__all__ = ["RightsGovernanceProjection", "RightsProjectionError"]
