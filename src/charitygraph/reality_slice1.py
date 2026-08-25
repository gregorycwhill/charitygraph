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


def source_opportunities(member: CohortMember) -> tuple[SourceOpportunity, ...]:
    assert_development_member(abn=member.abn)
    website, publisher = _WEBSITES[member.abn]
    rows = [
        SourceOpportunity(member.abn, "acnc", "register_identity_and_classification", "https://www.acnc.gov.au/charity/charities", "ACNC registration, ABN, current name and source-native classifications", "Australian Charities and Not-for-profits Commission"),
        SourceOpportunity(member.abn, "abr", "exact_identity_and_status", "https://abr.business.gov.au/", "ABN status and legal identity", "Australian Business Register"),
        SourceOpportunity(member.abn, "ato-dgr", "dgr_and_tax_concession", "https://www.ato.gov.au/", "DGR/tax-concession facts", "Australian Taxation Office"),
        SourceOpportunity(member.abn, "official-website", "current_program_and_service_description", website, "current program/service description", publisher),
        SourceOpportunity(member.abn, "annual-report", "reported_programs_and_financial_context", website + "/annual-report", "annual or audited report facts", publisher),
    ]
    for family in member.expected_source_families[5:]:
        rows.append(SourceOpportunity(member.abn, family, "bounded_case_specific_context", website, "case-specific contextual evidence", publisher))
    return tuple(rows)


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
            source_record_id = deterministic_id("srcrec:", {"definition": definition.record_id, "hash": artifact.content_hash})
            if self.catalog is not None:
                self.catalog.record_acquisition_receipt(AcquisitionReceipt(record_id=deterministic_id("acq:", {"definition": definition.record_id, "hash": artifact.content_hash}), created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "reality-slice1-acquirer", "version": "1"}, source_definition_id=definition.record_id, requested_locator=opportunity.url, resolved_locator=resolved, retrieved_at=datetime.now(UTC), outcome="available", response_status=status, media_type=media_type, content_hash=artifact.content_hash, byte_size=artifact.byte_size, artifact_id=artifact.artifact_id, tool_id="urllib", tool_version="stdlib"))
                self.catalog.register_source_record(SourceRecord(record_id=source_record_id, created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "reality-slice1-acquirer", "version": "1"}, source_family=opportunity.family, source_role=opportunity.role, source_version="bounded-2026-08", source_locator=resolved, retrieved_at=datetime.now(UTC), observed_at=datetime.now(UTC), media_type=media_type, payload_ref=artifact.artifact_id, payload_hash=artifact.content_hash, rights_policy_id=opportunity.rights_policy, attribution=opportunity.publisher))
            return AcquisitionOutcome(opportunity, "available", opportunity.url, resolved, retrieved_at, media_type, artifact.content_hash, artifact.byte_size, artifact.artifact_id, source_record_id)
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
    {"id": "activity.service_delivery", "label": "Service delivery", "facet": "activity"},
    {"id": "activity.advocacy", "label": "Advocacy", "facet": "activity"},
    {"id": "activity.research_evaluation", "label": "Research and evaluation", "facet": "activity"},
    {"id": "activity.grantmaking", "label": "Grantmaking", "facet": "activity"},
    {"id": "activity.fundraising", "label": "Fundraising", "facet": "activity"},
    {"id": "activity.community_engagement", "label": "Community engagement", "facet": "activity"},
)


def project_costs(members: Iterable[CohortMember], *, task_types: tuple[str, ...] = ("program_decomposition", "classie_subject", "classie_population", "activity", "sdg_alignment", "evidence_selection"), input_tokens: int = 2500, output_tokens: int = 900, cache_hits: Mapping[str, int] | None = None) -> dict[str, Any]:
    cache_hits = cache_hits or {}
    rows = []
    for member in members:
        count = len(task_types)
        usd = Decimal(input_tokens * count) * Decimal("0.25") / Decimal(1_000_000) + Decimal(output_tokens * count) * Decimal("2.00") / Decimal(1_000_000)
        aud = (usd * Decimal("1.55")).quantize(Decimal("0.000001"))
        hit = int(cache_hits.get(member.abn, 0)); rows.append(CostProjection(member.abn, count, input_tokens * count, output_tokens * count, aud, hit, count - hit))
    total = sum((row.estimated_aud for row in rows), Decimal("0"))
    reservations = [{"reservation_id": deterministic_id("reservation:", {"abn": row.member_abn, "phase": "reality-slice1-preflight"}), "member_abn": row.member_abn, "proposed_aud": str(row.estimated_aud), "status": "proposed_not_reserved"} for row in rows]
    return {"cap_aud": str(BUDGET_CAP_AUD), "rows": [row.__dict__ | {"estimated_aud": str(row.estimated_aud)} for row in rows], "proposed_reservations": reservations, "total_estimated_aud": str(total), "within_cap": total <= BUDGET_CAP_AUD, "paid_calls_executed": False}


def build_proposed_reference_set(members: Iterable[CohortMember], outcomes: Iterable[AcquisitionOutcome]) -> tuple[ProposedReferenceEntry, ...]:
    by_abn: dict[str, tuple[str, ...]] = {}
    for outcome in outcomes:
        if outcome.source_record_id:
            by_abn.setdefault(outcome.source.member_abn, tuple())
            by_abn[outcome.source.member_abn] = by_abn[outcome.source.member_abn] + (outcome.source_record_id,)
    fields = ("material_organisation", "material_program", "scope_boundary", "source_reported_facts", "classie_subject", "classie_population", "charitygraph_activity", "sdg_alignment", "insufficient_evidence")
    return tuple(ProposedReferenceEntry(member.abn, member.subject_id, field, "proposed", by_abn.get(member.abn, ()), "Requires independent human approval; no model-derived gold") for member in members for field in fields)


def run_development_preflight(*, runtime_root: str | Path, catalog: SQLiteCatalog | None = None, allow_network: bool = False, manifest: str | Path | None = None, members: Iterable[CohortMember] | None = None) -> dict[str, Any]:
    selected = tuple(members or development_members(manifest))
    for member in selected:
        assert_development_member(abn=member.abn, path=manifest)
    acquirer = BoundedPublicAcquirer(runtime_root, catalog=catalog)
    outcomes = tuple(acquirer.acquire(opportunity, allow_network=allow_network) for member in selected for opportunity in source_opportunities(member))
    references = build_proposed_reference_set(selected, outcomes)
    cost = project_costs(selected)
    task_rows = [{"member_abn": member.abn, "subject_id": member.subject_id, "task_type": task_type, "status": "planned", "evidence_frozen": False, "scheme_version": CLASSIE_VERSION} for member in selected for task_type in ("program_decomposition", "classie_subject", "classie_population", "activity", "sdg_alignment", "evidence_selection")]
    scopes = build_assessment_scopes(selected, outcomes)
    scope_rows = [scope.__dict__ for scope in scopes]
    telemetry = {"retrieval_count": len(outcomes), "available_count": sum(item.status == "available" for item in outcomes), "blocked_count": sum(item.status == "blocked" for item in outcomes), "failed_count": sum(item.status == "failed" for item in outcomes), "bytes_available": sum(item.byte_size or 0 for item in outcomes)}
    outcome_rows = [outcome.__dict__ | {"source": outcome.source.__dict__} for outcome in outcomes]
    subjects = [{"subject_id": member.subject_id, "display_name": member.legal_current_name, "abn": member.abn, "identity_status": "deterministic_internal_candidate", "public_subject_minting": "forbidden"} for member in selected]
    exact_join_status = [{"member_abn": member.abn, "status": "pending_national_backbone_input", "name_fallback": False, "subject_id": member.subject_id} for member in selected]
    return {"manifest": str(manifest_path(manifest)), "development_members": [member.__dict__ | {"subject_id": member.subject_id} for member in selected], "organisation_subjects": subjects, "identity_joins": exact_join_status, "holdout_firewall": {"holdout_abns": sorted(_HOLDOUT_ABNS), "enforced": True, "acquisition_receipts_for_holdouts": 0, "model_tasks_for_holdouts": 0, "evidence_artefacts_for_holdouts": 0}, "source_opportunities": len(outcomes), "acquisition_telemetry": telemetry, "acquisition_outcomes": outcome_rows, "assessment_scopes": scope_rows, "structured_program_candidates": [], "task_plan": task_rows, "proposed_reference_set": [entry.__dict__ for entry in references], "taxonomy": {"classie": {"version": CLASSIE_VERSION, "status": "blocked_until_authoritative_private_reference"}, "sdg": {"concept_count": 17, "titles_canonical": True}, "charitygraph_activity": {"version": ACTIVITY_VOCABULARY_VERSION, "concept_count": len(CHARITYGRAPH_ACTIVITY_VOCABULARY)}}, "provider": OpenAIProviderAdapter().validate_configuration(), "economics": cost, "coverage": {"organisation_identity": "deterministic_candidate_pending_backbone_exact_join", "program_candidates": "not_attempted_without_model_assistance", "semantic_fields": "not_attempted", "high_consequence_review": "human_review_required"}, "review_gate": "stop_before_paid_semantic_execution", "private": True}

def build_assessment_scopes(members: Iterable[CohortMember], outcomes: Iterable[AcquisitionOutcome]) -> tuple[AssessmentScope, ...]:
    grouped: dict[str, list[AcquisitionOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.source.member_abn, []).append(outcome)
    rows = []
    for member in members:
        processed = [item for item in grouped.get(member.abn, ()) if item.status == "available" and item.source_record_id]
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
