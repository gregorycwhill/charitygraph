"""Offline, prospective admissibility decisions for the blocked Phase-5 run."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .phase5_baseline_corpus import governed_website_hosts, governed_website_url


DECISION_VERSION = "phase5-p5a-admissibility-v1"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _body_path(runtime_root: Path, content_hash: str) -> Path:
    return runtime_root / "objects" / "objects" / "sha256" / content_hash[:2] / content_hash


def audit_website_events(*, runtime_root: Path, historical_root: Path, catalog_path: Path | None = None) -> list[dict[str, Any]]:
    """Classify preserved website events without changing their historical status.

    The request is bound only by the exact governed profile locator after the
    runner's documented scheme normalisation.  A matching host is never a bind.
    """
    profiles = _read(historical_root / "acnc-profiles.json")["entities"]
    catalog = None
    if catalog_path is not None:
        if not catalog_path.is_file() or not catalog_path.stat().st_size:
            raise FileNotFoundError("expected existing non-empty source catalogue")
        catalog = sqlite3.connect(f"file:{catalog_path.as_posix()}?mode=ro", uri=True)
    expected: dict[str, list[str]] = {}
    for abn, item in profiles.items():
        value = ((item.get("profile") or {}).get("data") or {}).get("Website")
        if value:
            expected.setdefault(governed_website_url(str(value)), []).append(str(abn))
    decisions: list[dict[str, Any]] = []
    for cache_path in sorted((runtime_root / "network-cache").glob("*.json")):
        cached = _read(cache_path)
        event = cached.get("event") or {}
        if event.get("source_family") != "official_website":
            continue
        requested, resolved = event.get("requested_url"), event.get("resolved_url")
        candidates = expected.get(str(requested), [])
        content_hash = event.get("content_hash")
        body = _body_path(runtime_root, str(content_hash)) if content_hash else None
        body_valid = bool(body and body.is_file() and hashlib.sha256(body.read_bytes()).hexdigest() == content_hash)
        artifact_id = f"srcblob:{content_hash}" if content_hash else None
        receipts = records = artifacts = []
        if catalog is not None and content_hash:
            receipts = catalog.execute("select acquisition_id from acquisition_receipts where content_hash=? and requested_locator=? and resolved_locator=? and outcome='available'", (content_hash, requested, resolved)).fetchall()
            records = catalog.execute("select source_record_id from source_records where source_family='official_website' and source_role='official_homepage' and payload_hash=? and source_locator=?", (content_hash, resolved)).fetchall()
            artifacts = catalog.execute("select artifact_id from artifact_index where artifact_id=? and content_hash=? and availability='available'", (artifact_id, content_hash)).fetchall()
        lineage_ok = catalog is None or bool(receipts and records and artifacts)
        resolved_host = (urlsplit(str(resolved)).hostname or "").casefold()
        redirect_ok = bool(candidates and resolved_host in governed_website_hosts(str(requested)))
        successful = event.get("outcome") == "available"
        if not successful:
            classification, permitted, reason = "NOT_ADMISSIBLE", False, "original_event_not_successful"
        elif len(candidates) != 1:
            classification, permitted, reason = "ADMISSIBILITY_UNRESOLVED", False, "requested_locator_not_exactly_bound_to_one_governed_subject"
        elif not redirect_ok:
            classification, permitted, reason = "ADMISSIBILITY_UNRESOLVED", False, "resolved_host_outside_governed_locator_policy"
        elif not body_valid:
            classification, permitted, reason = "ADMISSIBILITY_UNRESOLVED", False, "retained_artifact_missing_or_hash_invalid"
        elif not lineage_ok:
            classification, permitted, reason = "ADMISSIBILITY_UNRESOLVED", False, "receipt_source_record_or_artifact_lineage_not_exact"
        else:
            classification, permitted, reason = "ELIGIBLE_PROSPECTIVE_REUSE", True, "exact_governed_locator_and_hash_verified_preserved_event"
        decisions.append({"decision_version": DECISION_VERSION, "cache_event": cache_path.name, "original_event": event, "abn": candidates[0] if len(candidates) == 1 else None, "governed_locator_candidates": candidates, "classification": classification, "permitted_in_clean_corpus": permitted, "reason": reason, "artifact_id": artifact_id, "receipt_ids": [x[0] for x in receipts], "source_record_ids": [x[0] for x in records], "retained_bytes_hash_verified": body_valid})
    return decisions


def summarise_admissibility(decisions: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(item["classification"] for item in decisions).items()))
