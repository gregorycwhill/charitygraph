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
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen

from pydantic import Field, field_validator, model_validator

from .contracts.common import SchemaRef, Sha256, StrictModel, VersionedPolicy
from .contracts.economics import CostLedgerEntry, Money
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

    @model_validator(mode="after")
    def _hashes(self) -> "EvidenceBundle":
        material = [segment.model_dump(mode="json") for segment in self.source_segments]
        expected = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if expected != self.bundle_hash:
            raise ValueError("bundle_hash does not match exact evidence segments")
        expected_selection = hashlib.sha256(json.dumps({"tier": self.tier, "segments": [s.evidence_id for s in self.source_segments]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if expected_selection != self.selection_hash:
            raise ValueError("selection_hash does not match deterministic segment selection")
        return self


class SemanticProposal(StrictModel):
    proposal_id: str
    label: str
    kind: str
    durable: bool | None = None
    parent_proposal_id: str | None = None
    description: str | None = None
    evidence_refs: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    confidence: str | None = None
    competing_interpretation: str | None = None
    candidate_observation_refs: tuple[str, ...] = ()

    @field_validator("proposal_id", "label", "kind")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposal identity fields must be nonblank")
        return value


class SemanticAssertion(StrictModel):
    proposition: str
    evidence_refs: tuple[str, ...] = ()
    confidence: str | None = None
    competing_interpretation: str | None = None

    @field_validator("proposition")
    @classmethod
    def _proposition(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposition must be nonblank")
        return value


class RichSemanticOutput(StrictModel):
    """One model response containing independently reviewable logical outputs."""
    programs: tuple[SemanticProposal, ...] = ()
    services: tuple[SemanticProposal, ...] = ()
    projects: tuple[SemanticProposal, ...] = ()
    campaigns: tuple[SemanticProposal, ...] = ()
    organisational_units: tuple[SemanticProposal, ...] = ()
    activities: tuple[SemanticAssertion, ...] = ()
    populations: tuple[SemanticAssertion, ...] = ()
    geographies: tuple[SemanticAssertion, ...] = ()
    sdg_alignments: tuple[SemanticAssertion, ...] = ()
    assertions: tuple[SemanticAssertion, ...] = ()
    semantic_outcome: str = "insufficient_evidence"
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _no_unbound_refs(self) -> "RichSemanticOutput":
        # Evidence binding is checked against the bundle by validate_output;
        # this model intentionally carries no source text or hidden rationale.
        return self


class SourceDocument(StrictModel):
    url: str
    retrieved_at: datetime
    publisher: str
    content_hash: Sha256
    artifact_id: str
    media_type: str
    byte_size: int
    text: str


class SpikeRunConfig(StrictModel):
    runtime_root: str
    provider_id: str = "openai"
    model_snapshot: str = "gpt-5.6-luna"
    execute_paid: bool = False
    max_output_tokens: int = 1800
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
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


def parse_document(body: bytes) -> str:
    """Strip markup mechanically and retain text in source order."""
    parser = _TextParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    # stable adjacent deduplication prevents template repetition without
    # deciding whether any phrase is relevant.
    result: list[str] = []
    for part in parser.parts:
        if not result or result[-1] != part:
            result.append(part)
    return "\n".join(result)


def acquire_documents(runtime_root: str | Path, *, transport: Callable[[str], tuple[bytes, str]] | None = None) -> tuple[SourceDocument, ...]:
    """Acquire only the explicit seven-charity URL plan into private CAS."""
    root = Path(runtime_root).resolve()
    store = ContentAddressedArtifactStore(root / "reality-slice1-llm-semantic-economics", allowed_roots=(root,))
    documents: list[SourceDocument] = []
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
                documents.append(SourceDocument(url=url, retrieved_at=datetime.now(UTC), publisher=member.legal_current_name, content_hash=stored.content_hash, artifact_id=stored.artifact_id, media_type=media_type, byte_size=len(body), text=parse_document(body)))
            except Exception:
                # Denied/unavailable pages remain unacquired; no homepage or
                # semantic fallback is substituted.
                continue
    return tuple(documents)


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
        evidence_id = deterministic_id("evidence:", {"subject_id": subject_id, "url": doc.url, "hash": doc.content_hash, "tier": tier, "ordinal": ordinal})
        rows.append(EvidenceSegment(evidence_id=evidence_id, source_url=doc.url, source_artifact_id=doc.artifact_id, content_hash=doc.content_hash, ordinal=ordinal, text=text))
        used += len(text)
    material = [segment.model_dump(mode="json") for segment in rows]
    bundle_hash = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    selection_hash = hashlib.sha256(json.dumps({"tier": tier, "segments": [s.evidence_id for s in rows]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    bundle_id = deterministic_id("derivative:", {"subject_id": subject_id, "tier": tier, "bundle_hash": bundle_hash})
    return EvidenceBundle(bundle_id=bundle_id, subject_id=subject_id, tier=tier, source_segments=tuple(rows), bundle_hash=bundle_hash, selection_hash=selection_hash)


def semantic_prompt(bundle: EvidenceBundle, charity_name: str) -> str:
    evidence = "\n\n".join(f"[{segment.evidence_id}] SOURCE {segment.source_url}\n{segment.text}" for segment in bundle.source_segments)
    return f"""You are reviewing official source evidence for {charity_name}. Return JSON matching the supplied schema.\n\nDistinguish substantive delivered activity from mission or aspiration, promotional positioning, fundraising/campaign language, claimed outcome, and actual intervention. Propose programs/services/projects only when the evidence supports the distinction; otherwise abstain and record blockers. Include source labels, kind, durability, parent relation, description, aliases, confidence, competing interpretation, and evidence_refs for every proposal. Include operational activities, populations, geographies and scoped SDG alignments only when evidence-bound. Adversarial rules: aspiration is not accomplishment; mission is not delivery; association is not identity; repeated wording is not proof; taxonomy-adjacent vocabulary is not assignment evidence.\n\nEvidence bundle {bundle.bundle_id} (hash {bundle.bundle_hash}, tier {bundle.tier}):\n{evidence}"""


def build_model_task(subject_id: str, bundle: EvidenceBundle, *, provider_id: str, model_snapshot: str) -> ModelTask[Any]:
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-task:1.0", schema_version="1.0")
    output_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:semantic-rich-output:1.0", schema_version="1.0")
    inputs = tuple(EvidenceInput(evidence_id=s.evidence_id, content_hash=s.content_hash, selection_hash=bundle.selection_hash) for s in bundle.source_segments)
    policy_refs = (VersionedPolicy(policy_id=POLICY_ID, version="1"),)
    parameters = {"tier": bundle.tier, "evidence_bundle_hash": bundle.bundle_hash}
    cache_key = model_task_cache_key(task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version="1", policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, material_tool_versions=())
    task_id = deterministic_id("modeltask:", {"subject_id": subject_id, "scope_id": None, "task_type": "semantic_interpretation", "cache_key": cache_key, "output_schema": output_schema})
    return ModelTask(record_id=task_id, created_at=datetime.now(UTC), producer={"kind": "code", "producer_id": "charitygraph-llm-semantic-economics", "version": SPIKE_VERSION}, subject_id=subject_id, task_type="semantic_interpretation", task_schema=task_schema, output_schema=output_schema, evidence_inputs=inputs, prompt_template_id=PROMPT_TEMPLATE_ID, prompt_template_version="1", policy_refs=policy_refs, provider_id=provider_id, model_snapshot=model_snapshot, parameters=parameters, paid_output_categories=("semantic_judgement", "extraction"))

def validate_output(output: RichSemanticOutput, bundle: EvidenceBundle) -> RichSemanticOutput:
    valid = {segment.evidence_id for segment in bundle.source_segments}
    refs: list[str] = []
    for collection in (output.programs, output.services, output.projects, output.campaigns, output.organisational_units, output.activities, output.populations, output.geographies, output.sdg_alignments, output.assertions):
        refs.extend(ref for item in collection for ref in item.evidence_refs)
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
            "candidate_observation_refs": list(proposal.candidate_observation_refs),
            "disposition": "required",
        })
    return rows

def _estimate_tokens(prompt: str) -> int:
    return max(1, (len(prompt.encode("utf-8")) + 3) // 4)


def _cost_entry(*, cohort_id: str, run_id: str, task_run_id: str, reservation_id: str, pricing_id: str, fx_id: str, model_snapshot: str, usage: ApiUsage, aud_cost: Decimal, recorded_at: datetime) -> CostLedgerEntry:
    return CostLedgerEntry(cohort_id=cohort_id, run_id=run_id, task_run_id=task_run_id, reservation_id=reservation_id, pricing_snapshot_id=pricing_id, fx_snapshot_id=fx_id, entry_type="actual", paid_output_category="semantic_judgement", provider_cost=Money(amount=estimate_response_cost(model_snapshot, usage) or Decimal("0"), currency="USD"), aud_cost=Money(amount=aud_cost, currency="AUD"), usage=ProviderUsage(input_tokens=usage.input_tokens or 0, output_tokens=usage.output_tokens or 0), recorded_at=recorded_at)


def run_spike(config: SpikeRunConfig, *, transport: Callable[[str], tuple[bytes, str]] | None = None) -> dict[str, Any]:
    members = development_members()
    if {m.abn for m in members} != {"28000030179", "50169561394", "20077830347", "22007498482", "15000002522", "28004778081", "46070556642"}:
        raise RuntimeError("development cohort does not match the frozen seven")
    documents = acquire_documents(config.runtime_root, transport=transport)
    bundles = {(member.abn, tier): build_evidence_bundle(member.subject_id, tier, [doc for doc in documents if doc.publisher == member.legal_current_name]) for member in members for tier in TIERS}
    tasks = {(abn, tier): build_model_task(next(m.subject_id for m in members if m.abn == abn), bundle, provider_id=config.provider_id, model_snapshot=config.model_snapshot) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
    prompts = {(abn, tier): semantic_prompt(bundle, next(m.legal_current_name for m in members if m.abn == abn)) for (abn, tier), bundle in bundles.items() if bundle.source_segments}
    estimates = {key: _estimate_tokens(prompt) for key, prompt in prompts.items()}
    projected_usd = sum((Decimal(tokens) * Decimal("0.20") / Decimal(1_000_000) + Decimal(config.max_output_tokens) * Decimal("1.20") / Decimal(1_000_000) for tokens in estimates.values()), Decimal("0"))
    projected_aud = (projected_usd * Decimal(os.environ.get("CHARITYGRAPH_USD_AUD_RATE", "1.50"))).quantize(Decimal("0.000001"))
    if projected_aud > config.budget_cap_aud:
        raise RuntimeError(f"projected paid cost {projected_aud} AUD exceeds cap {config.budget_cap_aud} AUD")
    root = Path(config.runtime_root).resolve() / "reality-slice1-llm-semantic-economics"
    root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"version": SPIKE_VERSION, "private": True, "development_abns": [m.abn for m in members], "holdout_firewall": {"enforced": True, "holdout_model_tasks": 0}, "tiers": list(TIERS), "task_count": len(tasks), "source_document_count": len(documents), "evidence_bundles": {f"{key[0]}:{key[1]}": bundle.model_dump(mode="json") for key, bundle in bundles.items()}, "projected": {"input_tokens": sum(estimates.values()), "output_tokens": len(tasks) * config.max_output_tokens, "aud": str(projected_aud), "within_cap": projected_aud <= config.budget_cap_aud}, "paid_execution": config.execute_paid, "results": [], "human_review": {"denominator_current": 1, "proposed_durable_program_service_subjects": [], "model_output_is_not_gold": True}}
    report["economics"] = {"by_charity_tier": [{"abn": key[0], "tier": key[1], "estimated_input_tokens": estimates[key], "estimated_output_tokens": config.max_output_tokens, "estimated_aud": str((Decimal(estimates[key]) * Decimal("0.20") / Decimal(1_000_000) + Decimal(config.max_output_tokens) * Decimal("1.20") / Decimal(1_000_000)) * Decimal(os.environ.get("CHARITYGRAPH_USD_AUD_RATE", "1.50"))) } for key in sorted(prompts)], "production_equivalent": {"status": "not_configured", "discount_assumed": False}, "aggregate": {"semantic_assertions": 0, "credible_proposals": 0, "grounded_propositions": 0, "incremental_yield": "pending_human_review", "quality_effect": "pending_human_review", "human_review_burden": "pending_paid_run"}}
    review_rows: list[dict[str, Any]] = []
    if config.execute_paid and not tasks:
        raise RuntimeError("paid execution requires at least one evidence-bound task")
    if config.execute_paid:
        # Reservation is created before the first call.  A fresh DB is private
        # runtime state; no model call can occur through this path otherwise.
        catalog = SQLiteCatalog(root / "ledger.sqlite3").open(initialize=True)
        now = datetime.now(UTC)
        cohort_id = deterministic_id("cohort:", {"spike": SPIKE_VERSION, "members": [m.abn for m in members]})
        run_id = deterministic_id("run:", {"cohort": cohort_id, "spike": SPIKE_VERSION})
        catalog.register_cohort({"record_id": cohort_id, "cohort_code": "REALITY-SLICE1", "definition_version": "1", "membership_hash": hashlib.sha256("|".join(m.abn for m in members).encode()).hexdigest(), "budget_cap": {"amount": str(config.budget_cap_aud), "currency": "AUD"}, "created_at": now})
        catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "economics_spike", "status": "planned", "configuration_hash": hashlib.sha256(SPIKE_VERSION.encode()).hexdigest(), "created_at": now})
        for task in tasks.values():
            catalog.register_task({"record_id": task.record_id, "run_id": run_id, "subject_id": task.subject_id, "cohort_id": cohort_id, "task_type": task.task_type, "task_schema": task.task_schema.model_dump(), "cache_key": task.cache_key, "provider_id": task.provider_id, "model_snapshot": task.model_snapshot, "created_at": now})
        reservation_id = deterministic_id("reservation:", {"run": run_id, "tasks": sorted(t.record_id for t in tasks.values())})
        catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(projected_aud), "currency": "AUD"}, "model_task_ids": tuple(t.record_id for t in tasks.values())}, now=now)
        pricing_id = deterministic_id("pricing:", {"model": config.model_snapshot, "spike": SPIKE_VERSION})
        fx_id = deterministic_id("fx:", {"rate": os.environ.get("CHARITYGRAPH_USD_AUD_RATE", "1.50"), "spike": SPIKE_VERSION})
        for key, task in tasks.items():
            task_run_id = deterministic_id("taskrun:", {"task": task.record_id, "run": run_id})
            api = responses_create(model=config.model_snapshot, input_text=prompts[key], text_format={"type": "json_schema", "name": "rich_semantic_output", "strict": True, "schema": RichSemanticOutput.model_json_schema()}, max_output_tokens=config.max_output_tokens)
            output = validate_output(RichSemanticOutput.model_validate(json.loads(api.output_text)), bundles[key])
            raw_ref = str(root / "responses" / f"{task_run_id}.json")
            Path(raw_ref).parent.mkdir(parents=True, exist_ok=True); Path(raw_ref).write_text(api.output_text, encoding="utf-8")
            usage = api.usage
            usd = estimate_response_cost(config.model_snapshot, usage) or Decimal("0")
            aud = (usd * Decimal(os.environ.get("CHARITYGRAPH_USD_AUD_RATE", "1.50"))).quantize(Decimal("0.000001"))
            entry = _cost_entry(cohort_id=cohort_id, run_id=run_id, task_run_id=task_run_id, reservation_id=reservation_id, pricing_id=pricing_id, fx_id=fx_id, model_snapshot=config.model_snapshot, usage=usage, aud_cost=aud, recorded_at=datetime.now(UTC))
            catalog.record_cost_entry(entry, entry_key=deterministic_id("costledger:", {"task_run": task_run_id, "output_hash": hashlib.sha256(api.output_text.encode()).hexdigest()}))
            report["results"].append({"abn": key[0], "tier": key[1], "task_id": task.record_id, "task_run_id": task_run_id, "output": output.model_dump(mode="json"), "usage": usage.__dict__, "actual_aud": str(aud), "raw_response_ref": raw_ref, "validation_status": "valid"})
            review_rows.extend(build_human_review_proposals(next(m.legal_current_name for m in members if m.abn == key[0]), output))
        report["ledger"] = {"database": str(catalog.path), "cohort_id": cohort_id, "run_id": run_id, "reservation_id": reservation_id, "budget_position": catalog.budget_position(cohort_id).as_dict()}
        catalog.close()
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
