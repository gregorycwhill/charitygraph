"""Fail-closed reconciliation of historical S0 control state.

Historical terminal records are deliberately not live execution attempts.  The
only live-history import is Attempt 17, whose complete immutable checkpoint is
copied after its database digest is verified.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from .runtime.catalog import CatalogError, ConflictError, SQLiteCatalog

ATTEMPT17_DB_SHA256 = "861da72ab04ead55512b03a0936038584a5488a57cdd57659cfa2df7de124be5"
ATTEMPT18_CHECKPOINT_SHA256 = "32919e7c8c599f8b96231041657e75f7ffdea2e46378f5238941122fcc3c741a"
ATTEMPT18_DB_SHA256 = "c9db6fe59170b7a4173d6bb62481e689d5afc719b8f4d2b156e6522f40bdd60f"

_ATTEMPT17_TABLES = (
    "cohorts", "runs", "scale_s0_mandates", "tasks", "delivery_jobs", "budget_reservations",
    "scale_s0_execution_attempts", "scale_s0_frozen_packets", "scale_s0_physical_bundles",
    "scale_s0_reservation_bindings", "reservation_tasks",
    "physical_attempts", "provider_request_items", "physical_attempt_members",
    "provider_request_attempts", "standard_transport_traces", "scale_s0_attestation_windows",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_attempt17_rows(catalog: SQLiteCatalog, source: Path) -> None:
    if _sha256(source) != ATTEMPT17_DB_SHA256:
        raise ConflictError("Attempt-17 checkpoint database hash is not the certified immutable hash")
    src = sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True)
    src.row_factory = sqlite3.Row
    try:
        with catalog._connection(immediate=True) as dst:
            for table in _ATTEMPT17_TABLES:
                source_columns = [row[1] for row in src.execute(f'PRAGMA table_info("{table}")')]
                target_columns = [row[1] for row in dst.execute(f'PRAGMA table_info("{table}")')]
                columns = [name for name in source_columns if name in target_columns]
                if not columns:
                    continue
                pk = [row[1] for row in src.execute(f'PRAGMA table_info("{table}")') if row[5]]
                if not pk:
                    raise CatalogError(f"historical import table has no primary key: {table}")
                for row in src.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in columns)} FROM "{table}"'):
                    values = tuple(row[c] for c in columns)
                    where = " AND ".join(f'"{key}"=?' for key in pk)
                    prior = dst.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in columns)} FROM "{table}" WHERE {where}', tuple(row[key] for key in pk)).fetchone()
                    if prior is not None:
                        if tuple(prior[c] for c in columns) != values:
                            raise ConflictError(f"Attempt-17 historical row conflicts in {table}")
                        continue
                    placeholders = ", ".join("?" for _ in columns)
                    try:
                        dst.execute(f'INSERT INTO "{table}" ({", ".join(chr(34)+c+chr(34) for c in columns)}) VALUES ({placeholders})', values)
                    except sqlite3.IntegrityError as error:
                        raise CatalogError(f"Attempt-17 historical dependency is absent in {table}") from error
            catalog._commit(dst)
    finally:
        src.close()


def import_attempt17(catalog: SQLiteCatalog, *, checkpoint_db: str | Path) -> None:
    """Import only the exact operational rows proven by Attempt-17's DB."""
    _copy_attempt17_rows(catalog, Path(checkpoint_db))


def import_historical_terminals(catalog: SQLiteCatalog, *, attempt18_checkpoint: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Record Attempts 18/19 without manufacturing live allocator rows."""
    checkpoint = Path(attempt18_checkpoint)
    db = checkpoint.with_name("attempt18.sqlite3")
    if _sha256(checkpoint) != ATTEMPT18_CHECKPOINT_SHA256 or _sha256(db) != ATTEMPT18_DB_SHA256:
        raise ConflictError("Attempt-18 certified evidence hash mismatch")
    a18 = catalog.register_scale_s0_historical_terminal({
        "attempt_id": "attempt:s0:18", "run_id": "run:s0:attempt-18",
        "terminal_state": "consumed_non_resumable",
        "terminal_reason": "zero_crossing_obsolete_non_resumable_builder_identity_changed",
        "provider_crossings": "zero", "reservation_state": "not_created",
        "a3_state": "not_created", "checkpoint_state": "preprovider_only",
        "evidence": {"authority_id": "CG-S0-PO-ATTEMPT18-2026-09-26",
                     "checkpoint_sha256": ATTEMPT18_CHECKPOINT_SHA256, "checkpoint_db_sha256": ATTEMPT18_DB_SHA256,
                     "evidence_runs": ["CG-S0-ATTEMPT18-AUTHORITY-PREPROVIDER-MEGA-TERRA-060",
                                       "CG-S0-ATTEMPT18-LIVE-LOCATOR-EXECUTION-063",
                                       "CG-S0-ATTEMPT18-LOCATOR-BODY-REPAIR-TERRA-064"]},
        "recorded_at": "2026-09-26T00:00:00+00:00",
    })
    a19 = catalog.register_scale_s0_historical_terminal({
        "attempt_id": "attempt:s0:19", "run_id": "run:s0:attempt-19",
        "terminal_state": "consumed_non_resumable",
        "terminal_reason": "historical_superseded_before_preprovider_checkpoint",
        "provider_crossings": "zero", "reservation_state": "not_created",
        "a3_state": "not_created", "checkpoint_state": "not_created",
        "evidence": {"authority_id": "CG-S0-PO-ATTEMPT19-2026-09-26",
                     "evidence_runs": ["CG-S0-ATTEMPT19-DATA-AUTHORITY-MEGA-TERRA-068",
                                       "CG-S0-ATTEMPT19-PREPROVIDER-FINAL-MEGA-TERRA-069"],
                     "maximum_new_exposure_usd": "0.30", "conservative_aggregate_exposure_usd": "0.40",
                     "provider_calls": 0, "reservations": 0, "a3_attestations": 0,
                     "attempt19_checkpoint": "not_created"},
        "recorded_at": "2026-09-26T00:00:00+00:00",
    })
    return a18, a19
