"""Bounded, provenance-first official-site traversal for the frozen G2 corpus.

This deliberately accepts an ACNC-derived inventory, never a guessed or historic
fallback domain.  The inventory is the authority; a URL in an old attempt ledger
is evidence only and is not used to seed the queue.
"""
from __future__ import annotations

import argparse, hashlib, json, re, time
from collections import Counter, defaultdict, deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .corpus_replay import _canonical, _read, _sha, verify_package

KEYWORDS = {
    "annual_or_financial_reports": ("annual", "financial", "report"), "about": ("about",),
    "mission_values": ("mission", "values", "purpose"), "history": ("history", "our-story"),
    "programs_services": ("program", "service", "what-we-do"), "impact_results": ("impact", "result", "outcome"),
    "governance_leadership": ("govern", "leadership", "board"), "policies_codes_safeguarding_inclusion": ("polic", "safeguard", "inclusion"),
    "affiliations_accreditations": ("accredit", "affiliat", "member"), "strategy": ("strategy", "strategic"),
    "news_campaigns": ("news", "campaign", "media"), "research_evaluation_publications": ("research", "publication", "evaluation"),
}

def canonical_url(value: str) -> str:
    p = urlsplit(value.strip())
    if p.scheme not in {"http", "https"} or not p.netloc: raise ValueError("non-http locator")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", "", ""))

def site_key(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.lower().removeprefix("www.")

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag in {"a", "link"}:
            href = dict(attrs).get("href")
            if href: self.links.append(href)

class Recorder(HTTPRedirectHandler):
    def __init__(self): super().__init__(); self.chain: list[str] = []
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append(canonical_url(newurl)); return super().redirect_request(req, fp, code, msg, headers, newurl)

def governed_locators(inventory: Path) -> dict[str, dict[str, Any]]:
    """Extract only retained official_website records from the frozen inventory."""
    result = {}
    for subject in _read(inventory)["per_charity_inventory"]:
        for cls in subject["classes"]:
            if cls["source_class"] == "charity_authored":
                urls = [canonical_url(o["resolved_locator"]) for o in cls["retained_objects"] if o.get("source_family") == "official_website"]
                if urls: result[subject["subject_id"]] = {"locator": urls[0], "basis": "retained_governed_inventory_official_website", "display_name": subject["display_name"]}
    return result

def _fetch(url: str) -> tuple[dict[str, Any], bytes]:
    redirect = Recorder(); opener = build_opener(redirect)
    record = {"requested_locator": url, "redirect_chain": [], "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with opener.open(Request(url, headers={"User-Agent":"CharityGraph-G2-governed-traversal/1.0"}), timeout=20) as response:
            body = response.read(2_000_000); record.update({"resolved_locator": canonical_url(response.geturl()), "redirect_chain": redirect.chain, "status": response.status, "content_type": response.headers.get_content_type(), "body_sha256": hashlib.sha256(body).hexdigest()}); return record, body
    except (HTTPError, URLError, OSError, ValueError) as e:
        record.update({"resolved_locator": url, "redirect_chain": redirect.chain, "transport_error": f"{type(e).__name__}: {e}"}); return record, b""

def execute(package: Path, inventory: Path, output: Path, *, page_cap: int = 16) -> dict[str, Any]:
    verification = verify_package(package)
    if not verification["all_passed"]: raise ValueError("CG384 verification failed")
    if _sha(inventory) != "e6d105a4a4bc556c016590bf23453ae7a0cb21c398c28857fd1d32f0f5c62a3e": raise ValueError("governed inventory hash mismatch")
    matrix = _read(package / "original_recovered" / "cg364-matrix-after.json"); locators = governed_locators(inventory)
    requests: list[dict[str, Any]]=[]; identities=[]; frontiers=[]; captures=defaultdict(set)
    for sid, details in sorted(locators.items()):
        root=details["locator"]; domain=site_key(root); queue=deque([root]); visited=set(); bound=False
        while queue and len(visited) < page_cap:
            url=queue.popleft()
            if url in visited: continue
            visited.add(url); event, body=_fetch(url); event.update({"subject_id":sid,"locator_provenance":details["basis"]}); requests.append(event)
            resolved=event["resolved_locator"]
            # Cross-domain resolution is not admitted without independent positive proof; do not crawl it.
            if site_key(resolved) != domain:
                event["identity_disposition"]="CROSS_DOMAIN_NOT_BOUND_FAIL_CLOSED"; continue
            bound=True; event["identity_disposition"]="BOUND_BY_GOVERNED_LOCATOR_SAME_DOMAIN"
            text=body.decode("utf-8", errors="ignore")
            hay=(resolved+" "+text[:200000]).lower()
            for category, words in KEYWORDS.items():
                if any(word in hay for word in words): captures[sid].add(category)
            if event.get("content_type") == "text/html":
                parser=Links(); parser.feed(text)
                for href in parser.links:
                    try: candidate=canonical_url(urljoin(resolved, href))
                    except ValueError: continue
                    if site_key(candidate)==domain and candidate not in visited and len(queue) < page_cap * 4: queue.append(candidate)
        identities.append({"subject_id":sid,"governed_locator":root,"binding": "BOUND_BY_GOVERNED_LOCATOR_SAME_DOMAIN" if bound else "IDENTITY_NOT_BOUND_AFTER_RESOLUTION","basis":details["basis"]})
        frontiers.append({"subject_id":sid,"visited":len(visited),"queued_admissible_urls":len(queue),"page_cap":page_cap,"state":"TRUNCATED" if queue else "EXHAUSTED"})
    seen={x["subject_id"] for x in identities}
    for cell in matrix["coverage_matrix"]:
        sid=cell["subject_id"]
        if sid not in seen:
            identities.append({"subject_id":sid,"binding":"IDENTITY_NOT_BOUND_AFTER_RESOLUTION","basis":"no_retained_governed_official_locator"})
            frontiers.append({"subject_id":sid,"visited":0,"queued_admissible_urls":0,"page_cap":page_cap,"state":"EXHAUSTED"})
            seen.add(sid)
    bind={x["subject_id"]:x["binding"] for x in identities}; fs={x["subject_id"]:x for x in frontiers}; after=[]; transitions=[]
    for cell in matrix["coverage_matrix"]:
        c=dict(cell); before=c["state"]; sid=c["subject_id"]
        if bind[sid] != "BOUND_BY_GOVERNED_LOCATOR_SAME_DOMAIN": state="IDENTITY_NOT_BOUND_AFTER_RESOLUTION"; cause="identity_policy_or_source_locator_absence"
        elif c["category"] in captures[sid]: state="CAPTURED"; cause="governed_same_domain_live_capture"
        elif fs[sid]["state"] == "TRUNCATED": state="TRUNCATED"; cause="safety_cap_left_admissible_frontier"
        else: state="DISCOVERY_EXHAUSTED_NO_CAPTURE"; cause="admissible_same_domain_frontier_drained"
        c.update({"historical_state":before,"state":state,"root_cause":cause,"builder_contamination_cleared": cause != "safety_cap_left_admissible_frontier"}); after.append(c)
        if before in {"IDENTITY_NOT_BOUND_AFTER_RESOLUTION","TRUNCATED"}: transitions.append({"case_id":c["case_id"],"category":c["category"],"before":before,"after":state,"root_cause":cause,"builder_contamination_cleared":c["builder_contamination_cleared"]})
    output.mkdir(parents=True, exist_ok=True)
    files={"before-matrix.json":matrix,"after-matrix.json":{"coverage_matrix":after,"cohort_hash":verification["cohort_hash"]},"live-request-ledger.json":{"requests":requests},"identity-binding-ledger.json":{"bindings":identities},"traversal-frontier-ledger.json":{"frontiers":frontiers},"transition-ledger.json":{"transition_count":len(transitions),"transitions":transitions}}
    counts=Counter(x["state"] for x in after); contamination=sum(not x["builder_contamination_cleared"] for x in after if x["historical_state"] in {"TRUNCATED","IDENTITY_NOT_BOUND_AFTER_RESOLUTION"})
    files["contamination-summary.json"]={"before":dict(Counter(x["state"] for x in matrix["coverage_matrix"])),"after":dict(counts),"live_request_count":len(requests),"builder_contamination_residual":contamination,"verdict":"G2_CORPUS_NOT_READY"}
    for name,value in files.items(): (output/name).write_bytes(_canonical(value))
    sums={name:_sha(output/name) for name in sorted(files)}; (output/"SHA256SUMS.json").write_bytes(_canonical(sums)); manifest={"schema":"charitygraph.g2.governed-traversal/v1","cg384_verification":verification,"governed_inventory_sha256":_sha(inventory),"cohort_hash":verification["cohort_hash"],"outputs":sums,"live_request_count":len(requests),"verdict":"G2_CORPUS_NOT_READY"}; (output/"manifest.json").write_bytes(_canonical(manifest)); return files["contamination-summary.json"]

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("package",type=Path); p.add_argument("inventory",type=Path); p.add_argument("output",type=Path); p.add_argument("--page-cap",type=int,default=16); a=p.parse_args(); print(json.dumps(execute(a.package,a.inventory,a.output,page_cap=a.page_cap),sort_keys=True))
