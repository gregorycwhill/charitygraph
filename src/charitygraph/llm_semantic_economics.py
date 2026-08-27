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
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from .openai_client import ApiResult, ApiUsage, OpenAIRequestError, estimate_response_cost, responses_create
from .private_classie import load_private_classie_payload
from .reality_slice1 import BUDGET_CAP_AUD, development_members, assert_development_member
from .runtime import SQLiteCatalog
from .evidence_store import ContentAddressedArtifactStore

UTC = timezone.utc
SPIKE_VERSION = "reality-slice1-llm-semantic-economics-v2"
PROMPT_TEMPLATE_ID = "charitygraph-reality-slice1-semantic-rich-v1"
PROMPT_TEMPLATE_VERSION = "2"
POLICY_ID = "CG-D027"
TIERS: tuple[str, ...] = ("lean", "broad", "very_broad")
TIER_LIMITS = {"lean": 16_000, "broad": 42_000, "very_broad": 90_000}

# Human-governed gold dispositions for the development review packet. These
# are review data, not semantic rules and never alter raw provider output.
HUMAN_GOLD_DISPOSITIONS = {
    "The Smith Family": {
        "program:learning-for-life": "REQUIRED", "learning-for-life": "REQUIRED",
        "learning-clubs": "REQUIRED", "program:lets-read": "REQUIRED", "program:passport": "REQUIRED",
        "the-connection": "UNRESOLVED", "literacy-programs": "EXCLUDE", "technology-programs": "EXCLUDE",
        "numeracy-programs": "EXCLUDE", "mentoring-programs": "EXCLUDE",
        "aboriginal-and-torres-strait-islander-programs": "EXCLUDE", "arts-programs": "EXCLUDE",
        "community-programs": "EXCLUDE", "financial-programs": "EXCLUDE",
        "school-transition-programs": "EXCLUDE", "work-experience-programs": "EXCLUDE",
    },
    "Australian Red Cross Society": {
        "service:disaster-support": "REQUIRED", "service:first-aid-training": "REQUIRED",
        "program:migration-support-australia": "ACCEPTABLE", "program:telecross-telechat": "UNRESOLVED",
        "service:community-services-vulnerable-people": "EXCLUDE",
    },
    "Australian Communities Foundation Limited": {
        "proposal:impact-fund": "REQUIRED", "service:acf-advisory": "REQUIRED",
        "service:scholarship-funds": "REQUIRED", "service:structured-giving": "EXCLUDE",
        "service:responsible-investing": "EXCLUDE",
    },
    "The Fred Hollows Foundation": {
        "program:eye-health-workforce-training": "REQUIRED", "program:training-and-empowerment": "REQUIRED",
        "program:eye-health-advocacy-for-change": "REQUIRED", "program:eye-health-advocacy": "REQUIRED",
        "program:advocacy-for-change": "REQUIRED", "program:research-and-technology": "REQUIRED",
        "program:global-eye-health-and-avoidable-blindness": "UNRESOLVED", "program:ending-avoidable-blindness": "UNRESOLVED",
        "service:sight-saving-eye-care-delivery": "EXCLUDE", "service:eye-health-care": "EXCLUDE",
    },
}
REQUIRED_GOLD_COUNT = 12
HUMAN_GOLD_REQUIRED_VARIANTS = {
    ("The Smith Family", "learning-for-life"): ("learning-for-life", "program:learning-for-life"),
    ("The Smith Family", "learning-clubs"): ("learning-clubs", "program:learning-clubs", "proposal:learning-clubs"),
    ("The Smith Family", "program:lets-read"): ("program:lets-read",),
    ("The Smith Family", "program:passport"): ("program:passport",),
    ("Australian Red Cross Society", "service:disaster-support"): ("service:disaster-support", "service_disaster_support"),
    ("Australian Red Cross Society", "service:first-aid-training"): ("service:first-aid-training", "service_first_aid_training"),
    ("Australian Communities Foundation Limited", "proposal:impact-fund"): ("proposal:impact-fund", "program:impact-fund"),
    ("Australian Communities Foundation Limited", "service:acf-advisory"): ("service:acf-advisory",),
    ("Australian Communities Foundation Limited", "service:scholarship-funds"): ("service:scholarship-funds",),
    ("The Fred Hollows Foundation", "program:eye-health-workforce-training"): ("program:eye-health-workforce-training", "program:training-and-empowerment", "proposal:eye-health-workforce-training", "service:eye-health-workforce-training"),
    ("The Fred Hollows Foundation", "program:eye-health-advocacy-for-change"): ("program:eye-health-advocacy-for-change", "program:eye-health-advocacy", "program:advocacy-for-change"),
    ("The Fred Hollows Foundation", "program:research-and-technology"): ("program:research-and-technology", "program:eye-health-research-technology"),
}


def score_human_gold(results):
    """Score deduplicated program/service proposals against human dispositions."""
    observed = set()
    for result in results:
        output = result.get("output") or {}
        charity = str(result.get("charity") or result.get("subject_name") or result.get("legal_current_name") or "")
        for collection in (output.get("programs", ()), output.get("services", ())):
            for proposal in collection:
                observed.add((charity, str(proposal.get("proposal_id", ""))))
    found = set()
    for family_key, variants in HUMAN_GOLD_REQUIRED_VARIANTS.items():
        if any((family_key[0], variant) in observed for variant in variants):
            found.add(family_key)
    excludes = {(charity, proposal_id) for charity, mapping in HUMAN_GOLD_DISPOSITIONS.items() for proposal_id, disposition in mapping.items() if disposition == "EXCLUDE"}
    prohibited = excludes & observed
    recall = len(found) / REQUIRED_GOLD_COUNT if REQUIRED_GOLD_COUNT else None
    precision = len(found) / len(observed) if observed else None
    return {
        "required_denominator": REQUIRED_GOLD_COUNT, "required_found": len(found),
        "required_missed": sorted(f"{charity}:{proposal_id}" for charity, proposal_id in HUMAN_GOLD_REQUIRED_VARIANTS if (charity, proposal_id) not in found),
        "recall": recall, "proposed_program_service_count": len(observed),
        "non_required_proposals": len(observed - {(c, v) for (c, _), variants in HUMAN_GOLD_REQUIRED_VARIANTS.items() for v in variants}), "precision": precision,
        "explicit_exclude_proposals": sorted(f"{charity}:{proposal_id}" for charity, proposal_id in prohibited),
        "zero_critical_scope_errors": not prohibited,
        "thresholds": {"recall_at_least_0_90": recall is not None and recall >= 0.90, "precision_at_least_0_80": precision is not None and precision >= 0.80, "zero_critical_scope_errors": not prohibited},
    }

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
    subject_proposal_id: str | None
    scope_kind: Literal["organisation", "proposal"]
    evidence_refs: tuple[str, ...]
    confidence: str | None
    competing_interpretation: str | None

    @field_validator("proposition")
    @classmethod
    def _proposition(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposition must be nonblank")
        return value

    @model_validator(mode="after")
    def _scope(self) -> "SemanticAssertion":
        if self.scope_kind == "proposal" and not self.subject_proposal_id:
            raise ValueError("proposal-scoped assertions require subject_proposal_id")
        if self.scope_kind == "organisation" and self.subject_proposal_id is not None:
            raise ValueError("organisation-scoped assertions cannot carry subject_proposal_id")
        return self


class ClassieAssignment(StrictModel):
    subject_proposal_id: str | None
    scope_kind: Literal["organisation", "proposal"]
    external_concept_id: str
    role: Literal["primary", "secondary"]
    evidence_refs: tuple[str, ...]
    confidence: str | None
    rationale: str | None
    competing_interpretation: str | None
    model_review_recommendation: Literal["required", "acceptable", "unresolved", "exclude"] | None

    @field_validator("external_concept_id")
    @classmethod
    def _concept(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("CLASSIE concept IDs must be nonblank")
        return value

    @model_validator(mode="after")
    def _scope(self) -> "ClassieAssignment":
        if self.scope_kind == "proposal" and not self.subject_proposal_id:
            raise ValueError("proposal-scoped CLASSIE assignments require subject_proposal_id")
        if self.scope_kind == "organisation" and self.subject_proposal_id is not None:
            raise ValueError("organisation-scoped CLASSIE assignments cannot carry subject_proposal_id")
        return self


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
    classie_assignments: tuple[ClassieAssignment, ...]
    semantic_outcome: str
    blockers: tuple[str, ...]

    @model_validator(mode="after")
    def _proposal_refs(self) -> "RichSemanticOutput":
        proposal_ids = {item.proposal_id for item in (*self.programs, *self.services, *self.projects, *self.campaigns, *self.organisational_units)}
        for item in (*self.activities, *self.populations, *self.geographies, *self.sdg_alignments, *self.assertions, *self.classie_assignments):
            if item.subject_proposal_id is not None and item.subject_proposal_id not in proposal_ids:
                raise ValueError(f"unknown subject_proposal_id {item.subject_proposal_id}")
        return self


def rich_semantic_output_schema() -> dict[str, Any]:
    """Return the exact strict wire schema sent to the Responses API."""
    return RichSemanticOutput.model_json_schema()


def request_specific_rich_semantic_output_schema(*, permitted_evidence_ids: Iterable[str], classie_concept_ids: Iterable[str] = (), classie_enabled: bool = False) -> dict[str, Any]:
    """Derive the strict provider schema for one exact evidence/runtime request."""
    schema = deepcopy(rich_semantic_output_schema())
    evidence_ids = tuple(dict.fromkeys(str(item) for item in permitted_evidence_ids if str(item)))
    if not evidence_ids:
        raise ValueError("request-specific schema requires permitted evidence IDs")
    for definition_name in ("SemanticProposal", "SemanticAssertion", "ClassieAssignment"):
        schema["$defs"][definition_name]["properties"]["evidence_refs"]["items"] = {
            "type": "string", "enum": list(evidence_ids),
        }
    if classie_enabled:
        concept_ids = tuple(dict.fromkeys(str(item) for item in classie_concept_ids if str(item)))
        if not concept_ids:
            raise ValueError("enabled private CLASSIE schema requires concept IDs")
        schema["$defs"]["ClassieAssignment"]["properties"]["external_concept_id"] = {
            "type": "string", "enum": list(concept_ids),
        }
    else:
        schema["properties"]["classie_assignments"]["maxItems"] = 0
    return schema


def rich_semantic_output_text_format(*, permitted_evidence_ids: Iterable[str] | None = None, classie_concept_ids: Iterable[str] = (), classie_enabled: bool = False) -> dict[str, Any]:
    """Return the exact strict response format supplied to OpenAI."""
    schema = rich_semantic_output_schema() if permitted_evidence_ids is None else request_specific_rich_semantic_output_schema(permitted_evidence_ids=permitted_evidence_ids, classie_concept_ids=classie_concept_ids, classie_enabled=classie_enabled)
    return {"type": "json_schema", "name": "rich_semantic_output", "strict": True, "schema": schema}


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
    classie_payload_path: str | None = None
    classie_expected_version: str | None = None

    @field_validator("runtime_root", "provider_id", "model_snapshot")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("run configuration values must be nonblank")
        return value

    @field_validator("classie_payload_path", "classie_expected_version")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("optional CLASSIE configuration values must be nonblank")
        return value

    @model_validator(mode="after")
    def _cap(self) -> "SpikeRunConfig":
        if self.budget_cap_aud <= 0:
            raise ValueError("budget cap must be positive")
        if self.classie_expected_version and not self.classie_payload_path:
            raise ValueError("classie_expected_version requires classie_payload_path")
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

def semantic_prompt(bundle: EvidenceBundle, charity_name: str, *, classie_concepts: Iterable[Mapping[str, str]] = ()) -> str:
    evidence = "\n\n".join(f"[{segment.evidence_id}] SOURCE {segment.source_url}\n{segment.text}" for segment in bundle.source_segments)
    concepts = tuple(classie_concepts)
    classie_text = ""
    if concepts:
        classie_text = "\n\nPrivate CharityGraph CLASSIE concepts (independent assessment; do not use ACNC-reported classifications):\n" + "\n".join(
            f"- {item.get('external_concept_id')}: {item.get('preferred_label')} — {item.get('definition', '')}" for item in concepts
        )
    else:
        classie_text = "\n\nPrivate CharityGraph CLASSIE processing is disabled/not-configured for this request. Return classie_assignments as an empty array and do not make CLASSIE assignments."
    return f"""You are reviewing official source evidence for {charity_name}. Return JSON matching the supplied schema.\n\nDistinguish substantive delivered activity from mission or aspiration, promotional positioning, fundraising/campaign language, claimed outcome, and actual intervention. A page heading, navigation heading, plural category, thematic portfolio, activity family, capability or partnership model is not by itself a durable program/service subject. Propose a program/service subject when evidence supports a stable identifiable offering or operating entity that can reasonably be referred to again as the same thing; a proper name is not required, and descriptive services may qualify when stable delivery is evidenced. When a broad category contains a specific named program, prefer the specific durable subject and represent the category in the appropriate activity/assertion layer. Do not use keyword, regex or other lexical rules to make this judgment. Otherwise abstain and record blockers. Include source labels, kind, durability, parent relation, description, aliases, confidence, competing interpretation, and evidence_refs for every proposal. Include operational activities, populations, geographies and scoped SDG alignments only when evidence-bound and link program/service assertions with subject_proposal_id plus scope_kind=proposal. UN Sustainable Development Goal alignment is CharityGraph model-assessed: the evidence must support the substantive activity/intervention, but need not mention SDGs or use UN terminology. Keep alignment distinct from impact, outcome achievement, causation and UN endorsement; assess it independently, evidence-bound, scoped and confidence-bearing, and do not infer it from generic mission language. Whole-organisation assertions must use scope_kind=organisation and null subject_proposal_id. CharityGraph CLASSIE is independent: use only supplied evidence and private CLASSIE concepts, never ACNC-reported CLASSIE selections. Adversarial rules: aspiration is not accomplishment; mission is not delivery; association is not identity; repeated wording is not proof; taxonomy-adjacent vocabulary is not assignment evidence.\n\nEvidence pack content hash {bundle.evidence_content_hash}:{classie_text}\n{evidence}"""


def build_model_task(subject_id: str, bundle: EvidenceBundle, *, provider_id: str, model_snapshot: str, classie_runtime: Mapping[str, Any] | None = None) -> ModelTask[Any]:
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-task:1.0", schema_version="1.0")
    output_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-output:1.0", schema_version="1.0")
    inputs = tuple(EvidenceInput(evidence_id=s.evidence_id, content_hash=s.content_hash, selection_hash=bundle.selection_hash) for s in bundle.source_segments)
    evidence_ids = tuple(s.evidence_id for s in bundle.source_segments)
    classie_enabled = classie_runtime is not None
    classie_ids = tuple(item["external_concept_id"] for item in (classie_runtime or {}).get("concepts", ()))
    request_schema = request_specific_rich_semantic_output_schema(permitted_evidence_ids=evidence_ids, classie_concept_ids=classie_ids, classie_enabled=classie_enabled)
    request_schema_hash = hashlib.sha256(json.dumps(request_schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    classie_material = {
        "enabled": classie_enabled,
        "scheme_id": None if classie_runtime is None else classie_runtime.get("scheme_id"),
        "version": None if classie_runtime is None else classie_runtime.get("version"),
        "content_hash": None if classie_runtime is None else classie_runtime.get("content_hash"),
        "concept_ids": list(classie_ids),
    }
    policy_refs = (VersionedPolicy(policy_id=POLICY_ID, version="1"),)
    parameters = {
        "evidence_bundle_hash": bundle.bundle_hash,
        "evidence_content_hash": bundle.evidence_content_hash,
        "evidence_reference_ids": list(evidence_ids),
        "classie_runtime": classie_material,
        "request_schema_hash": request_schema_hash,
    }
    cache_key = model_task_cache_key(task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version=PROMPT_TEMPLATE_VERSION, policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, material_tool_versions=())
    task_id = deterministic_id("modeltask:", {"subject_id": subject_id, "scope_id": None, "task_type": "semantic_interpretation", "cache_key": cache_key, "output_schema": output_schema})
    return ModelTask(record_id=task_id, created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "charitygraph-llm-semantic-economics", "version": SPIKE_VERSION}, subject_id=subject_id, task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version=PROMPT_TEMPLATE_VERSION, policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, paid_output_categories=("semantic_judgement", "extraction"))
def validate_output(output: RichSemanticOutput, bundle: EvidenceBundle, *, classie_concept_ids: set[str] | None = None) -> RichSemanticOutput:
    valid = {segment.evidence_id for segment in bundle.source_segments}
    collections = (output.programs, output.services, output.projects, output.campaigns, output.organisational_units, output.activities, output.populations, output.geographies, output.sdg_alignments, output.assertions, output.classie_assignments)
    refs: list[str] = [ref for collection in collections for item in collection for ref in item.evidence_refs]
    missing = [type(item).__name__ for collection in collections for item in collection if not item.evidence_refs]
    if missing:
        raise ValueError("substantive model output requires at least one evidence reference")
    unknown = sorted(set(refs) - valid)
    if unknown:
        raise ValueError(f"model output contains unbound evidence refs: {unknown}")
    if output.classie_assignments:
        if classie_concept_ids is None:
            raise ValueError("CLASSIE assignments require a loaded private CLASSIE scheme")
        unknown_concepts = sorted({item.external_concept_id for item in output.classie_assignments} - set(classie_concept_ids))
        if unknown_concepts:
            raise ValueError(f"model output contains unknown CLASSIE concept IDs: {unknown_concepts}")
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
            "proposal_id": proposal.proposal_id,
            "candidate_observation_id": deterministic_id("candidate:", {"charity": charity_name, "label": proposal.label, "kind": proposal.kind, "evidence_refs": proposal.evidence_refs}),
            "model_recommendation": proposal.model_review_recommendation,
            "review_status": "human_reviewed" if proposal.proposal_id in HUMAN_GOLD_DISPOSITIONS.get(charity_name, {}) else "proposed",
            "human_disposition": HUMAN_GOLD_DISPOSITIONS.get(charity_name, {}).get(proposal.proposal_id),
        })
    return rows

def _estimate_tokens(prompt: str) -> int:
    return max(1, (len(prompt.encode("utf-8")) + 3) // 4)


def _output_metrics(output: Mapping[str, Any]) -> dict[str, int]:
    proposal_names = ("programs", "services", "projects", "campaigns", "organisational_units")
    assertion_names = ("activities", "populations", "geographies", "sdg_alignments", "assertions")
    all_names = proposal_names + assertion_names + ("classie_assignments",)
    proposal_count = sum(len(output.get(name, ())) for name in proposal_names)
    assertion_count = sum(len(output.get(name, ())) for name in assertion_names)
    classie_assignment_count = len(output.get("classie_assignments", ()))
    grounded_count = sum(1 for name in all_names for item in output.get(name, ()) if item.get("evidence_refs"))
    outcome = str(output.get("semantic_outcome", "")).casefold()
    return {"proposal_count": proposal_count, "semantic_assertion_count": assertion_count, "classie_assignment_count": classie_assignment_count, "grounded_proposition_count": grounded_count, "unresolved_count": int(outcome in {"unresolved", "insufficient_evidence"})}


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
    """Write a concise private review projection with governed dispositions."""
    path = root / "human-review.md"
    review = report.get("human_review", {})
    lines = ["# Reality Slice 1 semantic proposals", "", "Private proposed review records; model recommendations are not approval.", "", "Current adequacy denominator: " + str(review.get("denominator_current", 1)), ""]
    for row in review.get("proposed_durable_program_service_subjects", ()):
        lines.extend([
            "## " + str(row.get("charity")) + ": " + str(row.get("label")),
            "- kind: " + str(row.get("kind")),
            "- model recommendation: " + str(row.get("model_recommendation")),
            "- review status: " + str(row.get("review_status", "proposed")),
            "- human disposition: " + str(row.get("human_disposition")),
            "- evidence refs: " + ", ".join(row.get("evidence_refs", ())),
            "",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

HISTORICAL_RUN_ID = "run:6fa24311932e427fb5cc3a5ae228a54b256d1d480f798f02177d158be19c9016"
HISTORICAL_RESERVATION_ID = "reservation:f78e03131491009d16cad859d99ae17555f0f1ad00a37f5c89848776aa05d4cb"


def _redacted_provider_error(error: BaseException) -> tuple[str, str]:
    if isinstance(error, OpenAIRequestError) and error.status_code is not None:
        return f"http_{error.status_code}", str(error)[:512]
    return "provider_error", str(error)[:512]


def run_spike(config: SpikeRunConfig, *, transport: Callable[[str], tuple[bytes, str]] | None = None, pricing_snapshot: PricingSnapshot | None = None, fx_snapshot: FxRateSnapshot | None = None, provider_call: Callable[[ModelTask[Any], str], ApiResult] | None = None) -> dict[str, Any]:
    classie_runtime: dict[str, Any] | None = None
    if config.classie_payload_path:
        classie_runtime = load_private_classie_payload(config.classie_payload_path, expected_scheme_id="classie")
        if config.classie_expected_version and classie_runtime["version"] != config.classie_expected_version:
            raise ValueError("private CLASSIE payload version does not match configured expected version")
    members = development_members()
    if {m.abn for m in members} != {"28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642"}:
        raise RuntimeError("development cohort does not match the frozen seven")
    documents, failures = _acquire_documents(config.runtime_root, transport=transport)
    bundles = {(member.abn, tier): build_evidence_bundle(member.subject_id, tier, [doc for doc in documents if doc.publisher == member.legal_current_name]) for member in members for tier in TIERS}
    tasks = {(abn, tier): build_model_task(next(m.subject_id for m in members if m.abn == abn), bundle, provider_id=config.provider_id, model_snapshot=config.model_snapshot, classie_runtime=classie_runtime) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
    classie_concepts = () if classie_runtime is None else classie_runtime["concepts"]
    prompts = {(abn, tier): semantic_prompt(bundle, next(m.legal_current_name for m in members if m.abn == abn), classie_concepts=classie_concepts) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
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
    report: dict[str, Any] = {"version": SPIKE_VERSION, "private": True, "development_abns": [m.abn for m in members], "holdout_firewall": {"enforced": True, "holdout_model_tasks": 0}, "tiers": list(TIERS), "task_count": len(tasks), "unique_semantic_evidence_pack_count": len(unique_keys), "source_document_count": len(documents), "source_documents_by_charity": source_counts, "task_count_by_tier": tier_counts, "acquisition_failures": [failure.model_dump(mode="json") for failure in failures], "evidence_bundles": {f"{key[0]}:{key[1]}": bundle.model_dump(mode="json") for key, bundle in bundles.items()}, "projected": {"input_tokens": sum(unique_estimates.values()), "output_tokens": len(unique_keys) * config.max_output_tokens, "max_reserved_output_tokens": len(unique_keys) * config.max_output_tokens, "aud": None if projected_aud is None else str(projected_aud), "within_cap": None if projected_aud is None else projected_aud <= config.budget_cap_aud, "status": "missing_bound_snapshots" if projected_aud is None else "projected_from_bound_snapshots"}, "paid_execution": config.execute_paid, "results": [], "human_review": {"denominator_current": REQUIRED_GOLD_COUNT, "required_distribution": {"The Smith Family": 4, "Australian Red Cross Society": 2, "Australian Communities Foundation Limited": 3, "The Fred Hollows Foundation": 3}, "governed_dispositions": HUMAN_GOLD_DISPOSITIONS, "proposed_durable_program_service_subjects": [], "model_output_is_not_gold": True}, "quality": {"status": "pending_human_review", "unsupported_claims": "not automatically adjudicated", "duplicates_or_overfragmentation": "not automatically adjudicated", "apparent_misses": "not automatically adjudicated", "evidence_limited_cases": [], "model_limited_cases": []}}
    report["classie_runtime"] = ({"status": "private_runtime_loaded", "scheme_id": classie_runtime["scheme_id"], "version": classie_runtime["version"], "content_hash": classie_runtime["content_hash"], "source_locator": classie_runtime.get("source_locator"), "source_publisher": classie_runtime.get("source_publisher"), "source_release_date": classie_runtime.get("source_release_date"), "source_sheet": classie_runtime.get("source_sheet"), "original_file_hash": classie_runtime.get("original_file_hash"), "transformation_version": classie_runtime.get("transformation_version"), "transformation_hash": classie_runtime.get("transformation_hash"), "external_scheme_id": classie_runtime.get("external_scheme_id"), "rights_policy": classie_runtime.get("rights_policy"), "publication_eligibility": classie_runtime["publication_eligibility"]} if classie_runtime is not None else {"status": "disabled_not_configured", "scheme_id": None, "version": None, "content_hash": None, "source_locator": None, "source_publisher": None, "source_release_date": None, "source_sheet": None, "original_file_hash": None, "transformation_version": None, "transformation_hash": None, "external_scheme_id": None, "rights_policy": None, "publication_eligibility": "withheld"})
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
        membership_hash = hashlib.sha256("|".join(m.abn for m in members).encode()).hexdigest()
        cohort_spec = {"record_id": cohort_id, "cohort_code": "REALITY-SLICE1", "definition_version": "1", "membership_hash": membership_hash, "budget_cap": {"amount": str(config.budget_cap_aud), "currency": "AUD"}, "created_at": now}
        cohort_row = catalog.get_cohort(cohort_id) or catalog.register_cohort(cohort_spec)
        if (cohort_row["cohort_id"], cohort_row["membership_hash"], Decimal(cohort_row["budget_cap_aud"])) != (cohort_id, membership_hash, config.budget_cap_aud):
            raise RuntimeError("existing Reality Slice cohort conflicts with the frozen definition")
        historical = catalog.get_run(HISTORICAL_RUN_ID)
        historical_report: dict[str, Any] | None = None
        if historical is not None:
            if historical["cohort_id"] != cohort_id:
                raise RuntimeError("historical failed run belongs to an unexpected cohort")
            old_reservation = catalog.get_reservation(HISTORICAL_RESERVATION_ID)
            if old_reservation is not None:
                old_position = catalog.reservation_position(HISTORICAL_RESERVATION_ID)
                if old_position["outstanding"] < 0:
                    raise RuntimeError("historical reservation has negative outstanding exposure")
                if old_position["outstanding"] > 0:
                    catalog.release_reservation(HISTORICAL_RESERVATION_ID, {"amount": old_position["outstanding"], "currency": "AUD"}, now=now, entry_key="reservation-release:historical-reality-slice1")
                old_position = catalog.reservation_position(HISTORICAL_RESERVATION_ID)
            else:
                old_position = {"reserved": Decimal("0"), "actual": Decimal("0"), "released": Decimal("0"), "outstanding": Decimal("0")}
            if historical["status"] in {"planned", "running"}:
                historical = catalog.transition_run(HISTORICAL_RUN_ID, "failed", now=now)
            historical_report = {"run_id": HISTORICAL_RUN_ID, "reservation_id": HISTORICAL_RESERVATION_ID, "final_status": historical["status"], "provider_attempts": 2, "accepted_results": 0, "recorded_provider_cost": "0", "actual_cost": "0", "reservation_position": {key: str(value) for key, value in old_position.items()}, "note": "provider attempts occurred before task-attempt accounting was wired; no synthetic attempts were fabricated"}
        run_instance_id = uuid.uuid4().hex
        run_id = deterministic_id("run:", {"cohort": cohort_id, "spike": SPIKE_VERSION, "configuration": SPIKE_VERSION, "run_instance": run_instance_id})
        configuration_hash = hashlib.sha256(json.dumps({"spike": SPIKE_VERSION, "provider": config.provider_id, "model": config.model_snapshot, "run_instance": run_instance_id}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "economics_spike", "status": "planned", "configuration_hash": configuration_hash, "run_instance_id": run_instance_id, "created_at": now})
        catalog.transition_run(run_id, "running", now=now)
        owner = f"reality-slice1:{run_id}"
        execution_ids = {key: deterministic_id("modeltask:", {"logical_task_id": tasks[key].record_id, "run_id": run_id}) for key in unique_keys}
        unique_tasks = {tasks[key].record_id: tasks[key] for key in unique_keys}
        for key in unique_keys:
            task = tasks[key]
            catalog.register_task({"record_id": execution_ids[key], "run_id": run_id, "subject_id": task.subject_id, "scope_id": task.record_id, "cohort_id": cohort_id, "task_type": task.task_type, "task_schema": task.task_schema.model_dump(), "cache_key": task.cache_key, "provider_id": task.provider_id, "model_snapshot": task.model_snapshot, "created_at": now})
        reservation_id = deterministic_id("reservation:", {"run": run_id, "tasks": sorted(execution_ids.values())})
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(projected_aud), "currency": "AUD"}, "model_task_ids": tuple(execution_ids[key] for key in unique_keys)}, now=now)
        if catalog.budget_position(cohort_id).outstanding_reserved_exposure_aud > config.budget_cap_aud:
            raise RuntimeError("new reservation exceeds the remaining Reality Slice budget")
        pricing_id = pricing_snapshot.record_id
        fx_id = fx_snapshot.record_id
        results_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        failure: dict[str, Any] | None = None
        for key, logical_task in tasks.items():
            pack_hash = bundles[key].evidence_content_hash
            if key != first_for_pack[pack_hash]:
                original_key = first_for_pack[pack_hash]
                original = results_by_key[original_key]
                reused = {"abn": key[0], "tier": key[1], "task_id": logical_task.record_id, "logical_task_id": logical_task.record_id, "execution_task_id": original.get("execution_task_id"), "task_run_id": original["task_run_id"], "output": original["output"], "usage": original["usage"], "actual_aud": "0.000000", "raw_response_ref": original["raw_response_ref"], "validation_status": "reused_exact_evidence_pack", "effective_evidence_pack_hash": pack_hash, "reused_from": {"tier": original_key[1], "task_id": original["task_id"], "task_run_id": original["task_run_id"]}}
                report["results"].append(reused)
                results_by_key[key] = reused
                continue
            execution_task_id = execution_ids[key]
            lease_now = datetime.now(UTC)
            catalog.claim_task(execution_task_id, owner=owner, lease_expires_at=lease_now + timedelta(hours=1), now=lease_now)
            current_task_run_id = deterministic_id("taskrun:", {"task": execution_task_id, "run": run_id, "attempt": 1})
            catalog.begin_task_attempt(execution_task_id, owner=owner, task_run_id=current_task_run_id, now=lease_now, reservation_id=reservation_id)
            attempt_number = 1
            def on_retry(next_attempt: int, error: OpenAIRequestError) -> None:
                nonlocal current_task_run_id, attempt_number
                error_class, error_message = _redacted_provider_error(error)
                catalog.finish_failed_attempt(current_task_run_id, owner=owner, completed_at=datetime.now(UTC), retryable=True, error_class=error_class, error_message_redacted=error_message)
                retry_now = datetime.now(UTC)
                catalog.claim_task(execution_task_id, owner=owner, lease_expires_at=retry_now + timedelta(hours=1), now=retry_now)
                attempt_number = next_attempt
                current_task_run_id = deterministic_id("taskrun:", {"task": execution_task_id, "run": run_id, "attempt": attempt_number})
                catalog.begin_task_attempt(execution_task_id, owner=owner, task_run_id=current_task_run_id, now=retry_now, reservation_id=reservation_id)
            try:
                if provider_call is not None:
                    api = provider_call(logical_task, prompts[key])
                else:
                    api = responses_create(model=config.model_snapshot, input_text=prompts[key], text_format=rich_semantic_output_text_format(permitted_evidence_ids=[segment.evidence_id for segment in bundles[key].source_segments], classie_concept_ids=() if classie_runtime is None else [item["external_concept_id"] for item in classie_runtime["concepts"]], classie_enabled=classie_runtime is not None), max_output_tokens=config.max_output_tokens, on_retry=on_retry)
            except Exception as error:
                error_class, error_message = _redacted_provider_error(error)
                catalog.finish_failed_attempt(current_task_run_id, owner=owner, completed_at=datetime.now(UTC), retryable=False, error_class=error_class, error_message_redacted=error_message)
                failure = {"abn": key[0], "tier": key[1], "logical_task_id": logical_task.record_id, "execution_task_id": execution_task_id, "task_run_id": current_task_run_id, "error_class": error_class, "error_message_redacted": error_message}
                break
            safe_task_run_id = current_task_run_id.replace(":", "_")
            raw_ref = str(root / "responses" / f"{safe_task_run_id}.json")
            Path(raw_ref).parent.mkdir(parents=True, exist_ok=True)
            Path(raw_ref).write_text(api.output_text, encoding="utf-8")
            usage = api.usage
            usd = Decimal(usage.input_tokens or 0) * _snapshot_price(pricing_snapshot, "input_tokens") + Decimal(usage.output_tokens or 0) * _snapshot_price(pricing_snapshot, "output_tokens")
            aud = (usd * fx_snapshot.aud_per_base_unit).quantize(Decimal("0.000001"))
            entry = _cost_entry(cohort_id=cohort_id, run_id=run_id, task_run_id=current_task_run_id, reservation_id=reservation_id, pricing_id=pricing_id, fx_id=fx_id, provider_cost_usd=usd, usage=usage, aud_cost=aud, recorded_at=datetime.now(UTC))
            catalog.record_cost_entry(entry, entry_key=deterministic_id("costledger:", {"task_run": current_task_run_id, "output_hash": hashlib.sha256(api.output_text.encode()).hexdigest()}))
            try:
                output = validate_output(RichSemanticOutput.model_validate(json.loads(api.output_text)), bundles[key], classie_concept_ids=set() if classie_runtime is None else {item["external_concept_id"] for item in classie_runtime["concepts"]})
            except Exception as error:
                error_class, error_message = "output_validation", str(error)[:512]
                catalog.finish_failed_attempt(current_task_run_id, owner=owner, completed_at=datetime.now(UTC), retryable=False, error_class=error_class, error_message_redacted=error_message, result_artifact_id=raw_ref, provider_request_id=api.response_id, usage=usage.__dict__, pricing_snapshot_id=pricing_id, fx_snapshot_id=fx_id)
                failure = {"abn": key[0], "tier": key[1], "logical_task_id": logical_task.record_id, "execution_task_id": execution_task_id, "task_run_id": current_task_run_id, "error_class": error_class, "error_message_redacted": error_message}
                invalid_result = {"abn": key[0], "tier": key[1], "task_id": logical_task.record_id, "logical_task_id": logical_task.record_id, "execution_task_id": execution_task_id, "task_run_id": current_task_run_id, "output": None, "usage": usage.__dict__, "actual_aud": str(aud), "raw_response_ref": raw_ref, "validation_status": "invalid_output", "effective_evidence_pack_hash": pack_hash, "reused_from": None, "originating_attempt_number": attempt_number, "error_class": error_class, "error_message_redacted": error_message}
                report["results"].append(invalid_result)
                results_by_key[key] = invalid_result
                break
            catalog.finish_successful_attempt(current_task_run_id, owner=owner, completed_at=datetime.now(UTC), result_artifact_id=raw_ref, provider_request_id=api.response_id, usage=usage.__dict__, pricing_snapshot_id=pricing_id, fx_snapshot_id=fx_id)
            result = {"abn": key[0], "tier": key[1], "task_id": logical_task.record_id, "logical_task_id": logical_task.record_id, "execution_task_id": execution_task_id, "task_run_id": current_task_run_id, "output": output.model_dump(mode="json"), "usage": usage.__dict__, "actual_aud": str(aud), "raw_response_ref": raw_ref, "validation_status": "valid", "effective_evidence_pack_hash": pack_hash, "reused_from": None, "originating_attempt_number": attempt_number}
            report["results"].append(result)
            results_by_key[key] = result
            review_rows.extend({**row, "originating_tier": key[1], "originating_evidence_pack_hash": pack_hash} for row in build_human_review_proposals(next(m.legal_current_name for m in members if m.abn == key[0]), output))
        independent_results = [(row, _output_metrics(row["output"])) for row in report["results"] if row["validation_status"] == "valid"]
        proposal_count = sum(metrics["proposal_count"] for _, metrics in independent_results)
        assertion_count = sum(metrics["semantic_assertion_count"] for _, metrics in independent_results)
        grounded_count = sum(metrics["grounded_proposition_count"] for _, metrics in independent_results)
        unresolved_count = sum(metrics["unresolved_count"] for _, metrics in independent_results)
        actual_total = sum((Decimal(row["actual_aud"]) for row in report["results"]), Decimal("0"))
        report["economics"]["aggregate"] = {"semantic_assertions": assertion_count, "proposal_count": proposal_count, "credible_proposals": proposal_count, "grounded_propositions": grounded_count, "unresolved_count": unresolved_count, "actual_cost_aud": str(actual_total), "useful_yield": {"grounded_propositions": grounded_count, "proposals_with_evidence": grounded_count, "cost_per_grounded_proposition_aud": None if not grounded_count else str((actual_total / grounded_count).quantize(Decimal("0.000001")))}, "incremental_tier_yield": "computed_from_independent_packs", "quality_effect": "pending_human_review", "human_review_burden": len(review_rows)}
        report["economics"]["actual_by_charity_tier"] = [{"abn": row["abn"], "tier": row["tier"], "actual_aud": row["actual_aud"], "evidence_content_hash": row["effective_evidence_pack_hash"], "reused_exact_evidence_pack": row["validation_status"] != "valid", "proposal_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["proposal_count"], "semantic_assertion_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["semantic_assertion_count"], "grounded_proposition_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["grounded_proposition_count"], "unresolved_count": 0 if row["validation_status"] != "valid" else _output_metrics(row["output"])["unresolved_count"]} for row in report["results"]]
        report["economics"]["incremental_tier_yield"] = [{"tier": tier, "task_count": sum(1 for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), "reused_task_count": sum(1 for row in report["results"] if row["tier"] == tier and row["validation_status"] != "valid"), "actual_cost_aud": str(sum((Decimal(row["actual_aud"]) for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), Decimal("0"))), "proposal_count": sum(_output_metrics(row["output"])["proposal_count"] for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid"), "grounded_proposition_count": sum(_output_metrics(row["output"])["grounded_proposition_count"] for row in report["results"] if row["tier"] == tier and row["validation_status"] == "valid")} for tier in TIERS]
        reservation_position = catalog.reservation_position(reservation_id)
        if reservation_position["outstanding"] > 0:
            catalog.release_reservation(reservation_id, {"amount": reservation_position["outstanding"], "currency": "AUD"}, now=datetime.now(UTC), entry_key=f"reservation-release:{run_id}")
        final_status = "failed" if failure is not None else "succeeded"
        catalog.transition_run(run_id, final_status, now=datetime.now(UTC))
        budget = catalog.budget_position(cohort_id).as_dict()
        report["run_lifecycle"] = {"cohort_id": cohort_id, "cohort_registered_once": True, "run_id": run_id, "run_instance_id": run_instance_id, "run_status": final_status, "reservation_id": reservation_id, "logical_task_count": len(unique_tasks), "execution_task_count": len(unique_tasks), "logical_task_ids": sorted(unique_tasks), "execution_task_ids": sorted(execution_ids.values()), "historical_failed_run": historical_report, "failure": failure, "provider_attempts_recorded": sum(1 for row in report["results"] if row["validation_status"] == "valid") + (0 if failure is None else 1)}
        report["ledger"] = {"database": str(catalog.path), "cohort_id": cohort_id, "run_id": run_id, "reservation_id": reservation_id, "budget_position": budget, "new_reservation_position": {key: str(Decimal("0.000000") if value == 0 else value) for key, value in catalog.reservation_position(reservation_id).items()}}
        report["human_review"]["proposed_durable_program_service_subjects"] = review_rows
        scored_rows = []
        for result in report["results"]:
            if result.get("validation_status") == "valid":
                scored_rows.append({"charity": next(m.legal_current_name for m in members if m.abn == result["abn"]), "output": result.get("output") or {}})
        report["human_review"]["score"] = score_human_gold(scored_rows)
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
    parser.add_argument("--classie-payload-path", default=os.environ.get("CHARITYGRAPH_CLASSIE_PAYLOAD_PATH"))
    parser.add_argument("--classie-expected-version", default=os.environ.get("CHARITYGRAPH_CLASSIE_EXPECTED_VERSION"))
    args = parser.parse_args(argv)
    report = run_spike(SpikeRunConfig(runtime_root=args.runtime_root, execute_paid=args.execute_paid, model_snapshot=args.model, classie_payload_path=args.classie_payload_path, classie_expected_version=args.classie_expected_version))
    print(json.dumps({"task_count": report["task_count"], "source_document_count": report["source_document_count"], "projected": report["projected"], "paid_execution": report["paid_execution"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
