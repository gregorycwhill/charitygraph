"""Thin, rebuildable SQLite operational catalogue for Builder control state.

The catalogue stores identifiers, hashes and operational metadata only.  It is
never an evidence or model-response authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping

from .migrations import MIGRATIONS, SUPPORTED_VERSION


class CatalogError(RuntimeError):
    """Base exception for operational catalogue failures."""


class MigrationError(CatalogError):
    """Migration metadata or application failure."""


class ConflictError(CatalogError):
    """An idempotent key was reused with different material content."""


class InvalidTransitionError(CatalogError):
    """A task-state transition or lease operation is not permitted."""


class LeaseError(CatalogError):
    """The caller does not hold a valid, unexpired task lease."""


class BudgetExceededError(CatalogError):
    """A proposed reservation would exceed the pooled cohort cap."""


TASK_STATES = {
    "ready", "leased", "running", "succeeded", "failed_retryable", "failed_terminal", "held", "cancelled",
}
TERMINAL_TASK_STATES = {"succeeded", "failed_terminal", "cancelled"}
TASK_TRANSITIONS = {
    "ready": {"leased", "held", "cancelled"},
    "leased": {"running", "ready", "failed_retryable", "failed_terminal"},
    "running": {"succeeded", "failed_retryable", "failed_terminal", "held"},
    "failed_retryable": {"leased", "held", "cancelled"},
    "succeeded": set(), "failed_terminal": set(), "held": set(), "cancelled": set(),
}


def default_database_path(runtime_root: str | Path) -> Path:
    """Return the production path without creating a directory or database."""

    return Path(runtime_root) / "state" / "charitygraph.sqlite3"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python", by_alias=True)
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return value.value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python", by_alias=True)
    if isinstance(value, Mapping):
        return {str(k): _dump(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return value.value
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(_dump(value), sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _get(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _text(value: Any, field: str) -> str:
    if value is None or not str(value).strip():
        raise CatalogError(f"{field} is required")
    return str(value)


def _decimal(value: Any, field: str = "amount") -> Decimal:
    if isinstance(value, float):
        raise CatalogError(f"{field} cannot use binary float")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CatalogError(f"{field} must be a decimal") from exc
    if not result.is_finite():
        raise CatalogError(f"{field} must be finite")
    return result


def _money_amount(value: Any, field: str = "amount") -> Decimal:
    amount = _get(value, "amount", default=value)
    result = _decimal(amount, field)
    if result < 0:
        raise CatalogError(f"{field} must be non-negative")
    currency = _get(value, "currency")
    if currency is not None and str(currency) != "AUD":
        raise CatalogError(f"{field} must be AUD")
    return result


def _utc(value: datetime | str, field: str = "timestamp") -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CatalogError(f"{field} must be an ISO timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CatalogError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else dict(row)


@dataclass(frozen=True)
class BudgetPosition:
    cohort_id: str
    cohort_cap_aud: Decimal
    outstanding_reserved_exposure_aud: Decimal
    released_reserve_aud: Decimal
    actual_spend_aud: Decimal
    reservation_overrun_aud: Decimal
    unreserved_actual_aud: Decimal
    credits_aud: Decimal
    adjustment_debits_aud: Decimal
    adjustment_credits_aud: Decimal
    net_actual_spend_aud: Decimal
    committed_exposure_aud: Decimal
    remaining_budget_aud: Decimal
    breach: bool

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in result.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
        return result


class SQLiteCatalog:
    """A per-operation-connection SQLite catalogue with explicit transactions."""

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = int(busy_timeout_ms)
        if self.busy_timeout_ms <= 0:
            raise CatalogError("busy_timeout_ms must be positive")
        self._opened = False

    def open(self, *, initialize: bool = False) -> "SQLiteCatalog":
        """Open the catalogue lifecycle; initialize explicitly migrates it."""

        self._opened = True
        if initialize:
            self.migrate()
        return self

    def close(self) -> None:
        self._opened = False

    def __enter__(self) -> "SQLiteCatalog":
        return self.open()

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if not self._opened:
            raise CatalogError("catalogue is not open; call open() explicitly")

    @contextmanager
    def _connection(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        self._ensure_open()
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(self.path), timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        except sqlite3.Error as exc:
            raise CatalogError("could not open SQLite catalogue") from exc
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
            if self.path != Path(":memory:"):
                conn.execute("PRAGMA journal_mode = WAL")
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
        except CatalogError:
            if conn.in_transaction:
                conn.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            if conn.in_transaction:
                conn.rollback()
            raise ConflictError("SQLite catalogue constraint conflict") from exc
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.rollback()
            raise CatalogError("SQLite catalogue operation failed") from exc
        finally:
            conn.close()

    @staticmethod
    def _commit(conn: sqlite3.Connection) -> None:
        conn.commit()

    def migrate(self) -> int:
        self._ensure_open()
        try:
            with self._connection(immediate=True) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)")
                rows = conn.execute("SELECT version, name, checksum FROM schema_migrations ORDER BY version").fetchall()
                applied = {int(row[0]): (row[1], row[2]) for row in rows}
                if applied and max(applied) > SUPPORTED_VERSION:
                    raise MigrationError("database is newer than supported application version")
                for migration in MIGRATIONS:
                    if migration.version in applied:
                        name, checksum = applied[migration.version]
                        if name != migration.name or checksum != migration.checksum:
                            raise MigrationError(f"migration checksum mismatch at version {migration.version}")
                        continue
                    if migration.version != (max(applied) + 1 if applied else 1):
                        raise MigrationError("migration versions must be applied in order")
                    for statement in migration.sql.split(";"):
                        if statement.strip():
                            conn.execute(statement)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                        (migration.version, migration.name, migration.checksum, datetime.now(timezone.utc).isoformat()),
                    )
                    applied[migration.version] = (migration.name, migration.checksum)
                self._commit(conn)
                return max(applied) if applied else 0
        except MigrationError:
            raise
        except CatalogError as exc:
            raise MigrationError("migration failed and was rolled back") from exc
        except sqlite3.Error as exc:
            raise MigrationError("migration failed and was rolled back") from exc

    def integrity_check(self) -> str:
        with self._connection() as conn:
            result = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            if result != "ok":
                raise CatalogError(f"SQLite integrity check failed: {result}")
            return result

    def _require_migrated(self) -> None:
        with self._connection() as conn:
            try:
                row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            except sqlite3.Error as exc:
                raise MigrationError("catalogue has not been migrated") from exc
            if row[0] != SUPPORTED_VERSION:
                raise MigrationError("catalogue is not at the supported migration version")

    def register_cohort(self, cohort: Any) -> dict[str, Any]:
        self._require_migrated()
        cohort_id = _text(_get(cohort, "record_id", "cohort_id"), "cohort_id")
        material_hash = _canonical_hash(cohort)
        row_values = (
            cohort_id, _text(_get(cohort, "cohort_code"), "cohort_code"), _text(_get(cohort, "definition_version"), "definition_version"),
            _text(_get(cohort, "membership_hash"), "membership_hash"), str(_money_amount(_get(cohort, "budget_cap"), "budget_cap_aud")),
            _utc(_get(cohort, "created_at"), "created_at"), material_hash,
        )
        with self._connection(immediate=True) as conn:
            existing = conn.execute("SELECT * FROM cohorts WHERE cohort_id = ?", (cohort_id,)).fetchone()
            if existing:
                if existing["material_hash"] != material_hash:
                    raise ConflictError(f"cohort {cohort_id} is already registered with different material")
                return dict(existing)
            conn.execute("INSERT INTO cohorts(cohort_id, cohort_code, definition_version, membership_hash, budget_cap_aud, created_at, material_hash) VALUES (?, ?, ?, ?, ?, ?, ?)", row_values)
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM cohorts WHERE cohort_id = ?", (cohort_id,)).fetchone())

    def register_run(self, run: Any) -> dict[str, Any]:
        self._require_migrated()
        run_id = _text(_get(run, "record_id", "run_id"), "run_id")
        material_hash = _canonical_hash(run)
        now = _get(run, "created_at")
        row_values = (
            run_id, _get(run, "cohort_id"), _text(_get(run, "run_kind"), "run_kind"), _text(_get(run, "status"), "status"),
            _text(_get(run, "configuration_hash"), "configuration_hash"), _utc(now, "created_at"),
            _utc(_get(run, "started_at"), "started_at") if _get(run, "started_at") is not None else None,
            _utc(_get(run, "completed_at"), "completed_at") if _get(run, "completed_at") is not None else None,
            _utc(now, "updated_at"), material_hash,
        )
        with self._connection(immediate=True) as conn:
            existing = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if existing:
                if existing["material_hash"] != material_hash:
                    raise ConflictError(f"run {run_id} is already registered with different material")
                return dict(existing)
            conn.execute("INSERT INTO runs(run_id, cohort_id, run_kind, status, configuration_hash, created_at, started_at, completed_at, updated_at, material_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row_values)
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())

    def register_task(self, task: Any, *, run_id: str | None = None, now: datetime | str | None = None) -> dict[str, Any]:
        self._require_migrated()
        task_id = _text(_get(task, "record_id", "model_task_id"), "model_task_id")
        resolved_run_id = run_id or _get(task, "run_id")
        if resolved_run_id is None:
            raise CatalogError("register_task requires run_id")
        timestamp = _utc(now or _get(task, "created_at"), "created_at")
        material_hash = _canonical_hash({"task": task, "run_id": resolved_run_id})
        schema = _get(task, "task_schema")
        schema_id = _text(_get(schema, "schema_id", default=schema), "task_schema_id")
        values = (
            task_id, resolved_run_id, _text(_get(task, "subject_id"), "subject_id"), _get(task, "scope_id"), _get(task, "cohort_id"),
            _text(_get(task, "task_type"), "task_type"), schema_id, _text(_get(task, "cache_key"), "cache_key"),
            _text(_get(task, "provider_id"), "provider_id"), _text(_get(task, "model_snapshot"), "model_snapshot"), "ready", 0,
            None, None, None, None, None, None, timestamp, timestamp, material_hash,
        )
        with self._connection(immediate=True) as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE model_task_id = ?", (task_id,)).fetchone()
            if existing:
                if existing["material_hash"] != material_hash:
                    raise ConflictError(f"task {task_id} is already registered with different material")
                return dict(existing)
            conn.execute("INSERT INTO tasks(model_task_id, run_id, subject_id, scope_id, cohort_id, task_type, task_schema_id, cache_key, provider_id, model_snapshot, status, attempt_count, lease_owner, lease_expires_at, next_eligible_at, result_artifact_id, error_class, error_message_redacted, created_at, updated_at, material_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM tasks WHERE model_task_id = ?", (task_id,)).fetchone())

    def get_task(self, model_task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            return _row(conn.execute("SELECT * FROM tasks WHERE model_task_id = ?", (model_task_id,)).fetchone())

    def claim_task(self, model_task_id: str, *, owner: str, lease_expires_at: datetime | str, now: datetime | str) -> bool:
        now_s, expiry_s = _utc(now, "now"), _utc(lease_expires_at, "lease_expires_at")
        if expiry_s <= now_s:
            raise LeaseError("lease expiry must be after now")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT status, lease_owner, lease_expires_at FROM tasks WHERE model_task_id = ?", (model_task_id,)).fetchone()
            if row is None:
                raise CatalogError(f"unknown task {model_task_id}")
            if row["status"] not in {"ready", "failed_retryable"}:
                if row["lease_expires_at"] and row["lease_expires_at"] > now_s:
                    return False
                return False
            conn.execute("UPDATE tasks SET status='leased', lease_owner=?, lease_expires_at=?, updated_at=? WHERE model_task_id=?", (owner, expiry_s, now_s, model_task_id))
            self._commit(conn)
            return True

    def transition_task(self, model_task_id: str, target_status: str, *, now: datetime | str, owner: str | None = None, error_class: str | None = None, error_message_redacted: str | None = None) -> dict[str, Any]:
        """Apply one explicitly permitted operational task-state transition."""
        if target_status not in TASK_STATES:
            raise InvalidTransitionError(f"unknown task state {target_status}")
        now_s = _utc(now, "now")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE model_task_id=?", (model_task_id,)).fetchone()
            if row is None:
                raise CatalogError(f"unknown task {model_task_id}")
            if target_status not in TASK_TRANSITIONS.get(row["status"], set()):
                raise InvalidTransitionError(f"cannot transition {row["status"]} to {target_status}")
            if row["status"] in {"leased", "running"} and owner is None:
                raise LeaseError("a leased or running task requires its lease owner")
            if row["status"] in {"leased", "running"} and row["lease_owner"] != owner:
                raise LeaseError("wrong task lease owner")
            conn.execute("UPDATE tasks SET status=?, lease_owner=NULL, lease_expires_at=NULL, error_class=?, error_message_redacted=?, updated_at=? WHERE model_task_id=?", (target_status, error_class, error_message_redacted, now_s, model_task_id))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM tasks WHERE model_task_id=?", (model_task_id,)).fetchone())

    def _lease_row(self, conn: sqlite3.Connection, task_id: str, owner: str, now: datetime | str) -> sqlite3.Row:
        now_s = _utc(now, "now")
        row = conn.execute("SELECT * FROM tasks WHERE model_task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise CatalogError(f"unknown task {task_id}")
        if row["status"] in TERMINAL_TASK_STATES:
            raise InvalidTransitionError("terminal task states have no outgoing transitions")
        if row["lease_owner"] != owner or not row["lease_expires_at"] or row["lease_expires_at"] <= now_s:
            raise LeaseError("caller does not hold an unexpired task lease")
        return row

    def begin_task_attempt(self, model_task_id: str, *, owner: str, task_run_id: str, now: datetime | str, provider_request_id: str | None = None, provider_batch_id: str | None = None, reservation_id: str | None = None) -> dict[str, Any]:
        now_s = _utc(now, "now")
        with self._connection(immediate=True) as conn:
            row = self._lease_row(conn, model_task_id, owner, now_s)
            if row["status"] != "leased":
                raise InvalidTransitionError("only leased tasks can begin an attempt")
            attempt = int(row["attempt_count"]) + 1
            conn.execute("INSERT INTO task_attempts(task_run_id, model_task_id, attempt_number, status, provider_request_id, provider_batch_id, submitted_at, started_at, reservation_id) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)", (task_run_id, model_task_id, attempt, provider_request_id, provider_batch_id, now_s, now_s, reservation_id))
            conn.execute("UPDATE tasks SET status='running', attempt_count=?, updated_at=? WHERE model_task_id=?", (attempt, now_s, model_task_id))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM task_attempts WHERE task_run_id = ?", (task_run_id,)).fetchone())

    def _finish_attempt(self, task_run_id: str, *, owner: str, completed_at: datetime | str, status: str, result_artifact_id: str | None = None, retryable: bool | None = None, error_class: str | None = None, error_message_redacted: str | None = None) -> dict[str, Any]:
        completed_s = _utc(completed_at, "completed_at")
        with self._connection(immediate=True) as conn:
            attempt = conn.execute("SELECT * FROM task_attempts WHERE task_run_id = ?", (task_run_id,)).fetchone()
            if attempt is None:
                raise CatalogError(f"unknown task attempt {task_run_id}")
            task = self._lease_row(conn, attempt["model_task_id"], owner, completed_s)
            if task["status"] != "running":
                raise InvalidTransitionError("only running tasks can finish an attempt")
            if status == "succeeded":
                next_state = "succeeded"
            elif status == "held":
                next_state = "held"
            elif status == "failed_retryable":
                next_state = "failed_retryable"
            else:
                next_state = "failed_terminal"
            conn.execute("UPDATE task_attempts SET status=?, completed_at=?, retryable=?, result_artifact_id=?, error_class=?, error_message_redacted=? WHERE task_run_id=?", (status, completed_s, retryable, result_artifact_id, error_class, error_message_redacted, task_run_id))
            conn.execute("UPDATE tasks SET status=?, lease_owner=NULL, lease_expires_at=NULL, result_artifact_id=?, error_class=?, error_message_redacted=?, updated_at=? WHERE model_task_id=?", (next_state, result_artifact_id, error_class, error_message_redacted, completed_s, task["model_task_id"]))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM tasks WHERE model_task_id = ?", (task["model_task_id"],)).fetchone())

    def finish_successful_attempt(self, task_run_id: str, *, owner: str, completed_at: datetime | str, result_artifact_id: str) -> dict[str, Any]:
        return self._finish_attempt(task_run_id, owner=owner, completed_at=completed_at, status="succeeded", result_artifact_id=result_artifact_id, retryable=False)

    def finish_failed_attempt(self, task_run_id: str, *, owner: str, completed_at: datetime | str, retryable: bool, error_class: str, error_message_redacted: str) -> dict[str, Any]:
        return self._finish_attempt(task_run_id, owner=owner, completed_at=completed_at, status="failed_retryable" if retryable else "failed_terminal", retryable=retryable, error_class=error_class, error_message_redacted=error_message_redacted)

    def finish_held_attempt(self, task_run_id: str, *, owner: str, completed_at: datetime | str, error_class: str, error_message_redacted: str) -> dict[str, Any]:
        return self._finish_attempt(task_run_id, owner=owner, completed_at=completed_at, status="held", retryable=False, error_class=error_class, error_message_redacted=error_message_redacted)

    def recover_expired_leases(self, *, now: datetime | str) -> int:
        now_s = _utc(now, "now")
        with self._connection(immediate=True) as conn:
            rows = conn.execute("SELECT model_task_id, status FROM tasks WHERE status IN ('leased','running') AND lease_expires_at <= ?", (now_s,)).fetchall()
            for row in rows:
                if row["status"] == "leased":
                    conn.execute("UPDATE tasks SET status='ready', lease_owner=NULL, lease_expires_at=NULL, updated_at=? WHERE model_task_id=?", (now_s, row["model_task_id"]))
                else:
                    conn.execute("UPDATE task_attempts SET status='failed_retryable', completed_at=?, retryable=1, error_class='lease_expired', error_message_redacted='lease expired' WHERE model_task_id=? AND status='running'", (now_s, row["model_task_id"]))
                    conn.execute("UPDATE tasks SET status='failed_retryable', lease_owner=NULL, lease_expires_at=NULL, error_class='lease_expired', error_message_redacted='lease expired', updated_at=? WHERE model_task_id=?", (now_s, row["model_task_id"]))
            self._commit(conn)
            return len(rows)

    def begin_operation(self, operation_key: str, *, operation_type: str, request_hash: str, now: datetime | str) -> dict[str, Any]:
        now_s = _utc(now, "now")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM operation_receipts WHERE operation_key=?", (operation_key,)).fetchone()
            if row:
                if row["request_hash"] != request_hash:
                    raise ConflictError("operation key was reused with a different request hash")
                return dict(row)
            conn.execute("INSERT INTO operation_receipts(operation_key, operation_type, request_hash, state, created_at, updated_at) VALUES (?, ?, ?, 'started', ?, ?)", (operation_key, operation_type, request_hash, now_s, now_s))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM operation_receipts WHERE operation_key=?", (operation_key,)).fetchone())

    def complete_operation(self, operation_key: str, *, request_hash: str, now: datetime | str, result_ref: str | None = None) -> dict[str, Any]:
        return self._finish_operation(operation_key, request_hash=request_hash, now=now, state="completed", result_ref=result_ref)

    def fail_operation(self, operation_key: str, *, request_hash: str, now: datetime | str, result_ref: str | None = None) -> dict[str, Any]:
        return self._finish_operation(operation_key, request_hash=request_hash, now=now, state="failed", result_ref=result_ref)

    def _finish_operation(self, operation_key: str, *, request_hash: str, now: datetime | str, state: str, result_ref: str | None) -> dict[str, Any]:
        now_s = _utc(now, "now")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM operation_receipts WHERE operation_key=?", (operation_key,)).fetchone()
            if row is None:
                raise CatalogError("operation receipt does not exist")
            if row["request_hash"] != request_hash:
                raise ConflictError("operation key was reused with a different request hash")
            if row["state"] == "completed":
                return dict(row)
            conn.execute("UPDATE operation_receipts SET state=?, result_ref=?, updated_at=? WHERE operation_key=?", (state, result_ref, now_s, operation_key))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM operation_receipts WHERE operation_key=?", (operation_key,)).fetchone())

    def _position(self, conn: sqlite3.Connection, cohort_id: str) -> BudgetPosition:
        cohort = conn.execute("SELECT budget_cap_aud FROM cohorts WHERE cohort_id=?", (cohort_id,)).fetchone()
        if cohort is None:
            raise CatalogError(f"unknown cohort {cohort_id}")
        reservations = conn.execute("SELECT reservation_id, reserved_aud FROM budget_reservations WHERE cohort_id=?", (cohort_id,)).fetchall()
        reservation_ids = {row["reservation_id"] for row in reservations}
        outstanding = Decimal("0")
        overrun = Decimal("0")
        for reservation in reservations:
            rid, reserved = reservation["reservation_id"], Decimal(reservation["reserved_aud"])
            actual = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND reservation_id=? AND entry_type='actual'", (cohort_id, rid)).fetchone()[0])
            released = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND reservation_id=? AND entry_type='reservation_release'", (cohort_id, rid)).fetchone()[0])
            remaining = reserved - min(actual, reserved) - released
            if remaining < 0:
                raise ConflictError("reservation releases cannot exceed the unused portion of their own reservation")
            outstanding += remaining
            overrun += max(actual - reserved, Decimal("0"))
        actual = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='actual'", (cohort_id,)).fetchone()[0])
        released = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='reservation_release'", (cohort_id,)).fetchone()[0])
        credits = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='credit'", (cohort_id,)).fetchone()[0])
        debits = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='adjustment' AND adjustment_direction='debit'", (cohort_id,)).fetchone()[0])
        adjustment_credits = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='adjustment' AND adjustment_direction='credit'", (cohort_id,)).fetchone()[0])
        unreserved = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE cohort_id=? AND entry_type='actual' AND reservation_id NOT IN (SELECT reservation_id FROM budget_reservations WHERE cohort_id=?)", (cohort_id, cohort_id)).fetchone()[0])
        cap = Decimal(cohort["budget_cap_aud"])
        net = actual + debits - credits - adjustment_credits
        committed = net + outstanding
        return BudgetPosition(cohort_id, cap, outstanding, released, actual, overrun, unreserved, credits, debits, adjustment_credits, net, committed, cap - committed, committed > cap)

    def budget_position(self, cohort_id: str) -> BudgetPosition:
        self._require_migrated()
        with self._connection() as conn:
            return self._position(conn, cohort_id)

    def reserve_cost(self, reservation: Any, *, now: datetime | str) -> dict[str, Any]:
        self._require_migrated()
        now_s = _utc(now, "now")
        rid = _text(_get(reservation, "record_id", "reservation_id"), "reservation_id")
        cohort_id = _text(_get(reservation, "cohort_id"), "cohort_id")
        run_id = _text(_get(reservation, "run_id"), "run_id")
        amount = _money_amount(_get(reservation, "reserved_aud"), "reserved_aud")
        expires = _get(reservation, "expires_at")
        material_hash = _canonical_hash(reservation)
        with self._connection(immediate=True) as conn:
            existing = conn.execute("SELECT * FROM budget_reservations WHERE reservation_id=?", (rid,)).fetchone()
            if existing:
                if existing["material_hash"] != material_hash:
                    raise ConflictError(f"reservation {rid} is already registered with different material")
                return dict(existing)
            position = self._position(conn, cohort_id)
            if position.net_actual_spend_aud + position.outstanding_reserved_exposure_aud + amount > position.cohort_cap_aud:
                raise BudgetExceededError("reservation would exceed the cohort budget cap")
            conn.execute("INSERT INTO budget_reservations(reservation_id, cohort_id, run_id, reserved_aud, status, reserved_at, expires_at, updated_at, material_hash) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)", (rid, cohort_id, run_id, str(amount), now_s, _utc(expires, "expires_at") if expires is not None else None, now_s, material_hash))
            for task_id in (_get(reservation, "model_task_ids", default=()) or ()):
                conn.execute("INSERT INTO reservation_tasks(reservation_id, model_task_id) VALUES (?, ?)", (rid, task_id))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM budget_reservations WHERE reservation_id=?", (rid,)).fetchone())

    def release_reservation(self, reservation_id: str, amount: Any, *, now: datetime | str, entry_key: str | None = None) -> dict[str, Any]:
        """Record a release event using deterministic system metadata."""

        with self._connection(immediate=True) as conn:
            reservation = conn.execute("SELECT * FROM budget_reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
            if reservation is None:
                raise ConflictError("reservation release requires a matching reservation")
            amount_decimal = _money_amount(amount, "release amount")
            key = entry_key or f"release:{reservation_id}:{amount_decimal}"
            payload = {"entry_key": key, "reservation_id": reservation_id, "amount": str(amount_decimal), "recorded_at": _utc(now, "now")}
            entry_hash = _canonical_hash(payload)
            existing = conn.execute("SELECT * FROM cost_entries WHERE entry_key=?", (key,)).fetchone()
            if existing:
                if existing["entry_hash"] != entry_hash:
                    raise ConflictError("cost entry key was reused with different content")
                return dict(existing)
            reserved = Decimal(reservation["reserved_aud"])
            actual = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE reservation_id=? AND entry_type='actual'", (reservation_id,)).fetchone()[0])
            released = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE reservation_id=? AND entry_type='reservation_release'", (reservation_id,)).fetchone()[0])
            if amount_decimal > reserved - min(actual, reserved) - released:
                raise ConflictError("reservation release exceeds its own unused amount")
            conn.execute("INSERT INTO cost_entries(entry_key, entry_hash, cohort_id, run_id, task_run_id, reservation_id, entry_type, paid_output_category, provider_amount, provider_currency, aud_amount, pricing_snapshot_id, fx_snapshot_id, usage_json, recorded_at) VALUES (?, ?, ?, ?, ?, ?, 'reservation_release', 'retry', '0', 'AUD', ?, 'system', 'system', '{}', ?)", (key, entry_hash, reservation["cohort_id"], reservation["run_id"], f"system:{reservation_id}", reservation_id, str(amount_decimal), payload["recorded_at"]))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM cost_entries WHERE entry_key=?", (key,)).fetchone())

    def record_cost_entry(self, entry: Any, *, entry_key: str, entry_hash: str | None = None) -> dict[str, Any]:
        self._require_migrated()
        material_hash = entry_hash or _canonical_hash(entry)
        cohort_id = _text(_get(entry, "cohort_id"), "cohort_id")
        reservation_id = _text(_get(entry, "reservation_id"), "reservation_id")
        entry_type = _text(_get(entry, "entry_type"), "entry_type")
        amount = _money_amount(_get(entry, "aud_cost"), "aud_cost")
        with self._connection(immediate=True) as conn:
            existing = conn.execute("SELECT * FROM cost_entries WHERE entry_key=?", (entry_key,)).fetchone()
            if existing:
                if existing["entry_hash"] != material_hash:
                    raise ConflictError("cost entry key was reused with different content")
                return dict(existing)
            reservation = conn.execute("SELECT * FROM budget_reservations WHERE reservation_id=?", (reservation_id,)).fetchone()
            if entry_type == "reservation_release":
                if reservation is None:
                    raise ConflictError("reservation release requires a matching reservation")
                actual = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE reservation_id=? AND entry_type='actual'", (reservation_id,)).fetchone()[0])
                released = Decimal(conn.execute("SELECT COALESCE(SUM(aud_amount), '0') FROM cost_entries WHERE reservation_id=? AND entry_type='reservation_release'", (reservation_id,)).fetchone()[0])
                if amount > Decimal(reservation["reserved_aud"]) - min(actual, Decimal(reservation["reserved_aud"])) - released:
                    raise ConflictError("reservation release exceeds its own unused amount")
            usage = _dump(_get(entry, "usage", default={}))
            provider_cost = _get(entry, "provider_cost", default={})
            recorded = _get(entry, "recorded_at")
            values = (
                entry_key, material_hash, cohort_id, _text(_get(entry, "run_id"), "run_id"), _text(_get(entry, "task_run_id"), "task_run_id"), reservation_id,
                entry_type, _text(_get(entry, "paid_output_category"), "paid_output_category"), str(_decimal(_get(provider_cost, "amount", default=provider_cost), "provider_cost")), str(_get(provider_cost, "currency", default="AUD")), str(amount),
                _get(entry, "adjustment_direction"), _text(_get(entry, "pricing_snapshot_id"), "pricing_snapshot_id"), _text(_get(entry, "fx_snapshot_id"), "fx_snapshot_id"), json.dumps(usage, sort_keys=True, separators=(",", ":")), _utc(recorded, "recorded_at"),
            )
            conn.execute("INSERT INTO cost_entries(entry_key, entry_hash, cohort_id, run_id, task_run_id, reservation_id, entry_type, paid_output_category, provider_amount, provider_currency, aud_amount, adjustment_direction, pricing_snapshot_id, fx_snapshot_id, usage_json, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM cost_entries WHERE entry_key=?", (entry_key,)).fetchone())

    def release_cost(self, reservation_id: str, amount: Any, *, now: datetime | str, entry_key: str | None = None) -> dict[str, Any]:
        return self.release_reservation(reservation_id, amount, now=now, entry_key=entry_key)

    def put_cache(self, *, cache_key: str, model_task_id: str, result_artifact_id: str, result_content_hash: str, created_at: datetime | str, replace_invalidated: bool = False) -> dict[str, Any]:
        created_s = _utc(created_at, "created_at")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM cache_entries WHERE cache_key=?", (cache_key,)).fetchone()
            if row:
                if row["status"] == "valid":
                    if (row["result_artifact_id"], row["result_content_hash"]) != (result_artifact_id, result_content_hash):
                        raise ConflictError("valid cache key was reused with a different result")
                    return dict(row)
                if not replace_invalidated:
                    raise ConflictError("replacement after invalidation must be explicit")
                conn.execute("UPDATE cache_entries SET model_task_id=?, result_artifact_id=?, result_content_hash=?, status='valid', created_at=?, invalidated_at=NULL, invalidation_reason=NULL WHERE cache_key=?", (model_task_id, result_artifact_id, result_content_hash, created_s, cache_key))
            else:
                conn.execute("INSERT INTO cache_entries(cache_key, model_task_id, result_artifact_id, result_content_hash, status, created_at) VALUES (?, ?, ?, ?, 'valid', ?)", (cache_key, model_task_id, result_artifact_id, result_content_hash, created_s))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM cache_entries WHERE cache_key=?", (cache_key,)).fetchone())

    def retrieve_cache(self, cache_key: str) -> dict[str, Any] | None:
        return self.get_cache(cache_key)

    def get_cache(self, cache_key: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            return _row(conn.execute("SELECT * FROM cache_entries WHERE cache_key=? AND status='valid'", (cache_key,)).fetchone())

    def invalidate_cache(self, cache_key: str, *, invalidated_at: datetime | str, reason: str) -> dict[str, Any]:
        timestamp = _utc(invalidated_at, "invalidated_at")
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM cache_entries WHERE cache_key=?", (cache_key,)).fetchone()
            if row is None:
                raise CatalogError("cache entry does not exist")
            if row["status"] == "invalidated":
                return dict(row)
            conn.execute("UPDATE cache_entries SET status='invalidated', invalidated_at=?, invalidation_reason=? WHERE cache_key=?", (timestamp, reason, cache_key))
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM cache_entries WHERE cache_key=?", (cache_key,)).fetchone())

    def index_artifact(self, *, artifact_id: str, content_hash: str, schema_id: str, schema_version: str, storage_path: str, availability: str, created_at: datetime | str, indexed_at: datetime | str) -> dict[str, Any]:
        if availability not in {"available", "missing", "quarantined"}:
            raise CatalogError("invalid artefact availability")
        values = (artifact_id, content_hash, schema_id, schema_version, storage_path, availability, _utc(created_at, "created_at"), _utc(indexed_at, "indexed_at"))
        with self._connection(immediate=True) as conn:
            row = conn.execute("SELECT * FROM artifact_index WHERE artifact_id=?", (artifact_id,)).fetchone()
            if row:
                if row["content_hash"] != content_hash:
                    raise ConflictError("artefact ID was indexed with a different content hash")
                return dict(row)
            conn.execute("INSERT INTO artifact_index(artifact_id, content_hash, schema_id, schema_version, storage_path, availability, created_at, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
            self._commit(conn)
            return dict(conn.execute("SELECT * FROM artifact_index WHERE artifact_id=?", (artifact_id,)).fetchone())

    def retrieve_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            return _row(conn.execute("SELECT * FROM artifact_index WHERE artifact_id=?", (artifact_id,)).fetchone())


    # End of catalogue operations.
