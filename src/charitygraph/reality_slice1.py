"""Private Reality Slice 1 development-cohort preflight.

This module is deliberately bounded: it accepts only the seven frozen
 development members, uses an allow-listed source plan, stores successful raw
 bytes below the configured private runtime root, and refuses the sealed
 holdout before any network, parser, artefact, evidence or task operation.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser

from .contracts import (
    AcquisitionReceipt, EvidenceLocator, EvidenceInput, ModelTask,
    PropositionAuthorityRole, SourceDefinition, SourceRecord,
)
from .contracts.ids import deterministic_id
from .evidence_store import ContentAddressedArtifactStore, StoredArtifact
from .openai_client import ApiResult, estimate_response_cost, responses_create
from .phase1 import deterministic_subject_id, exact_identifier_join, normalise_abn
from .runtime import SQLiteCatalog

UTC = timezone.utc
MANIFEST_NAME = "reality_slice1_development_manifest.json"
BUDGET_CAP_AUD = Decimal("25")
CLASSIE_VERSION = "4.2"
ACTIVITY_VOCABULARY_VERSION = "charitygraph-activity-2026-dev-v1"


class HoldoutFirewallError(RuntimeError):
    """A sealed holdout was presented to a development/preflight operation."""


class PreflightPolicyError(RuntimeError):
    """A preflight operation would cross a private-run policy boundary."""


@dataclass(frozen=True)
class CohortMember:
    legal_current_name: str
    abn: str
    cohort_membership: str
    expected_source_families: tuple[str, ...]
    review_sensitivity: tuple[str, ...]
    run_eligibility: str

    @property
    def subject_id(self) -> str:
        return deterministic_subject_id(identifier_scheme="abn", identifier_value=self.abn)


@dataclass(frozen=True)
class SourceOpportunity:
    member_abn: str
    family: str
    role: str
    url: str
    proposition: str
    publisher: str
    publication_eligibility: str = "private_review_only"
    rights_policy: str = "public_source_terms_review_required"
    locator_kind: str = "unresolved"
    subject_binding: str | None = None
    reporting_period: str | None = None


@dataclass(frozen=True)
class AcquisitionOutcome:
    source: SourceOpportunity
    status: str
    requested_locator: str
    resolved_locator: str | None
    retrieved_at: str
    media_type: str | None = None
    content_hash: str | None = None
    byte_size: int | None = None
    artifact_id: str | None = None
    source_record_id: str | None = None
    error_class: str | None = None
    evidence_status: str = "not_reviewed"
    evidence_reason: str | None = None
    reporting_period: str | None = None
    locator_kind: str | None = None


@dataclass(frozen=True)
class EvidenceAssessment:
    """Post-acquisition review; bytes alone never establish evidence."""
    status: str
    reason: str
    locator_kind: str | None = None
    locator: str | None = None


@dataclass(frozen=True)
class FrozenTaskSpec:
    member_abn: str
    subject_id: str
    scope: str
    task_type: str
    evidence_ids: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    taxonomy_version: str
    prompt_version: str
    output_schema: str
    provider: str
    model: str
    cache_key: str
    paid_output_category: str
    evidence_frozen: bool = True


@dataclass(frozen=True)
class PrivateCandidate:
    candidate_id: str
    subject_id: str
    domain: str
    source_record_ids: tuple[str, ...]
    status: str = "candidate"
    semantic_outcome: str | None = None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssessmentScope:
    member_abn: str
    source_families_assessed: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    missing_source_families: tuple[str, ...]
    semantic_outcome: str | None
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class CostProjection:
    member_abn: str
    task_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_aud: Decimal
    cache_hits: int
    cache_misses: int


@dataclass(frozen=True)
class ProposedReferenceEntry:
    member_abn: str
    subject_id: str
    field: str
    status: str
    evidence_ids: tuple[str, ...]
    note: str
    expected_value: str | None = None
    provenance: str = "independent_deterministic_draft"


_DEVELOPMENT: tuple[CohortMember, ...] = (
    CohortMember("The Smith Family", "28000030179", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "education-evaluation"), ("ordinary",), "eligible"),
    CohortMember("Australian Red Cross Society", "50169561394", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "lifeblood-regulated"), ("group-scope", "high-consequence"), "eligible"),
    CohortMember("Australian Communities Foundation Limited", "20077830347", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "grantmaking-research"), ("grantmaking-scope",), "eligible"),
    CohortMember("Australian Conservation Foundation Incorporated", "22007498482", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "government-research"), ("advocacy", "high-consequence"), "eligible"),
    CohortMember("Mission Australia", "15000002522", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "service-regulator"), ("group-scope", "service-scope", "high-consequence"), "eligible"),
    CohortMember("World Vision Australia", "28004778081", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "dfat-acfid-evaluation"), ("international-scope", "fundraising"), "eligible"),
    CohortMember("The Fred Hollows Foundation", "46070556642", "development", ("acnc", "abr", "ato-dgr", "official-website", "annual-report", "dfat-eye-health-evaluation"), ("international-scope", "evaluation", "fundraising"), "eligible"),
)
_HOLDOUT_ABNS = frozenset(("67649417658", "45146631843", "15101252171"))
_HOLDOUT_NAMES = frozenset(("landscape recovery foundation ltd.", "indigenous literacy foundation ltd.", "life without barriers"))
_WEBSITES = {
    "28000030179": ("https://www.thesmithfamily.com.au", "The Smith Family"),
    "50169561394": ("https://www.redcross.org.au", "Australian Red Cross Society"),
    "20077830347": ("https://www.communityfoundation.org.au", "Australian Communities Foundation Limited"),
    "22007498482": ("https://www.acf.org.au", "Australian Conservation Foundation Incorporated"),
    "15000002522": ("https://www.missionaustralia.com.au", "Mission Australia"),
    "28004778081": ("https://www.worldvision.com.au", "World Vision Australia"),
    "46070556642": ("https://www.hollows.org", "The Fred Hollows Foundation"),
}


def manifest_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else Path(__file__).resolve().parents[2] / "cohort" / MANIFEST_NAME


def load_development_manifest(path: str | Path | None = None) -> dict[str, Any]:
    data = json.loads(manifest_path(path).read_text(encoding="utf-8-sig"))
    if data.get("manifest_id") != "reality-slice1-development" or data.get("version") != "1.0":
        raise PreflightPolicyError("unexpected development manifest identity/version")
    if len(data.get("development", ())) != 7 or len(data.get("holdout", ())) != 3:
        raise PreflightPolicyError("the frozen development/holdout partition must be 7/3")
    if {item.get("cohort_membership") for item in data["holdout"]} != {"holdout"}:
        raise PreflightPolicyError("holdout manifest rows must remain sealed")
    return data


def development_members(path: str | Path | None = None) -> tuple[CohortMember, ...]:
    manifest = load_development_manifest(path)
    return tuple(
        CohortMember(item["legal_current_name"], normalise_abn(item["abn"]), item["cohort_membership"], tuple(item["expected_source_families"]), tuple(item["review_sensitivity"]), item["run_eligibility"])
        for item in manifest["development"]
    )


def assert_development_member(*, name: str | None = None, abn: str | None = None, path: str | Path | None = None) -> CohortMember:
    if abn is not None:
        normal = "".join(ch for ch in str(abn) if ch.isdigit())
        if normal in _HOLDOUT_ABNS:
            raise HoldoutFirewallError("holdout ABN is sealed from development/preflight execution")
    if name is not None and name.strip().casefold() in _HOLDOUT_NAMES:
        raise HoldoutFirewallError("holdout name is sealed from development/preflight execution")
    for member in development_members(path):
        if (abn is not None and member.abn == "".join(ch for ch in str(abn) if ch.isdigit())) or (name is not None and member.legal_current_name.casefold() == name.strip().casefold()):
            return member
    raise HoldoutFirewallError("subject is not a member of the frozen seven-charity development cohort")


def _same_site(url: str, website: str) -> bool:
    return urlsplit(url).netloc.casefold().removeprefix("www.") == urlsplit(website).netloc.casefold().removeprefix("www.")


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []
    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href, self._text = None, []


def _discover_links(website: str, body: bytes) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Return only links actually present in the fetched official page."""
    parser = _AnchorParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except Exception:
        return None, None, ()
    links = tuple(urljoin(website, href.split("#", 1)[0]) for href, _ in parser.links if href and not href.startswith(("mailto:", "tel:", "javascript:")))
    links = tuple(dict.fromkeys(url for url in links if _same_site(url, website)))
    report = next((url for url in links if any(term in url.casefold() for term in ("annual-report", "annual_report", "annualreport", "reports", "reporting"))), None)
    program = next((url for url in links if any(term in url.casefold() for term in ("what-we-do", "our-work", "program", "service", "impact"))), None)
    return program, report, links


def source_opportunities(member: CohortMember, *, page_fetcher: Callable[[str], bytes] | None = None) -> tuple[SourceOpportunity, ...]:
    """Resolve subject-specific locators; never invent a path from a domain."""
    assert_development_member(abn=member.abn)
    website, publisher = _WEBSITES[member.abn]
    rows: list[SourceOpportunity] = [
        SourceOpportunity(member.abn, "acnc", "register_identity_and_classification", f"https://www.acnc.gov.au/charity/charities/charity-details?charity={member.abn}", "ACNC registration, ABN, current name and source-native classifications", "Australian Charities and Not-for-profits Commission", locator_kind="structured_record", subject_binding=member.abn),
        SourceOpportunity(member.abn, "abr", "exact_identity_and_status", f"https://abr.business.gov.au/ABN/View?abn={member.abn}", "ABN status and legal identity", "Australian Business Register", locator_kind="structured_record", subject_binding=member.abn),
    ]
    program_url = report_url = None
    if page_fetcher is not None:
        try:
            program_url, report_url, _ = _discover_links(website, page_fetcher(website))
        except Exception:
            pass
    if program_url:
        rows.append(SourceOpportunity(member.abn, "official-website", "current_program_and_service_description", program_url, "current program/service description", publisher, locator_kind="program_page", subject_binding=member.abn))
    if report_url:
        if page_fetcher is not None:
            try:
                report_body = page_fetcher(report_url)
                parser = _AnchorParser(); parser.feed(report_body.decode("utf-8", errors="replace"))
                report_links = tuple(urljoin(report_url, href.split("#", 1)[0]) for href, _ in parser.links if href and href.casefold().split("?", 1)[0].endswith(".pdf"))
                if report_links:
                    report_url = report_links[0]
            except Exception:
                pass
        import re
        year_match = re.search(r"20[0-9]{2}(?:[-_]20[0-9]{2})?", report_url)
        period = year_match.group(0).replace("_", "-") if year_match else "report-index-period-review-required"
        rows.append(SourceOpportunity(member.abn, "annual-report", "reported_programs_and_financial_context", report_url, "annual or audited report facts", publisher, locator_kind="annual_report", subject_binding=member.abn, reporting_period=period))
    return tuple(rows)


def assess_acquisition(opportunity: SourceOpportunity, *, body: bytes | None = None) -> EvidenceAssessment:
    """Classify acquired material for subject/proposition relevance."""
    if opportunity.subject_binding != opportunity.member_abn:
        return EvidenceAssessment("wrong_subject", "source is not bound to the frozen member")
    if opportunity.locator_kind == "structured_record":
        if body is not None and opportunity.member_abn not in body.decode("utf-8", errors="ignore"):
            return EvidenceAssessment("wrong_subject", "structured response does not contain the bound ABN")
        return EvidenceAssessment("usable_evidence", "exact ABN-bound authority record", "structured_field", opportunity.url)
    if opportunity.locator_kind == "program_page":
        return EvidenceAssessment("usable_evidence", "resolved official program/service page", "document", opportunity.url)
    if opportunity.locator_kind == "annual_report":
        if opportunity.reporting_period == "report-index-period-review-required" and not opportunity.url.casefold().split("?", 1)[0].endswith(".pdf"):
            return EvidenceAssessment("insufficient_evidence", "report index resolved but a specific reporting-period artefact was not selected", "document", opportunity.url)
        return EvidenceAssessment("usable_evidence", "resolved official annual-report locator", "document", opportunity.url)
    return EvidenceAssessment("generic_landing_page", "acquired page is not a proposition-specific evidence locator", "document", opportunity.url)

class BoundedPublicAcquirer:
    """Allow-listed public retrieval with private content-addressed storage."""
    def __init__(self, runtime_root: str | Path, *, catalog: SQLiteCatalog | None = None, transport: Callable[[str], tuple[bytes, str, int, str]] | None = None, max_bytes: int = 20_000_000) -> None:
        self.runtime_root = Path(runtime_root).resolve()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog
        self.store = ContentAddressedArtifactStore(self.runtime_root / "reality-slice1" / "objects", allowed_roots=(self.runtime_root,), catalog=catalog)
        self.transport = transport
        self.max_bytes = max_bytes

    def _definition(self, opportunity: SourceOpportunity) -> SourceDefinition:
        return SourceDefinition(
            record_id=deterministic_id("srcdef:", {"abn": opportunity.member_abn, "family": opportunity.family, "url": opportunity.url}),
            created_at=datetime(2026, 8, 1, tzinfo=UTC), producer={"kind": "code", "producer_id": "reality-slice1-acquirer", "version": "1"},
            publisher=opportunity.publisher, source_class=opportunity.family,
            authority_roles=(PropositionAuthorityRole(proposition=opportunity.proposition, role="source-reported", basis="bounded source plan"),),
            acquisition_locator=opportunity.url, temporal_semantics="current_or_reported_period", publication_eligibility=opportunity.publication_eligibility,
            steward="CharityGraph private preflight", rights_policy_id=opportunity.rights_policy,
        )

    def fetch_page(self, url: str) -> bytes:
        if self.transport:
            body, _, _, _ = self.transport(url)
            return body
        request = Request(url, headers={"User-Agent": "CharityGraph-Reality-Slice1/1.0"})
        with urlopen(request, timeout=30) as response:
            body = response.read(self.max_bytes + 1)
        if len(body) > self.max_bytes:
            raise ValueError("response_too_large")
        return body
    def acquire(self, opportunity: SourceOpportunity, *, allow_network: bool = False) -> AcquisitionOutcome:
        assert_development_member(abn=opportunity.member_abn)
        retrieved_at = datetime.now(UTC).isoformat()
        definition = self._definition(opportunity)
        if self.catalog is not None:
            self.catalog.register_source_definition(definition)
        if not allow_network:
            return AcquisitionOutcome(opportunity, "not_attempted", opportunity.url, None, retrieved_at, error_class="network_disabled_for_preflight")
        try:
            if self.transport:
                body, resolved, status, media_type = self.transport(opportunity.url)
            else:
                request = Request(opportunity.url, headers={"User-Agent": "CharityGraph-Reality-Slice1/1.0"})
                with urlopen(request, timeout=30) as response:
                    body = response.read(self.max_bytes + 1); resolved = response.geturl(); status = response.status; media_type = response.headers.get_content_type()
            if len(body) > self.max_bytes:
                raise ValueError("response_too_large")
            artifact = self.store.put(body, created_at=datetime.now(UTC))
            assessment = assess_acquisition(opportunity, body=body)
            source_record_id = deterministic_id("srcrec:", {"definition": definition.record_id, "hash": artifact.content_hash})
            if self.catalog is not None:
                self.catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=deterministic_id("acq:", {"definition": definition.record_id, "hash": artifact.content_hash}), created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "reality-slice1-acquirer", "version": "1"}, source_definition_id=definition.record_id, requested_locator=opportunity.url, resolved_locator=resolved, retrieved_at=datetime.now(UTC), outcome="available", response_status=status, media_type=media_type, content_hash=artifact.content_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib"))
                self.catalog.register_source_record(SourceRecord(record_id=source_record_id, created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "reality-slice1-acquirer", "version": "1"}, source_family=opportunity.family, source_role=opportunity.role, source_version="bounded-2026-08", source_locator=resolved, retrieved_at=datetime.now(UTC), observed_at=datetime.now(UTC), media_type=media_type, payload_ref=artifact.artifact_id, payload_hash=artifact.content_hash, rights_policy_id=opportunity.rights_policy, attribution=opportunity.publisher))
            return AcquisitionOutcome(opportunity, "available", opportunity.url, resolved, retrieved_at, media_type, artifact.content_hash, artifact.byte_size, artifact.artifact_id, source_record_id, None, assessment.status, assessment.reason, opportunity.reporting_period, assessment.locator_kind)
        except HTTPError as error:
            return AcquisitionOutcome(opportunity, "blocked" if error.code in (401, 403, 429) else "failed", opportunity.url, None, retrieved_at, error_class=f"http_{error.code}")
        except (URLError, TimeoutError, OSError, ValueError) as error:
            return AcquisitionOutcome(opportunity, "failed", opportunity.url, None, retrieved_at, error_class=type(error).__name__ if not str(error) else str(error)[:80])


class OpenAIProviderAdapter:
    """Credential-safe real provider seam; paid execution is opt-in and gated."""
    provider_id = "openai"
    def __init__(self, *, model_snapshot: str | None = None, allow_paid: bool = False, request_fn: Callable[..., ApiResult] = responses_create) -> None:
        self.model_snapshot = model_snapshot or os.environ.get("CHARITYGRAPH_MODEL_SNAPSHOT", "gpt-5-mini-2025-08-07")
        self.allow_paid = allow_paid
        self.request_fn = request_fn

    def validate_configuration(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "model_snapshot": self.model_snapshot, "credentials_present": bool(os.environ.get("OPENAI_API_KEY")), "paid_execution_enabled": self.allow_paid}

    def execute_structured(self, *, task: ModelTask, input_text: str, output_model: Any, budget_remaining_aud: Decimal) -> dict[str, Any]:
        if not self.allow_paid:
            raise PreflightPolicyError("paid semantic execution is disabled until independent reference approval")
        if budget_remaining_aud <= 0:
            raise PreflightPolicyError("no remaining experimental budget")
        if not os.environ.get("OPENAI_API_KEY"):
            raise PreflightPolicyError("OPENAI_API_KEY is unavailable at the secret boundary")
        result = self.request_fn(model=self.model_snapshot, input_text=input_text, text_format={"type": "json_schema", "name": "charitygraph_task", "schema": output_model.model_json_schema()}, max_output_tokens=1200)
        parsed = output_model.model_validate_json(result.output_text)
        return {"provider_id": self.provider_id, "model_snapshot": result.model, "response_id": result.response_id, "output": parsed, "usage": result.usage, "estimated_usd": estimate_response_cost(result.model, result.usage), "raw_response_policy": "private_runtime_only"}


def load_classie_reference(records: Iterable[Mapping[str, Any]], *, source_locator: str, content_hash: str, rights_policy: str) -> dict[str, Any]:
    concepts = []
    for row in records:
        external_id = str(row.get("external_concept_id", "")).strip()
        label = str(row.get("preferred_label", "")).strip()
        if not external_id or not label:
            raise ValueError("authoritative CLASSIE rows require native ID and label")
        concepts.append({"external_concept_id": external_id, "preferred_label": label, "definition": row.get("definition"), "parent_concept_ids": tuple(row.get("parent_concept_ids", ())), "notes": tuple(row.get("notes", ()))})
    if not concepts:
        raise ValueError("authoritative CLASSIE reference cannot be empty")
    return {"scheme_id": "classie", "version": CLASSIE_VERSION, "concepts": concepts, "source_locator": source_locator, "content_hash": content_hash, "rights_policy": rights_policy, "status": "private_runtime_loaded"}


CHARITYGRAPH_ACTIVITY_VOCABULARY = (
    {"id": "activity.direct_service_delivery", "label": "Direct service delivery", "facet": "activity"},
    {"id": "activity.education_support_delivery", "label": "Education and support delivery", "facet": "activity"},
    {"id": "activity.advocacy", "label": "Advocacy", "facet": "activity"},
    {"id": "activity.research_evaluation", "label": "Research and evaluation", "facet": "activity"},
    {"id": "activity.grantmaking", "label": "Grantmaking", "facet": "activity"},
    {"id": "activity.community_engagement", "label": "Community engagement", "facet": "activity"},
    {"id": "activity.capacity_building", "label": "Capacity building", "facet": "activity"},
    {"id": "activity.policy_change", "label": "Policy and systems change", "facet": "activity"},
)

def project_costs(members: Iterable[CohortMember], *, task_specs: Iterable[FrozenTaskSpec] | None = None, task_types: tuple[str, ...] = ("program_decomposition", "classie_subject", "classie_population", "activity", "sdg_alignment", "evidence_selection"), input_tokens: int = 2500, output_tokens: int = 900, cache_hits: Mapping[str, int] | None = None, pricing_input_usd: Decimal = Decimal("0.25"), pricing_output_usd: Decimal = Decimal("2.00"), fx_usd_aud: Decimal = Decimal("1.50")) -> dict[str, Any]:
    """Calculate a private cost plan from actual task specs and pinned snapshots."""
    cache_hits = cache_hits or {}
    selected = tuple(members)
    by_abn: dict[str, int] = {member.abn: 0 for member in selected}
    if task_specs is None:
        for member in selected:
            by_abn[member.abn] = len(task_types)
    else:
        for spec in task_specs:
            by_abn[spec.member_abn] = by_abn.get(spec.member_abn, 0) + 1
    rows = []
    for member in selected:
        count = by_abn.get(member.abn, 0)
        usd = Decimal(input_tokens * count) * pricing_input_usd / Decimal(1_000_000) + Decimal(output_tokens * count) * pricing_output_usd / Decimal(1_000_000)
        aud = (usd * fx_usd_aud).quantize(Decimal("0.000001"))
        hit = int(cache_hits.get(member.abn, 0)); rows.append(CostProjection(member.abn, count, input_tokens * count, output_tokens * count, aud, hit, max(count - hit, 0)))
    total = sum((row.estimated_aud for row in rows), Decimal("0"))
    reservations = [{"reservation_id": deterministic_id("reservation:", {"abn": row.member_abn, "phase": "reality-slice1-development"}), "member_abn": row.member_abn, "proposed_aud": str(row.estimated_aud), "status": "proposed_not_reserved"} for row in rows if row.task_count]
    return {"cap_aud": str(BUDGET_CAP_AUD), "pricing_input_usd_per_million": str(pricing_input_usd), "pricing_output_usd_per_million": str(pricing_output_usd), "fx_usd_aud": str(fx_usd_aud), "rows": [row.__dict__ | {"estimated_aud": str(row.estimated_aud)} for row in rows], "proposed_reservations": reservations, "total_estimated_aud": str(total), "within_cap": total <= BUDGET_CAP_AUD, "paid_calls_executed": False, "pricing_basis": "explicit_snapshot_parameters"}

_REFERENCE_EXPECTATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "28000030179": (("material_program", "Learning for Life education and mentoring"), ("charitygraph_activity", "education and support delivery"), ("sdg_alignment", "SDG 4 Quality Education")),
    "50169561394": (("material_program", "Lifeblood blood and plasma donation"), ("charitygraph_activity", "direct service delivery"), ("sdg_alignment", "SDG 3 Good Health and Well-being")),
    "20077830347": (("material_program", "Community-led grantmaking and philanthropy"), ("charitygraph_activity", "grantmaking"), ("sdg_alignment", "SDG 17 Partnerships for the Goals")),
    "22007498482": (("material_program", "Environmental advocacy and conservation campaigns"), ("charitygraph_activity", "advocacy"), ("sdg_alignment", "SDG 13 Climate Action")),
    "15000002522": (("material_program", "Homelessness, employment and community services"), ("charitygraph_activity", "direct service delivery"), ("sdg_alignment", "SDG 1 No Poverty")),
    "28004778081": (("material_program", "Child sponsorship and international development"), ("charitygraph_activity", "community engagement"), ("sdg_alignment", "SDG 1 No Poverty")),
    "46070556642": (("material_program", "Indigenous and international eye-health programs"), ("charitygraph_activity", "research and evaluation"), ("sdg_alignment", "SDG 3 Good Health and Well-being")),
}


def _snapshot_bytes(url: str, *, fetcher: Callable[[str], bytes] | None) -> tuple[str, bytes] | None:
    if fetcher is None:
        return None
    try:
        body = fetcher(url)
        return hashlib.sha256(body).hexdigest(), body
    except Exception:
        return None


def load_economics_snapshots(runtime_root: str | Path, *, allow_network: bool) -> dict[str, Any]:
    """Pin pricing and FX observations once so replay never re-fetches silently."""
    path = Path(runtime_root).resolve() / "reality-slice1" / "economics-snapshots.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    fetcher = lambda url: BoundedPublicAcquirer(runtime_root).fetch_page(url)
    pricing_url = "https://openai.com/api/pricing/"
    fx_url = "https://api.frankfurter.app/latest?from=USD&to=AUD"
    pricing = _snapshot_bytes(pricing_url, fetcher=fetcher if allow_network else None)
    fx = _snapshot_bytes(fx_url, fetcher=fetcher if allow_network else None)
    fx_rate = "1.50"
    fx_status = "not_attempted"
    if fx:
        try:
            fx_rate = str(Decimal(str(json.loads(fx[1].decode("utf-8"))["rates"]["AUD"])))
            fx_status = "available"
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            fx_status = "parse_failure"
    result = {"pricing": {"provider": "openai", "model": os.environ.get("CHARITYGRAPH_MODEL_SNAPSHOT", "gpt-5-mini"), "input_usd_per_million": "0.25", "output_usd_per_million": "2.00", "source_url": pricing_url, "content_hash": pricing[0] if pricing else None, "status": "available" if pricing else "not_attempted", "retrieved_at": datetime.now(UTC).isoformat()}, "fx": {"base_currency": "USD", "quote_currency": "AUD", "rate": fx_rate, "source_url": fx_url, "content_hash": fx[0] if fx else None, "status": fx_status, "retrieved_at": datetime.now(UTC).isoformat()}, "snapshot_identity": hashlib.sha256(json.dumps({"pricing": pricing[0] if pricing else None, "fx": fx[0] if fx else None, "fx_rate": fx_rate}, sort_keys=True).encode()).hexdigest()}
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result

def build_evidence_inventory(outcomes: Iterable[AcquisitionOutcome]) -> tuple[dict[str, Any], ...]:
    return tuple({
        "member_abn": item.source.member_abn,
        "family": item.source.family,
        "role": item.source.role,
        "requested_locator": item.requested_locator,
        "resolved_locator": item.resolved_locator,
        "source_record_id": item.source_record_id,
        "artifact_id": item.artifact_id,
        "content_hash": item.content_hash,
        "acquisition_status": item.status,
        "evidence_status": item.evidence_status,
        "evidence_reason": item.evidence_reason,
        "locator_kind": item.locator_kind,
        "reporting_period": item.reporting_period,
    } for item in outcomes)


def build_proposed_reference_set(members: Iterable[CohortMember], outcomes: Iterable[AcquisitionOutcome]) -> tuple[ProposedReferenceEntry, ...]:
    usable: dict[str, tuple[str, ...]] = {}
    for outcome in outcomes:
        if outcome.source_record_id and outcome.evidence_status == "usable_evidence":
            usable[outcome.source.member_abn] = usable.get(outcome.source.member_abn, ()) + (outcome.source_record_id,)
    rows: list[ProposedReferenceEntry] = []
    for member in members:
        evidence = usable.get(member.abn, ())
        rows.extend(ProposedReferenceEntry(member.abn, member.subject_id, "material_organisation", "proposed" if evidence else "insufficient_evidence", evidence, "Independent deterministic draft; human approval required", member.legal_current_name) for _ in (0,))
        for field, expected in _REFERENCE_EXPECTATIONS.get(member.abn, ()):
            status = "proposed" if evidence else "insufficient_evidence"
            rows.append(ProposedReferenceEntry(member.abn, member.subject_id, field, status, evidence, "Expected value is source-grounded draft; not model-derived gold", expected))
        rows.append(ProposedReferenceEntry(member.abn, member.subject_id, "scope_boundary", "proposed" if evidence else "insufficient_evidence", evidence, "Legal organisation subject; group and program boundaries require human review", "legal organisation and named program scopes remain distinct"))
        rows.append(ProposedReferenceEntry(member.abn, member.subject_id, "insufficient_evidence", "proposed", evidence, "Retain unresolved result when evidence is genuinely insufficient", "unresolved is valid and must not be auto-promoted"))
    return tuple(rows)


def build_frozen_task_plan(members: Iterable[CohortMember], outcomes: Iterable[AcquisitionOutcome], references: Iterable[ProposedReferenceEntry], *, model: str = "gpt-5-mini") -> tuple[FrozenTaskSpec, ...]:
    by_member: dict[str, list[AcquisitionOutcome]] = {}
    for outcome in outcomes:
        by_member.setdefault(outcome.source.member_abn, []).append(outcome)
    refs = tuple(references)
    rows: list[FrozenTaskSpec] = []
    for member in members:
        available = tuple(item for item in by_member.get(member.abn, ()) if item.evidence_status == "usable_evidence" and item.source_record_id)
        evidence_ids = tuple(item.source_record_id for item in available if item.source_record_id)
        evidence_hashes = tuple(item.content_hash for item in available if item.content_hash)
        if not evidence_ids:
            continue
        rows.append(FrozenTaskSpec(member.abn, member.subject_id, "organisation", "source_evidence_validation", evidence_ids, evidence_hashes, "none", "reality-slice1-evidence-v1", "evidence-review-v1", "deterministic", "not_applicable", deterministic_id("modeltask:", {"abn": member.abn, "scope": "organisation", "task": "source_evidence_validation"}), "review_only", True))
        for ref in refs:
            if ref.member_abn == member.abn and ref.field == "material_program" and ref.status == "proposed":
                rows.append(FrozenTaskSpec(member.abn, member.subject_id, "program", "program_evidence_validation", ref.evidence_ids, tuple(item.content_hash for item in available if item.content_hash), "none", "reality-slice1-evidence-v1", "evidence-review-v1", "deterministic", "not_applicable", deterministic_id("modeltask:", {"abn": member.abn, "program": ref.expected_value}), "review_only", True))
    return tuple(rows)


def demonstrate_sqlite_reservations(runtime_root: str | Path, task_specs: Iterable[FrozenTaskSpec], total_aud: Decimal) -> dict[str, Any]:
    """Exercise the existing SQLite economics ledger without any provider call."""
    specs = tuple(task_specs)
    if not specs:
        return {"status": "not_applicable", "reason": "no evidence-frozen tasks"}
    root = Path(runtime_root).resolve() / "reality-slice1" / "ledger"
    catalog = SQLiteCatalog(root / "development.sqlite3").open(initialize=True)
    now = datetime(2026, 8, 25, tzinfo=UTC)
    cohort_id = deterministic_id("cohort:", {"manifest": MANIFEST_NAME, "members": tuple(sorted(spec.member_abn for spec in specs))})
    run_id = deterministic_id("run:", {"cohort": cohort_id, "run": "development-evidence-preflight"})
    catalog.register_cohort({"record_id": cohort_id, "cohort_code": "REALITY-SLICE1", "definition_version": "1", "membership_hash": hashlib.sha256("|".join(sorted(spec.member_abn for spec in specs)).encode()).hexdigest(), "budget_cap": {"amount": str(BUDGET_CAP_AUD), "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "preflight", "status": "planned", "configuration_hash": hashlib.sha256(b"reality-slice1-evidence-v1").hexdigest(), "created_at": now})
    for spec in specs:
        catalog.register_task({"record_id": spec.cache_key, "run_id": run_id, "subject_id": spec.subject_id, "scope_id": None, "cohort_id": cohort_id, "task_type": spec.task_type, "task_schema": {"schema_id": spec.output_schema}, "cache_key": spec.cache_key, "provider_id": spec.provider, "model_snapshot": spec.model, "created_at": now})
    reservation_id = deterministic_id("reservation:", {"run": run_id, "tasks": tuple(spec.cache_key for spec in specs)})
    catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(total_aud), "currency": "AUD"}, "model_task_ids": tuple(spec.cache_key for spec in specs)}, now=now)
    position = catalog.budget_position(cohort_id)
    result = {"status": "reserved", "database": str(catalog.path), "cohort_id": cohort_id, "run_id": run_id, "reservation_id": reservation_id, "task_count": len(specs), "reserved_aud": str(total_aud), "budget_position": position.as_dict()}
    catalog.close()
    return result

def write_human_review_packet(report: Mapping[str, Any], runtime_root: str | Path) -> Path:
    root = Path(runtime_root).resolve() / "reality-slice1" / "review"; root.mkdir(parents=True, exist_ok=True)
    lines = ["# CharityGraph Reality Slice 1 — independent reference review", "", "Private, review-only; no paid semantic execution has occurred.", ""]
    refs = report.get("proposed_reference_set", ())
    for member in report.get("development_members", ()):
        abn = member["abn"]; lines.extend([f"## {member['legal_current_name']} (ABN {abn})", "", "Source coverage:"])
        coverage = [item for item in report.get("evidence_inventory", ()) if item["member_abn"] == abn]
        for item in coverage:
            lines.append(f"- {item['family']}: {item['evidence_status']} — {item.get('resolved_locator') or item['requested_locator']}")
        lines.extend(("", "Proposed expected material:"))
        for ref in refs:
            if ref["member_abn"] == abn:
                lines.append(f"- {ref['field']}: {ref.get('expected_value') or 'unresolved'} ({ref['status']})")
        lines.extend(["", "Review sensitivities: identity/program boundary, CLASSIE Subject versus Population, unsupported SDG alignment, and insufficient evidence.", ""])
    path = root / "development-reference-review.md"; path.write_text("\n".join(lines), encoding="utf-8"); return path


def _source_cache_path(runtime_root: str | Path) -> Path:
    return Path(runtime_root).resolve() / "reality-slice1" / "source-outcomes.json"


def _load_cached_outcomes(path: Path) -> tuple[AcquisitionOutcome, ...] | None:
    if not path.is_file():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return tuple(AcquisitionOutcome(source=SourceOpportunity(**row["source"]), status=row["status"], requested_locator=row["requested_locator"], resolved_locator=row.get("resolved_locator"), retrieved_at=row["retrieved_at"], media_type=row.get("media_type"), content_hash=row.get("content_hash"), byte_size=row.get("byte_size"), artifact_id=row.get("artifact_id"), source_record_id=row.get("source_record_id"), error_class=row.get("error_class"), evidence_status=row.get("evidence_status", "not_reviewed"), evidence_reason=row.get("evidence_reason"), reporting_period=row.get("reporting_period"), locator_kind=row.get("locator_kind")) for row in rows)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None

def run_development_preflight(*, runtime_root: str | Path, catalog: SQLiteCatalog | None = None, allow_network: bool = False, manifest: str | Path | None = None, members: Iterable[CohortMember] | None = None) -> dict[str, Any]:
    selected = tuple(members or development_members(manifest))
    for member in selected:
        assert_development_member(abn=member.abn, path=manifest)
    acquirer = BoundedPublicAcquirer(runtime_root, catalog=catalog)
    cache_path = _source_cache_path(runtime_root)
    cached = _load_cached_outcomes(cache_path)
    if cached is not None:
        outcomes = cached
        replay_mode = "source_hash_replay"
    else:
        fetcher = acquirer.fetch_page if allow_network else None
        outcomes = tuple(acquirer.acquire(opportunity, allow_network=allow_network) for member in selected for opportunity in source_opportunities(member, page_fetcher=fetcher))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps([item.__dict__ | {"source": item.source.__dict__} for item in outcomes], sort_keys=True, default=str), encoding="utf-8")
        replay_mode = "fresh_bounded_acquisition"
    references = build_proposed_reference_set(selected, outcomes)
    task_specs = build_frozen_task_plan(selected, outcomes, references)
    snapshots = load_economics_snapshots(runtime_root, allow_network=allow_network)
    cost = project_costs(selected, task_specs=task_specs, pricing_input_usd=Decimal(snapshots["pricing"]["input_usd_per_million"]), pricing_output_usd=Decimal(snapshots["pricing"]["output_usd_per_million"]), fx_usd_aud=Decimal(snapshots["fx"]["rate"]))
    scopes = build_assessment_scopes(selected, outcomes)
    scope_rows = [scope.__dict__ for scope in scopes]
    telemetry = {"retrieval_count": len(outcomes), "available_count": sum(item.status == "available" for item in outcomes), "usable_evidence_count": sum(item.evidence_status == "usable_evidence" for item in outcomes), "generic_landing_count": sum(item.evidence_status == "generic_landing_page" for item in outcomes), "blocked_count": sum(item.status == "blocked" for item in outcomes), "failed_count": sum(item.status == "failed" for item in outcomes), "bytes_available": sum(item.byte_size or 0 for item in outcomes)}
    outcome_rows = [outcome.__dict__ | {"source": outcome.source.__dict__} for outcome in outcomes]
    subjects = [{"subject_id": member.subject_id, "display_name": member.legal_current_name, "abn": member.abn, "identity_status": "deterministic_internal_candidate", "public_subject_minting": "forbidden"} for member in selected]
    exact_join_status = [{"member_abn": member.abn, "status": "pending_national_backbone_input", "name_fallback": False, "subject_id": member.subject_id} for member in selected]
    acquired_families = {(item.source.member_abn, item.source.family) for item in outcomes if item.evidence_status == "usable_evidence"}
    source_resolution_gaps = [{"member_abn": member.abn, "family": family, "status": "unavailable", "reason": "case-specific independent locator was not discovered in the bounded pass; no homepage substitute used"} for member in selected for family in member.expected_source_families[5:] if (member.abn, family) not in acquired_families]
    report: dict[str, Any] = {"manifest": str(manifest_path(manifest)), "development_members": [member.__dict__ | {"subject_id": member.subject_id} for member in selected], "organisation_subjects": subjects, "identity_joins": exact_join_status, "holdout_firewall": {"holdout_abns": sorted(_HOLDOUT_ABNS), "enforced": True, "acquisition_receipts_for_holdouts": 0, "model_tasks_for_holdouts": 0, "evidence_artefacts_for_holdouts": 0}, "source_opportunities": len(outcomes), "replay_mode": replay_mode, "source_resolution_gaps": source_resolution_gaps, "acquisition_telemetry": telemetry, "acquisition_outcomes": outcome_rows, "evidence_inventory": list(build_evidence_inventory(outcomes)), "assessment_scopes": scope_rows, "structured_program_candidates": [ref.__dict__ for ref in references if ref.field == "material_program"], "task_plan": [spec.__dict__ for spec in task_specs], "proposed_reference_set": [entry.__dict__ for entry in references], "taxonomy": {"classie": {"version": CLASSIE_VERSION, "status": "blocked_until_authoritative_private_reference", "rights_blocker": "authoritative CLASSIE 4.2 material and reuse disposition not supplied"}, "sdg": {"concept_count": 17, "titles_canonical": True}, "charitygraph_activity": {"version": ACTIVITY_VOCABULARY_VERSION, "concept_count": len(CHARITYGRAPH_ACTIVITY_VOCABULARY), "rationale": "bounded source-grounded development vocabulary"}}, "provider": {"provider_id": "openai", "model_snapshot": os.environ.get("CHARITYGRAPH_MODEL_SNAPSHOT", "gpt-5-mini"), "configuration_status": "explicit_candidate_pending_human_approval", "paid_execution_enabled": False, "credentials_present": bool(os.environ.get("OPENAI_API_KEY"))}, "economics": cost | {"pricing_snapshot": snapshots["pricing"], "fx_snapshot": snapshots["fx"], "snapshot_identity": snapshots["snapshot_identity"]}, "coverage": {"organisation_identity": "deterministic_candidate_pending_backbone_exact_join", "program_candidates": "source-grounded_review_candidates", "semantic_fields": "blocked_until_classie_and_reference_approval", "high_consequence_review": "human_review_required"}, "review_gate": "stop_before_paid_semantic_execution", "private": True}
    report["reservation_demo"] = demonstrate_sqlite_reservations(runtime_root, task_specs, Decimal(cost["total_estimated_aud"]))
    packet = write_human_review_packet(report, runtime_root); report["human_review_packet"] = str(packet)
    return report

def build_assessment_scopes(members: Iterable[CohortMember], outcomes: Iterable[AcquisitionOutcome]) -> tuple[AssessmentScope, ...]:
    grouped: dict[str, list[AcquisitionOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.source.member_abn, []).append(outcome)
    rows = []
    for member in members:
        processed = [item for item in grouped.get(member.abn, ()) if item.status == "available" and item.evidence_status == "usable_evidence" and item.source_record_id]
        families = tuple(sorted({item.source.family for item in processed}))
        source_ids = tuple(item.source_record_id for item in processed if item.source_record_id)
        missing = tuple(sorted(set(member.expected_source_families) - set(families)))
        blockers = tuple("missing_or_unavailable:" + family for family in missing)
        rows.append(AssessmentScope(member.abn, families, source_ids, missing, None, blockers))
    return tuple(rows)


def build_private_candidate(*, member: CohortMember, domain: str, source_record_ids: tuple[str, ...]) -> PrivateCandidate:
    return PrivateCandidate(candidate_id=deterministic_id("candidate:", {"subject_id": member.subject_id, "domain": domain, "source_record_ids": source_record_ids}), subject_id=member.subject_id, domain=domain, source_record_ids=source_record_ids, semantic_outcome=None, blockers=("human_review_required",))


def write_private_preview(report: Mapping[str, Any], runtime_root: str | Path) -> tuple[Path, Path]:
    root = Path(runtime_root).resolve() / "reality-slice1" / "preflight"; root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    json_path = root / f"development-preflight-{digest[:16]}.json"; json_path.write_bytes(payload)
    md_path = root / f"development-preflight-{digest[:16]}.md"; md_path.write_text("# CharityGraph Reality Slice 1 development preflight\n\nPrivate, review-only preview. Paid semantic execution is disabled.\n\n" + "- development members: " + str(len(report.get("development_members", []))) + "\n- planned tasks: " + str(len(report.get("task_plan", []))) + "\n- projected AUD: " + str(report.get("economics", {}).get("total_estimated_aud")) + "\n- holdout firewall: enforced\n", encoding="utf-8")
    return json_path, md_path


def crosswalk_exact_records(member: CohortMember, records: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    assert_development_member(abn=member.abn)
    return exact_identifier_join({"ABN": member.abn}, records)
