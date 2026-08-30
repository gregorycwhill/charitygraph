"""Baseline Charity Corpus v1: private, immutable source-material manifests.

This module deliberately stops at acquisition and document representation.  It
does not infer charity semantics, create subjects, or emit public cards.
"""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .openai_client import responses_create, estimate_response_cost
from .sources.documents import extract_pdf_evidence


class DiscoveryState(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"
    NOT_ATTEMPTED = "not_attempted"


class AcquisitionState(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    NOT_MODIFIED = "not_modified"
    ABSENT = "absent"
    BLOCKED = "blocked"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class BindingState(StrEnum):
    BOUND = "bound"
    NO_BOUND_RECORD = "no_bound_record"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    NONE = "none"


class MaterialOrigin(StrEnum):
    NEWLY_ACQUIRED = "newly_acquired"
    REUSED_EXISTING = "reused_existing"
    MIXED = "mixed"
    NONE = "none"


class RepresentationReadiness(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"
    NOT_ATTEMPTED = "not_attempted"


class CorpusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CorpusMember(CorpusModel):
    source_family: str
    source_definition_id: str
    acquisition_receipt_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    evidence_locator_ids: tuple[str, ...] = ()
    source_revision: str | None = None
    effective_period: str | None = None
    discovery: DiscoveryState
    acquisition: AcquisitionState
    subject_binding: BindingState
    material_origin: MaterialOrigin
    representation_readiness: RepresentationReadiness = RepresentationReadiness.NOT_REQUIRED
    representation_artifact_ids: tuple[str, ...] = ()
    representation_gaps: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _references(self) -> "CorpusMember":
        if self.acquisition in {AcquisitionState.AVAILABLE, AcquisitionState.PARTIAL} and not self.artifact_ids:
            raise ValueError("available corpus members require immutable artefact references")
        if self.subject_binding == BindingState.BOUND and not self.source_record_ids and not self.evidence_locator_ids:
            raise ValueError("bound corpus members require source-record or evidence-locator references")
        if self.representation_readiness in {RepresentationReadiness.READY, RepresentationReadiness.PARTIAL} and not self.representation_artifact_ids:
            raise ValueError("ready representations require derived artefact references")
        return self


class CorpusManifest(CorpusModel):
    corpus_id: str
    subject_id: str
    corpus_profile_version: str
    material_members: tuple[CorpusMember, ...]
    cohort_id: str | None = None
    run_id: str | None = None
    retrieval_timestamps: tuple[str, ...] = ()
    builder_commit: str | None = None
    derived_representation_ids: tuple[str, ...] = ()
    material_identity_hash: str
    provenance_hash: str

    @model_validator(mode="after")
    def _identity(self) -> "CorpusManifest":
        payload = {
            "subject_id": self.subject_id,
            "corpus_profile_version": self.corpus_profile_version,
            "material_members": [_material_member(member) for member in self.material_members],
        }
        expected = sha256_json(payload)
        if self.material_identity_hash != expected:
            raise ValueError("material_identity_hash must depend only on subject, profile and material members")
        if self.provenance_hash == expected:
            raise ValueError("provenance_hash must remain distinct from material identity")
        return self


class SourceCoverage(CorpusModel):
    source_family: str
    discovery: DiscoveryState
    acquisition: AcquisitionState
    subject_binding: BindingState
    material_origin: MaterialOrigin
    member_count: int = 0
    artifact_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def normalise_host(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(str(value).strip())
    host = parsed.netloc or parsed.path.split("/", 1)[0]
    host = host.split("@")[-1].split(":", 1)[0].casefold()
    return host.removeprefix("www.") or None


def load_v05_cards(card_root: str | Path) -> list[dict[str, Any]]:
    root = Path(card_root)
    cards: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("contract_version") == "0.5" and value.get("causebase_id"):
            cards.append(value)
    return cards


def normalise_v05_subject(card: dict[str, Any]) -> dict[str, Any]:
    identity = card.get("identity") or {}
    return {
        "subject_id": card["causebase_id"],
        "display_name": identity.get("display_name"),
        "legal_name": identity.get("legal_name"),
        "operating_names": tuple(identity.get("operating_names") or ()),
        "website": identity.get("website"),
        "website_domain": normalise_host(identity.get("website")),
        "external_identifiers": tuple(identity.get("external_identifiers") or ()),
        "subject_kind": card.get("subject_kind"),
        "identity_ambiguity_signals": tuple(card.get("identity_ambiguity_signals") or ()),
        "source_record_refs": tuple(card.get("source_record_refs") or ()),
        "evidence": tuple(card.get("evidence") or ()),
        "financial_available": bool(card.get("financial_records") or card.get("financial_metrics") or card.get("funding_sources")),
    }


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.links: list[tuple[str, str]] = []; self._href: str | None = None; self._text: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a": self._href = dict(attrs).get("href"); self._text = []
    def handle_data(self, data: str) -> None:
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href:
            self.links.append((self._href, " ".join(" ".join(self._text).split()))); self._href = None; self._text = []


def enumerate_site_candidates(html: str, base_url: str, *, sitemap_xml: str | None = None) -> list[dict[str, Any]]:
    """Enumerate same-origin candidates mechanically; no lexical filtering."""
    base = urlsplit(base_url); urls: list[str] = [base_url]
    parser = _LinkParser(); parser.feed(html)
    for href, label in parser.links:
        absolute = urljoin(base_url, href.split("#", 1)[0])
        parsed = urlsplit(absolute)
        if parsed.scheme in {"http", "https"} and parsed.netloc.casefold() == base.netloc.casefold():
            urls.append(absolute)
    if sitemap_xml:
        try:
            root = ElementTree.fromstring(sitemap_xml)
            for node in root.iter():
                if node.tag.casefold().endswith("}loc") and node.text:
                    absolute = urljoin(base_url, node.text.strip()); parsed = urlsplit(absolute)
                    if parsed.netloc.casefold() == base.netloc.casefold(): urls.append(absolute)
        except ElementTree.ParseError:
            pass
    unique = list(dict.fromkeys(urls))
    return [{"ordinal": index, "url": url, "label": next((label for href, label in parser.links if urljoin(base_url, href.split("#", 1)[0]) == url), ""), "source": "homepage_navigation" if index else "homepage"} for index, url in enumerate(unique)]


def rank_site_candidates_with_luna(candidates: list[dict[str, Any]], *, subject_name: str, model: str = "gpt-5.6-luna", max_output_tokens: int = 8000, request_fn: Callable[..., Any] = responses_create) -> dict[str, Any]:
    """Ask Luna only for ordinal information-value ranking, never semantics."""
    schema = {"type": "object", "additionalProperties": False, "properties": {"ranked_ordinals": {"type": "array", "items": {"type": "integer"}}}, "required": ["ranked_ordinals"]}
    prompt = "Rank the supplied official-site URL candidates by durable information value across the North Star card. Return only ordinals, preserving every ordinal exactly once. Do not classify, summarise, or infer charity facts. Subject: " + subject_name + "\n" + json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
    result = request_fn(model=model, input_text=prompt, text_format={"type": "json_schema", "name": "site_information_ranking", "strict": True, "schema": schema}, max_output_tokens=max_output_tokens, max_attempts=2, reasoning={"effort": "high"})
    try:
        output = json.loads(result.output_text)
    except json.JSONDecodeError:
        return {"model": result.model, "ranked_ordinals": [], "usage": result.usage.__dict__, "cost_usd": str(estimate_response_cost(result.model, result.usage) or 0), "transport_requests": result.transport_requests, "validation_error": "response was not valid JSON"}
    ranked = output.get("ranked_ordinals", [])
    allowed = {int(item["ordinal"]) for item in candidates}
    if len(ranked) != len(allowed) or set(ranked) != allowed:
        return {"model": result.model, "ranked_ordinals": ranked, "usage": result.usage.__dict__, "cost_usd": str(estimate_response_cost(result.model, result.usage) or 0), "transport_requests": result.transport_requests, "validation_error": "ranking must contain every candidate ordinal exactly once"}
    return {"model": result.model, "ranked_ordinals": ranked, "usage": result.usage.__dict__, "cost_usd": str(estimate_response_cost(result.model, result.usage) or 0), "transport_requests": result.transport_requests}


def _material_member(member: CorpusMember) -> dict[str, Any]:
    """Return only bytes/lineage identity; operational provenance is excluded."""
    return {
        "source_family": member.source_family,
        "source_definition_id": member.source_definition_id,
        "artifact_ids": list(member.artifact_ids),
        "source_record_ids": list(member.source_record_ids),
        "evidence_locator_ids": list(member.evidence_locator_ids),
        "source_revision": member.source_revision,
        "effective_period": member.effective_period,
    }


def build_corpus_manifest(*, subject_id: str, profile_version: str, members: list[CorpusMember], cohort_id: str | None = None, run_id: str | None = None, retrieval_timestamps: tuple[str, ...] = (), builder_commit: str | None = None) -> CorpusManifest:
    material = {"subject_id": subject_id, "corpus_profile_version": profile_version, "material_members": [_material_member(item) for item in members]}
    material_hash = sha256_json(material)
    provenance = sha256_json({**material, "cohort_id": cohort_id, "run_id": run_id, "retrieval_timestamps": retrieval_timestamps, "builder_commit": builder_commit})
    return CorpusManifest(corpus_id=f"corpus:{material_hash}", subject_id=subject_id, corpus_profile_version=profile_version, material_members=tuple(members), cohort_id=cohort_id, run_id=run_id, retrieval_timestamps=retrieval_timestamps, builder_commit=builder_commit, derived_representation_ids=tuple(a for member in members for a in member.representation_artifact_ids), material_identity_hash=material_hash, provenance_hash=provenance)


def represent_pdf(path: str | Path, *, vision_extractor: Callable[[dict], Any] | None = None) -> dict[str, Any]:
    """Run native extraction and retain page gaps; visual escalation is injected."""
    result = extract_pdf_evidence(Path(path), vision_extractor=vision_extractor)
    diagnostics = result["extraction_diagnostics"]
    gaps = sorted(set(diagnostics["low_text_pages"] + diagnostics["image_only_or_scanned_pages"] + diagnostics["visual_relationships_unresolved_pages"]))
    gap_reasons = {
        "low_text": list(diagnostics["low_text_pages"]),
        "image_only_or_scanned": list(diagnostics["image_only_or_scanned_pages"]),
        "visual_relationships_unresolved": list(diagnostics["visual_relationships_unresolved_pages"]),
    }
    readiness = RepresentationReadiness.READY if not gaps else RepresentationReadiness.PARTIAL if result["pages"] else RepresentationReadiness.FAILED
    return {"readiness": readiness.value, "page_gaps": gaps, "gap_reasons": gap_reasons, "native_text_pages": diagnostics["native_text_pages"], "visual_escalations": len(diagnostics["vision_escalations"]), "source_sha256": result["source_sha256"], "page_count": result["page_count"], "extracted_page_count": result["extracted_page_count"], "pages": result["pages"]}



def normalise_entity_label(value: str) -> str:
    """Conservative name key for governed identity candidate comparison."""
    return "".join(ch.casefold() for ch in str(value) if ch.isalnum())


def resolve_wikipedia_candidate(organisation_names: list[str], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Bind only a unique exact source-native title; never compare ABNs."""
    names = {normalise_entity_label(name) for name in organisation_names if str(name).strip()}
    matches = [item for item in candidates if normalise_entity_label(item.get("title", "")) in names]
    if len(matches) == 1:
        return {"status": "bound", "candidate": matches[0], "basis": "unique_exact_source_native_name"}
    if len(matches) > 1:
        return {"status": "ambiguous", "candidates": matches, "basis": "multiple_exact_source_native_names"}
    return {"status": "no_bound_record", "candidates": candidates, "basis": "no_exact_source_native_name"}


def resolve_wikipedia_candidate_with_luna(
    organisation_names: list[str],
    candidates: list[dict[str, Any]],
    *,
    subject_context: dict[str, Any],
    model: str = "gpt-5.6-luna",
    max_output_tokens: int = 8000,
    request_fn: Callable[..., Any] = responses_create,
) -> dict[str, Any]:
    """Ask Luna only for residual Wikipedia entity identity resolution.

    The mechanical exact-title path remains authoritative.  This function is
    deliberately limited to selecting ``bound``, ``ambiguous`` or
    ``no_bound_record`` from the bounded search candidates and identity context;
    it performs no fuzzy matching in Python and never receives article content.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["bound", "ambiguous", "no_bound_record"]},
            "candidate_index": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        },
        "required": ["status", "candidate_index"],
    }
    prompt = (
        "Decide whether one bounded Wikipedia search candidate represents the same registered organisation. "
        "Use only the supplied candidate titles/snippets and identity context. Do not infer from ABN equality, "
        "and do not extract facts. Return bound only with the zero-based candidate_index; use ambiguous when "
        "multiple candidates remain plausible, otherwise no_bound_record.\nIDENTITY:\n"
        + json.dumps({"names": organisation_names, "context": subject_context}, ensure_ascii=False, separators=(",", ":"))
        + "\nCANDIDATES:\n"
        + json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
    )
    result = request_fn(
        model=model,
        input_text=prompt,
        text_format={"type": "json_schema", "name": "wikipedia_entity_resolution", "strict": True, "schema": schema},
        max_output_tokens=max_output_tokens,
        max_attempts=2,
        reasoning={"effort": "high"},
    )
    usage = result.usage.__dict__
    base = {
        "model": result.model,
        "usage": usage,
        "cost_usd": str(estimate_response_cost(result.model, result.usage) or 0),
        "transport_requests": result.transport_requests,
    }
    try:
        output = json.loads(result.output_text)
    except json.JSONDecodeError:
        return {**base, "status": "no_bound_record", "candidate_index": None, "validation_error": "response was not valid JSON"}
    status = output.get("status")
    index = output.get("candidate_index")
    if status not in {"bound", "ambiguous", "no_bound_record"} or (index is not None and (not isinstance(index, int) or index < 0 or index >= len(candidates))):
        return {**base, "status": "no_bound_record", "candidate_index": None, "validation_error": "invalid identity-resolution response"}
    if status == "bound" and index is None:
        return {**base, "status": "no_bound_record", "candidate_index": None, "validation_error": "bound response lacked candidate_index"}
    return {**base, "status": status, "candidate_index": index}


def partition_site_candidates(candidates: list[dict[str, Any]], *, max_output_tokens: int = 8000, max_request_tokens: int = 16000) -> list[list[dict[str, Any]]]:
    """Partition candidates by the configured request/output budget.

    The boundary is derived from serialized request size plus the ordinal output
    estimate, not from a fixed URL-count heuristic. Candidate order is stable.
    """
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for candidate in candidates:
        trial = current + [candidate]
        input_tokens = len(json.dumps(trial, ensure_ascii=False, separators=(",", ":"))) // 4 + 256
        output_tokens = max(1, len(trial) * 4)
        if current and input_tokens + output_tokens > max_request_tokens:
            batches.append(current)
            current = [candidate]
        else:
            current = trial
    if current:
        batches.append(current)
    return batches


def extract_pfra_members(html: str, *, page_role: str, base_url: str = "https://pfra.org.au/") -> list[dict[str, Any]]:
    """Extract one logical PFRA member per role-specific h4 card."""
    parser = _PFRAParser(base_url=base_url, page_role=page_role)
    parser.feed(html); parser.close()
    return parser.records


class _PFRAParser(HTMLParser):
    def __init__(self, *, base_url: str, page_role: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.page_role = page_role
        self.records: list[dict[str, Any]] = []
        self._label: str | None = None
        self._text: list[str] = []
        self._links: list[str] = []
        self._in_heading = False
    def _flush(self) -> None:
        if not self._label: return
        if self._label.casefold() not in {"charity members", "fundraising agency members"}:
            self.records.append({"member_role": self.page_role, "label": self._label, "linked_domains": [urlsplit(link).netloc.casefold().removeprefix("www.") for link in self._links if urlsplit(link).scheme in {"http", "https"}], "source_links": self._links[:]})
        self._label = None; self._text = []; self._links = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"h4", "h3"}:
            self._flush(); self._in_heading = True; self._text = []
        elif tag == "a" and self._label is not None:
            href = dict(attrs).get("href")
            if href: self._links.append(urljoin(self.base_url, href.strip()))
    def handle_data(self, data: str) -> None:
        if self._in_heading: self._text.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"h4", "h3"} and self._in_heading:
            self._label = " ".join(" ".join(self._text).split())
            self._in_heading = False
    def close(self) -> None:
        super().close(); self._flush()


def provider_budget_allows(current_actual: Decimal | str, current_reserved: Decimal | str, projected_maximum: Decimal | str, cap: Decimal | str = Decimal("0.50")) -> bool:
    return Decimal(str(current_actual)) + Decimal(str(current_reserved)) + Decimal(str(projected_maximum)) <= Decimal(str(cap))


def select_filing_documents(documents: list[dict[str, Any]], reporting_period: str) -> list[dict[str, Any]]:
    """Select ACNC filing attachments by structured period/type metadata only."""
    allowed = {"Annual Information Statement": "annual_information_statement", "Annual Report": "annual_report", "Financial Report": "financial_report", "Other Report": "other_narrative_report"}
    selected = []
    for document in documents:
        if str(document.get("Year") or "") != str(reporting_period): continue
        role = allowed.get(str(document.get("type") or ""))
        if role and document.get("Url"): selected.append({"role": role, **document})
    return selected


BASELINE_SOURCE_FAMILIES = ("acnc_register", "acnc_ais_bundle", "ato_abr_dgr", "official_website", "wikipedia_wikimedia", "pfra")
