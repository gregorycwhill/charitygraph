"""Bounded Reality Slice 1 LLM semantic/economics spike.

This module is intentionally private-run infrastructure.  It packs high-recall
source evidence, asks one typed semantic question per charity/tier, and writes
all source, prompt, response and review material below a configured runtime
root.  No output from this spike is public CauseBase/CharityGraph data or gold.

The implementation contains no lexical relevance classifier.  Source URLs are
an explicit, human-authored allow-list and the parser retains document
structure without deciding what the text means.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping
from urllib.request import Request, urlopen

from pydantic import Field, field_validator, model_validator

from .contracts.common import SchemaRef, Sha256, StrictModel, VersionedPolicy
from .contracts.economics import CostLedgerEntry, Money, PricingSnapshot, PriceRate, FxRateSnapshot
from .contracts.ids import deterministic_id
from .contracts.tasks import EvidenceInput, ModelTask, ProviderUsage, model_task_cache_key
from .openai_client import ApiResult, ApiUsage, estimate_response_cost, responses_create
from .reality_slice1 import BUDGET_CAP_AUD, development_members, assert_development_member
from .runtime import SQLiteCatalog
from .evidence_store import ContentAddressedArtifactStore

UTC = timezone.utc
SPIKE_VERSION = "reality-slice1-llm-semantic-economics-v1"
PROMPT_TEMPLATE_ID = "charitygraph-reality-slice1-semantic-rich-v1"
POLICY_ID = "CG-D027"
TIERS: tuple[str, ...] = ("lean", "broad", "very_broad")
TIER_LIMITS = {"lean": 16_000, "broad": 42_000, "very_broad": 90_000}

# Explicitly selected bounded pages.  This is source navigation, never a
# semantic URL filter; the seven rows are the only permitted development scope.
SOURCE_URLS: Mapping[str, tuple[str, ...]] = {
    "28000030179": (
        "https://www.thesmithfamily.com.au/",
        "https://www.thesmithfamily.com.au/programs/learning-for-life",
        "https://www.thesmithfamily.com.au/programs/educators",
        "https://www.thesmithfamily.com.au/programs/literacy/lets-read",
        "https://www.thesmithfamily.com.au/programs/school-transition/passport",
    ),
    "50169561394": ("https://www.redcross.org.au/", "https://www.redcross.org.au/publications/"),
    "20077830347": (
        "https://communityfoundation.org.au/",
        "https://communityfoundation.org.au/philanthropic-services/acf-advisory/",
        "https://communityfoundation.org.au/impact/impact-fund/",
        "https://communityfoundation.org.au/impact/responsible-investing/",
        "https://communityfoundation.org.au/impact/focus-areas/",
        "https://communityfoundation.org.au/philanthropic-services/professional-advisors/",
        "https://communityfoundation.org.au/philanthropic-services/scholarship-funds/",
        "https://communityfoundation.org.au/philanthropic-services/trusts-and-foundations/",
    ),
    "22007498482": ("https://www.acf.org.au/", "https://www.acf.org.au/publications/reports"),
    "15000002522": ("https://www.missionaustralia.com.au/",),
    "28004778081": ("https://www.worldvision.com.au/",),
    "46070556642": (
        "https://www.hollows.org/",
        "https://www.hollows.org/what-we-do/advocacy/",
        "https://www.hollows.org/what-we-do/ending-avoidable-blindness/",
        "https://www.hollows.org/what-we-do/research-technology/",
        "https://www.hollows.org/what-we-do/training/",
        "https://www.hollows.org/what-we-do/our-impact/",
    ),
}


class EvidenceSegment(StrictModel):
    evidence_id: str
    source_url: str
    source_artifact_id: str
    content_hash: Sha256
    ordinal: int
    heading_path: tuple[str, ...] = ()
    text: str
    links: tuple[str, ...] = ()

    @field_validator("evidence_id", "source_url", "source_artifact_id", "text")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence segment fields must be nonblank")
        return value


class EvidenceBundle(StrictModel):
    bundle_id: str
    subject_id: str
    tier: str
    source_segments: tuple[EvidenceSegment, ...]
    bundle_hash: Sha256
    selection_hash: Sha256
    evidence_content_hash: Sha256

    @model_validator(mode="after")
    def _hashes(self) -> "EvidenceBundle":
        material = [segment.model_dump(mode="json") for segment in self.source_segments]
        expected = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if expected != self.bundle_hash:
            raise ValueError("bundle_hash does not match exact evidence segments")
        expected_selection = hashlib.sha256(json.dumps({"segments": [s.evidence_id for s in self.source_segments]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if expected_selection != self.selection_hash:
            raise ValueError("selection_hash does not match deterministic segment selection")
        content_material = [{"source_url": s.source_url, "source_artifact_id": s.source_artifact_id, "content_hash": s.content_hash, "ordinal": s.ordinal, "heading_path": s.heading_path, "text": s.text, "links": s.links} for s in self.source_segments]
        expected_content = hashlib.sha256(json.dumps(content_material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if expected_content != self.evidence_content_hash:
            raise ValueError("evidence_content_hash does not match ordered source material")
        return self

class SemanticProposal(StrictModel):
    proposal_id: str
    label: str
    kind: str
    durable: bool | None
    parent_proposal_id: str | None
    description: str | None
    evidence_refs: tuple[str, ...]
    aliases: tuple[str, ...]
    confidence: str | None
    competing_interpretation: str | None
    model_review_recommendation: Literal["required", "acceptable", "unresolved", "exclude"] | None

    @field_validator("proposal_id", "label", "kind")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposal identity fields must be nonblank")
        return value


class SemanticAssertion(StrictModel):
    proposition: str
    evidence_refs: tuple[str, ...]
    confidence: str | None
    competing_interpretation: str | None

    @field_validator("proposition")
    @classmethod
    def _proposition(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposition must be nonblank")
        return value


class RichSemanticOutput(StrictModel):
    """One model response containing independently reviewable logical outputs."""
    programs: tuple[SemanticProposal, ...]
    services: tuple[SemanticProposal, ...]
    projects: tuple[SemanticProposal, ...]
    campaigns: tuple[SemanticProposal, ...]
    organisational_units: tuple[SemanticProposal, ...]
    activities: tuple[SemanticAssertion, ...]
    populations: tuple[SemanticAssertion, ...]
    geographies: tuple[SemanticAssertion, ...]
    sdg_alignments: tuple[SemanticAssertion, ...]
    assertions: tuple[SemanticAssertion, ...]
    semantic_outcome: str
    blockers: tuple[str, ...]

    @model_validator(mode="after")
    def _no_unbound_refs(self) -> "RichSemanticOutput":
        # Evidence binding is checked against the bundle by validate_output;
        # this model intentionally carries no source text or hidden rationale.
        return self


def rich_semantic_output_schema() -> dict[str, Any]:
    """Return the exact strict wire schema sent to the Responses API."""
    return RichSemanticOutput.model_json_schema()


def rich_semantic_output_text_format() -> dict[str, Any]:
    """Return the exact strict response format supplied to OpenAI."""
    return {"type": "json_schema", "name": "rich_semantic_output", "strict": True, "schema": rich_semantic_output_schema()}


class SourceDocument(StrictModel):
    url: str
    retrieved_at: datetime
    publisher: str
    content_hash: Sha256
    artifact_id: str
    media_type: str
    byte_size: int
    text: str
    headings: tuple[str, ...] = ()
    links: tuple[str, ...] = ()


class SpikeRunConfig(StrictModel):
    runtime_root: str
    provider_id: str = "openai"
    model_snapshot: str = "gpt-5.6-luna"
    execute_paid: bool = False
    max_output_tokens: int = 8000
    budget_cap_aud: Decimal = BUDGET_CAP_AUD

    @field_validator("runtime_root", "provider_id", "model_snapshot")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run configuration values must be nonblank")
        return value

    @model_validator(mode="after")
    def _cap(self) -> "SpikeRunConfig":
        if self.budget_cap_aud <= 0:
            raise ValueError("budget cap must be positive")
        return self


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.headings: list[str] = []
        self._skip = 0
        self._heading: list[str] | None = None
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("mailto:", "tel:", "javascript:")):
                self.links.append(href)
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip += 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and not self._skip:
            self._heading = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        compact = re.sub(r"\s+", " ", data).strip()
        if not compact:
            return
        self.parts.append(compact)
        if self._heading is not None:
            self._heading.append(compact)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "template", "svg"} and self._skip:
            self._skip -= 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading is not None:
            heading = " ".join(self._heading).strip()
            if heading:
                self.headings.append(heading)
            self._heading = None


def _parse_structure(body: bytes) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    parser = _TextParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    result: list[str] = []
    for part in parser.parts:
        if not result or result[-1] != part:
            result.append(part)
    return "\n".join(result), tuple(dict.fromkeys(parser.headings)), tuple(dict.fromkeys(parser.links))


def parse_document(body: bytes) -> str:
    """Strip markup mechanically and retain text in source order."""
    return _parse_structure(body)[0]

class AcquisitionFailure(StrictModel):
    url: str
    charity: str
    failure_class: str
    occurred_at: datetime


def _acquire_documents(runtime_root: str | Path, *, transport: Callable[[str], tuple[bytes, str]] | None = None) -> tuple[tuple[SourceDocument, ...], tuple[AcquisitionFailure, ...]]:
    """Acquire only the explicit seven-charity URL plan into private CAS."""
    root = Path(runtime_root).resolve()
    store = ContentAddressedArtifactStore(root / "reality-slice1-llm-semantic-economics", allowed_roots=(root,))
    documents: list[SourceDocument] = []
    failures: list[AcquisitionFailure] = []
    for member in development_members():
        assert_development_member(abn=member.abn)
        for url in SOURCE_URLS[member.abn]:
            try:
                if transport:
                    body, media_type = transport(url)
                else:
                    request = Request(url, headers={"User-Agent": "CharityGraph-Reality-Slice1/2.0"})
                    with urlopen(request, timeout=30) as response:
                        body, media_type = response.read(20_000_001), response.headers.get_content_type()
                if len(body) > 20_000_000:
                    raise ValueError("source document exceeds bounded size")
                stored = store.put(body, created_at=datetime.now(UTC))
                text, headings, links = _parse_structure(body)
                documents.append(SourceDocument(url=url, retrieved_at=datetime.now(UTC), publisher=member.legal_current_name, content_hash=stored.content_hash, artifact_id=stored.artifact_id, media_type=media_type, byte_size=len(body), text=text, headings=headings, links=links))
            except Exception as exc:
                failures.append(AcquisitionFailure(url=url, charity=member.legal_current_name, failure_class=type(exc).__name__.lower(), occurred_at=datetime.now(UTC)))
    return tuple(documents), tuple(failures)


def acquire_documents(runtime_root: str | Path, *, transport: Callable[[str], tuple[bytes, str]] | None = None) -> tuple[SourceDocument, ...]:
    """Acquire bounded documents; failures are retained by the private helper."""
    return _acquire_documents(runtime_root, transport=transport)[0]


def build_evidence_bundle(subject_id: str, tier: str, documents: Iterable[SourceDocument]) -> EvidenceBundle:
    if tier not in TIERS:
        raise ValueError("unknown evidence tier")
    rows: list[EvidenceSegment] = []
    limit = TIER_LIMITS[tier]
    used = 0
    for ordinal, doc in enumerate(sorted(documents, key=lambda item: (item.url, item.content_hash))):
        remaining = max(0, limit - used)
        if not remaining:
            break
        text = doc.text[:remaining]
        if not text:
            continue
        evidence_id = deterministic_id("evidence:", {"subject_id": subject_id, "url": doc.url, "hash": doc.content_hash, "ordinal": ordinal})
        rows.append(EvidenceSegment(evidence_id=evidence_id, source_url=doc.url, source_artifact_id=doc.artifact_id, content_hash=doc.content_hash, ordinal=ordinal, heading_path=doc.headings[:6], text=text, links=doc.links))
        used += len(text)
    material = [segment.model_dump(mode="json") for segment in rows]
    bundle_hash = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    selection_hash = hashlib.sha256(json.dumps({"segments": [s.evidence_id for s in rows]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    content_material = [{"source_url": s.source_url, "source_artifact_id": s.source_artifact_id, "content_hash": s.content_hash, "ordinal": s.ordinal, "heading_path": s.heading_path, "text": s.text, "links": s.links} for s in rows]
    evidence_content_hash = hashlib.sha256(json.dumps(content_material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    bundle_id = deterministic_id("derivative:", {"subject_id": subject_id, "tier": tier, "bundle_hash": bundle_hash})
    return EvidenceBundle(bundle_id=bundle_id, subject_id=subject_id, tier=tier, source_segments=tuple(rows), bundle_hash=bundle_hash, selection_hash=selection_hash, evidence_content_hash=evidence_content_hash)

def semantic_prompt(bundle: EvidenceBundle, charity_name: str) -> str:
    evidence = "\n\n".join(f"[{segment.evidence_id}] SOURCE {segment.source_url}\n{segment.text}" for segment in bundle.source_segments)
    return f"""You are reviewing official source evidence for {charity_name}. Return JSON matching the supplied schema.\n\nDistinguish substantive delivered activity from mission or aspiration, promotional positioning, fundraising/campaign language, claimed outcome, and actual intervention. Propose programs/services/projects only when the evidence supports the distinction; otherwise abstain and record blockers. Include source labels, kind, durability, parent relation, description, aliases, confidence, competing interpretation, and evidence_refs for every proposal. Include operational activities, populations, geographies and scoped SDG alignments only when evidence-bound. Adversarial rules: aspiration is not accomplishment; mission is not delivery; association is not identity; repeated wording is not proof; taxonomy-adjacent vocabulary is not assignment evidence.\n\nEvidence pack content hash {bundle.evidence_content_hash}:\n{evidence}"""


def build_model_task(subject_id: str, bundle: EvidenceBundle, *, provider_id: str, model_snapshot: str) -> ModelTask[Any]:
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-task:1.0", schema_version="1.0")
    output_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-output:1.0", schema_version="1.0")
    inputs = tuple(EvidenceInput(evidence_id=s.evidence_id, content_hash=s.content_hash, selection_hash=bundle.selection_hash) for s in bundle.source_segments)
    policy_refs = (VersionedPolicy(policy_id=POLICY_ID, version="1"),)
    parameters = {"evidence_bundle_hash": bundle.bundle_hash, "evidence_content_hash": bundle.evidence_content_hash}
    cache_key = model_task_cache_key(task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version="1", policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, material_tool_versions=())
    task_id = deterministic_id("modeltask:", {"subject_id": subject_id, "scope_id": None, "task_type": "semantic_interpretation", "cache_key": cache_key, "output_schema": output_schema})
    return ModelTask(record_id=task_id, created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "charitygraph-llm-semantic-economics", "version": SPIKE_VERSION}, subject_id=subject_id, task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version="1", policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, paid_output_categories=("semantic_judgement", "extraction"))

def validate_output(output: RichSemanticOutput, bundle: EvidenceBundle) -> RichSemanticOutput:
    valid = {segment.evidence_id for segment in bundle.source_segments}
    refs: list[str] = []
    for collection in (output.programs, output.services, output.projects, output.campaigns, output.organisational_units, output.activities, output.populations, output.geographies, output.sdg_alignments, output.assertions):
        refs.extend(ref for item in collection for ref in item.evidence_refs)
    missing = [type(item).__name__ for collection in (output.programs, output.services, output.projects, output.campaigns, output.organisational_units, output.activities, output.populations, output.geographies, output.sdg_alignments, output.assertions) for item in collection if not item.evidence_refs]
    if missing:
        raise ValueError("substantive model output requires at least one evidence reference")
    unknown = sorted(set(refs) - valid)
    if unknown:
        raise ValueError(f"model output contains unbound evidence refs: {unknown}")
    return output


def build_human_review_proposals(charity_name: str, output: RichSemanticOutput) -> list[dict[str, Any]]:
    """Translate model proposals into a private review queue, never durable subjects."""
    rows: list[dict[str, Any]] = []
    for proposal in (*output.programs, *output.services):
        rows.append({
            "charity": charity_name,
            "label": proposal.label,
            "kind": proposal.kind,
            "durable": proposal.durable,
            "parent": proposal.parent_proposal_id,
            "description": proposal.description,
            "evidence_refs": list(proposal.evidence_refs),
            "aliases": list(proposal.aliases),
            "confidence": proposal.confidence,
            "competing_interpretation": proposal.competing_interpretation,
            "candidate_observation_id": deterministic_id("candidate:", {"charity": charity_name, "label": proposal.label, "kind": proposal.kind, "evidence_refs": proposal.evidence_refs}),
            "model_recommendation": proposal.model_review_recommendation,
            "review_status": "proposed",
            "human_disposition": None,
        })
    return rows

def _estimate_tokens(prompt: str) -> int:
    return max(1, (len(prompt.encode("utf-8")) + 3) // 4)


def _output_metrics(output: Mapping[str, Any]) -> dict[str, int]:
    proposal_names = ("programs", "services", "projects", "campaigns", "organisational_units")
    assertion_names = ("activities", "populations", "geographies", "sdg_alignments", "assertions")
    all_names = proposal_names + assertion_names
    proposal_count = sum(len(output.get(name, ())) for name in proposal_names)
    assertion_count = sum(len(output.get(name, ())) for name in assertion_names)
    grounded_count = sum(1 for name in all_names for item in output.get(name, ()) if item.get("evidence_refs"))
    outcome = str(output.get("semantic_outcome", "")).casefold()
    return {"proposal_count": proposal_count, "semantic_assertion_count": assertion_count, "grounded_proposition_count": grounded_count, "unresolved_count": int(outcome in {"unresolved", "insufficient_evidence"})}


def build_pricing_snapshot(*, provider_id: str, model_snapshot: str, rates: Iterable[PriceRate], source_content_hash: str, authoritative_source_url: str, now: datetime | None = None) -> PricingSnapshot:
    """Bind explicitly captured provider rates; never infer rates from provider/model names."""
    observed = now or datetime.now(UTC)
    captured_rates = tuple(rates)
    if not captured_rates:
        raise ValueError("pricing snapshot requires explicitly captured rates")
    return PricingSnapshot(record_id=deterministic_id("pricing:", {"provider": provider_id, "model": model_snapshot, "source_hash": source_content_hash, "rates": [rate.model_dump(mode="json") for rate in captured_rates]}), created_at=observed, producer={"kind": "code", "producer_id": "charitygraph-llm-semantic-economics", "version": SPIKE_VERSION}, provider_id=provider_id, model_snapshot=model_snapshot, effective_at=observed, retrieved_at=observed, provider_currency="USD", authoritative_source_url=authoritative_source_url, rates=captured_rates, source_content_hash=source_content_hash)


def build_fx_snapshot(*, aud_per_usd: Decimal, source_name: str, source_url: str, source_content_hash: str, now: datetime | None = None) -> FxRateSnapshot:
    observed = now or datetime.now(UTC)
    return FxRateSnapshot(record_id=deterministic_id("fx:", {"rate": str(aud_per_usd), "source_hash": source_content_hash}), created_at=observed, producer={"kind": "code", "producer_id": "charitygraph-llm-semantic-economics", "version": SPIKE_VERSION}, base_currency="USD", quote_currency="AUD", aud_per_base_unit=aud_per_usd, observed_at=observed, source_name=source_name, source_url=source_url, source_content_hash=source_content_hash)


def _snapshot_price(snapshot: PricingSnapshot, dimension: str) -> Decimal:
    for rate in snapshot.rates:
        if rate.dimension == dimension:
            return rate.price_per_unit / rate.unit_quantity
    raise ValueError(f"pricing snapshot lacks {dimension} rate")

def _estimate_aud(tokens: int, output_tokens: int, pricing_snapshot: PricingSnapshot | None, fx_snapshot: FxRateSnapshot | None) -> Decimal | None:
    if pricing_snapshot is None or fx_snapshot is None:
        return None
    return (Decimal(tokens) * _snapshot_price(pricing_snapshot, "input_tokens") + Decimal(output_tokens) * _snapshot_price(pricing_snapshot, "output_tokens")) * fx_snapshot.aud_per_base_unit


def _cost_entry(*, cohort_id: str, run_id: str, task_run_id: str, reservation_id: str, pricing_id: str, fx_id: str, provider_cost_usd: Decimal, usage: ApiUsage, aud_cost: Decimal, recorded_at: datetime) -> CostLedgerEntry:
    return CostLedgerEntry(cohort_id=cohort_id, run_id=run_id, task_run_id=task_run_id, reservation_id=reservation_id, pricing_snapshot_id=pricing_id, fx_snapshot_id=fx_id, entry_type="actual", paid_output_category="semantic_judgement", provider_cost=Money(amount=provider_cost_usd, currency="USD"), aud_cost=Money(amount=aud_cost, currency="AUD"), usage=ProviderUsage(input_tokens=usage.input_tokens or 0, output_tokens=usage.output_tokens or 0), recorded_at=recorded_at)


def write_human_review_report(report: Mapping[str, Any], root: Path) -> Path:
    """Write a concise private review projection; human disposition stays null."""
    path = root / "human-review.md"
    review = report.get("human_review", {})
    lines = ["# Reality Slice 1 semantic proposals", "", "Private proposed review records; model recommendations are not approval.", "", "Current adequacy denominator: " + str(review.get("denominator_current", 1)), ""]
    for row in review.get("proposed_durable_program_service_subjects", ()):
        lines.extend([
            "## " + str(row.get("charity")) + ": " + str(row.get("label")),
            "- kind: " + str(row.get("kind")),
            "- model recommendation: " + str(row.get("model_recommendation")),
            "- review status: proposed",
            "- human disposition: null",
            "- evidence refs: " + ", ".join(row.get("evidence_refs", ())),
            "",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

def run_spike(config: SpikeRunConfig, *, transport: Callable[[str], tuple[bytes, str]] | None = None, pricing_snapshot: PricingSnapshot | None = None, fx_snapshot: FxRateSnapshot | None = None, provider_call: Callable[[ModelTask[Any], str], ApiResult] | None = None) -> dict[str, Any]:
    members = development_members()
    if {m.abn for m in members} != {"28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642"}:
        raise RuntimeError("development cohort does not match the frozen seven")
    documents, failures = _acquire_documents(config.runtime_root, transport=transport)
    bundles = {(member.abn, tier): build_evidence_bundle(member.subject_id, tier, [doc for doc in documents if doc.publisher == member.legal_current_name]) for member in members for tier in TIERS}
    tasks = {(abn, tier): build_model_task(next(m.subject_id for m in members if m.abn == abn), bundle, provider_id=config.provider_id, model_snapshot=config.model_snapshot) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
    prompts = {(abn, tier): semantic_prompt(bundle, next(m.legal_current_name for m in members if m.abn == abn)) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
    first_for_pack: dict[str, tuple[str, str]] = {}
    for key in prompts:
        first_for_pack.setdefault(bundles[key].evidence_content_hash, key)
    unique_keys = tuple(first_for_pack.values())
    estimates = {key: _estimate_tokens(prompts[key]) for key in prompts}
    unique_estimates = {key: estimates[key] for key in unique_keys}
    if pricing_snapshot is None or fx_snapshot is None:
        projected_usd = None
        projected_aud = None
    else:
        input_rate = _snapshot_price(pricing_snapshot, "input_tokens")
        output_rate = _snapshot_price(pricing_snapshot, "output_tokens")
        projected_usd = sum((Decimal(tokens) * input_rate + Decimal(config.max_output_tokens) * output_rate for tokens in unique_estimates.values()), Decimal("0"))
        projected_aud = (projected_usd * fx_snapshot.aud_per_base_unit).quantize(Decimal("0.000001"))
        if projected_aud > config.budget_cap_aud:
            raise RuntimeError(f"projected paid cost {projected_aud} AUD exceeds cap {config.budget_cap_aud} AUD")
    root = Path(config.runtime_root).resolve() / "reality-slice1-llm-semantic-economics"
    root.mkdir(parents=True, exist_ok=True)
    source_counts: dict[str, int] = {}
    for document in documents:
        source_counts[document.publisher] = source_counts.get(document.publisher, 0) + 1
    tier_counts = {tier: sum(1 for key in tasks if key[1] == tier) for tier in TIERS}
    report: dict[str, Any] = {"version": SPIKE_VERSION, "private": True, "development_abns": [m.abn for m in members], "holdout_firewall": {"enforced": True, "holdout_model_tasks": 0}, "tiers": list(TIERS), "task_count": len(tasks), "unique_semantic_evidence_pack_count": len(unique_keys), "source_document_count": len(documents), "source_documents_by_charity": source_counts, "task_count_by_tier": tier_counts, "acquisition_failures": [failure.model_dump(mode="json") for failure in failures], "evidence_bundles": {f"{key[0]}:{key[1]}": bundle.model_dump(mode="json") for key, bundle in bundles.items()}, "projected": {"input_tokens": sum(unique_estimates.values()), "output_tokens": len(unique_keys) * config.max_output_tokens, "max_reserved_output_tokens": len(unique_keys) * config.max_output_tokens, "aud": None if projected_aud is None else str(projected_aud), "within_cap": None if projected_aud is None else projected_aud <= config.budget_cap_aud, "status": "missing_bound_snapshots" if projected_aud is None else "projected_from_bound_snapshots"}, "paid_execution": config.execute_paid, "results": [], "human_review": {"denominator_current": 1, "proposed_durable_program_service_subjects": [], "model_output_is_not_gold": True}}
    report["pricing_snapshot"] = None if pricing_snapshot is None else pricing_snapshot.model_dump(mode="json")
    report["fx_snapshot"] = None if fx_snapshot is None else fx_snapshot.model_dump(mode="json")
    report["economics"] = {"by_charity_tier": [{"abn": key[0], "tier": key[1], "evidence_content_hash": bundles[key].evidence_content_hash, "exact_pack_reuse": key != first_for_pack[bundles[key].evidence_content_hash], "estimated_input_tokens": estimates[key], "estimated_output_tokens": config.max_output_tokens, "estimated_aud": None if _estimate_aud(estimates[key], config.max_output_tokens, pricing_snapshot, fx_snapshot) is None else str(_estimate_aud(estimates[key], config.max_output_tokens, pricing_snapshot, fx_snapshot))} for key in sorted(prompts)], "production_equivalent": {"status": "not_configured", "discount_assumed": False}, "aggregate": {"semantic_assertions": 0, "proposal_count": 0, "credible_proposals": 0, "grounded_propositions": 0, "unresolved_count": 0, "actual_cost_aud": "0", "useful_yield": {"grounded_propositions": 0}, "incremental_tier_yield": "pending_paid_run", "quality_effect": "pending_human_review", "human_review_burden": "pending_paid_run"}}
    review_rows: list[dict[str, Any]] = []
    if config.execute_paid and (pricing_snapshot is None or fx_snapshot is None):
        raise RuntimeError("paid execution requires bound pricing and FX snapshots")
    if config.execute_paid and not tasks:
        raise RuntimeError("paid execution requires at least one evidence-bound task")
    if config.execute_paid:
        catalog = SQLiteCatalog(root / "ledger.sqlite3").open(initialize=True)
        now = datetime.now(UTC)
        cohort_id = deterministic_id("cohort:", {"spike": SPIKE_VERSION, "members": [m.abn for m in members]})
        run_id = deterministic_id("run:", {"cohort": cohort_id, "spike": SPIKE_VERSION})
        catalog.register_cohort({"record_id": cohort_id, "cohort_code": "REALITY-SLICE1", "definition_version": "1", "membership_hash": hashlib.sha256("|".join(m.abn for m in members).encode()).hexdigest(), "budget_cap": {"amount": str(config.budget_cap_aud), "currency": "AUD"}, "created_at": now})
        catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "economics_spike", "status": "planned", "configuration_hash": hashlib.sha256(SPIKE_VERSION.encode()).hexdigest(), "created_at": now})
        unique_tasks = {tasks[key].record_id: tasks[key] for key in unique_keys}
        for task in unique_tasks.values():
            catalog.register_task({"record_id": task.record_id, "run_id": run_id, "subject_id": task.subject_id, "cohort_id": cohort_id, "task_type": task.task_type, "task_schema": task.task_schema.model_dump(), "cache_key": task.cache_key, "provider_id": task.provider_id, "model_snapshot": task.model_snapshot, "created_at": now})
        reservation_id = deterministic_id("reservation:", {"run": run_id, "tasks": sorted(unique_tasks)})
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(projected_aud), "currency": "AUD"}, "model_task_ids": tuple(unique_tasks)}, now=now)
        pricing_id = pricing_snapshot.record_id
        fx_id = fx_snapshot.record_id
        results_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for key, task in tasks.items():
            pack_hash = bundles[key].evidence_content_hash
            if key != first_for_pack[pack_hash]:
                original_key = first_for_pack[pack_hash]
                original = results_by_key[original_key]
                reused = {"abn": key[0], "tier": key[1], "task_id": task.record_id, "task_run_id": original["task_run_id"], "output": original["output"], "usage": original["usage"], "actual_aud": "0.000000", "raw_response_ref": original["raw_response_ref"], "validation_status": "reused_exact_evidence_pack", "effective_evidence_pack_hash": pack_hash, "reused_from": {"tier": original_key[1], "task_id": original["task_id"], "task_run_id": original["task_run_id"]}}
                report["results"].append(reused)
                results_by_key[key] = reused
                continue
            task_run_id = deterministic_id("taskrun:", {"task": task.record_id, "run": run_id})
            api = provider_call(task, prompts[key]) if provider_call is not None else responses_create(model=config.model_snapshot, input_text=prompts[key], text_format=rich_semantic_output_text_format(), max_output_tokens=config.max_output_tokens)
            output = validate_output(RichSemanticOutput.model_validate(json.loads(api.output_text)), bundles[key])
            raw_ref = str(root / "responses" / f"{task_run_id}.json")
            Path(raw_ref).parent.mkdir(parents=True, exist_ok=True)
            Path(raw_ref).write_text(api.output_text, encoding="utf-8")
            usage = api.usage
            usd = Decimal(usage.input_tokens or 0) * _snapshot_price(pricing_snapshot, "input_tokens") + Decimal(usage.output_tokens or 0) * _snapshot_price(pricing_snapshot, "output_tokens")
            aud = (usd * fx_snapshot.aud_per_base_unit).quantize(Decimal("0.000001"))
            entry = _cost_entry(cohort_id=cohort_id, run_id=run_id, task_run_id=task_run_id, reservation_id=reservation_id, pricing_id=pricing_id, fx_id=fx_id, provider_cost_usd=usd, usage=usage, aud_cost=aud, recorded_at=datetime.now(UTC))
            catalog.record_cost_entry(entry, entry_key=deterministic_id("costledger:", {"task_run": task_run_id, "output_hash": hashlib.sha256(api.output_text.encode()).hexdigest()}))
            result = {"abn": key[0], "tier": key[1], "task_id": task.record_id, "task_run_id": task_run_id, "output": output.model_dump(mode="json"), "usage": usage.__dict__, "actual_aud": str(aud), "raw_response_ref": raw_ref, "validation_status": "valid", "effective_evidence_pack_hash": pack_hash, "reused_from": None}
            report["results"].append(result)
            results_by_key[key] = result
            review_rows.extend(build_human_review_proposals(next(m.legal_current_name for m in members if m.abn == key[0]), output))
        independent_results = [(row, _output_metrics(row["output"])) for row in report["results"] if row["validation_status"] == "valid"]
        proposal_count = sum(metrics["proposal_count"] for _, metrics in independent_results)
        assertion_count = sum(metrics["semantic_assertion_count"] for _, metrics in independent_results)
        grounded_count = sum(metrics["grounded_proposition_count"] for _, metrics in independent_results)
        unresolved_count = sum(metrics["unresolved_count"] for _, metrics in independent_results)
        actual_total = sum((Decimal(row["actual_aud"]) for row, _ in independent_results), Decimal("0"))
        report["economics"]["aggregate"] = {"semantic_assertions": assertion_count, "proposal_count": proposal_count, "credible_proposals": proposal_count, "grounded_propositions": grounded_count, "unresolved_count": unresolved_count, "actual_cost_aud": str(actual_total), "useful_yield": {"grounded_propositions": grounded_count, "proposals_with_evidence": grounded_count, "cost_per_grounded_proposition_aud": None if not grounded_count else str((actual_total / grounded_count).quantize(Decimal("0.000001")))}, "incremental_tier_yield": "computed_from_independent_packs", "quality_effect": "pending_human_review", "human_review_burden": len(review_rows)}
        report["economics"]["actual_by_charity_tier"] = [{"abn": row["abn"], "tier": row["tier"], "actual_aud": row["actual_aud"], "evidence_content_hash": row["effective_evidence_pack_hash"], "reused_exact_evidence_pack": row["validation_status"] != "valid", "proposal_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["proposal_count"], "semantic_assertion_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["semantic_assertion_count"], "grounded_proposition_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["grounded_proposition_count"], "unresolved_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["unresolved_count"]} for row in report["results"]]
        report["economics"]["incremental_tier_yield"] = [{"tier": tier, "task_count": sum(1 for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), "reused_task_count": sum(1 for row in report["results"] if row["tier"] == tier and row["validation_status"] != "valid"), "actual_cost_aud": str(sum((Decimal(row["actual_aud"]) for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), Decimal("0"))), "proposal_count": sum(_output_metrics(row["output"])["proposal_count"] for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), "grounded_proposition_count": sum(_output_metrics(row["output"])["grounded_proposition_count"] for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid")} for tier in TIERS]
        report["ledger"] = {"database": str(catalog.path), "cohort_id": cohort_id, "run_id": run_id, "reservation_id": reservation_id, "budget_position": catalog.budget_position(cohort_id).as_dict()}
        report["human_review"]["proposed_durable_program_service_subjects"] = review_rows
        catalog.close()
    (root / "spike-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report["human_review_report"] = str(write_human_review_report(report, root))
    (root / "spike-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return report

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the private Reality Slice 1 LLM semantic economics spike")
    parser.add_argument("--runtime-root", default=os.environ.get("CHARITYGRAPH_RUNTIME_ROOT", r"C:\CharityGraph-runtime"))
    parser.add_argument("--execute-paid", action="store_true")
    parser.add_argument("--model", default=os.environ.get("CHARITYGRAPH_MODEL_SNAPSHOT", "gpt-5.6-luna"))
    args = parser.parse_args(argv)
    report = run_spike(SpikeRunConfig(runtime_root=args.runtime_root, execute_paid=args.execute_paid, model_snapshot=args.model))
    print(json.dumps({"task_count": report["task_count"], "source_document_count": report["source_document_count"], "projected": report["projected"], "paid_execution": report["paid_execution"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
