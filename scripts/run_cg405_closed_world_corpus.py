"""Provider-free CG405 closed-world acquisition experiment.

This is deliberately a narrow orchestration layer over the established ACNC,
ABR, Wikimedia and PFRA paths.  It persists private immutable bytes under the
runtime root and emits only provenance/identity metadata alongside them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from charitygraph.baseline_corpus import extract_pfra_members, resolve_wikipedia_candidate, select_filing_documents
from charitygraph.scoped_benchmark_v2 import ABNS, NAMES, SUBJECT_IDS, build_scoped_benchmark_v2

FAMILIES = ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website", "annual_report", "wikipedia_wikimedia", "pfra")
ACNC = "https://www.acnc.gov.au/api/dynamics"
WIKI = "https://en.wikipedia.org/w/api.php"
PFRA = ("https://pfra.org.au/membership/charity-members/", "https://pfra.org.au/membership/fundraising-agency-members/")
ABR = "https://abr.business.gov.au/ABN/View"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def put_json(path: Path, value: Any) -> str:
    body = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def git_value(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


class ClosedWorldFetch:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events: list[dict[str, Any]] = []
        self.objects = root / "objects" / "sha256"

    def fetch(self, family: str, url: str, hosts: set[str]) -> dict[str, Any]:
        started = utcnow()
        requested_host = (urlsplit(url).hostname or "").casefold()
        event: dict[str, Any] = {"source_family": family, "requested_url": url, "requested_host": requested_host, "started_at": started}
        if requested_host not in hosts:
            event.update({"outcome": "FAILED_CLASSIFIED", "reason": "host_outside_declared_family_boundary", "finished_at": utcnow()})
            self.events.append(event)
            return event
        try:
            request = Request(url, headers={"User-Agent": "CharityGraph CG405 closed-world corpus/1.0"})
            with urlopen(request, timeout=5) as response:  # nosec B310: host boundary checked above
                body = response.read(30_000_001)
                resolved = response.geturl()
                resolved_host = (urlsplit(resolved).hostname or "").casefold()
                if resolved_host not in hosts:
                    event.update({"outcome": "FAILED_CLASSIFIED", "reason": "redirect_left_declared_family_boundary", "resolved_url": resolved, "resolved_host": resolved_host})
                elif len(body) > 30_000_000:
                    event.update({"outcome": "FAILED_CLASSIFIED", "reason": "response_exceeds_bound", "resolved_url": resolved, "resolved_host": resolved_host})
                else:
                    digest = hashlib.sha256(body).hexdigest()
                    destination = self.objects / digest
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists():
                        destination.write_bytes(body)
                    event.update({"outcome": "CAPTURED", "resolved_url": resolved, "resolved_host": resolved_host, "response_status": response.status, "media_type": response.headers.get_content_type(), "byte_size": len(body), "content_sha256": digest, "object_path": str(destination)})
        except HTTPError as error:
            event.update({"outcome": "LEGITIMATELY_ABSENT" if error.code == 404 else "INACCESSIBLE", "response_status": error.code, "reason": f"http_{error.code}"})
        except (URLError, TimeoutError, ValueError) as error:
            event.update({"outcome": "INACCESSIBLE", "reason": type(error).__name__})
        event["finished_at"] = utcnow()
        self.events.append(event)
        return event


def terminal(row: dict[str, Any], state: str, reason: str, captures: list[dict[str, Any]] = []) -> dict[str, Any]:
    return {**row, "status": state, "reason": reason, "capture_events": captures, "terminal": True}


def event_state(event: dict[str, Any]) -> str:
    return event["outcome"] if event["outcome"] != "CAPTURED" else "CAPTURED"


def main(root: Path, data_repo: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    fetcher = ClosedWorldFetch(root)
    builder_repo = Path(__file__).resolve().parents[1]
    baseline = {
        "builder": {"path": str(builder_repo), "head": git_value(builder_repo, "rev-parse", "HEAD"), "starting_status_porcelain": "", "current_status_after_campaign_implementation": git_value(builder_repo, "status", "--porcelain=v1")},
        "data": {"path": str(data_repo), "head": git_value(data_repo, "-c", f"safe.directory={data_repo}", "rev-parse", "HEAD"), "status_porcelain": git_value(data_repo, "-c", f"safe.directory={data_repo}", "status", "--porcelain=v1")},
    }
    if baseline["builder"]["head"] != "cef02cb80c26ea4c52cd3c4ea97b996023ba686c" or baseline["data"]["head"] != "443d195abea91d7da111f5e573e90247ae823c36":
        raise RuntimeError("CG405 canonical baseline mismatch")
    put_json(root / "baseline-verification.json", baseline)
    benchmark = build_scoped_benchmark_v2().to_dict()
    # Design provenance is retained; its historical evidence registry is not corpus evidence.
    benchmark["evidence_registry"] = []
    benchmark["cg405_note"] = "Frozen design only. CG405 evidence is exclusively the fresh captured-corpus-manifest."
    benchmark_hash = put_json(root / "benchmark-manifest.json", benchmark)
    demand_path = data_repo / "docs" / "semantic-demand-catalogue-399" / "semantic-demand-catalogue.v1.json"
    demand_bytes = demand_path.read_bytes()
    demand_hash = hashlib.sha256(demand_bytes).hexdigest()
    (root / "semantic-demand-manifest.v1.json").write_bytes(demand_bytes)
    put_json(root / "semantic-demand-provenance.json", {"canonical_path": str(demand_path), "data_head": baseline["data"]["head"], "content_sha256": demand_hash})

    ledger: list[dict[str, Any]] = []
    subject_context: dict[str, dict[str, Any]] = {}
    for key, abn in ABNS.items():
        base = {"subject_key": key, "abn": abn, "subject_id": SUBJECT_IDS[key], "source_family": "acnc_register"}
        search_url = f"{ACNC}/search/charity?" + urlencode({"search": abn})
        search = fetcher.fetch("acnc_register", search_url, {"www.acnc.gov.au"})
        if search["outcome"] != "CAPTURED":
            ledger.append(terminal(base, event_state(search), "acnc_search_unavailable", [search]))
            subject_context[abn] = {"entity": {}, "names": [NAMES[key]], "register_ok": False}
            continue
        payload = json.loads(Path(search["object_path"]).read_bytes())
        matches = [r for r in payload.get("results", []) if str(r.get("data", {}).get("Abn")) == abn]
        if len(matches) != 1:
            ledger.append(terminal(base, "FAILED_CLASSIFIED", f"acnc_search_exact_abn_match_count_{len(matches)}", [search]))
            subject_context[abn] = {"entity": {}, "names": [NAMES[key]], "register_ok": False}
            continue
        entity_url = f"{ACNC}/entity/{matches[0]['uuid']}"
        entity_event = fetcher.fetch("acnc_register", entity_url, {"www.acnc.gov.au"})
        if entity_event["outcome"] != "CAPTURED":
            ledger.append(terminal(base, event_state(entity_event), "acnc_entity_unavailable", [search, entity_event]))
            subject_context[abn] = {"entity": {}, "names": [NAMES[key]], "register_ok": False}
            continue
        entity = json.loads(Path(entity_event["object_path"]).read_bytes())
        if str(entity.get("data", {}).get("Abn")) != abn:
            ledger.append(terminal(base, "FAILED_CLASSIFIED", "acnc_entity_abn_mismatch", [search, entity_event]))
            subject_context[abn] = {"entity": {}, "names": [NAMES[key]], "register_ok": False}
            continue
        ledger.append(terminal(base, "CAPTURED", "acnc_exact_abn_bound_entity", [search, entity_event]))
        names = [str(entity["data"].get(k)) for k in ("Name", "CharityLegalName", "LegalName") if entity["data"].get(k)] or [NAMES[key]]
        subject_context[abn] = {"entity": entity, "names": names, "register_ok": True}

    pfra_events = [fetcher.fetch("pfra", url, {"pfra.org.au", "www.pfra.org.au"}) for url in PFRA]
    pfra_rows = []
    for event, role in zip(pfra_events, ("current_charity_membership", "agency_membership")):
        if event["outcome"] == "CAPTURED":
            pfra_rows.extend(extract_pfra_members(Path(event["object_path"]).read_text(encoding="utf-8", errors="replace"), page_role=role, base_url=event["resolved_url"]))

    for key, abn in ABNS.items():
        context = subject_context[abn]; entity = context["entity"]; data = entity.get("data", {})
        rowbase = {"subject_key": key, "abn": abn, "subject_id": SUBJECT_IDS[key]}
        # AIS bundle and report opportunities derive exclusively from ACNC structured metadata.
        reports = [x for x in data.get("AnnualReports", []) if x.get("IsAIS") and x.get("Status") == "Submitted" and x.get("AISId")]
        latest = max(reports, key=lambda x: (int(x.get("Year") or 0), str(x.get("DateReceived") or "")), default=None)
        if not context["register_ok"]:
            ledger.extend([terminal({**rowbase, "source_family": f}, "FAILED_CLASSIFIED", "prerequisite_acnc_register_unavailable") for f in ("acnc_ais_bundle", "annual_report", "official_website")])
        elif latest is None:
            ledger.append(terminal({**rowbase, "source_family": "acnc_ais_bundle"}, "LEGITIMATELY_ABSENT", "no_submitted_ais_in_acnc_entity"))
            ledger.append(terminal({**rowbase, "source_family": "annual_report"}, "LEGITIMATELY_ABSENT", "no_latest_submitted_ais_for_structured_document_selection"))
        else:
            ais = fetcher.fetch("acnc_ais_bundle", f"{ACNC}/entity/{latest['AISId']}", {"www.acnc.gov.au"})
            ledger.append(terminal({**rowbase, "source_family": "acnc_ais_bundle", "reporting_year": str(latest.get("Year"))}, event_state(ais), "latest_submitted_ais" if ais["outcome"] == "CAPTURED" else "latest_submitted_ais_unavailable", [ais]))
            documents = select_filing_documents(data.get("Documents") or [], str(latest.get("Year")))
            doc_events = [fetcher.fetch("annual_report", str(d["Url"]), {"www.acnc.gov.au", "acncpubfilesprodstorage.blob.core.windows.net"}) for d in documents]
            if not doc_events:
                ledger.append(terminal({**rowbase, "source_family": "annual_report", "reporting_year": str(latest.get("Year"))}, "LEGITIMATELY_ABSENT", "no_structured_acnc_report_document_for_latest_ais"))
            else:
                status = "CAPTURED" if any(e["outcome"] == "CAPTURED" for e in doc_events) else event_state(doc_events[0])
                ledger.append(terminal({**rowbase, "source_family": "annual_report", "reporting_year": str(latest.get("Year"))}, status, "structured_acnc_document_selection", doc_events))
        abr = fetcher.fetch("ato_abr_dgr", f"{ABR}?" + urlencode({"abn": abn}), {"abr.business.gov.au"})
        ledger.append(terminal({**rowbase, "source_family": "ato_abr_dgr"}, event_state(abr), "abr_abn_view" if abr["outcome"] == "CAPTURED" else "abr_abn_view_unavailable", [abr]))
        website_raw = str(data.get("Website") or "").strip()
        # ACNC's structured locator may omit a scheme; adding HTTPS is the
        # permitted mechanical normalisation, and the raw locator remains in
        # the ledger for repair lineage.
        website = website_raw if urlsplit(website_raw).scheme else ("https://" + website_raw if website_raw else "")
        if not context["register_ok"]:
            pass
        elif not website:
            ledger.append(terminal({**rowbase, "source_family": "official_website"}, "LEGITIMATELY_ABSENT", "acnc_governed_website_locator_empty"))
        elif urlsplit(website).scheme not in {"http", "https"} or not urlsplit(website).hostname:
            ledger.append(terminal({**rowbase, "source_family": "official_website"}, "FAILED_CLASSIFIED", "acnc_website_locator_invalid"))
        else:
            host = urlsplit(website).hostname.casefold(); allowed = {host, ("www." + host) if not host.startswith("www.") else host[4:]}
            site = fetcher.fetch("official_website", website, allowed)
            ledger.append(terminal({**rowbase, "source_family": "official_website", "governed_locator_raw": website_raw, "governed_locator_normalized": website}, event_state(site), "acnc_governed_locator_homepage" if site["outcome"] == "CAPTURED" else "acnc_governed_locator_unavailable", [site]))
        query_events = [] ; candidates = []
        for name in context["names"]:
            q = fetcher.fetch("wikipedia_wikimedia", WIKI + "?" + urlencode({"action":"query","list":"search","srsearch":name,"format":"json","srlimit":10}), {"en.wikipedia.org"})
            query_events.append(q)
            if q["outcome"] == "CAPTURED": candidates.extend(json.loads(Path(q["object_path"]).read_bytes()).get("query", {}).get("search", []))
        resolution = resolve_wikipedia_candidate(context["names"], candidates) if candidates else {"status":"no_bound_record", "basis":"search_unavailable_or_empty"}
        if resolution["status"] == "bound":
            title = resolution["candidate"]["title"]
            page = fetcher.fetch("wikipedia_wikimedia", WIKI + "?" + urlencode({"action":"query","prop":"info|revisions","rvprop":"ids|timestamp|content","rvslots":"main","rvlimit":1,"titles":title,"format":"json","formatversion":2}), {"en.wikipedia.org"})
            ledger.append(terminal({**rowbase, "source_family":"wikipedia_wikimedia"}, event_state(page), "unique_exact_source_native_title" if page["outcome"] == "CAPTURED" else "bound_wikipedia_page_unavailable", query_events + [page]))
        else:
            ledger.append(terminal({**rowbase, "source_family":"wikipedia_wikimedia"}, "FAILED_CLASSIFIED", f"identity_{resolution['status']}_{resolution['basis']}", query_events))
        domain = (urlsplit(website).hostname or "").casefold().removeprefix("www.")
        matches = [r for r in pfra_rows if domain and domain in {str(d).casefold().removeprefix("www.") for d in r.get("linked_domains", [])}]
        if any(e["outcome"] == "CAPTURED" for e in pfra_events):
            ledger.append(terminal({**rowbase, "source_family":"pfra"}, "CAPTURED" if len(matches) == 1 else ("LEGITIMATELY_ABSENT" if not matches else "FAILED_CLASSIFIED"), "exact_linked_domain" if len(matches) == 1 else ("no_exact_linked_domain_in_captured_directories" if not matches else "multiple_exact_linked_domain_records"), pfra_events))
        else:
            ledger.append(terminal({**rowbase, "source_family":"pfra"}, "INACCESSIBLE", "both_governed_pfra_directories_unavailable", pfra_events))
    if len(ledger) != len(ABNS) * len(FAMILIES) or any(not r["terminal"] for r in ledger):
        raise RuntimeError(f"ledger is not complete: {len(ledger)} rows")
    ledger_hash = put_json(root / "acquisition-ledger.json", {"families": list(FAMILIES), "rows": ledger})
    corpus_events = [e for e in fetcher.events if e.get("outcome") == "CAPTURED"]
    corpus_hash = put_json(root / "captured-corpus-manifest.json", {"private_root": str(root), "objects_are_private_and_not_for_git": True, "captured_events": corpus_events, "captured_count": len(corpus_events)})
    by_family = {family: dict(Counter(r["status"] for r in ledger if r["source_family"] == family)) for family in FAMILIES}
    audit = {"provider_calls": 0, "provider_open_world_crossings": 0, "non_admitted_family_events": [e for e in fetcher.events if e["source_family"] not in FAMILIES], "result": "PASS"}
    put_json(root / "provider-open-world-segregation-audit.json", audit)
    summary = {"campaign":"CG405", "baseline": baseline, "benchmark_manifest_sha256": benchmark_hash, "semantic_demand_manifest_sha256": demand_hash, "acquisition_ledger_sha256": ledger_hash, "captured_corpus_manifest_sha256": corpus_hash, "subjects": len(ABNS), "opportunities": len(ledger), "terminal_opportunities": sum(r["terminal"] for r in ledger), "per_family_status_counts": by_family, "private_material_excluded_from_git": True, "provider_open_world_audit":"PASS", "successor_t02": "Use acquisition-ledger.json and captured-corpus-manifest.json as the sole CG405 evidence inputs; do not substitute historic or 403/404 material."}
    put_json(root / "predecessor-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(r"C:\CharityGraph-runtime\artifacts\cg405-source-universe-sufficiency"))
    parser.add_argument("--data-repo", type=Path, default=Path(r"C:\CharityGraph-clean\charitygraph-data"))
    raise SystemExit(main(parser.parse_args().root.resolve(), parser.parse_args().data_repo.resolve()))
