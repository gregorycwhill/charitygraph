from __future__ import annotations

from decimal import Decimal

from .models import FundraisingEstimate, MoneyObservation


def _fixture_observation(value: object) -> MoneyObservation:
    amount = Decimal(str(value))
    return MoneyObservation(
        source_amount=amount,
        source_currency="AUD",
        source_unit_scale=1,
        normalised_amount=amount,
        normalised_currency="AUD",
        source_raw_value=str(value),
    )


def estimate_fundraising(source: dict) -> FundraisingEstimate | None:
    """Return an evidence-backed estimate, or ``None`` when unavailable.

    Fundraising expenditure has no universal prior or peer-imputation fallback.
    """
    financials = source["financials"]
    period_value = financials.get("period", {})
    period = period_value if isinstance(period_value, str) else period_value.get("label")
    financial_record_id = financials.get("financial_record_id")
    fr = source.get("fundraising", {})

    direct = fr.get("direct")
    if direct is not None:
        return FundraisingEstimate(
            normalised_amount=Decimal(str(direct["value"])),
            normalised_currency="AUD",
            reporting_period_label=period,
            financial_record_id=financial_record_id,
            method="direct_extract",
            confidence="high",
            evidence_ids=list(direct.get("evidence_ids", [])),
            direct_observation=_fixture_observation(direct["value"]),
            note="Explicit fundraising expenditure disclosed by the organisation.",
        )

    # Labels are not an attribution rule.  A generic card builder cannot turn
    # marketing, events, public-relations, or donor-acquisition rows into a
    # fundraising amount: their source-native scope and component treatment
    # must be governed by the typed finance path before any reconstruction or
    # bounds can be considered.
    return None
