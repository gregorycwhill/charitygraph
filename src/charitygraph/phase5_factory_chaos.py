"""Deterministic, private Factory fault-selection policy for core rehearsal."""
from __future__ import annotations
import hashlib
from collections import Counter
from typing import Iterable

CHAOS_POLICY_VERSION = "phase5-core-chaos-v1"

def fault_bucket(physical_attempt_id: str) -> int:
    return int(hashlib.sha256((CHAOS_POLICY_VERSION + physical_attempt_id).encode()).hexdigest()[:8], 16) % 100

def scenario_for(physical_attempt_id: str) -> str | None:
    bucket=fault_bucket(physical_attempt_id)
    return ("C1_pre_send" if bucket < 4 else "C2_send_ambiguous" if bucket < 8 else "C3_receipt_restart" if bucket < 12 else "C4_structural" if bucket < 16 else "C5_grounding" if bucket < 20 else "C6_partial_bundle" if bucket < 24 else None)

def scenario_ledger(physical_attempt_ids: Iterable[str]) -> dict[str, object]:
    rows=[{"physical_attempt_id":attempt,"scenario":scenario_for(attempt)} for attempt in sorted(physical_attempt_ids)]
    return {"policy_version":CHAOS_POLICY_VERSION,"rows":rows,"counts":dict(sorted(Counter(row["scenario"] or "reference" for row in rows).items()))}
