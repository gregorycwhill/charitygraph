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
    CorpusBindingContext,
    DiscoveryState,
    MaterialOrigin,
    RepresentationReadiness,
    build_corpus_manifest,
    enumerate_site_candidates,
    extract_pfra_members,
    provider_budget_allows,
    partition_site_candidates,
    rank_site_candidates_with_luna,
    represent_pdf,
    resolve_wikipedia_candidate_with_luna,
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


class WebsiteFetchError(RuntimeError):
    def __init__(self, base_url: str, attempts: list[dict]) -> None:
        super().__init__(f"official website unavailable: {urlsplit(base_url).netloc}")
        self.base_url = base_url
        self.attempts = attempts


def fetch_website_homepage(base_url: str) -> tuple[bytes, str, int, str, list[dict]]:
    """Try only canonical same-site locator variants and retain failure telemetry."""
    parsed = urlsplit(base_url)
    variants = [base_url, base_url.rstrip("/") + "/"]
    if parsed.hostname and parsed.hostname.casefold().startswith("www."):
        variants.append(f"{parsed.scheme}://{parsed.hostname.removeprefix('www.')}/")
    attempts: list[dict] = []
    for locator in dict.fromkeys(variants):
        try:
            body, resolved, status, media = fetch(locator)
            return body, resolved, status, media, attempts + [{"url": locator, "status": status, "outcome": "available"}]
        except Exception as exc:
            attempts.append({"url": locator, "outcome": "failed", "error_class": type(exc).__name__, "error": str(exc)[:160]})
    raise WebsiteFetchError(base_url, attempts)


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def extract_abr_dgr_fields(body: bytes) -> dict[str, str | None]:
    """Return only mechanically structured ABR fields; never interpret prose."""
    # The current ABR acquisition is HTML and exposes no governed structured
    # DGR field.  Keep the raw source artefact and defer legal-status parsing.
    return {
        "status": None,
        "effective_date": None,
        "item": None,
        "source_native": False,
        "extraction": "deferred",
        "reason": "no structured ABR DGR field adapter",
    }


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
    artifact_existing = catalog.get_artifact(artifact_id) is not None and store.exists(artifact_id)
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


def acnc_reporting_scope(entity: dict, *, fetch_fn=fetch) -> tuple[dict, dict | None, dict | None]:
    """Resolve the source-native ACNC reporting envelope, if grouped."""
    data = entity.get("data") or {}
    parent_id = data.get("ParentAccountId")
    if not parent_id:
        return {"scope_kind": "registered_entity", "entity_id": data.get("uuid"), "name": data.get("Name")}, None, None
    group_url = f"{API}/entity/{parent_id}"
    body, resolved, _, _ = fetch_fn(group_url)
    group_entity = json.loads(body)
    group_data = group_entity.get("data") or {}
    scope = {
        "scope_kind": "acnc_reporting_group",
        "entity_id": group_data.get("uuid") or parent_id,
        "name": group_data.get("Name"),
        "parent_account_id": parent_id,
    }
    return scope, group_entity, {"url": group_url, "body": body, "resolved": resolved}


def sitemap_urls(home_html: str, base: str) -> list[str]:
    urls = []
    for match in re.finditer(r"<link[^>]+rel=[\"']sitemap[\"'][^>]+href=[\"']([^\"']+)", home_html, re.I):
        urls.append(urljoin(base, match.group(1)))
    for match in re.finditer(r"<loc>([^<]+)</loc>", home_html, re.I):
        if "sitemap" in match.group(1).casefold():
            urls.append(urljoin(base, match.group(1).strip()))
    return list(dict.fromkeys(urls + [urljoin(base, "/sitemap_index.xml"), urljoin(base, "/sitemap.xml")]))


def robots_sitemap_urls(robots_text: str, base: str) -> list[str]:
    return list(dict.fromkeys(urljoin(base, line.split(":", 1)[1].strip()) for line in robots_text.splitlines() if line.casefold().startswith("sitemap:") and ":" in line))


def _member_from_lineage(lineage: dict, *, family: str, discovery: DiscoveryState = DiscoveryState.RESOLVED, binding: BindingState = BindingState.BOUND, readiness: RepresentationReadiness = RepresentationReadiness.NOT_REQUIRED, representation_ids: tuple[str, ...] = (), gaps: tuple[str, ...] = (), revision: str | None = None, period: str | None = None, binding_context: CorpusBindingContext | None = None) -> CorpusMember:
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
        binding_context=binding_context,
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
    selected_abns = (args.subject_abn,) if args.subject_abn else ABNS
    for abn in selected_abns:
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
        filing_data = data
        filing_scope = {"scope_kind": "registered_entity", "entity_id": data.get("uuid"), "name": data.get("Name")}
        group_context: CorpusBindingContext | None = None
        reporting_group_lineage = None
        reporting_group_error = None
        if data.get("ParentAccountId"):
            try:
                filing_scope, reporting_group, group_payload = acnc_reporting_scope(entity)
                if reporting_group is not None and group_payload is not None:
                    filing_data = reporting_group.get("data") or {}
                    reporting_group_lineage = source_lineage(
                        catalog,
                        store,
                        family="acnc_ais_bundle",
                        endpoint=f"{API}/entity/{{reporting_group_id}}",
                        url=group_payload["url"],
                        body=group_payload["body"],
                        resolved=group_payload["resolved"],
                        media="application/json",
                        role="reporting_group_profile",
                    )
                    group_context = CorpusBindingContext(
                        basis="acnc_reporting_group",
                        acnc_entity_id=str(filing_scope.get("entity_id") or data.get("ParentAccountId")),
                        source_native_group_name=str(filing_scope.get("name") or ""),
                    )
                    members.append(_member_from_lineage(reporting_group_lineage, family="acnc_ais_bundle", binding=BindingState.BOUND, binding_context=group_context))
                    acquired_new += reporting_group_lineage["origin"] == "newly_acquired"
                    reused += reporting_group_lineage["origin"] == "reused_existing"
            except Exception as exc:
                reporting_group_error = type(exc).__name__
        reports = [item for item in filing_data.get("AnnualReports", []) if item.get("IsAIS") and item.get("Status") == "Submitted" and item.get("AISId")]
        latest = max(reports, key=lambda item: (int(item.get("Year") or 0), item.get("DateReceived") or ""), default=None)
        filing_rows: list[dict] = []
        if latest:
            try:
                ais_url = f"{API}/entity/{latest['AISId']}"
                ais_body, ais_resolved, _, _ = fetch(ais_url)
                ais_lineage = source_lineage(catalog, store, family="acnc_ais_bundle", endpoint=f"{API}/entity/{{AISId}}", url=ais_url, body=ais_body, resolved=ais_resolved, media="application/json", role="annual_information_statement", revision=str(latest.get("Year")))
                ais_member = _member_from_lineage(ais_lineage, family="acnc_ais_bundle", revision=str(latest.get("Year")), period=str(latest.get("Year")), binding_context=group_context)
                members.append(ais_member)
                filing_rows.append({"role": "annual_information_statement", "source_record_id": ais_lineage["source_record_id"], "year": str(latest.get("Year"))})
                acquired_new += ais_lineage["origin"] == "newly_acquired"
                reused += ais_lineage["origin"] == "reused_existing"
            except Exception:
                pass
            for document in select_filing_documents(filing_data.get("Documents") or [], str(latest.get("Year"))):
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
                            pdf_report.append({"abn": abn, "source_record_id": lineage["source_record_id"], "role": role, "year": str(latest.get("Year")), "readiness": representation["readiness"], "page_count": representation.get("page_count"), "native_text_pages": representation.get("native_text_pages"), "visual_escalations": representation.get("visual_escalations", 0), "page_gaps": list(gaps), "gap_reasons": representation.get("gap_reasons", {}), "derived_artifact_id": representation_id})
                        except Exception as exc:
                            readiness = RepresentationReadiness.FAILED
                            gaps = (f"representation_error:{type(exc).__name__}",)
                            pdf_report.append({"abn": abn, "source_record_id": lineage["source_record_id"], "role": role, "year": str(latest.get("Year")), "readiness": "failed", "error": type(exc).__name__, "visual_escalations": 0})
                    members.append(_member_from_lineage(lineage, family="acnc_ais_bundle", readiness=readiness, representation_ids=representation_ids, gaps=gaps, revision=str(latest.get("Year")), period=str(latest.get("Year")), binding_context=group_context))
                    filing_rows.append({"role": role, "source_record_id": lineage["source_record_id"], "year": str(latest.get("Year")), "title": document.get("Title")})
                    acquired_new += lineage["origin"] == "newly_acquired"
                    reused += lineage["origin"] == "reused_existing"
                except Exception:
                    filing_rows.append({"role": document.get("role"), "url": document.get("Url"), "status": "failed"})
        coverage["acnc_ais_bundle"] = {"discovery": "resolved" if latest else "absent", "acquisition": "available" if latest else "absent", "binding": "bound" if latest else "no_bound_record", "origin": "newly_acquired" if latest else "none", "period": latest.get("Year") if latest else None, "bundle_member_count": len(filing_rows), "members": filing_rows, "filing_scope": filing_scope, "reporting_group_source_record_id": reporting_group_lineage["source_record_id"] if reporting_group_lineage else None, "reporting_group_error": reporting_group_error}
        abr_url = f"https://abr.business.gov.au/ABN/View?abn={abn}"
        try:
            abr_body, abr_resolved, _, abr_media = fetch(abr_url)
            lineage = source_lineage(catalog, store, family="ato_abr_dgr", endpoint="https://abr.business.gov.au/ABN/View", url=abr_url, body=abr_body, resolved=abr_resolved, media=abr_media, role="abr_entity")
            members.append(_member_from_lineage(lineage, family="ato_abr_dgr"))
            acquired_new += lineage["origin"] == "newly_acquired"
            reused += lineage["origin"] == "reused_existing"
            dgr_fields = extract_abr_dgr_fields(abr_body)
            coverage["ato_abr_dgr"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": lineage["origin"], "role": "abr_entity", "dgr_fields": dgr_fields, "record_ids": [lineage["source_record_id"]]}
        except Exception as exc:
            coverage["ato_abr_dgr"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "error": type(exc).__name__}
        base = WEBSITES[abn]
        site_row = {"status": "failed", "candidate_count": 0, "sitemap_urls": [], "sitemap_count": 0, "ranking": None, "acquired_page_records": [], "homepage_persisted": False, "ranking_attempted": False, "batch_count": 0, "finalist_count": 0, "homepage_transport_attempts": []}
        try:
            home_body, home_resolved, _, home_media, homepage_attempts = fetch_website_homepage(base)
            site_row["homepage_transport_attempts"] = homepage_attempts
            home_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=base, body=home_body, resolved=home_resolved, media=home_media, role="official_homepage")
            members.append(_member_from_lineage(home_lineage, family="official_website"))
            site_row["homepage_persisted"] = True
            acquired_new += home_lineage["origin"] == "newly_acquired"
            reused += home_lineage["origin"] == "reused_existing"
            sitemap_xmls = []
            sitemap_candidates = sitemap_urls(home_body.decode("utf-8", "replace"), base)
            try:
                robots_body, robots_resolved, _, robots_media = fetch(urljoin(base, "/robots.txt"))
                robots_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=urljoin(base, "/robots.txt"), body=robots_body, resolved=robots_resolved, media=robots_media, role="robots")
                members.append(_member_from_lineage(robots_lineage, family="official_website"))
                acquired_new += robots_lineage["origin"] == "newly_acquired"
                reused += robots_lineage["origin"] == "reused_existing"
                sitemap_candidates = list(dict.fromkeys(robots_sitemap_urls(robots_body.decode("utf-8", "replace"), base) + sitemap_candidates))
                site_row["robots_url"] = robots_resolved
            except Exception:
                site_row["robots_url"] = None
            for sitemap_url in sitemap_candidates:
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
                # Keep each request within the configured model context/output
                # envelope; this is a token-derived boundary, not a URL-count
                # shortcut. Large sites therefore use a few bounded batches.
                batches = partition_site_candidates(candidates, max_output_tokens=LUNA_MAX_OUTPUT_TOKENS, max_request_tokens=60000)
                site_row["batch_count"] = len(batches)
                batch_results = []
                finalists: list[dict] = []
                ranking_blocked = False
                subject_name = str(data.get("Name") or data.get("CharityLegalName") or abn)
                for batch_index, batch in enumerate(batches):
                    projected = projected_luna_cost(batch)
                    allowed = provider_budget_allows(provider_actual, provider_reserved, projected, MAX_PROVIDER_USD)
                    event = {"subject_abn": abn, "subject_name": subject_name, "phase": "batch", "batch_index": batch_index, "candidate_count": len(batch), "model": "gpt-5.6-luna", "projected_max_usd": f"{projected:.6f}", "actual_cost_usd": "0", "transport_requests": 0, "preflight_allowed": allowed}
                    if not allowed:
                        event["status"] = "blocked_budget"
                        provider_events.append(event)
                        ranking_blocked = True
                        break
                    try:
                        ranking = rank_site_candidates_with_luna(batch, subject_name=subject_name, model="gpt-5.6-luna", max_output_tokens=LUNA_MAX_OUTPUT_TOKENS)
                        actual = Decimal(str(ranking.get("cost_usd") or "0"))
                        provider_actual += actual
                        event.update({"actual_cost_usd": f"{actual:.6f}", "transport_requests": ranking.get("transport_requests", 0), "input_tokens": (ranking.get("usage") or {}).get("input_tokens"), "output_tokens": (ranking.get("usage") or {}).get("output_tokens"), "status": "completed" if not ranking.get("validation_error") else "invalid_output"})
                        if provider_actual + provider_reserved > MAX_PROVIDER_USD:
                            raise RuntimeError(f"Luna actual spend exceeded USD {MAX_PROVIDER_USD}")
                        provider_events.append(event)
                        batch_results.append({"batch_index": batch_index, "candidate_count": len(batch), "ranking": ranking})
                        if not ranking.get("validation_error"):
                            by_ordinal = {int(item["ordinal"]): item for item in batch}
                            finalists.extend(by_ordinal[ordinal] for ordinal in ranking["ranked_ordinals"][:10] if ordinal in by_ordinal)
                    except Exception as exc:
                        event.update({"status": "failed", "error": type(exc).__name__})
                        provider_events.append(event)
                        batch_results.append({"batch_index": batch_index, "candidate_count": len(batch), "status": "failed", "error": type(exc).__name__})
                # A second bounded ranking combines the batch finalists.  It is
                # still ordinal-only and is guarded independently by the cap.
                finalists = list({int(item["ordinal"]): item for item in finalists}.values())
                site_row["finalist_count"] = len(finalists)
                final_ranking = None
                if finalists and not ranking_blocked:
                    projected = projected_luna_cost(finalists)
                    allowed = provider_budget_allows(provider_actual, provider_reserved, projected, MAX_PROVIDER_USD)
                    event = {"subject_abn": abn, "subject_name": subject_name, "phase": "final", "candidate_count": len(finalists), "model": "gpt-5.6-luna", "projected_max_usd": f"{projected:.6f}", "actual_cost_usd": "0", "transport_requests": 0, "preflight_allowed": allowed}
                    if not allowed:
                        event["status"] = "blocked_budget"
                        provider_events.append(event)
                    else:
                        try:
                            final_ranking = rank_site_candidates_with_luna(finalists, subject_name=subject_name, model="gpt-5.6-luna", max_output_tokens=LUNA_MAX_OUTPUT_TOKENS)
                            actual = Decimal(str(final_ranking.get("cost_usd") or "0"))
                            provider_actual += actual
                            event.update({"actual_cost_usd": f"{actual:.6f}", "transport_requests": final_ranking.get("transport_requests", 0), "input_tokens": (final_ranking.get("usage") or {}).get("input_tokens"), "output_tokens": (final_ranking.get("usage") or {}).get("output_tokens"), "status": "completed" if not final_ranking.get("validation_error") else "invalid_output"})
                            provider_events.append(event)
                        except Exception as exc:
                            event.update({"status": "failed", "error": type(exc).__name__})
                            provider_events.append(event)
                            final_ranking = {"status": "failed", "error": type(exc).__name__}
                selected = []
                if final_ranking and not final_ranking.get("validation_error") and final_ranking.get("ranked_ordinals"):
                    by_ordinal = {int(item["ordinal"]): item for item in finalists}
                    selected = [by_ordinal[ordinal] for ordinal in final_ranking["ranked_ordinals"][:10] if ordinal in by_ordinal]
                for candidate in selected:
                    try:
                        page_body, page_resolved, _, page_media = fetch(candidate["url"])
                        page_lineage = source_lineage(catalog, store, family="official_website", endpoint=base, url=candidate["url"], body=page_body, resolved=page_resolved, media=page_media, role="official_page")
                        members.append(_member_from_lineage(page_lineage, family="official_website"))
                        site_row["acquired_page_records"].append({"url": candidate["url"], "source_record_id": page_lineage["source_record_id"], "artifact_id": page_lineage["artifact_id"]})
                        acquired_new += page_lineage["origin"] == "newly_acquired"
                        reused += page_lineage["origin"] == "reused_existing"
                    except Exception:
                        continue
                site_row["ranking"] = {"status": "completed" if final_ranking and not final_ranking.get("validation_error") else ("blocked_budget" if ranking_blocked else "partial"), "batch_rankings": batch_results, "finalists": finalists, "final_ranking": final_ranking}
            site_row["mechanical_candidates"] = [{"ordinal": c["ordinal"], "url": c["url"], "label": c.get("label", "")} for c in candidates]
            coverage["official_website"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": "newly_acquired", "candidate_count": len(candidates), "homepage_persisted": True, "sitemap_count": len(sitemap_xmls), "top_page_count": len(site_row["acquired_page_records"])}
        except WebsiteFetchError as exc:
            site_row["homepage_transport_attempts"] = exc.attempts
            site_row["error"] = type(exc).__name__
            coverage["official_website"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "homepage_persisted": False, "candidate_count": 0, "top_page_count": 0, "error": type(exc).__name__, "transport_attempts": exc.attempts}
        except Exception as exc:
            site_row["error"] = type(exc).__name__
            coverage["official_website"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "homepage_persisted": False, "candidate_count": 0, "top_page_count": 0, "error": type(exc).__name__}
        site_report[abn] = site_row
        names = [str(data.get(key) or "") for key in ("Name", "CharityLegalName", "LegalName") if data.get(key)] + [str(item) for item in (data.get("OtherNames") or []) if item]
        try:
            search_rows = []
            seen_titles = set()
            for query_name in names or [abn]:
                query_url = WIKI + "?" + urlencode({"action": "query", "list": "search", "srsearch": query_name, "format": "json", "srlimit": 10})
                wiki_body, _, _, _ = fetch(query_url)
                for row in json.loads(wiki_body).get("query", {}).get("search", []):
                    if row.get("title") not in seen_titles:
                        search_rows.append(row)
                        seen_titles.add(row.get("title"))
            resolution = resolve_wikipedia_candidate(names, search_rows)
            identity_resolution = None
            if resolution["status"] != "bound" and search_rows and not args.skip_luna:
                projected = projected_luna_cost(search_rows)
                allowed = provider_budget_allows(provider_actual, provider_reserved, projected, MAX_PROVIDER_USD)
                identity_event = {"subject_abn": abn, "subject_name": names[0] if names else abn, "phase": "wikipedia_identity", "candidate_count": len(search_rows), "model": "gpt-5.6-luna", "projected_max_usd": f"{projected:.6f}", "actual_cost_usd": "0", "transport_requests": 0, "preflight_allowed": allowed}
                if allowed:
                    identity_resolution = resolve_wikipedia_candidate_with_luna(names, search_rows, subject_context={"abn": abn, "registered_name": names[0] if names else None, "website": data.get("Website")}, model="gpt-5.6-luna", max_output_tokens=LUNA_MAX_OUTPUT_TOKENS)
                    actual = Decimal(str(identity_resolution.get("cost_usd") or "0"))
                    provider_actual += actual
                    identity_event.update({"actual_cost_usd": f"{actual:.6f}", "transport_requests": identity_resolution.get("transport_requests", 0), "input_tokens": (identity_resolution.get("usage") or {}).get("input_tokens"), "output_tokens": (identity_resolution.get("usage") or {}).get("output_tokens"), "status": "completed" if not identity_resolution.get("validation_error") else "invalid_output"})
                    provider_events.append(identity_event)
                    if identity_resolution.get("status") == "bound" and identity_resolution.get("candidate_index") is not None:
                        resolution = {"status": "bound", "candidate": search_rows[int(identity_resolution["candidate_index"])], "basis": "luna_bounded_entity_resolution"}
                    elif identity_resolution.get("status") in {"ambiguous", "no_bound_record"}:
                        resolution = {"status": identity_resolution["status"], "candidates": search_rows, "basis": "luna_bounded_entity_resolution"}
                else:
                    identity_event["status"] = "blocked_budget"
                    provider_events.append(identity_event)
            if resolution["status"] == "bound":
                title = resolution["candidate"]["title"]
                page_query = WIKI + "?" + urlencode({"action": "query", "prop": "info|revisions", "rvprop": "ids|timestamp|content", "rvslots": "main", "rvlimit": 1, "titles": title, "format": "json", "formatversion": "2"})
                page_body, page_resolved, _, page_media = fetch(page_query)
                page_data = json.loads(page_body)
                page = (page_data.get("query", {}).get("pages") or [{}])[0]
                revision = str((page.get("lastrevid") or ((page.get("revisions") or [{}])[0].get("revid")) or "")) or None
                lineage = source_lineage(catalog, store, family="wikipedia_wikimedia", endpoint=WIKI, url=page_query, body=page_body, resolved=page_resolved, media=page_media, role="article_identity", revision=revision)
                members.append(_member_from_lineage(lineage, family="wikipedia_wikimedia", revision=revision))
                wikipedia_report[abn] = {"status": "bound", "title": title, "page_id": page.get("pageid"), "revision_id": revision, "permalink": page.get("canonicalurl"), "content_artifact_id": lineage["artifact_id"], "source_record_id": lineage["source_record_id"], "basis": resolution["basis"]}
                coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "available", "binding": "bound", "origin": lineage["origin"], "title": title, "page_id": page.get("pageid"), "revision_id": revision, "content_artifact_id": lineage["artifact_id"]}
                acquired_new += lineage["origin"] == "newly_acquired"
                reused += lineage["origin"] == "reused_existing"
            else:
                wikipedia_report[abn] = {"status": resolution["status"], "basis": resolution["basis"], "candidate_count": len(resolution.get("candidates", [])), "candidates": [{"title": row.get("title"), "snippet": row.get("snippet")} for row in resolution.get("candidates", [])]}
                coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "available", "binding": resolution["status"], "origin": "none", "candidate_count": len(resolution.get("candidates", []))}
        except Exception as exc:
            wikipedia_report[abn] = {"status": "failed", "error": type(exc).__name__}
            coverage["wikipedia_wikimedia"] = {"discovery": "resolved", "acquisition": "failed", "binding": "none", "origin": "none", "error": type(exc).__name__}
        subject_domain = urlsplit(WEBSITES[abn]).hostname.casefold().removeprefix("www.") if urlsplit(WEBSITES[abn]).hostname else ""
        exact_pfra = [record for record in pfra_records if subject_domain in {str(domain).casefold().removeprefix("www.") for domain in record.get("linked_domains", [])}]
        candidate_pfra = [record for record in pfra_records if _normalise_name(record["label"]) in {_normalise_name(name) for name in names}]
        matched_pfra = exact_pfra[:1]
        pfra_basis = "exact_linked_domain" if len(exact_pfra) == 1 else None
        pfra_identity = None
        if not matched_pfra and candidate_pfra and not args.skip_luna:
            projected = projected_luna_cost([{"title": row["label"], "snippet": ", ".join(row.get("linked_domains", []))} for row in candidate_pfra])
            allowed = provider_budget_allows(provider_actual, provider_reserved, projected, MAX_PROVIDER_USD)
            identity_event = {"subject_abn": abn, "subject_name": names[0] if names else abn, "phase": "pfra_identity", "candidate_count": len(candidate_pfra), "model": "gpt-5.6-luna", "projected_max_usd": f"{projected:.6f}", "actual_cost_usd": "0", "transport_requests": 0, "preflight_allowed": allowed}
            if allowed:
                pfra_identity = resolve_wikipedia_candidate_with_luna(names, [{"title": row["label"], "snippet": ", ".join(row.get("linked_domains", []))} for row in candidate_pfra], subject_context={"abn": abn, "website_domain": subject_domain, "source_family": "PFRA"}, model="gpt-5.6-luna", max_output_tokens=LUNA_MAX_OUTPUT_TOKENS)
                actual = Decimal(str(pfra_identity.get("cost_usd") or "0"))
                provider_actual += actual
                identity_event.update({"actual_cost_usd": f"{actual:.6f}", "transport_requests": pfra_identity.get("transport_requests", 0), "input_tokens": (pfra_identity.get("usage") or {}).get("input_tokens"), "output_tokens": (pfra_identity.get("usage") or {}).get("output_tokens"), "status": "completed" if not pfra_identity.get("validation_error") else "invalid_output"})
                provider_events.append(identity_event)
                if pfra_identity.get("status") == "bound" and pfra_identity.get("candidate_index") is not None:
                    matched_pfra = [candidate_pfra[int(pfra_identity["candidate_index"])]]
                    pfra_basis = "luna_bounded_entity_resolution"
                elif pfra_identity.get("status") == "ambiguous":
                    pfra_basis = "ambiguous_name_candidate"
            else:
                identity_event["status"] = "blocked_budget"
                provider_events.append(identity_event)
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
        pfra_report[abn] = {"status": "bound" if pfra_rows else ("ambiguous" if pfra_basis == "ambiguous_name_candidate" else "no_bound_record"), "basis": pfra_basis or "no_exact_linked_domain", "records": pfra_rows, "candidate_records": candidate_pfra if not pfra_rows else [], "directory_counts": {"charity": sum(r["member_role"] == "current_charity_membership" for r in pfra_records), "agency": sum(r["member_role"] == "agency_membership" for r in pfra_records)}}
        coverage["pfra"] = {"discovery": "resolved", "acquisition": "available" if pfra_pages else "failed", "binding": "bound" if pfra_rows else ("ambiguous" if pfra_basis == "ambiguous_name_candidate" else "no_bound_record"), "origin": "newly_acquired" if pfra_rows else "none", "record_count": len(pfra_rows), "binding_basis": pfra_basis or "no_exact_linked_domain"}
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
        "aggregate": {"source_families": 6, "subjects": len(selected_abns), "newly_acquired_material_count": acquired_new, "reused_material_count": reused, "wikipedia_bound": sum(v.get("status") == "bound" for v in wikipedia_report.values()), "pfra_bound": sum(v.get("status") == "bound" for v in pfra_report.values()), "provider_calls": len(provider_events), "provider": "gpt-5.6-luna", "input_tokens": sum(int((e.get("usage") or {}).get("input_tokens") or 0) for e in provider_events), "output_tokens": sum(int((e.get("usage") or {}).get("output_tokens") or 0) for e in provider_events), "cost_usd": f"{provider_actual:.6f}", "semantic_extraction": False, "economics": "exact Luna usage/cost with conservative preflight and USD 0.50 fail-closed cap; no ranked BudgetCohort ledger used"},
    }
    output = runtime / "baseline-corpus-v1-report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (runtime / "baseline-corpus-v1-report.sha256").write_text(hashlib.sha256(output.read_bytes()).hexdigest() + "\n", encoding="ascii")
    catalog.close()
    print(json.dumps({"report": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "subjects": len(selected_abns), "provider_calls": len(provider_events), "cost_usd": f"{provider_actual:.6f}"}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\CharityGraph-runtime\baseline-corpus-v1-corrected-20260829"))
    parser.add_argument("--skip-luna", action="store_true")
    parser.add_argument("--subject-abn", choices=ABNS, help="Run one governed subject only")
    raise SystemExit(run(parser.parse_args()))
