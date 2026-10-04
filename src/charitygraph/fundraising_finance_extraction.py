"""Deterministic adapters for source-supported fundraising finance rows.

This is intentionally a narrow adapter: callers must supply the source's
chosen financial meaning.  Labels such as ``marketing`` are never promoted to
fundraising expenditure here.  The output retains a locator and all the
dimensions needed by the compatibility and derivative gates.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .finance_measurement import FundraisingMoneyMeasurement
from .fundraising_finance_source_contract import FundraisingFinanceSourceObservation
from .sources.documents import parse_money_observation


EXTRACTION_CONTRACT_VERSION = "1.0"
ExtractionOutcome = Literal["observed", "not_found_in_scoped_source", "not_processed", "unavailable"]


class FundraisingFinanceExtraction(BaseModel):
    """One adapter result, including explicit source-scoped non-results."""
    contract_version: str = EXTRACTION_CONTRACT_VERSION
    outcome: ExtractionOutcome
    observation: FundraisingFinanceSourceObservation | None = None
    source_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    missingness_note: str | None = None

    @model_validator(mode="after")
    def require_one_honest_outcome(self):
        if self.outcome == "observed":
            if self.observation is None or self.missingness_note:
                raise ValueError("observed extraction requires an observation only")
        elif self.observation is not None or not self.missingness_note:
            raise ValueError("non-observed extraction requires a reason and no observation")
        return self


def _period(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for key in ("period_start", "period_end"):
        if isinstance(result.get(key), str):
            result[key] = date.fromisoformat(result[key])
    return result


def normalise_fundraising_finance_row(row: dict[str, Any]) -> FundraisingFinanceExtraction:
    """Normalise one reviewed structured/PDF table row without label heuristics.

    ``coverage_status`` may express a scoped absence.  For an observed row,
    the adapter requires an explicit ``measure_kind`` and all provenance
    fields; this makes an unsupported source label fail closed rather than be
    guessed from nearby wording.
    """
    outcome = row.get("coverage_status", "observed")
    source_id = str(row.get("source_id", ""))
    locator = str(row.get("source_locator", ""))
    if outcome != "observed":
        return FundraisingFinanceExtraction(
            outcome=outcome, source_id=source_id, source_locator=locator,
            missingness_note=row.get("missingness_note") or "No supported fundraising finance observation was extracted from this scoped source.",
        )

    raw_value = row.get("raw_value")
    if raw_value is None:
        raise ValueError("observed fundraising finance row requires raw_value")
    amount = parse_money_observation(
        str(raw_value), currency=row.get("currency", "AUD"),
        unit_scale=Decimal(str(row.get("unit_scale", 1))), unit_label=row.get("unit_label"),
    )
    measurement = FundraisingMoneyMeasurement(
        observation_id=row["measurement_id"], amount=amount,
        measure_kind=row["measure_kind"], source_wording=row["source_native_wording"],
        evidence_ids=row["evidence_ids"], period=_period(row["period"]),
        reporting_scope=row["reporting_scope"],
        reporting_subject_causebase_id=row.get("reporting_subject_causebase_id"),
        consolidation_scope_id=row.get("consolidation_scope_id"),
        recognition_basis=row.get("recognition_basis", "unknown"),
        gross_net_basis=row.get("gross_net_basis", "unknown"),
        gst_treatment=row.get("gst_treatment", "unknown"),
        pass_through_treatment=row.get("pass_through_treatment", "unknown"),
        cost_attribution=row.get("cost_attribution", "not_applicable"),
        allocation_basis=row.get("allocation_basis"),
        allocation_method=row.get("allocation_method", "unknown"),
        amount_is_approximate=row.get("amount_is_approximate"),
        source_role=row.get("source_role", "unknown"), assurance=row.get("assurance", "unknown"),
        fundraising_activity_id=row.get("fundraising_activity_id"),
        aggregation_set_id=row.get("aggregation_set_id"), component_is_disjoint=row.get("component_is_disjoint", False),
    )
    observation = FundraisingFinanceSourceObservation(
        observation_id=row["observation_id"], measurement=measurement,
        source_family=row["source_family"], source_id=source_id, source_locator=locator,
        source_native_wording=row["source_native_wording"], subject_binding_basis=row["subject_binding_basis"],
        scope_kind=row["scope_kind"], scope_id=row["scope_id"], component_treatment=row["component_treatment"],
        production_method=row.get("production_method", "deterministic_parsing"),
        review_status=row.get("review_status", "automation_governed"), coverage_status="observed",
        observed_on=date.fromisoformat(row["observed_on"]) if row.get("observed_on") else None,
        valid_from=date.fromisoformat(row["valid_from"]) if row.get("valid_from") else None,
        valid_to=date.fromisoformat(row["valid_to"]) if row.get("valid_to") else None,
        geography=row.get("geography"), setting=row.get("setting"),
    )
    return FundraisingFinanceExtraction(outcome="observed", observation=observation, source_id=source_id, source_locator=locator)
