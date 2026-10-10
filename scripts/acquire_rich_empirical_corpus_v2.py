"""Central, source-family-neutral enrichment for a frozen empirical cohort.

This program consumes regulatory profiles already retained by central acquisition.
It mechanically follows only source-native ``Website`` and regulator ``Documents``
locators, retaining every successful byte stream and every failed request.  It has
no domain-section, prompt, provider, or prose-ranking logic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalise_web_locator(locator: object) -> str:
    """Return a fetchable HTTPS locator for an ACNC bare web domain.

    This is deliberately transport-only: absolute HTTP(S) locators are returned
    byte-for-byte, while only a syntactically valid domain (with optional
    port/path/query/fragment) receives an HTTPS scheme.  Other schemes and
    malformed values remain explicit acquisition failures rather than guesses.
    """
    if not isinstance(locator, str) or not locator or locator != locator.strip():
        raise ValueError("locator must be a non-empty, whitespace-free string")
    parsed = urlsplit(locator)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"unsupported absolute locator: {locator!r}")
        return locator
    if locator.startswith("//") or parsed.netloc:
        raise ValueError(f"locator has no supported scheme: {locator!r}")
    host = parsed.path.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    # Domains only; do not turn arbitrary labels, paths, IP literals, or local
    # names into network destinations.
    labels = host.split(".")
    if (len(labels) < 2 or any(not label or len(label) > 63 or
                               label[0] == "-" or label[-1] == "-" or
                               not all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in label)
                               for label in labels)):
        raise ValueError(f"unsupported bare web domain: {locator!r}")
    return "https://" + locator


def fetch(locator: str) -> tuple[bytes, str, int, str]:
    request = Request(locator, headers={"User-Agent": "CharityGraph central retained acquisition/2"})
    with urlopen(request, timeout=45) as response:  # nosec B310: public locators retained from a regulator profile
        return response.read(), response.geturl(), response.status, response.headers.get_content_type()


def retain(root: Path, *, case: dict, family: str, role: str, requested: str, body: bytes, resolved: str, status: int, media: str, source_version: str | None = None) -> dict:
    raw_hash = sha(body)
    raw_path = root / "raw" / raw_hash
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(body)
    # Decoding is representation, not language interpretation: the complete
    # source is preserved so later bounded consumers can select it.
    representation = {"kind": "decoded_source_v1", "input_blob_id": "srcblob:" + raw_hash,
                      "input_blob_hash": raw_hash, "media_type": media,
                      "text": body.decode("utf-8", "replace")}
    rep_bytes = canon(representation)
    rep_hash = sha(rep_bytes)
    rep_path = root / "representations" / (rep_hash + ".json")
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    if not rep_path.exists():
        rep_path.write_bytes(rep_bytes)
    retrieved_at = stamp()
    source_record_id = "srcrec:" + sha(canon({"family": family, "locator": resolved, "raw": raw_hash, "version": source_version}))
    binding = {"registry_subject_id": case["subject_id"], "state": "resolved",
               "policy_version": "central-regulatory-profile-bound-v2"}
    fragment = {"case": case["case_id"], "source_record_id": source_record_id, "representation": rep_hash}
    return {"case_id": case["case_id"], "subject_id": case["subject_id"], "source_family": family,
            "source_role": role, "status": "captured", "requested_locator": requested,
            "resolved_locator": resolved, "http_status": status, "media_type": media,
            "retrieved_at": retrieved_at, "source_version": source_version, "raw_blob_id": "srcblob:" + raw_hash,
            "raw_sha256": raw_hash, "representation_id": "repr:" + rep_hash,
            "representation_sha256": rep_hash, "representation_locator": rep_path.relative_to(root).as_posix(),
            "source_record_id": source_record_id, "subject_binding": binding,
            "evidence_fragment_id": "evidence:" + sha(canon(fragment)), "fragment_locator": "$",
            "fragment_sha256": sha(rep_bytes), "acquisition_method": "central_regulatory_profile_locator_v2"}


def failure(case: dict, family: str, requested: str, error: Exception | str) -> dict:
    return {"case_id": case["case_id"], "subject_id": case["subject_id"], "source_family": family,
            "status": "unavailable", "requested_locator": requested, "retrieved_at": stamp(),
            "failure": str(error), "coverage_gap": "central source-family acquisition unavailable",
            "acquisition_method": "central_regulatory_profile_locator_v2"}


def retryable_bare_domain_failure(item: dict) -> bool:
    """Whether an old failed official-site record is repairable by this rule."""
    if item.get("source_family") != "official_website" or item.get("status") == "captured":
        return False
    try:
        normalise_web_locator(item.get("requested_locator"))
    except ValueError:
        return False
    return not urlsplit(str(item.get("requested_locator"))).scheme


def acquisition_complete(*, original_attempts: list[dict], retry_attempts: list[dict]) -> bool:
    """A bounded plan is complete only after every repairable transport failure ran."""
    retried = {item.get("predecessor_attempt_sha256") for item in retry_attempts}
    return all(sha(canon(item)) in retried for item in original_attempts if retryable_bare_domain_failure(item))


def run_repairs(*, cohort: dict, prior_rich: Path, out: Path) -> dict:
    """Retry only historical bare-domain failures, retaining old/new provenance separately."""
    old = json.loads((prior_rich / "source-attempt-manifest.json").read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in cohort["cases"]}
    out.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    for predecessor in old["attempts"]:
        if not retryable_bare_domain_failure(predecessor):
            continue
        case = cases[predecessor["case_id"]]
        predecessor_hash = sha(canon(predecessor))
        requested = str(predecessor["requested_locator"])
        normalised = normalise_web_locator(requested)
        try:
            body, resolved, status, media = fetch(normalised)
            item = retain(out, case=case, family="official_website", role="supporting",
                          requested=requested, body=body, resolved=resolved, status=status,
                          media=media, source_version="central-retry:" + predecessor_hash)
        except Exception as exc:
            item = failure(case, "official_website", requested, exc)
        item.update({"predecessor_attempt_sha256": predecessor_hash,
                     "normalised_locator": normalised,
                     "retry_reason": "repair bare-domain transport locator",
                     "acquisition_method": "central_regulatory_profile_locator_v3_retry"})
        attempts.append(item)
    manifest = {"corpus_id": "empirical-ethos-notability-rich-v2-repair", "version": "3.0.0",
                "cohort_sha256": sha(canon(cohort)), "prior_manifest_sha256": old["manifest_sha256"],
                "network_owner": "central_acquisition_only", "provider_calls": 0,
                "attempts": attempts, "acquisition_finished_at": stamp()}
    manifest["repairable_transport_failures_exhausted"] = acquisition_complete(
        original_attempts=old["attempts"], retry_attempts=attempts)
    manifest["manifest_sha256"] = sha(canon(manifest))
    (out / "source-attempt-manifest.json").write_bytes(canon(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--prior-retained", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--retry-prior-rich", type=Path,
                        help="retry only eligible bare-domain failures from this retained rich corpus")
    args = parser.parse_args()
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    if len(cohort.get("cases", [])) != 15 or sum(c["arm"] == "challenge" for c in cohort["cases"]) != 10:
        raise SystemExit("frozen cohort shape is invalid")
    if args.retry_prior_rich:
        manifest = run_repairs(cohort=cohort, prior_rich=args.retry_prior_rich, out=args.out)
        print(json.dumps({"retried": len(manifest["attempts"]),
                          "captured": sum(x["status"] == "captured" for x in manifest["attempts"]),
                          "repairable_transport_failures_exhausted": manifest["repairable_transport_failures_exhausted"],
                          "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
        return 0
    prior = json.loads((args.prior_retained / "source-attempt-manifest.json").read_text(encoding="utf-8"))
    prior_by_case = {item["case_id"]: item for item in prior["attempts"] if item["status"] == "captured"}
    args.out.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    for case in cohort["cases"]:
        prior_item = prior_by_case.get(case["case_id"])
        if not prior_item:
            attempts.append(failure(case, "central_binding", "", "no resolved prior regulatory binding; no locator substitution"))
            continue
        raw = args.prior_retained / "raw" / (prior_item["raw_sha256"] + ".json")
        try:
            profile = json.loads(raw.read_text(encoding="utf-8"))["data"]
        except Exception as exc:
            attempts.append(failure(case, "acnc_regulatory", str(raw), exc))
            continue
        website = profile.get("Website")
        if website:
            try:
                body, resolved, status, media = fetch(str(website))
                attempts.append(retain(args.out, case=case, family="official_website", role="supporting", requested=str(website), body=body, resolved=resolved, status=status, media=media))
            except Exception as exc:
                attempts.append(failure(case, "official_website", str(website), exc))
        else:
            attempts.append(failure(case, "official_website", "", "ACNC profile has no Website locator"))
        reports = [d for d in (profile.get("Documents") or []) if d.get("Url") and str(d.get("type")) in {"Annual Report", "Financial Report"}]
        reports.sort(key=lambda d: (str(d.get("Year") or ""), str(d.get("Date") or ""), str(d.get("Url"))), reverse=True)
        if not reports:
            attempts.append(failure(case, "regulatory_filing", "", "ACNC profile has no annual/financial report locator"))
        for document in reports[:2]:
            url = str(document["Url"])
            try:
                body, resolved, status, media = fetch(url)
                attempts.append(retain(args.out, case=case, family="regulatory_filing", role="supporting", requested=url, body=body, resolved=resolved, status=status, media=media, source_version=str(document.get("Year") or "") or None))
            except Exception as exc:
                attempts.append(failure(case, "regulatory_filing", url, exc))
    manifest = {"corpus_id": "empirical-ethos-notability-rich-v2", "version": "2.0.0",
                "cohort_sha256": sha(canon(cohort)), "source_attempt_manifest_v1_sha256": prior.get("manifest_sha256"),
                "network_owner": "central_acquisition_only", "provider_calls": 0, "attempts": attempts,
                "coverage_gaps": [x for x in attempts if x["status"] != "captured"], "acquisition_finished_at": stamp()}
    manifest["manifest_sha256"] = sha(canon(manifest))
    (args.out / "source-attempt-manifest.json").write_bytes(canon(manifest))
    print(json.dumps({"captured": sum(x["status"] == "captured" for x in attempts), "failed": sum(x["status"] != "captured" for x in attempts), "manifest_sha256": manifest["manifest_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
