from decimal import Decimal

import pytest

from charitygraph.phase5_cost_cap import (
    ELIGIBLE_UNDER_CURRENT_CAP,
    EXCLUDED_COST_CAP,
    partition_cost_cap_requests,
)


def test_v12_remainder_is_mechanically_partitioned_13_eligible_3_excluded():
    amounts = ["0.077264", "0.065313", "0.081849", "0.059615", "0.092924", "0.058057",
               "0.462635", "0.053737", "0.076230", "0.078235", "0.062564", "0.300608",
               "0.269531", "0.059630", "0.065215", "0.048400"]
    rows = [{"provider_request_item_id": f"requestitem:{i:064x}",
             "subject_id": f"subject:{i:032x}", "corrected_hard_max_aud": amount,
             "semantic_content": "ignored by cost-only partition"} for i, amount in enumerate(amounts)]
    eligible, excluded = partition_cost_cap_requests(rows)
    assert len(eligible) == 13
    assert len(excluded) == 3
    assert {row["classification"] for row in eligible} == {ELIGIBLE_UNDER_CURRENT_CAP}
    assert {row["classification"] for row in excluded} == {EXCLUDED_COST_CAP}
    assert {Decimal(row["corrected_hard_max_aud"]) for row in excluded} == {
        Decimal("0.269531"), Decimal("0.300608"), Decimal("0.462635")}


def test_cost_partition_rejects_duplicate_or_invalid_ids_and_amounts():
    with pytest.raises(ValueError, match="unique"):
        partition_cost_cap_requests([
            {"provider_request_item_id": "requestitem:dup", "corrected_hard_max_aud": "0.1"},
            {"provider_request_item_id": "requestitem:dup", "corrected_hard_max_aud": "0.1"},
        ])
    with pytest.raises(ValueError, match="finite"):
        partition_cost_cap_requests([{"provider_request_item_id": "requestitem:x", "corrected_hard_max_aud": "NaN"}])
