"""Central-only ACNC acquisition for the frozen empirical Ethos/Notability cohort.

This is deliberately an acquisition/retention program, not a semantic worker:
it is the only module in this pilot which imports ``urllib``.  It writes raw
bytes, a deterministic JSON representation, and an append-only attempt record.
All unavailable source families are retained as coverage gaps rather than being
silently retried by a section-specific consumer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www.acnc.gov.au/api/dynamics"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def get(url: str) -> tuple[bytes, str, int, str]:
    request = Request(url, headers={"User-Agent": "CharityGraph central empirical acquisition/1"})
    with urlopen(request, timeout=45) as response:  # nosec: fixed public regulatory host
        return response.read(), response.headers.get_content_type(), response.status, response.geturl()


def attempt(case: dict[str, object], root: Path) -> dict[str, object]:
    name = str(case["display_name"])
    requested = f"{BASE}/search/charity?{urlencode({'search': name})}"
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = {"case_id": case["case_id"], "subject_id": case["subject_id"], "source_family": "acnc_regulatory", "source_role": "regulatory", "requested_locator": requested, "retrieved_at": stamp, "acquisition_method": "central_acnc_public_api_v1"}
    try:
        body, media_type, status, resolved = get(requested)
        search_hash = digest(body)
        search = json.loads(body)
        rows = search.get("results", [])
        # The public search envelope exposes ``Name`` while older entity
        # examples used ``CharityName``.  Keep this compatibility at the
        # central boundary and retain the exact-name requirement.
        exact = [row for row in rows if str(row.get("data", {}).get("Name", row.get("data", {}).get("CharityName", ""))).casefold() == name.casefold()]
        if len(exact) != 1:
            return {**base, "status": "binding_unresolved", "http_status": status, "resolved_locator": resolved, "raw_sha256": search_hash, "failure": f"expected one exact charity-name result; got {len(exact)}", "coverage_gap": "resolved subject binding unavailable"}
        uuid = exact[0]["uuid"]
        entity_url = f"{BASE}/entity/{uuid}"
        entity_body, entity_type, entity_status, entity_resolved = get(entity_url)
        entity_hash = digest(entity_body)
        entity = json.loads(entity_body)
        binding = {"registry_subject_id": case["subject_id"], "acnc_uuid": uuid, "abn": entity.get("data", {}).get("Abn"), "acnc_name": entity.get("data", {}).get("Name", entity.get("data", {}).get("CharityName")), "state": "resolved", "policy_version": "empirical-acnc-exact-name-binding-v1"}
        if str(binding["acnc_name"] or "").casefold() != name.casefold():
            return {**base, "status": "binding_unresolved", "http_status": entity_status, "resolved_locator": entity_resolved, "raw_sha256": entity_hash, "failure": "entity response name does not exactly bind frozen registry name", "coverage_gap": "resolved subject binding unavailable"}
        raw = root / "raw" / f"{entity_hash}.json"; raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(entity_body)
        representation = {"representation_id": "repr:" + entity_hash, "representation_hash": entity_hash, "representation_kind": "native_structured_json", "input_blob_id": "srcblob:" + entity_hash, "input_blob_hash": entity_hash, "json": entity}
        rep_bytes = canonical(representation); rep_hash = digest(rep_bytes)
        rep = root / "representations" / f"{rep_hash}.json"; rep.parent.mkdir(parents=True, exist_ok=True); rep.write_bytes(rep_bytes)
        return {**base, "status": "captured", "http_status": entity_status, "resolved_locator": entity_resolved, "source_version": entity_hash, "raw_blob_id": "srcblob:" + entity_hash, "raw_sha256": entity_hash, "representation_id": "repr:" + entity_hash, "representation_sha256": rep_hash, "representation_locator": rep.relative_to(root).as_posix(), "media_type": entity_type or media_type, "subject_binding": binding, "evidence_fragment_id": "evidence:" + digest(canonical({"case": case["case_id"], "representation": rep_hash})), "fragment_locator": "$.data", "fragment_sha256": digest(canonical(entity.get("data", {})))}
    except Exception as error:
        return {**base, "status": "unavailable", "failure": f"{type(error).__name__}: {error}", "coverage_gap": "central regulatory acquisition unavailable"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    if len(cohort.get("cases", [])) != 15 or sum(c["arm"] == "challenge" for c in cohort["cases"]) != 10 or sum(c["arm"] == "blind" for c in cohort["cases"]) != 5:
        raise SystemExit("cohort is not exactly 10 challenge plus 5 blind")
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "source-attempt-manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    attempts = [attempt(case, args.out) for case in cohort["cases"]]
    history = list(previous.get("attempt_history", previous.get("attempts", []))) + attempts
    manifest = {"corpus_id": "empirical-ethos-notability-v1", "version": "1.0.0", "cohort_sha256": digest(canonical(cohort)), "acquisition_finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "network_owner": "central_acquisition_only", "provider_calls": 0, "attempts": attempts, "attempt_history": history, "coverage_gaps": [a for a in attempts if a["status"] != "captured"]}
    manifest_bytes = canonical(manifest); manifest["manifest_sha256"] = digest(manifest_bytes)
    (args.out / "source-attempt-manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"captured": sum(a["status"] == "captured" for a in attempts), "failed": sum(a["status"] != "captured" for a in attempts), "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
