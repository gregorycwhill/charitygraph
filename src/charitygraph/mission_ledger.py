"""Durable O1E mission and supervisory-review state on the bridge ledger.

This module deliberately uses the existing bridge SQLite database.  It adds
operational mission/review records without creating a second execution queue,
worker, or source-of-truth for Builder product data.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .autonomous_loop import canonical_json, iso, sha256_text, utc_now


MISSION_SCHEMA = "charitygraph.g4-o1e-mission/v1"
EVENT_SCHEMA = "charitygraph.g4-o1e-event/v1"
REVIEW_SCHEMA = "charitygraph.g4-o1e-review/v1"


class MissionLedgerError(RuntimeError):
    """Base class for fail-closed mission-ledger errors."""


class MissionAlreadyExists(MissionLedgerError):
    pass


class DuplicateMissionEvent(MissionLedgerError):
    pass


class CompareAndSwapConflict(MissionLedgerError):
    pass


class SupervisorClaimUnavailable(MissionLedgerError):
    pass


class StaleReviewCursor(MissionLedgerError):
    pass


class StaleMissionIdentity(MissionLedgerError):
    pass


class MissionStopped(MissionLedgerError):
    pass


@dataclass(frozen=True)
class MissionContract:
    mission_id: str
    tranche_id: str
    instruction_id: str
    run_id: str
    supervisor_review_id: str
    repository: str
    workspace_path: str
    branch: str
    head: str
    authority_envelope: str = "gate4-engineering"
    created_at: str = ""
    schema_version: str = MISSION_SCHEMA

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "tranche_id": self.tranche_id,
            "instruction_id": self.instruction_id,
            "run_id": self.run_id,
            "supervisor_review_id": self.supervisor_review_id,
            "repository": self.repository,
            "workspace_path": self.workspace_path,
            "branch": self.branch,
            "head": self.head,
            "authority_envelope": self.authority_envelope,
            "created_at": self.created_at,
        }

    @classmethod
    def create(cls, **kwargs: Any) -> "MissionContract":
        return cls(created_at=kwargs.pop("created_at", iso(utc_now())), **kwargs)


def _hash_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def _require_hash(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise MissionLedgerError(f"{label} must be a lowercase SHA-256")
    return value


class MissionLedger:
    """Mission/review ledger sharing the existing adapter SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()

    def open(self) -> "MissionLedger":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    contract_json TEXT NOT NULL,
                    contract_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    stop_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS mission_events (
                    mission_id TEXT NOT NULL,
                    event_seq INTEGER NOT NULL,
                    event_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (mission_id, event_seq),
                    UNIQUE (mission_id, event_key)
                );
                CREATE TABLE IF NOT EXISTS review_cursors (
                    mission_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    cursor_seq INTEGER NOT NULL,
                    decision_id TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (mission_id, reviewer_id)
                );
                CREATE TABLE IF NOT EXISTS supervisor_claims (
                    mission_id TEXT NOT NULL,
                    claim_kind TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    claim_token TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (mission_id, claim_kind)
                );
                CREATE TABLE IF NOT EXISTS supervisor_decisions (
                    decision_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    cursor_seq INTEGER NOT NULL,
                    execution_disposition TEXT NOT NULL,
                    semantic_disposition TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    decision_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
        return self

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @staticmethod
    def _mission_state(conn: sqlite3.Connection, mission_id: str) -> str:
        row = conn.execute("SELECT state FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if row is None:
            raise MissionLedgerError(f"unknown mission: {mission_id}")
        return str(row["state"])

    @staticmethod
    def _next_seq(conn: sqlite3.Connection, mission_id: str) -> int:
        row = conn.execute("SELECT COALESCE(MAX(event_seq), 0) + 1 AS next_seq FROM mission_events WHERE mission_id=?", (mission_id,)).fetchone()
        return int(row["next_seq"])

    def _append_event_conn(
        self,
        conn: sqlite3.Connection,
        *,
        mission_id: str,
        event_key: str,
        event_type: str,
        payload: dict[str, Any],
        now_s: str,
    ) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        event_hash = sha256_text(payload_json)
        existing = conn.execute(
            "SELECT * FROM mission_events WHERE mission_id=? AND event_key=?",
            (mission_id, event_key),
        ).fetchone()
        if existing is not None:
            if existing["event_sha256"] != event_hash or existing["event_type"] != event_type:
                raise DuplicateMissionEvent(f"event key already contains different bytes: {event_key}")
            return dict(existing) | {"duplicate": True, "payload": json.loads(existing["event_json"])}
        seq = self._next_seq(conn, mission_id)
        conn.execute(
            "INSERT INTO mission_events(mission_id,event_seq,event_key,event_type,event_json,event_sha256,recorded_at) VALUES(?,?,?,?,?,?,?)",
            (mission_id, seq, event_key, event_type, payload_json, event_hash, now_s),
        )
        if event_type in {"mission_stopped", "mission_escalated"}:
            state = "stopped" if event_type == "mission_stopped" else "escalated"
            conn.execute("UPDATE missions SET state=?,stop_reason=?,updated_at=? WHERE mission_id=?", (state, payload.get("reason"), now_s, mission_id))
        else:
            conn.execute("UPDATE missions SET updated_at=? WHERE mission_id=?", (now_s, mission_id))
        return {
            "schema": EVENT_SCHEMA,
            "mission_id": mission_id,
            "event_seq": seq,
            "event_key": event_key,
            "event_type": event_type,
            "payload": payload,
            "event_sha256": event_hash,
            "recorded_at": now_s,
            "duplicate": False,
        }

    def start(self, contract: MissionContract) -> dict[str, Any]:
        if contract.schema_version != MISSION_SCHEMA:
            raise MissionLedgerError("unsupported mission schema")
        contract_json = canonical_json(contract.as_dict())
        contract_hash = sha256_text(contract_json)
        now_s = contract.created_at or iso(utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM missions WHERE mission_id=?", (contract.mission_id,)).fetchone()
            if existing is not None:
                if existing["contract_sha256"] != contract_hash:
                    raise MissionAlreadyExists("mission_id already contains a different contract")
                return dict(existing) | {"duplicate": True, "contract": contract.as_dict()}
            conn.execute(
                "INSERT INTO missions(mission_id,schema_version,contract_json,contract_sha256,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (contract.mission_id, contract.schema_version, contract_json, contract_hash, "running", now_s, now_s),
            )
            event = self._append_event_conn(
                conn,
                mission_id=contract.mission_id,
                event_key="mission-started",
                event_type="mission_started",
                payload={"contract_sha256": contract_hash, "run_id": contract.run_id, "instruction_id": contract.instruction_id},
                now_s=now_s,
            )
        return {"mission_id": contract.mission_id, "state": "running", "contract_sha256": contract_hash, "event": event, "duplicate": False}

    def append_event(self, mission_id: str, *, event_key: str, event_type: str, payload: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._mission_state(conn, mission_id)
            return self._append_event_conn(conn, mission_id=mission_id, event_key=event_key, event_type=event_type, payload=payload, now_s=now_s)

    def verify_identity(self, mission_id: str, *, branch: str, head: str, now: datetime | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT contract_json FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if row is None:
            raise MissionLedgerError(f"unknown mission: {mission_id}")
        contract = json.loads(row["contract_json"])
        if branch == contract["branch"] and head == contract["head"]:
            return {"verified": True, "branch": branch, "head": head}
        self.append_event(
            mission_id,
            event_key=f"stale-head:{branch}:{head}",
            event_type="stale_head_detected",
            payload={"expected_branch": contract["branch"], "expected_head": contract["head"], "observed_branch": branch, "observed_head": head},
            now=now,
        )
        raise StaleMissionIdentity(f"mission target is {contract['branch']}@{contract['head']}, observed {branch}@{head}")

    def record_execution(
        self,
        mission_id: str,
        *,
        run_id: str,
        instruction_sha256: str,
        result_sha256: str,
        branch: str,
        head: str,
        execution_disposition: str,
        report_ref: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        _require_hash(instruction_sha256, "instruction_sha256")
        _require_hash(result_sha256, "result_sha256")
        self.verify_identity(mission_id, branch=branch, head=head, now=now)
        payload = {
            "run_id": run_id,
            "instruction_sha256": instruction_sha256,
            "result_sha256": result_sha256,
            "repository": {"branch": branch, "head": head},
            "execution_disposition": execution_disposition,
            "report_ref": report_ref,
        }
        return self.append_event(mission_id, event_key=f"execution:{run_id}", event_type="execution_recorded", payload=payload, now=now)

    def claim_supervisor(self, mission_id: str, *, claim_kind: str, owner: str, expected_version: int, lease_seconds: int = 900, now: datetime | None = None) -> dict[str, Any]:
        if claim_kind not in {"review", "dispatch"}:
            raise MissionLedgerError("claim_kind must be review or dispatch")
        if not owner.strip() or expected_version < 0 or lease_seconds <= 0:
            raise MissionLedgerError("invalid supervisory claim arguments")
        current = now or utc_now()
        now_s = iso(current)
        expiry_s = iso(current + timedelta(seconds=lease_seconds))
        token = secrets.token_hex(16)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            state = self._mission_state(conn, mission_id)
            if state in {"stopped", "escalated"}:
                raise MissionStopped(f"mission is {state}")
            row = conn.execute("SELECT * FROM supervisor_claims WHERE mission_id=? AND claim_kind=?", (mission_id, claim_kind)).fetchone()
            if row is None:
                if expected_version != 0:
                    raise CompareAndSwapConflict("claim version does not start at zero")
                version = 1
                conn.execute(
                    "INSERT INTO supervisor_claims(mission_id,claim_kind,owner,claim_token,version,lease_expires_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (mission_id, claim_kind, owner, token, version, expiry_s, now_s),
                )
            else:
                if int(row["version"]) != expected_version:
                    raise CompareAndSwapConflict(f"expected claim version {expected_version}, current {row['version']}")
                if row["lease_expires_at"] > now_s:
                    raise SupervisorClaimUnavailable(f"{claim_kind} claim is held by {row['owner']}")
                version = expected_version + 1
                conn.execute(
                    "UPDATE supervisor_claims SET owner=?,claim_token=?,version=?,lease_expires_at=?,updated_at=? WHERE mission_id=? AND claim_kind=?",
                    (owner, token, version, expiry_s, now_s, mission_id, claim_kind),
                )
            event = self._append_event_conn(conn, mission_id=mission_id, event_key=f"claim:{claim_kind}:{version}", event_type="supervisor_claimed", payload={"claim_kind": claim_kind, "owner": owner, "version": version}, now_s=now_s)
        return {"mission_id": mission_id, "claim_kind": claim_kind, "owner": owner, "claim_token": token, "version": version, "lease_expires_at": expiry_s, "event": event}

    def release_supervisor(self, mission_id: str, *, claim_kind: str, owner: str, claim_token: str, version: int, now: datetime | None = None) -> dict[str, Any]:
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM supervisor_claims WHERE mission_id=? AND claim_kind=?", (mission_id, claim_kind)).fetchone()
            if row is None or row["owner"] != owner or row["claim_token"] != claim_token or int(row["version"]) != version:
                raise CompareAndSwapConflict("supervisory claim release lost its compare-and-swap identity")
            # Retain the version as the CAS fence.  A future claimant must
            # present this released version rather than restarting at zero.
            conn.execute("UPDATE supervisor_claims SET lease_expires_at=?,updated_at=? WHERE mission_id=? AND claim_kind=?", (now_s, now_s, mission_id, claim_kind))
            event = self._append_event_conn(conn, mission_id=mission_id, event_key=f"release:{claim_kind}:{version}", event_type="supervisor_released", payload={"claim_kind": claim_kind, "owner": owner, "version": version}, now_s=now_s)
        return {"released": True, "event": event}

    def record_review(
        self,
        mission_id: str,
        *,
        reviewer_id: str,
        decision_id: str,
        cursor_seq: int,
        execution_disposition: str,
        semantic_disposition: str,
        decision: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if cursor_seq < 0:
            raise StaleReviewCursor("cursor_seq must be non-negative")
        now_s = iso(now or utc_now())
        decision_payload = {
            "schema": REVIEW_SCHEMA,
            "decision_id": decision_id,
            "reviewer_id": reviewer_id,
            "cursor_seq": cursor_seq,
            "execution_disposition": execution_disposition,
            "semantic_disposition": semantic_disposition,
            "decision": decision,
        }
        decision_json = canonical_json(decision_payload)
        decision_hash = sha256_text(decision_json)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._mission_state(conn, mission_id)
            existing = conn.execute("SELECT * FROM supervisor_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if existing is not None:
                if existing["decision_sha256"] != decision_hash:
                    raise DuplicateMissionEvent("decision_id already contains different bytes")
                return dict(existing) | {"duplicate": True, "decision": json.loads(existing["decision_json"])}
            latest = self._next_seq(conn, mission_id) - 1
            if cursor_seq > latest:
                raise StaleReviewCursor(f"review cursor {cursor_seq} is beyond latest event {latest}")
            cursor = conn.execute("SELECT cursor_seq FROM review_cursors WHERE mission_id=? AND reviewer_id=?", (mission_id, reviewer_id)).fetchone()
            if cursor is not None and cursor_seq < int(cursor["cursor_seq"]):
                raise StaleReviewCursor(f"review cursor moved backwards from {cursor['cursor_seq']} to {cursor_seq}")
            conn.execute(
                "INSERT INTO supervisor_decisions(decision_id,mission_id,reviewer_id,cursor_seq,execution_disposition,semantic_disposition,decision_json,decision_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (decision_id, mission_id, reviewer_id, cursor_seq, execution_disposition, semantic_disposition, decision_json, decision_hash, now_s),
            )
            event = self._append_event_conn(conn, mission_id=mission_id, event_key=f"review:{decision_id}", event_type="supervisor_review_recorded", payload=decision_payload | {"decision_sha256": decision_hash}, now_s=now_s)
            conn.execute(
                "INSERT INTO review_cursors(mission_id,reviewer_id,cursor_seq,decision_id,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(mission_id,reviewer_id) DO UPDATE SET cursor_seq=excluded.cursor_seq,decision_id=excluded.decision_id,updated_at=excluded.updated_at",
                (mission_id, reviewer_id, cursor_seq, decision_id, now_s),
            )
        return {"decision_id": decision_id, "mission_id": mission_id, "decision_sha256": decision_hash, "cursor_seq": cursor_seq, "event": event, "duplicate": False}

    def dispatch(self, mission_id: str, *, owner: str, claim_token: str, version: int, instruction_id: str, instruction_sha256: str, now: datetime | None = None) -> dict[str, Any]:
        _require_hash(instruction_sha256, "instruction_sha256")
        now_s = iso(now or utc_now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM supervisor_claims WHERE mission_id=? AND claim_kind='dispatch'", (mission_id,)).fetchone()
            if row is None or row["owner"] != owner or row["claim_token"] != claim_token or int(row["version"]) != version or row["lease_expires_at"] <= now_s:
                raise CompareAndSwapConflict("dispatch claim is not current")
            event = self._append_event_conn(conn, mission_id=mission_id, event_key=f"dispatch:{instruction_id}:{instruction_sha256}", event_type="dispatch_authorised", payload={"instruction_id": instruction_id, "instruction_sha256": instruction_sha256, "owner": owner, "claim_version": version}, now_s=now_s)
        return event

    def status(self, mission_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            mission = conn.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
            if mission is None:
                raise MissionLedgerError(f"unknown mission: {mission_id}")
            event = conn.execute("SELECT * FROM mission_events WHERE mission_id=? ORDER BY event_seq DESC LIMIT 1", (mission_id,)).fetchone()
            cursors = [dict(row) for row in conn.execute("SELECT * FROM review_cursors WHERE mission_id=? ORDER BY reviewer_id", (mission_id,))]
            claims = [dict(row) for row in conn.execute("SELECT mission_id,claim_kind,owner,version,lease_expires_at,updated_at FROM supervisor_claims WHERE mission_id=? ORDER BY claim_kind", (mission_id,))]
            decision = conn.execute("SELECT * FROM supervisor_decisions WHERE mission_id=? ORDER BY created_at DESC LIMIT 1", (mission_id,)).fetchone()
        return {
            "schema": MISSION_SCHEMA,
            "mission_id": mission_id,
            "state": mission["state"],
            "contract": json.loads(mission["contract_json"]),
            "contract_sha256": mission["contract_sha256"],
            "latest_event": (dict(event) | {"payload": json.loads(event["event_json"])}) if event else None,
            "review_cursors": cursors,
            "supervisor_claims": claims,
            "latest_decision": (dict(decision) | {"decision": json.loads(decision["decision_json"])}) if decision else None,
            "updated_at": mission["updated_at"],
        }

    def supervisor_brief(self, mission_id: str) -> str:
        status = self.status(mission_id)
        contract = status["contract"]
        latest = status["latest_event"] or {}
        decision = status["latest_decision"] or {}
        return "\n".join(
            [
                f"Mission {mission_id} [{status['state']}]",
                f"Tranche: {contract['tranche_id']} | instruction: {contract['instruction_id']} | run: {contract['run_id']}",
                f"Repository: {contract['branch']}@{contract['head']}",
                f"Latest event: {latest.get('event_seq', 'none')} {latest.get('event_type', 'none')}",
                f"Review: {decision.get('execution_disposition', 'unreviewed')} / {decision.get('semantic_disposition', 'unreviewed')}",
                f"Cursors: {len(status['review_cursors'])} | active claims: {len(status['supervisor_claims'])}",
            ]
        )

    def stop(self, mission_id: str, *, reason: str, actor: str, now: datetime | None = None) -> dict[str, Any]:
        if not reason.strip() or not actor.strip():
            raise MissionLedgerError("stop reason and actor are required")
        return self.append_event(mission_id, event_key=f"stop:{actor}:{sha256_text(reason)[:16]}", event_type="mission_stopped", payload={"reason": reason, "actor": actor}, now=now)

    def escalate(self, mission_id: str, *, reason: str, actor: str, now: datetime | None = None) -> dict[str, Any]:
        if not reason.strip() or not actor.strip():
            raise MissionLedgerError("escalation reason and actor are required")
        return self.append_event(mission_id, event_key=f"escalate:{actor}:{sha256_text(reason)[:16]}", event_type="mission_escalated", payload={"reason": reason, "actor": actor}, now=now)


__all__ = [
    "CompareAndSwapConflict",
    "DuplicateMissionEvent",
    "EVENT_SCHEMA",
    "MissionAlreadyExists",
    "MissionContract",
    "MissionLedger",
    "MissionLedgerError",
    "MissionStopped",
    "MISSION_SCHEMA",
    "REVIEW_SCHEMA",
    "StaleMissionIdentity",
    "StaleReviewCursor",
    "SupervisorClaimUnavailable",
]
