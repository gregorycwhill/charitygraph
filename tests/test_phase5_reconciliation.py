from __future__ import annotations

import hashlib
import json
from pathlib import Path

from charitygraph.phase5_reconciliation import audit_website_events


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_audit_requires_catalogue_for_exact_locator_and_hash_verified_bytes(tmp_path: Path) -> None:
    historical = tmp_path / "historical"; runtime = tmp_path / "runtime"
    _write_json(historical / "acnc-profiles.json", {"entities": {"12345678901": {"profile": {"data": {"Website": "example.org"}}}}})
    body = b"kept"; digest = hashlib.sha256(body).hexdigest()
    (runtime / "objects" / "objects" / "sha256" / digest[:2]).mkdir(parents=True)
    (runtime / "objects" / "objects" / "sha256" / digest[:2] / digest).write_bytes(body)
    _write_json(runtime / "network-cache" / "good.json", {"event": {"source_family": "official_website", "outcome": "available", "requested_url": "https://example.org", "resolved_url": "https://www.example.org/", "content_hash": digest}})
    _write_json(runtime / "network-cache" / "bad.json", {"event": {"source_family": "official_website", "outcome": "available", "requested_url": "https://other.example.org", "resolved_url": "https://other.example.org", "content_hash": digest}})
    decisions = audit_website_events(runtime_root=runtime, historical_root=historical)
    assert decisions[0]["classification"] == "ADMISSIBILITY_UNRESOLVED"
    assert decisions[1]["classification"] == "ADMISSIBILITY_UNRESOLVED"
    assert decisions[1]["abn"] == "12345678901"
