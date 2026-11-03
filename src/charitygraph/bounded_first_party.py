"""Mechanical closure checks for a bounded first-party acquisition campaign.

This module deliberately does not read source prose.  A caller supplies the
category-to-attempt bindings made by central acquisition; this code only checks
that each fixed subject/category pair reaches an explicit, evidenced terminal
state and that captured material has replayable content-addressed lineage.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


CATEGORIES = (
    "annual_or_financial_reports", "about", "mission_values", "history",
    "programs_services", "impact_results", "governance_leadership",
    "policies_codes_safeguarding_inclusion", "affiliations_accreditations",
    "strategy", "news_campaigns", "research_evaluation_publications",
)
TERMINAL_STATES = {"CAPTURED", "ABSENT", "UNAVAILABLE", "NOT_APPLICABLE"}
ALLOWED_FAMILIES = {"acnc_regulator", "charity_authored", "wikipedia_revision_pinned", "pfra"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class CoverageError(ValueError):
    pass


def _capture_replayable(attempt: dict[str, Any], root: Path) -> bool:
    raw_hash, rep_hash = attempt.get("raw_sha256"), attempt.get("representation_sha256")
    if not isinstance(raw_hash, str) or not isinstance(rep_hash, str):
        return False
    raw = root / "raw" / raw_hash
    rep = root / "representations" / f"{rep_hash}.json"
    return raw.is_file() and rep.is_file() and hashlib.sha256(raw.read_bytes()).hexdigest() == raw_hash and hashlib.sha256(rep.read_bytes()).hexdigest() == rep_hash


def freeze_completeness(*, cohort: dict[str, Any], attempts: Iterable[dict[str, Any]], coverage: Iterable[dict[str, Any]], archive_root: Path) -> dict[str, Any]:
    """Validate and freeze a category matrix without interpreting English text."""
    cases = {row["case_id"]: row for row in cohort["per_charity_inventory"]}
    rows = list(coverage)
    matrix = {(r.get("case_id"), r.get("category")): r for r in rows}
    expected = {(case_id, category) for case_id in cases for category in CATEGORIES}
    if set(matrix) != expected:
        raise CoverageError("coverage matrix must contain exactly every fixed charity/category pair")
    attempts = list(attempts)
    for item in attempts:
        if item.get("source_class") not in ALLOWED_FAMILIES:
            raise CoverageError("unauthorised source family in acquisition attempts")
        if item.get("status") == "captured" and not _capture_replayable(item, archive_root):
            raise CoverageError("captured material is not offline replayable")
    attempt_ids = {a.get("attempt_id") for a in attempts}
    for key, row in matrix.items():
        if row.get("terminal_state") not in TERMINAL_STATES:
            raise CoverageError(f"non-terminal coverage state for {key}")
        evidence = row.get("attempt_ids")
        if not isinstance(evidence, list) or not evidence or not set(evidence) <= attempt_ids:
            raise CoverageError(f"coverage row lacks retained attempt evidence for {key}")
    counts = Counter((a.get("case_id"), a.get("source_class"), a.get("status")) for a in attempts)
    result = {
        "contract": "bounded-first-party-completeness-v1",
        "cohort_sha256": cohort["freeze"]["cohort_sha256"],
        "categories": list(CATEGORIES), "coverage_matrix": rows,
        "attempt_totals": [{"case_id": k[0], "source_family": k[1], "status": k[2], "count": v} for k, v in sorted(counts.items())],
        "provider_calls": 0, "prohibited_sources_used": False,
        "all_categories_terminal": True,
    }
    result["corpus_completeness_sha256"] = sha256(result)
    return result
