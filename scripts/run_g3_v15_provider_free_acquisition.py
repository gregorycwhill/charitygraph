"""Provider-free, bounded Source Universe v1 acquisition for frozen G3 rows.

This is deliberately transport-only: it never reads source prose to choose a
source, answer a question, or resolve an identity.  It retains immutable bytes
outside the repository and writes source-native acquisition metadata only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


FAMILIES = ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website", "annual_report", "wikipedia_wikimedia", "pfra")


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def retain(root: Path, body: bytes) -> str:
    digest = hashlib.sha256(body).hexdigest()
    target = root / "source-objects" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)
    return digest


def fetch(url: str, *, max_bytes: int = 5_000_000) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": "CharityGraph G3 provider-free acquisition/1.0"})
    with urlopen(request, timeout=45) as response:  # nosec B310: governed public locator
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise RuntimeError("response exceeds bounded acquisition size")
        return body, response.geturl(), response.headers.get_content_type()


def row(family: str, abn: str | None, url: str, root: Path, *, role: str, binding: str, max_bytes: int = 5_000_000) -> dict:
    try:
        body, resolved, media = fetch(url, max_bytes=max_bytes)
        if family == "official_website":
            requested_host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
            resolved_host = (urlsplit(resolved).hostname or "").casefold().removeprefix("www.")
            if requested_host != resolved_host:
                raise RuntimeError("official website redirect leaves governed locator host")
        return {"source_family": family, "abn": abn, "requested_locator": url, "resolved_locator": resolved,
                "role": role, "binding_state": binding, "acquisition_state": "ACQUIRED", "media_type": media,
                "byte_size": len(body), "payload_sha256": retain(root, body)}
    except Exception as error:
        return {"source_family": family, "abn": abn, "requested_locator": url, "role": role, "binding_state": binding,
                "acquisition_state": "UNAVAILABLE", "error_class": type(error).__name__, "error": str(error)[:240]}


def latest_report(data: dict) -> str | None:
    reports = [x for x in data.get("Documents") or [] if x.get("type") in {"Annual Report", "Financial Report"} and isinstance(x.get("Url"), str)]
    if not reports:
        return None
    return sorted(reports, key=lambda x: (str(x.get("Year") or ""), str(x.get("Date") or ""), str(x.get("Url"))), reverse=True)[0]["Url"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    payload = json.loads(args.profiles.read_text(encoding="utf-8"))
    args.output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    jobs: list[tuple[str, str | None, str, str, str, int]] = []
    for abn, item in sorted(payload["entities"].items()):
        profile = item["profile"]
        rows.append({"source_family": "acnc_register", "abn": abn, "requested_locator": "ACNC public profile payload", "role": "authority_identity", "binding_state": "EXACT_ABN_ACNC_BOUND", "acquisition_state": "ACQUIRED", "media_type": "application/json", "byte_size": len(canonical(profile)), "payload_sha256": retain(args.output_root, canonical(profile))})
        detail = item.get("ais_detail")
        if detail is not None:
            rows.append({"source_family": "acnc_ais_bundle", "abn": abn, "requested_locator": "ACNC latest submitted AIS", "role": "authority_filing", "binding_state": "EXACT_ABN_ACNC_BOUND", "acquisition_state": "ACQUIRED", "media_type": "application/json", "byte_size": len(canonical(detail)), "payload_sha256": retain(args.output_root, canonical(detail))})
        else:
            rows.append({"source_family": "acnc_ais_bundle", "abn": abn, "requested_locator": "ACNC latest submitted AIS", "role": "authority_filing", "binding_state": "EXACT_ABN_ACNC_BOUND", "acquisition_state": "UNAVAILABLE", "error_class": "NoSubmittedAIS", "error": item.get("ais_acquisition_failure")})
        jobs.append(("ato_abr_dgr", abn, f"https://abr.business.gov.au/ABN/View?id={abn}", "authority_identifier", "EXACT_ABN_BOUND", 2_000_000))
        website = (profile.get("data") or {}).get("Website")
        if isinstance(website, str) and website.startswith(("http://", "https://")):
            jobs.append(("official_website", abn, website, "official_homepage", "ACNC_GOVERNED_LOCATOR_BOUND", 2_000_000))
        else:
            rows.append({"source_family": "official_website", "abn": abn, "requested_locator": None, "role": "official_homepage", "binding_state": "NO_GOVERNED_LOCATOR", "acquisition_state": "UNAVAILABLE", "error_class": "NoACNCWebsite"})
        report = latest_report(profile.get("data") or {})
        if report:
            jobs.append(("annual_report", abn, report, "acnc_document_locator", "EXACT_ABN_ACNC_DOCUMENT_BOUND", 5_000_000))
        else:
            rows.append({"source_family": "annual_report", "abn": abn, "requested_locator": None, "role": "acnc_document_locator", "binding_state": "NO_ACNC_DOCUMENT_LOCATOR", "acquisition_state": "UNAVAILABLE", "error_class": "NoAnnualReportLocator"})
    jobs += [("wikipedia_wikimedia", None, "https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch=Australian%20charity", "shared_directory", "UNBOUND_SHARED_SOURCE", 1_000_000), ("pfra", None, "https://pfra.org.au/membership/charity-members/", "shared_directory", "UNBOUND_SHARED_SOURCE", 2_000_000)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(row, family, abn, url, args.output_root, role=role, binding=binding, max_bytes=max_bytes): (family, abn) for family, abn, url, role, binding, max_bytes in jobs}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda x: (x["source_family"], str(x.get("abn") or ""), str(x.get("requested_locator") or "")))
    result = {"schema": "charitygraph.g3.provider-free-source-acquisition/v1", "created_at": datetime.now(timezone.utc).isoformat(), "source_universe": list(FAMILIES), "provider_calls": 0, "rows": rows}
    result["ledger_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    (args.output_root / "acquisition-ledger.json").write_bytes(canonical(result))
    print(json.dumps({"rows": len(rows), "acquired": sum(x["acquisition_state"] == "ACQUIRED" for x in rows), "ledger_sha256": result["ledger_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
