"""Private Baseline Charity Corpus v1 acquisition experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from charitygraph.baseline_corpus import (
    AcquisitionState,
    BindingState,
    CorpusMember,
    DiscoveryState,
    MaterialOrigin,
    RepresentationReadiness,
    build_corpus_manifest,
    enumerate_site_candidates,
    extract_pfra_members,
    provider_budget_allows,
    rank_site_candidates_with_luna,
    represent_pdf,
    resolve_wikipedia_candidate,
    select_filing_documents,
)
from charitygraph.contracts import AcquisitionReceipt, PropositionAuthorityRole, SourceDefinition, SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog

ABNS = ("28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642", "67649417658", "45146631843", "15101252171")
WEBSITES = {
    "28000030179": "https://www.thesmithfamily.com.au",
    "50169561394": "https://www.redcross.org.au",
    "20077830347": "https://www.communityfoundation.org.au",
    "22007498482": "https://www.acf.org.au",
    "15000002522": "https://www.missionaustralia.com.au",
    "28004778081": "https://www.worldvision.com.au",
    "46070556642": "https://www.hollows.org",
    "67649417658": "https://landscaperecovery.com.au",
    "45146631843": "https://www.ilf.org.au",
    "15101252171": "https://www.lwb.org.au",
}
API = "https://www.acnc.gov.au/api/dynamics"
WIKI = "https://en.wikipedia.org/w/api.php"
PFRA_CHARITY = "https://pfra.org.au/membership/charity-members/"
PFRA_AGENCY = "https://pfra.org.au/membership/fundraising-agency-members/"
DEV = set(ABNS[:7])
MAX_PROVIDER_USD = Decimal("0.50")
LUNA_INPUT_USD_PER_MILLION = Decimal("0.20")
LUNA_OUTPUT_USD_PER_MILLION = Decimal("1.20")
LUNA_MAX_OUTPUT_TOKENS = 8000


def now() -> datetime:
    return datetime.now(timezone.utc)


def fetch(url: str) -> tuple[bytes, str, int, str]:
    request = Request(url, headers={"User-Agent": "CharityGraph baseline-corpus-v1/1.1"})
    with urlopen(request, timeout=45) as response:
        return response.read(), response.geturl(), response.status, response.headers.get_content_type()


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def projected_luna_cost(candidates: list[dict]) -> Decimal:
    input_tokens = (len(json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))) // 4) + 256
    return (Decimal(input_tokens) * LUNA_INPUT_USD_PER_MILLION + Decimal(LUNA_MAX_OUTPUT_TOKENS * 2) * LUNA_OUTPUT_USD_PER_MILLION) / Decimal(1_000_000)


def _normalise_name(value: str) -> str:
    return "".join(char.casefold() for char in str(value) if char.isalnum())


def subject_registry(catalog: SQLiteCatalog) -> dict[str, str]:
    with catalog._connection() as connection:
        rows = connection.execute(
            "SELECT e.identifier_value, e.subject_id FROM external_identifiers e "
            "WHERE e.scheme='ABN' AND e.issuing_authority='Australian Business Register' AND e.status='active'"
        ).fetchall()
    mapping = {str(row[0]): str(row[1]) for row in rows}
    if set(mapping) != set(ABNS) or len(mapping) != len(ABNS):
        raise RuntimeError("stable vNext catalogue does not contain exactly the ten governed ABNs")
    return mapping


def source_lineage(catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, *, family: str, endpoint: str, url: str, body: bytes, resolved: str, media: str, role: str, revision: str | None = None) -> dict:
    created = now()
    definition_id = deterministic_id("srcdef:", {"family": family, "endpoint": endpoint, "profile": "baseline-v1"})
    definition = SourceDefinition(
        record_id=definition_id,
        created_at=created,
        producer={"kind": "code", "producer_id": "baseline-corpus-v1", "version": "1.1"},
        publisher="Australian Charities and Not-for-profits Commission" if family.startswith("acnc") else family,
        source_class=family,
        authority_roles=(PropositionAuthorityRole(proposition="source material", role="source-reported", basis="bounded baseline acquisition"),),
        acquisition_locator=endpoint,
        temporal_semantics="current_or_reported_period",
        publication_eligibility="private_review_only",
        steward="CharityGraph private corpus",
    )
    if catalog.get_source_definition(definition_id) is None:
        catalog.register_source_definition(definition)
    content_hash = digest(body)
    artifact_id = "srcblob:" + content_hash
    artifact_existing = catalog.get_artifact(artifact_id) is not None
    if not artifact_existing:
        store.put(body, created_at=created)
    receipt_id = deterministic_id("acq:", {"source_definition_id": definition_id, "artifact_id": artifact_id, "requested_locator": url})
    receipt_existing = catalog.get_acquisition_receipt(receipt_id) is not None
    if not receipt_existing:
        catalog.record_acquisition_receipt(AcquisitionReceipt(
            record_id=receipt_id,
            created_at=created,
            producer={"kind": "code", "producer_id": "baseline-corpus-v1", "version": "1.1"},
            source_definition_id=definition_id,
            requested_locator=url,
            resolved_locator=resolved,
            retrieved_at=created,
            outcome="available",
            response_status=200,
            media_type=media,
            content_hash=content_hash,
            byte_size=len(body),
            artifact_id=artifact_id,
            tool_id="urllib",
            tool_version="stdlib",
        ))
    source_record_id = deterministic_id("srcrec:", {"source_family": family, "source_version": revision, "source_locator": resolved, "payload_hash": content_hash})
    record_existing = catalog.get_source_record(source_record_id) is not None
    if not record_existing:
        catalog.register_source_record(SourceRecord(
            record_id=source_record_id,
            created_at=created,
            producer={"kind": "code", "producer_id": "baseline-corpus-v1", "version": "1.1"},
            source_family=family,
            source_role=role,
            source_version=revision,
            source_locator=resolved,
            retrieved_at=created,
            observed_at=created,
            media_type=media,
            payload_ref=artifact_id,
            payload_hash=content_hash,
            attribution="Australian Charities and Not-for-profits Commission" if family.startswith("acnc") else None,
        ))
    return {
        "source_definition_id": definition_id,
        "acquisition_receipt_id": receipt_id,
        "artifact_id": artifact_id,
        "source_record_id": source_record_id,
        "origin": "reused_existing" if artifact_existing and record_existing else "newly_acquired",
    }


def acnc_fetch(abn: str) -> tuple[str, bytes, str, dict]:
    search_url = API + "/search/charity?" + urlencode({"search": abn})
    search_body, _, _, _ = fetch(search_url)
    search = json.loads(search_body)
    matches = [row for row in search.get("results", []) if str(row.get("data", {}).get("Abn", "")) == abn]
    if len(matches) != 1:
        raise RuntimeError(f"ACNC exact ABN resolution failed for {abn}")
    uuid = matches[0]["uuid"]
    entity_url = f"{API}/entity/{uuid}"
    body, resolved, _, _ = fetch(entity_url)
    entity = json.loads(body)
    if str(entity.get("data", {}).get("Abn", "")) != abn:
        raise RuntimeError(f"ACNC ABN mismatch for {abn}")
    return entity_url, body, resolved, entity


def sitemap_urls(home_html: str, base: str) -> list[str]:
    urls = []
    for match in re.finditer(r"<link[^>]+rel=[\"']sitemap[\"'][^>]+href=[\"']([^\"']+)", home_html, re.I):
        urls.append(urljoin(base, match.group(1)))
    for match in re.finditer(r"<loc>([^<]+)</loc>", home_html, re.I):
        if "sitemap" in match.group(1).casefold():
            urls.append(urljoin(base, match.group(1).strip()))
    return list(dict.fromkeys(urls + [urljoin(base, "/sitemap_index.xml"), urljoin(base, "/sitemap.xml")]))


def _member_from_lineage(lineage: dict, *, family: str, discovery: DiscoveryState = DiscoveryState.RESOLVED, binding: BindingState = BindingState.BOUND, readiness: RepresentationReadiness = RepresentationReadiness.NOT_REQUIRED, representation_ids: tuple[str, ...] = (), gaps: tuple[str, ...] = (), revision: str | None = None, period: str | None = None) -> CorpusMember:
    return CorpusMember(
        source_family=family,
        source_definition_id=lineage["source_definition_id"],
        acquisition_receipt_ids=(lineage["acquisition_receipt_id"],),
        artifact_ids=(lineage["artifact_id"],),
        source_record_ids=(lineage["source_record_id"],),
        source_revision=revision,
        effective_period=period,
        discovery=discovery,
        acquisition=AcquisitionState.AVAILABLE,
        subject_binding=binding,
        material_origin=MaterialOrigin(lineage["origin"]),
        representation_readiness=readiness,
        representation_artifact_ids=representation_ids,
        representation_gaps=gaps,
    )


def run(args: argparse.Namespace) -> int:
    runtime = args.runtime.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    pdf_root = runtime / "pdfs"
    pdf_root.mkdir(parents=True, exist_ok=True)
    catalog = SQLiteCatalog(Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")).open(initialize=True)
    store = ContentAddressedArtifactStore(runtime / "objects", allowed_roots=(runtime,), catalog=catalog)
    ids = subject_registry(catalog)
    provider_actual = Decimal("0")
    provider_reserved = Decimal("0")
    provider_events: list[dict] = []
    acquired_new = 0
    reused = 0
    pdf_report: list[dict] = []
    corpora: list[dict] = []
    matrix: list[dict] = []
    site_report: dict[str, dict] = {}
    wikipedia_report: dict[str, dict] = {}
    pfra_report: dict[str, dict] = {}
    pfra_pages: list[tuple[str, bytes, str, str]] = []
    for page_url, page_role in ((PFRA_CHARITY, "current_charity_membership"), (PFRA_AGENCY, "agency_membership")):
        try:
            body, resolved, _, media = fetch(page_url)
            pfra_pages.append((page_url, body, resolved, page_role))
        except Exception:
            continue
    pfra_records = [record for _, body, _, page_role in pfra_pages for record in extract_pfra_members(body.decode("utf-8", "replace"), page_role=page_role, base_url=PFRA_CHARITY)]
    for abn in ABNS:
        subject_id = ids[abn]
        members: list[CorpusMember] = []
        coverage: dict[str, dict] = {}
        try:
            register_url, register_body, register_resolved, entity = acnc_fetch(abn)
            register_lineage = source_lineage(catalog, store, family="acnc_register", endpoint=f"{API}/entity", url=register_url, body=register_body, resolved=register_resolved, media="application/json", role="register_identity")
            members.append(_member_from_lineage(register_lineage, family="acnc_register"))
            acquired_new += register_lineage["origin"] == "newly_acquired"
            reused += register_lineage["origin"] == "reused_existing"
            coverage["acnc_register"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": register_lineage["origin"], "record_ids": [register_lineage["source_record_id"]]}
        except Exception as exc:
            entity = {"data": {}}
            coverage["acnc_register"] = {"discovery": "failed", "acquisition": "failed", "binding": "none", "origin": "none", "error": type(exc).__name__}
        data = entity.get("data", {})
        reports = [item for item in data.get("AnnualReports", []) if item.get("IsAIS") and item.get("Status") == "Submitted" and item.get("AISId")]
        latest = max(reports, key=lambda item: (int(item.get("Year") or 0), item.get("DateReceived") or ""), default=None)
        filing_rows: list[dict] = []
        if latest:
            try:
                ais_url = f"{API}/entity/{latest['AISId']}"
                ais_body, ais_resolved, _, _ = fetch(ais_url)
                ais_lineage = source_lineage(catalog, store, family="acnc_ais_bundle", endpoint=f"{API}/entity/{{AISId}}", url=ais_url, body=ais_body, resolved=ais_resolved, media="application/json", role="annual_information_statement", revision=str(latest.get("Year")))
                ais_member = _member_from_lineage(ais_lineage, family="acnc_ais_bundle", revision=str(latest.get("Year")), period=str(latest.get("Year")))
                members.append(ais_member)
                filing_rows.append({"role": "annual_information_statement", "source_record_id": ais_lineage["source_record_id"], "year": str(latest.get("Year"))})
                acquired_new += ais_lineage["origin"] == "newly_acquired"
                reused += ais_lineage["origin"] == "reused_existing"
            except Exception:
                pass
            for document in select_filing_documents(data.get("Documents") or [], str(latest.get("Year"))):
                try:
                    doc_url = str(document["Url"])
                    doc_body, doc_resolved, _, doc_media = fetch(doc_url)
                    role = str(document["role"])
                    lineage = source_lineage(catalog, store, family="acnc_ais_bundle", endpoint=f"{API}/filing-documents", url=doc_url, body=doc_body, resolved=doc_resolved, media=doc_media, role=role, revision=str(latest.get("Year")))
                    representation_ids: tuple[str, ...] = ()
                    readiness = RepresentationReadiness.NOT_REQUIRED
                    gaps: tuple[str, ...] = ()
                    representation = None
                    if doc_media == "application/pdf" or doc_url.casefold().split("?", 1)[0].endswith(".pdf"):
                        pdf_path = pdf_root / f"{lineage['artifact_id'].split(':', 1)[1]}.pdf"
                        pdf_path.write_bytes(doc_body)
                        try:
                            representation = represent_pdf(pdf_path)
                            readiness = RepresentationReadiness(representation["readiness"])
                            gaps = tuple(str(item) for item in representation.get("page_gaps", []))
                            representation_body = json.dumps({"source_record_id": lineage["source_record_id"], "representation": representation}, ensure_ascii=False, sort_keys=True).encode("utf-8")
                            # Derived representations are content-addressed separately from
                            # source blobs. Reuse an indexed representation on reruns.
                            representation_id = "artifact:" + digest(representation_body)
                            if catalog.get_artifact(representation_id) is None:
                                representation_artifact = store.put_derived(
                                    representation_body,
                                    input_artifact_ids=(lineage["artifact_id"],),
                                    created_at=now(),
                                )
                                representation_id = representation_artifact.artifact_id
                            representation_ids = (representation_id,)
                            pdf_report.append({"abn": abn, "source_record_id": lineage["source_record_id"], "role": role, "year": str(latest.get("Year")), "readiness": representation["readiness"], "page_count": representation.get("page_count"), "native_text_pages": representation.get("native_text_pages"), "visual_escalations": representation.get("visual_escalations", 0), "page_gaps": list(gaps), "derived_artifact_id": representation_id})
                        except Exception as exc:
                            readiness = RepresentationReadiness.FAILED
                            gaps = (f"representation_error:{type(exc).__name__}",)
                            pdf_report.append({"abn": abn, "source_record_id": lineage["source_record_id"], "role": role, "year": str(latest.get("Year")), "readiness": "failed", "error": type(exc).__name__, "visual_escalations": 0})
                    members.append(_member_from_lineage(lineage, family="acnc_ais_bundle", readiness=readiness, representation_ids=representation_ids, gaps=gaps, revision=str(latest.get("Year")), period=str(latest.get("Year"))))
                    filing_rows.append({"role": role, "source_record_id": lineage["source_record_id"], "year": str(latest.get("Year")), "title": document.get("Title")})
                    acquired_new += lineage["origin"] == "newly_acquired"
                    reused += lineage["origin"] == "reused_existing"
                except Exception:
                    filing_rows.append({"role": document.get("role"), "url": document.get("Url"), "status": "failed"})
        coverage["acnc_ais_bundle"] = {"discovery": "resolved" if latest else "absent", "acquisition": "available" if latest else "absent", "binding": "bound" if latest else "no_bound_record", "origin": "newly_acquired" if latest else "none", "period": latest.get("Year") if latest else None, "bundle_member_count": len(filing_rows), "members": filing_rows}
        abr_url = f"https://abr.business.gov.au/ABN/View?abn={abn}"
        try:
            abr_body, abr_resolved, _, abr_media = fetch(abr_url)
            lineage = source_lineage(catalog, store, family="ato_abr_dgr", endpoint="https://abr.business.gov.au/ABN/View", url=abr_url, body=abr_body, resolved=abr_resolved, media=abr_media, role="abr_entity")
            members.append(_member_from_lineage(lineage, family="ato_abr_dgr"))
            acquired_new += lineage["origin"] == "newly_acquired"
            reused += lineage["origin"] == "reused_existing"
            coverage["ato_abr_dgr"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": lineage["origin"], "role": "abr_entity", "source_native_dgr_status": "not_established_by_identity_page", "record_ids": [lineage["source_record_id"]]}
        except Exception as exc:
            coverage["ato_abr_dgr"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "error": type(exc).__name__}
        base = WEBSITES[abn]
        site_row = {"status": "failed", "candidate_count": 0, "sitemap_urls": [], "sitemap_count": 0, "ranking": None, "acquired_page_records": [], "homepage_persisted": False, "ranking_attempted": False}
        try:
            home_body, home_resolved, _, home_media = fetch(base)
            home_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=base, body=home_body, resolved=home_resolved, media=home_media, role="official_homepage")
            members.append(_member_from_lineage(home_lineage, family="official_website"))
            site_row["homepage_persisted"] = True
            acquired_new += home_lineage["origin"] == "newly_acquired"
            reused += home_lineage["origin"] == "reused_existing"
            sitemap_xmls = []
            for sitemap_url in sitemap_urls(home_body.decode("utf-8", "replace"), base):
                try:
                    sitemap_body, sitemap_resolved, _, sitemap_media = fetch(sitemap_url)
                    if "xml" not in sitemap_media and b"<url" not in sitemap_body[:2000]:
                        continue
                    sitemap_xmls.append(sitemap_body.decode("utf-8", "replace"))
                    site_row["sitemap_urls"].append(sitemap_resolved)
                    sitemap_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=sitemap_url, body=sitemap_body, resolved=sitemap_resolved, media=sitemap_media, role="sitemap")
                    members.append(_member_from_lineage(sitemap_lineage, family="official_website"))
                    acquired_new += sitemap_lineage["origin"] == "newly_acquired"
                    reused += sitemap_lineage["origin"] == "reused_existing"
                except Exception:
                    continue
            site_row["sitemap_count"] = len(sitemap_xmls)
            candidates = enumerate_site_candidates(home_body.decode("utf-8", "replace"), base, sitemap_xml="\n".join(sitemap_xmls))
            site_row["status"] = "enumerated"
            site_row["candidate_count"] = len(candidates)
            if abn in DEV and not args.skip_luna and candidates:
                site_row["ranking_attempted"] = True
                projected = projected_luna_cost(candidates)
                allowed = provider_budget_allows(provider_actual, provider_reserved, projected, MAX_PROVIDER_USD)
                event = {"subject_abn": abn, "model": "gpt-5.6-luna", "projected_max_usd": f"{projected:.6f}", "actual_cost_usd": "0", "transport_requests": 0, "preflight_allowed": allowed}
                if not allowed:
                    site_row["ranking"] = {"status": "blocked_budget", "projected_max_usd": str(projected)}
                    provider_events.append(event)
                else:
                    try:
                        ranking = rank_site_candidates_with_luna(candidates, subject_name=abn, model="gpt-5.6-luna", max_output_tokens=LUNA_MAX_OUTPUT_TOKENS)
                        actual = Decimal(str(ranking.get("cost_usd") or "0"))
                        provider_actual += actual
                        event.update({"actual_cost_usd": f"{actual:.6f}", "transport_requests": ranking.get("transport_requests", 0), "status": "completed" if not ranking.get("validation_error") else "invalid_output"})
                        if provider_actual + provider_reserved > MAX_PROVIDER_USD:
                            raise RuntimeError(f"Luna actual spend exceeded USD {MAX_PROVIDER_USD}")
                        site_row["ranking"] = ranking
                        provider_events.append(event)
                        if not ranking.get("validation_error"):
                            for candidate in [candidates[i] for i in ranking["ranked_ordinals"][:10]]:
                                try:
                                    page_body, page_resolved, _, page_media = fetch(candidate["url"])
                                    page_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=candidate["url"], body=page_body, resolved=page_resolved, media=page_media, role="official_page")
                                    members.append(_member_from_lineage(page_lineage, family="official_website"))
                                    site_row["acquired_page_records"].append({"url": candidate["url"], "source_record_id": page_lineage["source_record_id"], "artifact_id": page_lineage["artifact_id"]})
                                    acquired_new += page_lineage["origin"] == "newly_acquired"
                                    reused += page_lineage["origin"] == "reused_existing"
                                except Exception:
                                    continue
                    except Exception as exc:
                        event.update({"status": "failed", "error": type(exc).__name__})
                        provider_events.append(event)
                        site_row["ranking"] = {"status": "failed", "error": type(exc).__name__}
            site_row["mechanical_candidates"] = [{"ordinal": c["ordinal"], "url": c["url"], "label": c.get("label", "")} for c in candidates]
            coverage["official_website"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": "newly_acquired", "candidate_count": len(candidates), "homepage_persisted": True, "sitemap_count": len(sitemap_xmls), "top_page_count": len(site_row["acquired_page_records"])}
        except Exception as exc:
            site_row["error"] = type(exc).__name__
            coverage["official_website"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "homepage_persisted": False, "candidate_count": 0, "top_page_count": 0, "error": type(exc).__name__}
        site_report[abn] = site_row
        names = [str(data.get(key) or "") for key in ("Name", "CharityLegalName", "LegalName") if data.get(key)] + [str(item) for item in (data.get("OtherNames") or []) if item]
        try:
            query_url = WIKI + "?" + urlencode({"action": "query", "list": "search", "srsearch": names[0] if names else abn, "format": "json", "srlimit": 10})
            wiki_body, _, _, _ = fetch(query_url)
            search_rows = json.loads(wiki_body).get("query", {}).get("search", [])
            resolution = resolve_wikipedia_candidate(names, search_rows)
            if resolution["status"] == "bound":
                title = resolution["candidate"]["title"]
                page_query = WIKI + "?" + urlencode({"action": "query", "prop": "info|revisions", "rvprop": "ids|timestamp", "titles": title, "format": "json", "formatversion": "2"})
                page_body, page_resolved, _, page_media = fetch(page_query)
                page_data = json.loads(page_body)
                page = (page_data.get("query", {}).get("pages") or [{}])[0]
                revision = str((page.get("lastrevid") or ((page.get("revisions") or [{}])[0].get("revid")) or "")) or None
                lineage = source_lineage(catalog, store, family="wikipedia_wikimedia", endpoint=WIKI, url=page_query, body=page_body, resolved=page_resolved, media=page_media, role="article_identity", revision=revision)
                members.append(_member_from_lineage(lineage, family="wikipedia_wikimedia", revision=revision))
                wikipedia_report[abn] = {"status": "bound", "title": title, "revision_id": revision, "source_record_id": lineage["source_record_id"], "basis": resolution["basis"]}
                coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": lineage["origin"], "title": title, "revision_id": revision}
                acquired_new += lineage["origin"] == "newly_acquired"
                reused += lineage["origin"] == "reused_existing"
            else:
                wikipedia_report[abn] = {"status": resolution["status"], "basis": resolution["basis"], "candidate_count": len(resolution.get("candidates", []))}
                coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "available", "binding": "no_bound_record", "origin": "none", "candidate_count": len(resolution.get("candidates", []))}
        except Exception as exc:
            wikipedia_report[abn] = {"status": "failed", "error": type(exc).__name__}
            coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "error": type(exc).__name__}
        matched_pfra = [record for record in pfra_records if _normalise_name(record["label"]) in {_normalise_name(name) for name in names}]
        pfra_rows = []
        for record in matched_pfra:
            page_match = next((item for item in pfra_pages if item[3] == record["member_role"]), None)
            if not page_match:
                continue
            page_url, page_body, page_resolved, page_role = page_match
            lineage = source_lineage(catalog, store, family="pfra", endpoint=page_url, url=page_url, body=page_body, resolved=page_resolved, media="text/html", role=page_role)
            members.append(_member_from_lineage(lineage, family="pfra"))
            pfra_rows.append({"member_role": record["member_role"], "label": record["label"], "linked_domains": record["linked_domains"], "source_record_id": lineage["source_record_id"]})
            acquired_new += lineage["origin"] == "newly_acquired"
            reused += lineage["origin"] == "reused_existing"
        pfra_report[abn] = {"status": "bound" if pfra_rows else "no_bound_record", "records": pfra_rows, "directory_counts": {"charity": sum(r["member_role"] == "current_charity_membership" for r in pfra_records), "agency": sum(r["member_role"] == "agency_membership" for r in pfra_records)}}
        coverage["pfra"] = {"discovery": "resolved", "acquisition": "available" if pfra_pages else "failed", "binding": "bound" if pfra_rows else "no_bound_record", "origin": "newly_acquired" if pfra_rows else "none", "record_count": len(pfra_rows)}
        manifest = build_corpus_manifest(subject_id=subject_id, profile_version="baseline-charity-corpus-v1", members=members, retrieval_timestamps=(now().isoformat(),), builder_commit=None)
        corpora.append(manifest.model_dump(mode="json"))
        matrix.append({"abn": abn, "subject_id": subject_id, "registered_name": data.get("Name") or data.get("CharityLegalName"), "coverage": coverage})
    provider_actual = sum((Decimal(str(event.get("actual_cost_usd") or "0")) for event in provider_events), Decimal("0"))
    report = {
        "version": "baseline-charity-corpus-v1",
        "private": True,
        "subjects": matrix,
        "corpora": corpora,
        "official_site_rankings": site_report,
        "wikipedia": wikipedia_report,
        "pfra": pfra_report,
        "pfra_directory_counts": {"charity": sum(r["member_role"] == "current_charity_membership" for r in pfra_records), "agency": sum(r["member_role"] == "agency_membership" for r in pfra_records)},
        "pdf_representation": pdf_report,
        "provider_telemetry": {"model": "gpt-5.6-luna", "events": provider_events, "actual_total_usd": f"{provider_actual:.6f}", "reserved_exposure_usd": f"{provider_reserved:.6f}", "cap_usd": str(MAX_PROVIDER_USD), "fail_closed_enforced": True},
        "aggregate": {"source_families": 6, "subjects": 10, "newly_acquired_material_count": acquired_new, "reused_material_count": reused, "wikipedia_bound": sum(v.get("status") == "bound" for v in wikipedia_report.values()), "pfra_bound": sum(v.get("status") == "bound" for v in pfra_report.values()), "provider_calls": len(provider_events), "provider": "gpt-5.6-luna", "input_tokens": sum(int((e.get("usage") or {}).get("input_tokens") or 0) for v in site_report.values() for e in [v.get("ranking") or {}]), "output_tokens": sum(int((e.get("usage") or {}).get("output_tokens") or 0) for v in site_report.values() for e in [v.get("ranking") or {}]), "cost_usd": f"{provider_actual:.6f}", "semantic_extraction": False, "economics": "exact Luna usage/cost with conservative preflight and USD 0.50 fail-closed cap; no ranked BudgetCohort ledger used"},
    }
    output = runtime / "baseline-corpus-v1-report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (runtime / "baseline-corpus-v1-report.sha256").write_text(hashlib.sha256(output.read_bytes()).hexdigest() + "\n", encoding="ascii")
    catalog.close()
    print(json.dumps({"report": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "subjects": 10, "provider_calls": len(provider_events), "cost_usd": f"{provider_actual:.6f}"}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-corrected-20260829"))
    parser.add_argument("--skip-luna", action="store_true")
    raise SystemExit(run(parser.parse_args()))