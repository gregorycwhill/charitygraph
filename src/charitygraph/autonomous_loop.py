"""Durable, fail-closed local ingress/result adapter for autonomous work.

This module is deliberately transport-only.  It does not discover sources,
make semantic decisions, publish, merge, or replace the Builder runtime.  A
host-side watcher can materialise an immutable instruction into ``inbox`` and
claim it exactly once through this small SQLite-backed control plane.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class BridgeError(RuntimeError):
    """Base class for fail-closed bridge errors."""


class InvalidInstruction(BridgeError):
    pass


class DuplicateInstruction(BridgeError):
    pass


class ClaimUnavailable(BridgeError):
    pass


class StaleOwnership(ClaimUnavailable):
    pass


class AmbiguousInterruption(ClaimUnavailable):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_filename(identifier: str) -> str:
    """Keep logical IDs intact in records while making Windows paths valid."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", identifier)


@dataclass(frozen=True)
class InstructionEnvelope:
    instruction_id: str
    content: str
    content_sha256: str
    authority: dict[str, Any]
    target: dict[str, Any]
    operation: str
    created_at: str
    schema_version: str = "charitygraph.autonomous-instruction/v1"
    execution: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        *,
        instruction_id: str,
        content: str,
        target: dict[str, Any],
        operation: str = "builder_rehearsal",
        created_at: datetime | None = None,
        authority: dict[str, Any] | None = None,
        execution: dict[str, Any] | None = None,
    ) -> "InstructionEnvelope":
        return cls(
            instruction_id=instruction_id,
            content=content,
            content_sha256=sha256_text(content),
            authority=authority or {"source": "chatgpt", "approved": True, "authority_envelope": "gate4-local"},
            target=target,
            operation=operation,
            created_at=iso(created_at or utc_now()),
            execution=execution,
        )

    def as_dict(self) -> dict[str, Any]:
        value = {
            "schema_version": self.schema_version,
            "instruction_id": self.instruction_id,
            "content": self.content,
            "content_sha256": self.content_sha256,
            "authority": self.authority,
            "target": self.target,
            "operation": self.operation,
            "created_at": self.created_at,
        }
        if self.execution is not None:
            value["execution"] = self.execution
        return value

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "InstructionEnvelope":
        required = {"instruction_id", "content", "content_sha256", "authority", "target", "operation", "created_at"}
        missing = sorted(required - raw.keys())
        if missing:
            raise InvalidInstruction(f"missing fields: {', '.join(missing)}")
        envelope = cls(
            instruction_id=str(raw["instruction_id"]),
            content=str(raw["content"]),
            content_sha256=str(raw["content_sha256"]),
            authority=dict(raw["authority"]),
            target=dict(raw["target"]),
            operation=str(raw["operation"]),
            created_at=str(raw["created_at"]),
            schema_version=str(raw.get("schema_version", "")),
            execution=dict(raw["execution"]) if raw.get("execution") is not None else None,
        )
        validate_envelope(envelope)
        return envelope


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
_FORBIDDEN_OPERATIONS = {"publish", "merge", "release", "acquire_sources", "paid_provider_execution", "close_gate"}
SUPPORTED_ENGINEERING_MODELS = {"luna-high"}


def validate_envelope(envelope: InstructionEnvelope) -> None:
    if not _ID.fullmatch(envelope.instruction_id):
        raise InvalidInstruction("instruction_id is not a stable bounded identifier")
    if not envelope.content.strip():
        raise InvalidInstruction("content must be non-empty")
    if envelope.content_sha256 != sha256_text(envelope.content):
        raise InvalidInstruction("content_sha256 does not match content")
    if envelope.authority.get("source") != "chatgpt" or envelope.authority.get("approved") is not True:
        raise InvalidInstruction("instruction is not an approved ChatGPT-originated envelope")
    if envelope.operation in _FORBIDDEN_OPERATIONS:
        raise InvalidInstruction(f"operation is outside the local engineering envelope: {envelope.operation}")
    target = envelope.target
    for field in ("repository", "workspace_path", "branch", "head", "model"):
        if not target.get(field):
            raise InvalidInstruction(f"target.{field} is required")
    if not re.fullmatch(r"[0-9a-f]{40}", str(target["head"])):
        raise InvalidInstruction("target.head must be a full commit identity")
    if target["model"] not in SUPPORTED_ENGINEERING_MODELS:
        raise InvalidInstruction(f"unsupported target model: {target['model']}")


class LocalAutonomousBridge:
    """Filesystem-visible ingress and result surface for one host watcher."""

    def __init__(self, root: str | Path, *, workspace: str | Path | None = None) -> None:
        self.root = Path(root).resolve()
        self.workspace = Path(workspace).resolve() if workspace else None
        self.db_path = self.root / "bridge.sqlite3"

    def open(self) -> "LocalAutonomousBridge":
        (self.root / "inbox").mkdir(parents=True, exist_ok=True)
        (self.root / "results").mkdir(parents=True, exist_ok=True)
        (self.root / "audit").mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS instructions (
                    instruction_id TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner TEXT,
                    lease_expires_at TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_sha256 TEXT,
                    result_path TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instruction_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )
        return self

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _event(self, conn: sqlite3.Connection, instruction_id: str, event_type: str, payload: dict[str, Any], now: str) -> None:
        conn.execute(
            "INSERT INTO events(instruction_id,event_type,event_json,recorded_at) VALUES(?,?,?,?)",
            (instruction_id, event_type, canonical_json(payload), now),
        )

    def _verify_target(self, envelope: InstructionEnvelope) -> dict[str, Any]:
        target = envelope.target
        observed: dict[str, Any] = {"repository": target["repository"], "workspace_path": target["workspace_path"], "branch": target["branch"], "expected_head": target["head"], "model": target["model"]}
        if self.workspace is None:
            observed["verified"] = False
            observed["verification_note"] = "host workspace was not configured"
            return observed
        if self.workspace != Path(target["workspace_path"]).resolve():
            raise InvalidInstruction("target workspace does not match configured host workspace")
        try:
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.workspace, text=True, stderr=subprocess.STDOUT).strip()
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=self.workspace, text=True, stderr=subprocess.STDOUT).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InvalidInstruction(f"unable to verify target workspace: {exc}") from exc
        if head != target["head"] or branch != target["branch"]:
            raise InvalidInstruction(f"target mismatch: observed {branch}@{head}")
        observed.update({"observed_head": head, "observed_branch": branch, "verified": True})
        return observed

    def submit(self, envelope: InstructionEnvelope) -> dict[str, Any]:
        validate_envelope(envelope)
        now = iso(utc_now())
        raw = canonical_json(envelope.as_dict())
        inbox_path = self.root / "inbox" / f"{_safe_filename(envelope.instruction_id)}.json"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM instructions WHERE instruction_id=?", (envelope.instruction_id,)).fetchone()
            if existing:
                if existing["content_sha256"] != envelope.content_sha256:
                    raise DuplicateInstruction("instruction_id was submitted with different content")
                return {"accepted": False, "duplicate": True, "status": existing["status"], "instruction_id": envelope.instruction_id}
            # A durable duplicate must be recognised before live target
            # verification.  Historical completed instructions may target a
            # prior committed HEAD; re-checking that identity on restart must
            # never turn a terminal record into a replay or rejection.
            target = self._verify_target(envelope)
            if inbox_path.exists() and inbox_path.read_text(encoding="utf-8") != raw:
                raise DuplicateInstruction("immutable inbox file conflicts with instruction")
            inbox_path.write_text(raw + "\n", encoding="utf-8", newline="\n")
            conn.execute(
                "INSERT INTO instructions(instruction_id,content_sha256,envelope_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (envelope.instruction_id, envelope.content_sha256, raw, "pending", envelope.created_at, now),
            )
            self._event(conn, envelope.instruction_id, "submitted", {"content_sha256": envelope.content_sha256, "target": target}, now)
        return {"accepted": True, "duplicate": False, "status": "pending", "instruction_id": envelope.instruction_id, "content_sha256": envelope.content_sha256}

    def import_materialized_instruction(self, path: str | Path) -> dict[str, Any]:
        """Import exactly one UTF-8 canonical-JSON export from a host mirror.

        The mirror, not this adapter, is responsible for obtaining/exporting
        the native connected document.  This boundary deliberately accepts
        only the documented byte representation and never interprets the
        instruction body as shell or Python authority.
        """
        source = Path(path)
        envelope, raw = self.read_materialized_instruction(source)
        result = self.submit(envelope)
        result.update({"materialized_path": str(source.resolve()), "materialized_sha256": hashlib.sha256(raw).hexdigest()})
        return result

    def read_materialized_instruction(self, path: str | Path) -> tuple[InstructionEnvelope, bytes]:
        """Read and validate a canonical materialized instruction without submitting it."""
        source = Path(path)
        raw = source.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise InvalidInstruction("UTF-8 BOM is not permitted in materialized instructions")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidInstruction("materialized instruction must be UTF-8") from exc
        if not text.endswith("\n") or text.count("\n") != 1:
            raise InvalidInstruction("materialized instruction must be one canonical JSON line")
        try:
            raw_object = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidInstruction("materialized instruction is not JSON") from exc
        if not isinstance(raw_object, dict):
            raise InvalidInstruction("materialized instruction must be a JSON object")
        expected = canonical_json(raw_object) + "\n"
        if expected != text:
            raise InvalidInstruction("materialized instruction bytes are not canonical JSON")
        envelope = InstructionEnvelope.from_dict(raw_object)
        return envelope, raw

    def latest_terminal(self) -> dict[str, Any] | None:
        """Return the newest durable terminal result for status recovery."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM instructions WHERE status IN ('complete','failed') "
                "ORDER BY updated_at DESC, instruction_id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            event = conn.execute(
                "SELECT event_type,recorded_at FROM events WHERE instruction_id=? "
                "ORDER BY event_id DESC LIMIT 1",
                (row["instruction_id"],),
            ).fetchone()
        result = None
        result_path = row["result_path"]
        if result_path:
            try:
                result = json.loads(Path(result_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result = None
        error = None
        if row["error_json"]:
            try:
                error = json.loads(row["error_json"])
            except json.JSONDecodeError:
                error = {"raw": row["error_json"]}
        return {
            "instruction_id": row["instruction_id"],
            "status": row["status"],
            "attempts": row["attempts"],
            "result_path": result_path,
            "result_sha256": row["result_sha256"],
            "result": result,
            "error": error,
            "updated_at": row["updated_at"],
            "last_event": event["event_type"] if event else None,
            "last_event_at": event["recorded_at"] if event else row["updated_at"],
        }

    def claim(self, *, owner: str, now: datetime | None = None, lease_seconds: int = 900) -> InstructionEnvelope:
        if not owner.strip():
            raise ClaimUnavailable("owner is required")
        current = now or utc_now()
        now_s = iso(current)
        expiry = iso(current + timedelta(seconds=lease_seconds))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM instructions WHERE status IN ('pending','claimed','running','reconciliation_required') ORDER BY created_at, instruction_id LIMIT 1").fetchone()
            if row is None:
                raise ClaimUnavailable("no claimable instruction")
            if row["status"] == "reconciliation_required":
                raise AmbiguousInterruption("instruction requires explicit reconciliation")
            if row["status"] in {"claimed", "running"}:
                if row["lease_expires_at"] and row["lease_expires_at"] > now_s:
                    raise ClaimUnavailable(f"instruction is leased by {row['owner']}")
                conn.execute("UPDATE instructions SET status='reconciliation_required', updated_at=?, error_json=? WHERE instruction_id=?", (now_s, canonical_json({"class": "ambiguous_interruption", "previous_owner": row["owner"]}), row["instruction_id"]))
                self._event(conn, row["instruction_id"], "ambiguous_interruption", {"previous_owner": row["owner"]}, now_s)
                conn.commit()
                raise AmbiguousInterruption("expired lease is ambiguous; explicit reconciliation required")
            envelope = InstructionEnvelope.from_dict(json.loads(row["envelope_json"]))
            target = self._verify_target(envelope)
            attempts = int(row["attempts"]) + 1
            conn.execute("UPDATE instructions SET status='claimed',owner=?,lease_expires_at=?,attempts=?,updated_at=? WHERE instruction_id=?", (owner, expiry, attempts, now_s, row["instruction_id"]))
            self._event(conn, row["instruction_id"], "claimed", {"owner": owner, "attempt": attempts, "target": target}, now_s)
            return envelope

    def begin(self, instruction_id: str, *, owner: str, now: datetime | None = None) -> None:
        self._transition(instruction_id, owner=owner, expected={"claimed"}, status="running", now=now, event_type="started")

    def checkpoint(self, instruction_id: str, *, owner: str, checkpoint: dict[str, Any], now: datetime | None = None) -> None:
        self._transition(instruction_id, owner=owner, expected={"running"}, status="running", now=now, event_type="checkpoint", payload={"checkpoint": checkpoint})

    def _transition(self, instruction_id: str, *, owner: str, expected: set[str], status: str, now: datetime | None, event_type: str, payload: dict[str, Any] | None = None) -> None:
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if row is None or row["status"] not in expected:
                raise ClaimUnavailable(f"instruction is not in {sorted(expected)}")
            if row["owner"] != owner:
                raise StaleOwnership("claim owner does not match")
            conn.execute("UPDATE instructions SET status=?,updated_at=? WHERE instruction_id=?", (status, now_s, instruction_id))
            self._event(conn, instruction_id, event_type, payload or {}, now_s)

    def complete(self, instruction_id: str, *, owner: str, result: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        now_s = iso(now or utc_now())
        result_raw = canonical_json(result)
        result_hash = sha256_text(result_raw)
        result_path = self.root / "results" / f"{_safe_filename(instruction_id)}.json"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if row is None:
                raise ClaimUnavailable("unknown instruction")
            if row["status"] == "complete":
                return {"status": "complete", "result_sha256": row["result_sha256"], "result_path": row["result_path"]}
            if row["status"] != "running" or row["owner"] != owner:
                raise StaleOwnership("only the active owner can complete a running instruction")
            if result_path.exists() and sha256_text(result_path.read_text(encoding="utf-8")) != result_hash:
                raise DuplicateInstruction("result surface already contains different bytes")
            fd, temp_name = tempfile.mkstemp(prefix=f"{_safe_filename(instruction_id)}.", suffix=".tmp", dir=self.root / "results")
            os.close(fd)
            temp_path = Path(temp_name)
            try:
                temp_path.write_text(result_raw + "\n", encoding="utf-8", newline="\n")
                temp_path.replace(result_path)
            finally:
                temp_path.unlink(missing_ok=True)
            conn.execute("UPDATE instructions SET status='complete',result_sha256=?,result_path=?,lease_expires_at=NULL,updated_at=? WHERE instruction_id=?", (result_hash, str(result_path), now_s, instruction_id))
            self._event(conn, instruction_id, "completed", {"result_sha256": result_hash, "result_path": str(result_path)}, now_s)
        return {"status": "complete", "result_sha256": result_hash, "result_path": str(result_path)}

    def fail(self, instruction_id: str, *, owner: str, error: dict[str, Any], now: datetime | None = None) -> None:
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status,owner FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if row is None or row["status"] not in {"claimed", "running"} or row["owner"] != owner:
                raise StaleOwnership("only the active owner can fail an instruction")
            conn.execute("UPDATE instructions SET status='failed',error_json=?,lease_expires_at=NULL,updated_at=? WHERE instruction_id=?", (canonical_json(error), now_s, instruction_id))
            self._event(conn, instruction_id, "failed", error, now_s)

    def reject_pending_input(
        self,
        instruction_id: str,
        *,
        actor: str,
        error: dict[str, Any],
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Terminalise a never-claimed invalid instruction without executing it.

        This is deliberately narrower than ``fail``: it is only for a legacy
        row that was inserted before host-side admission validation, and cannot
        consume an attempt, owner lease, or running worker.
        """
        if not actor.strip() or not error:
            raise ClaimUnavailable("pending rejection requires an actor and structured error")
        now_s = iso(now or utc_now())
        result_raw = canonical_json(result)
        result_hash = sha256_text(result_raw)
        result_path = self.root / "results" / f"{_safe_filename(instruction_id)}.json"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if (
                row is None
                or row["status"] != "pending"
                or int(row["attempts"]) != 0
                or row["owner"] is not None
                or row["lease_expires_at"] is not None
                or row["result_path"] is not None
            ):
                raise ClaimUnavailable("only an unclaimed zero-attempt pending instruction may be terminally rejected")
            if result.get("instruction_id") != instruction_id or result.get("content_sha256") != row["content_sha256"]:
                raise DuplicateInstruction("pending rejection result does not bind the stored instruction")
            if result_path.exists() and sha256_text(result_path.read_text(encoding="utf-8")) != result_hash:
                raise DuplicateInstruction("result surface already contains different bytes")
            fd, temp_name = tempfile.mkstemp(prefix=f"{_safe_filename(instruction_id)}.", suffix=".tmp", dir=self.root / "results")
            os.close(fd)
            temp_path = Path(temp_name)
            try:
                temp_path.write_text(result_raw + "\n", encoding="utf-8", newline="\n")
                temp_path.replace(result_path)
            finally:
                temp_path.unlink(missing_ok=True)
            conn.execute(
                "UPDATE instructions SET status='complete',result_sha256=?,result_path=?,error_json=?,lease_expires_at=NULL,updated_at=? WHERE instruction_id=?",
                (result_hash, str(result_path), canonical_json(error), now_s, instruction_id),
            )
            self._event(
                conn,
                instruction_id,
                "rejected_input",
                {"actor": actor, "error": error, "result_sha256": result_hash, "result_path": str(result_path)},
                now_s,
            )
        return {"status": "complete", "result_sha256": result_hash, "result_path": str(result_path)}

    def reconcile(self, instruction_id: str, *, actor: str, rationale: str, now: datetime | None = None) -> None:
        if not actor.strip() or not rationale.strip():
            raise AmbiguousInterruption("explicit actor and rationale are required")
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if row is None or row["status"] != "reconciliation_required":
                raise AmbiguousInterruption("only an ambiguous instruction can be reconciled")
            conn.execute("UPDATE instructions SET status='pending',owner=NULL,lease_expires_at=NULL,error_json=NULL,updated_at=? WHERE instruction_id=?", (now_s, instruction_id))
            self._event(conn, instruction_id, "reconciled", {"actor": actor, "rationale": rationale}, now_s)

    def inspect(self, instruction_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM instructions WHERE instruction_id=?", (instruction_id,)).fetchone()
            if row is None:
                raise BridgeError("unknown instruction")
            result = dict(row)
            result["envelope"] = json.loads(result.pop("envelope_json"))
            if result.get("error_json"):
                result["error"] = json.loads(result.pop("error_json"))
            return result

    def status_summary(self, instruction_id: str) -> dict[str, Any]:
        """Return concise human-readable status backed by the durable row."""
        row = self.inspect(instruction_id)
        return {
            "instruction_id": instruction_id,
            "status": row["status"],
            "owner": row["owner"],
            "attempts": row["attempts"],
            "result_path": row["result_path"],
            "result_sha256": row["result_sha256"],
            "updated_at": row["updated_at"],
        }

    def supervisory_ledger_summary(self) -> dict[str, Any]:
        """Return the read-only execution state needed by an external supervisor.

        The SQLite ledger remains the only authority for claims.  This is a
        deliberately small projection for a private transport surface: it
        exposes every non-terminal instruction (including an ambiguous one),
        but never instruction content or mutable claim tokens.  A supervisor
        can therefore prove whether dispatch is blocked without access to the
        Windows runtime or repository.
        """
        active_statuses = ("pending", "claimed", "running", "reconciliation_required")
        with self._connect() as conn:
            counts = {
                status: int(
                    conn.execute("SELECT COUNT(*) FROM instructions WHERE status=?", (status,)).fetchone()[0]
                )
                for status in ("pending", "claimed", "running", "reconciliation_required", "complete", "failed")
            }
            rows = conn.execute(
                "SELECT instruction_id,content_sha256,status,owner,lease_expires_at,attempts,created_at,updated_at "
                "FROM instructions WHERE status IN (?,?,?,?) ORDER BY created_at,instruction_id",
                active_statuses,
            ).fetchall()
            terminal = conn.execute(
                "SELECT instruction_id,content_sha256,status,attempts,result_sha256,result_path,updated_at "
                "FROM instructions WHERE status IN ('complete','failed') ORDER BY updated_at DESC,instruction_id DESC LIMIT 1"
            ).fetchone()
        blockers = [
            {
                "instruction_id": row["instruction_id"],
                "content_sha256": row["content_sha256"],
                "status": row["status"],
                "owner": row["owner"],
                "lease_expires_at": row["lease_expires_at"],
                "attempts": row["attempts"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return {
            "schema": "charitygraph.g4-o1c-supervisory-ledger/v1",
            "instruction_counts": counts,
            "dispatch_clear": not blockers,
            "active_or_ambiguous_claims": blockers,
            "latest_terminal": None if terminal is None else dict(terminal),
        }

    def events(self, instruction_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) | {"event": json.loads(row["event_json"])} for row in conn.execute("SELECT * FROM events WHERE instruction_id=? ORDER BY event_id", (instruction_id,))]

    def mission_ledger(self):
        """Return O1E mission state on this adapter's same SQLite database."""
        from .mission_ledger import MissionLedger

        return MissionLedger(self.db_path).open()


__all__ = [
    "AmbiguousInterruption", "BridgeError", "ClaimUnavailable", "DuplicateInstruction", "InstructionEnvelope",
    "InvalidInstruction", "LocalAutonomousBridge", "StaleOwnership", "canonical_json", "sha256_text", "validate_envelope",
    "SUPPORTED_ENGINEERING_MODELS",
]
