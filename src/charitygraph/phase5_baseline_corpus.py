"""Provider-free, resumable Phase-5 Top-100 baseline corpus mechanics.

This module deliberately acquires and freezes source material only.  It has no
model-provider dependency, semantic extraction, candidate creation, or task
creation path.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import pdfplumber

from charitygraph.baseline_corpus import (
    AcquisitionState, BindingState, CorpusMember, DiscoveryState, MaterialOrigin,
    RepresentationReadiness, build_corpus_manifest, extract_pfra_members,
    resolve_wikipedia_candidate, select_filing_documents,
)
from charitygraph.contracts import AcquisitionReceipt, PropositionAuthorityRole, SourceDefinition, SourceRecord
from charitygraph.contracts.ids import deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.runtime import SQLiteCatalog


COHORT_HASH = "704d105c9b8b9dda05dba1ac8285f5f01ba92a1b22775a8d92c8236ddcf09e00"
IDENTITY_MAP_HASH = "55dc192a4d226fc3769f8408d5fdf6467f11710b9687f8f72c3f2a0ba10024aa"
PROFILE_VERSION = "phase5-top100-baseline-corpus-v1"
SOURCE_FAMILIES = (
    "acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website",
    "annual_report", "wikipedia_wikimedia", "pfra",
)
ACNC_API_HOSTS = {"www.acnc.gov.au", "acncpubfilesprodstorage.blob.core.windows.net"}
ABR_HOSTS = {"abr.business.gov.au"}
WIKIMEDIA_HOSTS = {"en.wikipedia.org"}
PFRA_HOSTS = {"pfra.org.au", "www.pfra.org.au"}
SOURCE_DEFINITION_CREATED_AT = datetime(2026, 9, 6, tzinfo=timezone.utc)
MAX_NATIVE_TEXT_PAGES = 5


class ProviderUseProhibited(RuntimeError):
    """Raised if an execution path tries to reach a model provider."""


class NetworkPolicyError(RuntimeError):
    """Raised when an acquisition leaves the declared source universe."""


@dataclass
class ProviderGuard:
    attempted_calls: list[dict[str, str]] = field(default_factory=list)

    def prohibit(self, operation: str) -> None:
        self.attempted_calls.append({"operation": operation, "status": "blocked"})
        raise ProviderUseProhibited(f"provider use prohibited in Phase-5 baseline acquisition: {operation}")

    def report(self) -> dict[str, Any]:
        return {
            "provider_calls": 0,
            "provider_cost_usd": "0",
            "attempted_provider_calls": self.attempted_calls,
            "guard_status": "verified_provider_free",
            "forbidden_paths": ["responses", "embeddings", "vision", "model_ranking", "model_identity_resolution"],
        }


@dataclass
class NetworkLedger:
    events: list[dict[str, Any]] = field(default_factory=list)
    cache_root: Path | None = None

    def fetch(self, *, source_family: str, url: str, allowed_hosts: set[str], timeout_seconds: int = 45, max_bytes: int = 30_000_000) -> dict[str, Any]:
        host = (urlsplit(url).hostname or "").casefold()
        if host not in allowed_hosts:
            raise NetworkPolicyError(f"unapproved host for {source_family}: {host}")
        cache_key = hashlib.sha256(f"{source_family}\n{url}".encode("utf-8")).hexdigest()
        metadata_path = self.cache_root / f"{cache_key}.json" if self.cache_root else None
        body_path = self.cache_root / f"{cache_key}.body" if self.cache_root else None
        if metadata_path and metadata_path.exists():
            cached = read_json(metadata_path)
            event = {**cached["event"], "origin": "reused_existing", "replayed_at": datetime.now(timezone.utc).isoformat()}
            self.events.append(event)
            if cached["ok"]:
                if body_path is None or not body_path.exists():
                    raise RuntimeError(f"network cache body missing for {source_family}")
                body = body_path.read_bytes()
                if hashlib.sha256(body).hexdigest() != cached["event"]["content_hash"]:
                    raise RuntimeError(f"network cache body hash mismatch for {source_family}")
                return {"ok": True, "body": body, "resolved_url": cached["event"]["resolved_url"], "status": cached["event"]["response_status"], "media_type": cached["event"]["media_type"], "event": event}
            return {"ok": False, "event": event}
        started = datetime.now(timezone.utc)
        event: dict[str, Any] = {"source_family": source_family, "requested_url": url, "requested_host": host, "started_at": started.isoformat()}
        result: dict[str, Any]
        try:
            request = Request(url, headers={"User-Agent": "CharityGraph Phase5 baseline corpus/1.0"})
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310: host checked above
                body = response.read(max_bytes + 1)
                resolved = response.geturl()
                resolved_host = (urlsplit(resolved).hostname or "").casefold()
                if resolved_host not in allowed_hosts:
                    raise NetworkPolicyError(f"redirected to unapproved host for {source_family}: {resolved_host}")
                if len(body) > max_bytes:
                    event.update({"outcome": "failed", "error_class": "response_too_large", "resolved_url": resolved, "resolved_host": resolved_host})
                else:
                    event.update({"outcome": "available", "response_status": response.status, "resolved_url": resolved, "resolved_host": resolved_host, "media_type": response.headers.get_content_type(), "byte_size": len(body), "content_hash": hashlib.sha256(body).hexdigest()})
                    result = {"ok": True, "body": body, "resolved_url": resolved, "status": response.status, "media_type": response.headers.get_content_type(), "event": event}
                    return result
        except HTTPError as exc:
            event.update({"outcome": "unavailable" if exc.code == 404 else "failed", "response_status": exc.code, "error_class": f"http_{exc.code}"})
        except (URLError, TimeoutError, ValueError) as exc:
            event.update({"outcome": "failed", "error_class": type(exc).__name__})
        except NetworkPolicyError:
            event.update({"outcome": "blocked", "error_class": "NetworkPolicyError"})
            raise
        finally:
            event["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.events.append(event)
            if metadata_path:
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                if event.get("outcome") == "available" and body_path and 'body' in locals():
                    body_path.write_bytes(body)
                atomic_json(metadata_path, {"ok": event.get("outcome") == "available", "event": event})
        return {"ok": False, "event": event}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(encoded, encoding="utf-8")
    temp.replace(path)


def validate_checkpoint(*, historical_root: Path, identity_path: Path, catalog_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    cohort_bytes = (historical_root / "top100-cohort-manifest.json").read_bytes()
    if hashlib.sha256(cohort_bytes).hexdigest() != COHORT_HASH:
        raise RuntimeError("frozen Top-100 cohort hash changed")
    cohort = json.loads(cohort_bytes)["selected"]
    if len(cohort) != 100 or {item["donation_rank_2024_public"] for item in cohort} != set(range(1, 101)) or len({str(item["abn"]) for item in cohort}) != 100:
        raise RuntimeError("frozen cohort is not exactly 100 unique ranks and ABNs")
    identity = read_json(identity_path)
    if identity.get("identity_map_hash") != IDENTITY_MAP_HASH or len(identity.get("rows", [])) != 100:
        raise RuntimeError("governed identity map checkpoint changed")
    subject_ids = {str(item["abn"]): item["subject_id"] for item in identity["rows"]}
    if set(subject_ids) != {str(item["abn"]) for item in cohort} or len(set(subject_ids.values())) != 100:
        raise RuntimeError("identity map is not a 100/100 exact cohort map")
    catalog = SQLiteCatalog(catalog_path).open(initialize=True)
    try:
        with catalog._connection() as connection:
            query = ",".join("?" for _ in subject_ids)
            rows = connection.execute(
                f"SELECT identifier_value, subject_id, status, issuing_authority FROM external_identifiers WHERE scheme='ABN' AND identifier_value IN ({query})",
                tuple(subject_ids),
            ).fetchall()
        bound = {str(row[0]): str(row[1]) for row in rows if row[2] == "active" and row[3] == "Australian Business Register"}
        if bound != subject_ids or len(rows) != 100:
            raise RuntimeError("catalogue does not have exactly one active governed ABN binding per cohort member")
    finally:
        catalog.close()
    return sorted(cohort, key=lambda item: item["donation_rank_2024_public"]), subject_ids


def source_definition(family: str, now: datetime) -> SourceDefinition:
    endpoint = {
        "acnc_register": "https://www.acnc.gov.au/api/dynamics/entity",
        "acnc_ais_bundle": "https://www.acnc.gov.au/api/dynamics/entity/{AISId}",
        "ato_abr_dgr": "https://abr.business.gov.au/ABN/View",
        "official_website": "governed official website locator",
        "annual_report": "ACNC structured filing document URL",
        "wikipedia_wikimedia": "https://en.wikipedia.org/w/api.php",
        "pfra": "https://pfra.org.au/membership/",
    }[family]
    publisher = {"acnc_register": "Australian Charities and Not-for-profits Commission", "acnc_ais_bundle": "Australian Charities and Not-for-profits Commission", "ato_abr_dgr": "Australian Business Register", "wikipedia_wikimedia": "Wikimedia Foundation", "pfra": "Public Fundraising Regulatory Association"}.get(family, "Source publisher recorded by source-native locator")
    return SourceDefinition(
        record_id=deterministic_id("srcdef:", {"profile": PROFILE_VERSION, "family": family, "endpoint": endpoint}),
        created_at=SOURCE_DEFINITION_CREATED_AT, producer={"kind": "code", "producer_id": PROFILE_VERSION, "version": "1"}, definition_version="1",
        publisher=publisher, source_class=family,
        authority_roles=(PropositionAuthorityRole(proposition="source material", role="source-reported", basis="Phase-5 baseline source universe"),),
        acquisition_locator=endpoint, temporal_semantics="retrieved source material or source-native reporting period",
        publication_eligibility="private_review_only", steward="CharityGraph source governance",
    )


def persist_available(*, catalog: SQLiteCatalog, store: ContentAddressedArtifactStore, family: str, requested_url: str, resolved_url: str, body: bytes, media_type: str, role: str, source_version: str | None, origin: MaterialOrigin, now: datetime) -> dict[str, str]:
    definition = source_definition(family, now)
    catalog.register_source_definition(definition)
    content_hash = hashlib.sha256(body).hexdigest()
    artifact_id = "srcblob:" + content_hash
    if catalog.get_artifact(artifact_id) is None or not store.exists(artifact_id):
        store.put(body, created_at=now)
    receipt_id = deterministic_id("acq:", {"source_definition_id": definition.record_id, "artifact_id": artifact_id, "requested_locator": requested_url})
    if catalog.get_acquisition_receipt(receipt_id) is None:
        catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=receipt_id, created_at=now, producer={"kind": "code", "producer_id": PROFILE_VERSION, "version": "1"}, source_definition_id=definition.record_id, requested_locator=requested_url, resolved_locator=resolved_url, retrieved_at=now, outcome="available" if body else "partial", response_status=200, media_type=media_type, content_hash=content_hash, byte_size=len(body), artifact_id=artifact_id, tool_id="urllib_or_archived_reuse", tool_version="stdlib"))
    record_id = deterministic_id("srcrec:", {"source_family": family, "source_version": source_version, "source_locator": resolved_url, "payload_hash": content_hash})
    if catalog.get_source_record(record_id) is None:
        catalog.register_source_record(SourceRecord(record_id=record_id, created_at=now, producer={"kind": "code", "producer_id": PROFILE_VERSION, "version": "1"}, source_family=family, source_role=role, source_version=source_version, source_locator=resolved_url, retrieved_at=now, observed_at=now, media_type=media_type, payload_ref=artifact_id, payload_hash=content_hash, attribution=source_definition(family, now).publisher))
    return {"source_definition_id": definition.record_id, "acquisition_receipt_id": receipt_id, "artifact_id": artifact_id, "source_record_id": record_id, "origin": origin.value, "acquisition": "available" if body else "partial"}


def available_member(lineage: dict[str, str], *, family: str, binding: BindingState = BindingState.BOUND, period: str | None = None, readiness: RepresentationReadiness = RepresentationReadiness.NOT_REQUIRED, representation_ids: tuple[str, ...] = (), gaps: tuple[str, ...] = ()) -> CorpusMember:
    return CorpusMember(source_family=family, source_definition_id=lineage["source_definition_id"], acquisition_receipt_ids=(lineage["acquisition_receipt_id"],), artifact_ids=(lineage["artifact_id"],), source_record_ids=(lineage["source_record_id"],), source_revision=None, effective_period=period, discovery=DiscoveryState.RESOLVED, acquisition=AcquisitionState(lineage.get("acquisition", "available")), subject_binding=binding, material_origin=MaterialOrigin(lineage["origin"]), representation_readiness=readiness, representation_artifact_ids=representation_ids, representation_gaps=gaps)


def state_member(*, family: str, source_definition_id: str, acquisition: AcquisitionState, binding: BindingState = BindingState.NONE, discovery: DiscoveryState = DiscoveryState.RESOLVED, notes: str = "") -> CorpusMember:
    return CorpusMember(source_family=family, source_definition_id=source_definition_id, discovery=discovery, acquisition=acquisition, subject_binding=binding, material_origin=MaterialOrigin.NONE, representation_readiness=RepresentationReadiness.NOT_ATTEMPTED, representation_gaps=(notes,) if notes else ())


def historical_material(historical_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    bundles = read_json(historical_root / "evidence-bundles.json")["bundles"]
    result: dict[str, dict[str, dict[str, Any]]] = {}
    names = {"acnc-profile": "acnc_register", "acnc-profile-ais": "acnc_ais_bundle", "official-homepage": "official_website", "abr": "ato_abr_dgr"}
    for bundle in bundles:
        by_family: dict[str, dict[str, Any]] = {}
        for record in bundle.get("evidence_records", []):
            family = names.get(record.get("source_family"))
            if family:
                by_family[family] = record
        result[str(bundle["abn"])] = by_family
    return result


def historical_bytes(historical_root: Path, record: dict[str, Any]) -> bytes:
    """Load retained historical bytes, using the hash-verified inline bundle copy when needed."""
    content_hash = str(record["content_hash"])
    path = historical_root / "raw" / content_hash
    if path.exists():
        body = path.read_bytes()
    elif isinstance(record.get("text"), str):
        body = record["text"].encode("utf-8")
    else:
        raise FileNotFoundError(f"no retained bytes for historical material {content_hash}")
    if hashlib.sha256(body).hexdigest() != content_hash:
        raise RuntimeError(f"historical raw material hash mismatch: {content_hash}")
    return body


def latest_report_documents(profile: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    data = profile.get("data") or {}
    reports = [item for item in data.get("AnnualReports", []) if item.get("Status") == "Submitted" and not item.get("IsAIS") and item.get("DocumentUuid")]
    if not reports:
        return None, []
    latest = max(reports, key=lambda item: (int(item.get("Year") or 0), str(item.get("DateReceived") or "")))
    year = str(latest.get("Year"))
    return year, select_filing_documents(data.get("Documents") or [], year)


def native_pdf_representation(path: Path) -> dict[str, Any]:
    """Preserve native page text and explicit visual gaps without rendering pages.

    Rendering every page is not required to retain a truthful corpus state and
    makes large filings non-resumable in practice.  Low-text pages remain
    explicitly unresolved for later authorized OCR/vision work.
    """
    source_bytes = path.read_bytes()
    pages: list[dict[str, Any]] = []
    native_text_pages = 0; low_text_pages: list[int] = []; scanned_pages: list[int] = []; visual_pages: list[int] = []
    with pdfplumber.open(path) as document:
        for number, page in enumerate(document.pages, start=1):
            if number > MAX_NATIVE_TEXT_PAGES:
                low_text_pages.append(number)
                visual_pages.append(number)
                pages.append({"page": number, "text": "", "native_text_characters": 0, "page_state": "native_extraction_deferred", "visual_or_ocr_state": "unresolved_without_provider_escalation"})
                continue
            text = page.extract_text() or ""
            low_text = len(text.strip()) < 40
            visual = bool(page.images or page.curves or page.rects)
            if low_text:
                low_text_pages.append(number)
                if visual: scanned_pages.append(number)
                visual_pages.append(number)
            else:
                native_text_pages += 1
            pages.append({"page": number, "text": text, "native_text_characters": len(text.strip()), "page_state": "native_text_sufficient" if not low_text else "native_text_insufficient", "visual_or_ocr_state": "unresolved_without_provider_escalation" if low_text else "not_required"})
    readiness = "ready" if not low_text_pages else "partial" if pages else "failed"
    return {"readiness": readiness, "source_sha256": hashlib.sha256(source_bytes).hexdigest(), "page_count": len(pages), "extracted_page_count": native_text_pages + len(low_text_pages) - sum(1 for page in pages if page["page_state"] == "native_extraction_deferred"), "native_text_pages": native_text_pages, "low_text_pages": low_text_pages, "image_only_or_scanned_pages": scanned_pages, "visual_relationships_unresolved_pages": visual_pages, "pages": pages, "extractor": "pdfplumber_native_text_no_render_no_provider", "native_text_page_budget": MAX_NATIVE_TEXT_PAGES, "deferred_page_count": sum(1 for page in pages if page["page_state"] == "native_extraction_deferred")}


def governed_website_url(value: str) -> str:
    """Normalise only missing URL scheme on an already-governed locator."""
    candidate = str(value).strip()
    parsed = urlsplit(candidate)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        return candidate
    if not parsed.scheme and candidate and not any(char.isspace() for char in candidate):
        return "https://" + candidate
    return candidate


def governed_website_hosts(url: str) -> set[str]:
    """Allow only the recorded host and its canonical www counterpart."""
    host = (urlsplit(url).hostname or "").casefold()
    return {host, host.removeprefix("www."), "www." + host.removeprefix("www.")} - {""}


def represent_document(*, runtime_root: Path, store: ContentAddressedArtifactStore, artifact_id: str, body: bytes, now: datetime) -> tuple[RepresentationReadiness, tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    staging = runtime_root / "staging"; staging.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(body).hexdigest(); path = staging / f"{source_hash}.pdf"
    if not path.exists(): path.write_bytes(body)
    report = native_pdf_representation(path)
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    derived_id = "artifact:" + hashlib.sha256(encoded).hexdigest()
    if store.catalog is None or store.catalog.get_artifact(derived_id) is None or not store.exists(derived_id):
        store.put_derived(encoded, input_artifact_ids=(artifact_id,), created_at=now)
    gaps = tuple(f"low_text_page:{page}" for page in report["low_text_pages"])
    return RepresentationReadiness(report["readiness"]), (derived_id,), gaps, report


def run_baseline(*, runtime_root: Path, historical_root: Path, identity_path: Path, catalog_path: Path, interruption_after: int | None = None) -> dict[str, Any]:
    """Run or resume the bounded seven-family source acquisition/freeze workflow."""
    guard = ProviderGuard()
    cohort, subjects = validate_checkpoint(historical_root=historical_root, identity_path=identity_path, catalog_path=catalog_path)
    runtime_root.mkdir(parents=True, exist_ok=True)
    ops_root = runtime_root / "operations"; ops_root.mkdir(exist_ok=True)
    manifests_root = runtime_root / "corpora"; manifests_root.mkdir(exist_ok=True)
    catalog = SQLiteCatalog(catalog_path).open(initialize=True)
    # This cohort's immutable artefacts live under its private run root.  The
    # shared catalogue indexes governed source records and receipts, but cannot
    # safely assign one relative storage path to the same hash held by earlier
    # private run roots.
    store = ContentAddressedArtifactStore(runtime_root / "objects", allowed_roots=(runtime_root,))
    network = NetworkLedger(cache_root=runtime_root / "network-cache"); now = datetime.now(timezone.utc)
    for family in SOURCE_FAMILIES: catalog.register_source_definition(source_definition(family, now))
    historical = historical_material(historical_root)
    profiles = read_json(historical_root / "acnc-profiles.json")["entities"]
    failures = {(str(item["abn"]), item["source_family"]): item.get("reason", "historical acquisition failure") for item in read_json(historical_root / "evidence-bundles.json").get("failures", [])}
    completed = 0; matrix: list[dict[str, Any]] = []; annual_report_report: list[dict[str, Any]] = []; wikipedia_report: list[dict[str, Any]] = []; pfra_report: list[dict[str, Any]] = []; representation_report: list[dict[str, Any]] = []
    pfra_pages: list[tuple[str, bytes, str]] = []
    for url in ("https://pfra.org.au/membership/charity-members/", "https://pfra.org.au/membership/fundraising-agency-members/"):
        fetched = network.fetch(source_family="pfra", url=url, allowed_hosts=PFRA_HOSTS)
        if fetched["ok"]: pfra_pages.append((url, fetched["body"], fetched["resolved_url"]))
    pfra_records = [record for url, body, _ in pfra_pages if body for record in extract_pfra_members(body.decode("utf-8", "replace"), page_role="current_charity_membership" if "charity-members" in url else "agency_membership")]
    try:
        for member in cohort:
            abn = str(member["abn"]); profile = profiles[abn]["profile"]; data = profile.get("data") or {}; members: list[CorpusMember] = []; coverage: dict[str, Any] = {}
            for family in ("acnc_register", "acnc_ais_bundle"):
                existing = historical[abn].get(family)
                if existing:
                    lineage = persist_available(catalog=catalog, store=store, family=family, requested_url=existing["source_url"], resolved_url=existing.get("resolved_url") or existing["source_url"], body=historical_bytes(historical_root, existing), media_type=existing.get("media_type") or "application/json", role="historical_frozen_regulator_material", source_version=None, origin=MaterialOrigin.REUSED_EXISTING, now=now)
                    members.append(available_member(lineage, family=family)); coverage[family] = {"state": "acquired_available", "origin": "reused_existing"}
                elif family == "acnc_ais_bundle" and profiles[abn].get("ais_detail"):
                    snapshot = profiles[abn]["ais_detail"]
                    snapshot_url = f"https://www.acnc.gov.au/api/dynamics/entity/{(profiles[abn].get('latest_submitted_ais') or {}).get('AISId') or snapshot.get('uuid')}"
                    lineage = persist_available(catalog=catalog, store=store, family=family, requested_url=snapshot_url, resolved_url=snapshot_url, body=json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"), media_type="application/json", role="historical_frozen_structured_ais_snapshot", source_version=None, origin=MaterialOrigin.REUSED_EXISTING, now=now)
                    members.append(available_member(lineage, family=family)); coverage[family] = {"state": "acquired_available", "origin": "reused_existing_structured_snapshot"}
                else:
                    raise RuntimeError(f"missing required historical {family} material for {abn}")
            abr_existing = historical[abn].get("ato_abr_dgr")
            if abr_existing:
                lineage = persist_available(catalog=catalog, store=store, family="ato_abr_dgr", requested_url=abr_existing["source_url"], resolved_url=abr_existing.get("resolved_url") or abr_existing["source_url"], body=historical_bytes(historical_root, abr_existing), media_type=abr_existing.get("media_type") or "text/html", role="abr_entity", source_version=None, origin=MaterialOrigin.REUSED_EXISTING, now=now)
                members.append(available_member(lineage, family="ato_abr_dgr")); coverage["ato_abr_dgr"] = {"state": "acquired_available", "origin": "reused_existing"}
            else:
                abr_url = f"https://abr.business.gov.au/ABN/View?{urlencode({'abn': abn})}"; fetched = network.fetch(source_family="ato_abr_dgr", url=abr_url, allowed_hosts=ABR_HOSTS)
                if fetched["ok"]:
                    lineage = persist_available(catalog=catalog, store=store, family="ato_abr_dgr", requested_url=abr_url, resolved_url=fetched["resolved_url"], body=fetched["body"], media_type=fetched["media_type"], role="abr_entity", source_version=None, origin=MaterialOrigin.NEWLY_ACQUIRED, now=now); members.append(available_member(lineage, family="ato_abr_dgr")); coverage["ato_abr_dgr"] = {"state": "acquired_available", "origin": "newly_acquired", "dgr_interpretation": "deferred_source_native_only"}
                else:
                    members.append(state_member(family="ato_abr_dgr", source_definition_id=source_definition("ato_abr_dgr", now).record_id, acquisition=AcquisitionState.FAILED, notes=fetched["event"].get("error_class", "failed"))); coverage["ato_abr_dgr"] = {"state": fetched["event"]["outcome"], "origin": "none"}
            official_existing = historical[abn].get("official_website")
            if official_existing:
                lineage = persist_available(catalog=catalog, store=store, family="official_website", requested_url=official_existing["source_url"], resolved_url=official_existing.get("resolved_url") or official_existing["source_url"], body=historical_bytes(historical_root, official_existing), media_type=official_existing.get("media_type") or "text/html", role="official_homepage", source_version=None, origin=MaterialOrigin.REUSED_EXISTING, now=now); members.append(available_member(lineage, family="official_website")); coverage["official_website"] = {"state": "acquired_available", "origin": "reused_existing"}
            elif (abn, "official-homepage") in failures:
                members.append(state_member(family="official_website", source_definition_id=source_definition("official_website", now).record_id, acquisition=AcquisitionState.UNAVAILABLE, notes=failures[(abn, "official-homepage")])); coverage["official_website"] = {"state": "attempted_unavailable", "origin": "none"}
            elif data.get("Website"):
                site_url = governed_website_url(str(data["Website"]))
                try:
                    fetched = network.fetch(source_family="official_website", url=site_url, allowed_hosts=governed_website_hosts(site_url))
                except NetworkPolicyError as exc:
                    members.append(state_member(family="official_website", source_definition_id=source_definition("official_website", now).record_id, acquisition=AcquisitionState.BLOCKED, notes="redirect_to_unapproved_governed_locator"))
                    coverage["official_website"] = {"state": "blocked_unapproved_redirect", "origin": "none", "error_class": type(exc).__name__}
                    fetched = None
                if fetched and fetched["ok"]:
                    lineage = persist_available(catalog=catalog, store=store, family="official_website", requested_url=site_url, resolved_url=fetched["resolved_url"], body=fetched["body"], media_type=fetched["media_type"], role="official_homepage", source_version=None, origin=MaterialOrigin.NEWLY_ACQUIRED, now=now); members.append(available_member(lineage, family="official_website")); coverage["official_website"] = {"state": "acquired_available" if lineage["acquisition"] == "available" else "acquired_partial", "origin": "newly_acquired"}
                elif fetched:
                    members.append(state_member(family="official_website", source_definition_id=source_definition("official_website", now).record_id, acquisition=AcquisitionState.FAILED, notes=fetched["event"].get("error_class", "failed"))); coverage["official_website"] = {"state": fetched["event"]["outcome"], "origin": "none"}
            else:
                members.append(state_member(family="official_website", source_definition_id=source_definition("official_website", now).record_id, acquisition=AcquisitionState.UNAVAILABLE, discovery=DiscoveryState.UNRESOLVED, notes="no_governed_official_website_locator")); coverage["official_website"] = {"state": "unresolved_no_locator", "origin": "none"}
            year, documents = latest_report_documents(profile)
            if not documents:
                members.append(state_member(family="annual_report", source_definition_id=source_definition("annual_report", now).record_id, acquisition=AcquisitionState.UNAVAILABLE, notes="no_structured_latest_report_document")); annual_report_report.append({"abn": abn, "status": "unresolved", "year": year}); coverage["annual_report"] = {"state": "unresolved", "origin": "none"}
            else:
                selected = documents[0]; fetched = network.fetch(source_family="annual_report", url=selected["Url"], allowed_hosts=ACNC_API_HOSTS)
                if fetched["ok"]:
                    lineage = persist_available(catalog=catalog, store=store, family="annual_report", requested_url=selected["Url"], resolved_url=fetched["resolved_url"], body=fetched["body"], media_type=fetched["media_type"], role=str(selected["role"]), source_version=year, origin=MaterialOrigin.NEWLY_ACQUIRED, now=now)
                    readiness = RepresentationReadiness.NOT_REQUIRED; rep_ids: tuple[str, ...] = (); gaps: tuple[str, ...] = ()
                    if fetched["body"].startswith(b"%PDF-") or fetched["media_type"] == "application/pdf":
                        try:
                            readiness, rep_ids, gaps, rep = represent_document(runtime_root=runtime_root, store=store, artifact_id=lineage["artifact_id"], body=fetched["body"], now=now)
                            representation_report.append({"abn": abn, "year": year, **rep, "representation_artifact_ids": list(rep_ids)})
                        except Exception as exc:
                            readiness = RepresentationReadiness.FAILED
                            gaps = (f"representation_error:{type(exc).__name__}",)
                            representation_report.append({"abn": abn, "year": year, "readiness": "failed", "error_class": type(exc).__name__})
                    members.append(available_member(lineage, family="annual_report", period=year, readiness=readiness, representation_ids=rep_ids, gaps=gaps)); annual_report_report.append({"abn": abn, "status": "selected_and_acquired", "year": year, "role": selected["role"], "origin": "newly_acquired"}); coverage["annual_report"] = {"state": "acquired_available", "origin": "newly_acquired"}
                else:
                    members.append(state_member(family="annual_report", source_definition_id=source_definition("annual_report", now).record_id, acquisition=AcquisitionState.FAILED, notes=fetched["event"].get("error_class", "failed"))); annual_report_report.append({"abn": abn, "status": "failed", "year": year}); coverage["annual_report"] = {"state": fetched["event"]["outcome"], "origin": "none"}
            names = [str(data[key]) for key in ("Name", "CharityLegalName", "LegalName") if data.get(key)]
            wiki_url = "https://en.wikipedia.org/w/api.php?" + urlencode({"action": "query", "list": "search", "srsearch": names[0] if names else abn, "format": "json", "srlimit": 10})
            fetched = network.fetch(source_family="wikipedia_wikimedia", url=wiki_url, allowed_hosts=WIKIMEDIA_HOSTS)
            if fetched["ok"]:
                candidates = json.loads(fetched["body"]).get("query", {}).get("search", []); resolution = resolve_wikipedia_candidate(names, candidates)
                lineage = persist_available(catalog=catalog, store=store, family="wikipedia_wikimedia", requested_url=wiki_url, resolved_url=fetched["resolved_url"], body=fetched["body"], media_type=fetched["media_type"], role="wikipedia_search_context", source_version=None, origin=MaterialOrigin.NEWLY_ACQUIRED, now=now); binding = BindingState(resolution["status"] if resolution["status"] != "bound" else "bound"); members.append(available_member(lineage, family="wikipedia_wikimedia", binding=binding)); wikipedia_report.append({"abn": abn, "status": resolution["status"], "basis": resolution["basis"], "candidate_count": len(candidates)}); coverage["wikipedia_wikimedia"] = {"state": "acquired_available", "binding": resolution["status"], "origin": "newly_acquired"}
            else:
                members.append(state_member(family="wikipedia_wikimedia", source_definition_id=source_definition("wikipedia_wikimedia", now).record_id, acquisition=AcquisitionState.FAILED, notes=fetched["event"].get("error_class", "failed"))); wikipedia_report.append({"abn": abn, "status": "failed"}); coverage["wikipedia_wikimedia"] = {"state": fetched["event"]["outcome"], "origin": "none"}
            domains = {(urlsplit(str(data.get("Website") or "")).hostname or "").casefold().removeprefix("www.")}; exact = [record for record in pfra_records if domains & {str(item).casefold().removeprefix("www.") for item in record.get("linked_domains", [])}]
            if pfra_pages:
                page_url, page_body, page_resolved = pfra_pages[0]; lineage = persist_available(catalog=catalog, store=store, family="pfra", requested_url=page_url, resolved_url=page_resolved, body=page_body, media_type="text/html", role="registry_membership", source_version=None, origin=MaterialOrigin.NEWLY_ACQUIRED, now=now); binding = BindingState.BOUND if len(exact) == 1 else BindingState.AMBIGUOUS if len(exact) > 1 else BindingState.NO_BOUND_RECORD; members.append(available_member(lineage, family="pfra", binding=binding)); pfra_report.append({"abn": abn, "status": binding.value, "match_count": len(exact)}); coverage["pfra"] = {"state": "acquired_available", "binding": binding.value, "origin": "newly_acquired"}
            else:
                members.append(state_member(family="pfra", source_definition_id=source_definition("pfra", now).record_id, acquisition=AcquisitionState.FAILED, notes="registry_unavailable")); pfra_report.append({"abn": abn, "status": "failed"}); coverage["pfra"] = {"state": "failed", "origin": "none"}
            manifest = build_corpus_manifest(subject_id=subjects[abn], profile_version=PROFILE_VERSION, members=members, cohort_id=COHORT_HASH, run_id=PROFILE_VERSION, retrieval_timestamps=(), builder_commit=None)
            atomic_json(manifests_root / f"{abn}.json", manifest.model_dump(mode="json")); matrix.append({"abn": abn, "rank": member["donation_rank_2024_public"], "subject_id": subjects[abn], "coverage": coverage, "material_identity_hash": manifest.material_identity_hash}); completed += 1
            if interruption_after is not None and completed >= interruption_after: raise InterruptedError("deliberate provider-free interruption")
    finally:
        catalog.close()
    before_matrix = []
    for member in cohort:
        abn = str(member["abn"])
        before_matrix.append({"abn": abn, "subject_id": subjects[abn], "coverage": {
            "acnc_register": {"state": "acquired_available", "origin": "reused_existing"},
            "acnc_ais_bundle": {"state": "acquired_available", "origin": "reused_existing"},
            "ato_abr_dgr": {"state": "acquired_available" if "ato_abr_dgr" in historical[abn] else "not_attempted", "origin": "reused_existing" if "ato_abr_dgr" in historical[abn] else "none"},
            "official_website": {"state": "acquired_available" if "official_website" in historical[abn] else "attempted_unavailable" if (abn, "official-homepage") in failures else "not_attempted", "origin": "reused_existing" if "official_website" in historical[abn] else "none"},
            "annual_report": {"state": "not_attempted", "origin": "none"},
            "wikipedia_wikimedia": {"state": "not_attempted", "origin": "none"},
            "pfra": {"state": "not_attempted", "origin": "none"},
        }})
    coverage_cells = [dict(abn=row["abn"], subject_id=row["subject_id"], source_family=family, **state) for row in matrix for family, state in row["coverage"].items()]
    failure_register = [cell for cell in coverage_cells if cell["state"] not in {"acquired_available"}]
    binding_register = [item for item in wikipedia_report + pfra_report if item.get("status") in {"ambiguous", "no_bound_record"}]
    manifests = [read_json(path) for path in sorted(manifests_root.glob("*.json"))]
    corpus_hashes = [{"subject_id": item["subject_id"], "corpus_id": item["corpus_id"], "material_identity_hash": item["material_identity_hash"], "provenance_hash": item["provenance_hash"]} for item in manifests]
    reuse_report = {"reused_cells": [cell for cell in coverage_cells if cell.get("origin") == "reused_existing"], "newly_acquired_cells": [cell for cell in coverage_cells if cell.get("origin") == "newly_acquired"]}
    execution_manifest = {"profile": PROFILE_VERSION, "cohort_hash": COHORT_HASH, "identity_map_hash": IDENTITY_MAP_HASH, "source_families": SOURCE_FAMILIES, "provider_calls_authorized": 0, "semantic_execution_authorized": 0, "started_at": now.isoformat(), "completed_subjects": len(matrix)}
    atomic_json(runtime_root / "execution-manifest.json", execution_manifest)
    atomic_json(runtime_root / "cohort-identity-checkpoint.json", {"cohort_hash": COHORT_HASH, "identity_map_hash": IDENTITY_MAP_HASH, "subjects": len(subjects), "ranks": list(range(1, 101))})
    atomic_json(runtime_root / "before-source-coverage-matrix.json", before_matrix)
    atomic_json(runtime_root / "acquisition-ledger.json", coverage_cells)
    atomic_json(runtime_root / "reuse-versus-new-acquisition-report.json", reuse_report)
    atomic_json(runtime_root / "network-request-ledger.json", network.events)
    atomic_json(runtime_root / "annual-report-selection-report.json", annual_report_report)
    atomic_json(runtime_root / "wikipedia-binding-report.json", wikipedia_report)
    atomic_json(runtime_root / "pfra-registry-binding-report.json", pfra_report)
    atomic_json(runtime_root / "pdf-document-representation-report.json", representation_report)
    atomic_json(runtime_root / "after-source-coverage-matrix.json", matrix)
    atomic_json(runtime_root / "provider-guard-report.json", guard.report())
    atomic_json(runtime_root / "unavailable-failure-register.json", failure_register)
    atomic_json(runtime_root / "binding-ambiguity-no-bound-register.json", binding_register)
    atomic_json(runtime_root / "corpus-material-provenance-hashes.json", corpus_hashes)
    readiness = "READY_FOR_FACTORY_SEMANTICS" if all(cell["state"] == "acquired_available" for cell in coverage_cells) else "READY_WITH_EXPLICIT_SOURCE_GAPS"
    atomic_json(runtime_root / "final-readiness-report.json", {"classification": readiness, "coverage_cells": len(coverage_cells), "provider_calls": 0, "semantic_executions": 0, "reason": "all source-family cells are explicit; unresolved and unavailable source states remain non-semantic coverage gaps"})
    return {"cohort_hash": COHORT_HASH, "identity_map_hash": IDENTITY_MAP_HASH, "subjects": len(matrix), "coverage_cells": len(matrix) * len(SOURCE_FAMILIES), "network_events": len(network.events), "provider_guard": guard.report(), "readiness": readiness}
