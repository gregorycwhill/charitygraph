from __future__ import annotations

from decimal import Decimal

from .models import FundraisingComponent, FundraisingEstimate, MoneyObservation


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
    """Legacy display helper; canonical finance facts use the typed adapters.

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

    # Do not turn marketing, PR, events, or donor acquisition wording into a
    # canonical fundraising cost.  Older demo heuristic outputs are quarantined.
    return None
