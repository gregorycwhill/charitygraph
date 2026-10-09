"""Private CG353 comparison contract; orchestration and scoring only.

This module deliberately does not interpret evidence text.  It freezes the
inputs and output shapes for a later Luna-provider measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .compact_knowledge import CompactKnowledgeOutputV02
from .ethos_notability_extraction import CandidateBundle

EXPERIMENT_ID = "CG-UNIFIED-SEMANTIC-EXTRACTION-353"
MODEL = "gpt-5.6-luna"
ARMS = ("A_general_baseline", "B_dedicated_ethos_notability", "C_unified_general_plus_ethos_notability")
METRICS = (
    "supported_precision", "supported_recall", "unsupported_positive", "scope_transfer",
    "current_historical_confusion", "source_role_error", "temporal_error", "qualification_loss",
    "section_16_17_leakage", "event_dedupe_lineage_error", "missingness_abstention",
    "provenance_defect", "malformed_reject_rate", "human_review_burden_proxy",
    "input_tokens", "output_tokens", "calls", "usd_per_organisation",
)


def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UnifiedSemanticOutput(_Strict):
    """C-arm output: existing general atoms plus separate §15/§17 candidates."""
    general: CompactKnowledgeOutputV02
    ethos_notability: CandidateBundle


UNIFIED_SCHEMA = UnifiedSemanticOutput.model_json_schema()


class FrozenCase(_Strict):
    model_config = ConfigDict(extra="ignore", frozen=True)
    case_id: str
    subject_id: str
    arm: Literal["challenge", "blind"]


class CohortManifest(_Strict):
    model_config = ConfigDict(extra="ignore", frozen=True)
    cases: tuple[FrozenCase, ...]

    def validate_split(self) -> None:
        if len(self.cases) != 15 or sum(c.arm == "challenge" for c in self.cases) != 10 or sum(c.arm == "blind" for c in self.cases) != 5:
            raise ValueError("CG352 cohort must remain exactly 10 challenge and 5 blind cases")
        if len({c.case_id for c in self.cases}) != 15:
            raise ValueError("cohort case IDs must be unique")


@dataclass(frozen=True)
class ExperimentFreeze:
    cohort_sha256: str
    corpus_sha256: str
    baseline: Mapping[str, str]
    unified_schema_sha256: str
    metric_spec_sha256: str


def freeze_contract(cohort: Mapping[str, Any], corpus: Mapping[str, Any]) -> ExperimentFreeze:
    manifest = CohortManifest.model_validate(cohort)
    manifest.validate_split()
    if corpus.get("cohort_sha256") != canonical_hash(cohort):
        raise ValueError("frozen corpus does not bind this exact cohort")
    if corpus.get("provider_calls") != 0 or corpus.get("candidate_outputs_present") is not False:
        raise ValueError("corpus is not a pre-semantic frozen evidence corpus")
    # Compact v0.2 is the existing general production-shaped contract.  The
    # dedicated contract identity is intentionally recorded, not copied.
    baseline = {
        "general_contract": "compact-knowledge-v0.2",
        "general_schema_sha256": canonical_hash(CompactKnowledgeOutputV02.model_json_schema()),
        "dedicated_contract": "ethos-notability-extraction-v1",
        "dedicated_model": MODEL,
    }
    return ExperimentFreeze(canonical_hash(cohort), str(corpus.get("corpus_sha256") or canonical_hash(corpus)), baseline, canonical_hash(UNIFIED_SCHEMA), canonical_hash(METRICS))


def runnable_cases(cohort: Mapping[str, Any], *, final_holdout: bool = False) -> tuple[FrozenCase, ...]:
    """Keep blind controls unread until an explicitly final validation run."""
    manifest = CohortManifest.model_validate(cohort)
    manifest.validate_split()
    return tuple(c for c in manifest.cases if final_holdout or c.arm == "challenge")


def enforce_spend(ledger: Mapping[str, Any], proposed_usd: str, *, cap_usd: str = "2.00") -> Decimal:
    """Mechanical cumulative-cap guard; callers append only after a response."""
    spent = sum((Decimal(str(x.get("cost_usd", "0"))) for x in ledger.get("entries", ())), Decimal("0"))
    proposed, cap = Decimal(proposed_usd), Decimal(cap_usd)
    if spent + proposed > cap:
        raise ValueError("provider call would exceed the authorised cumulative spend cap")
    return cap - spent - proposed


def score_rows(rows: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    """Aggregate pre-labelled review outcomes without inferring semantics."""
    counts = {metric: 0 for metric in METRICS}
    for row in rows:
        for metric in METRICS:
            value = row.get(metric, 0)
            if metric in {"input_tokens", "output_tokens", "calls"}:
                counts[metric] += int(value)
            elif metric == "usd_per_organisation":
                counts[metric] += float(value)
            else:
                counts[metric] += int(bool(value))
    orgs = len({row.get("case_id") for row in rows})
    return {"rows": len(rows), "organisations": orgs, "metrics": counts,
            "usd_per_organisation": counts["usd_per_organisation"] / orgs if orgs else 0.0}
