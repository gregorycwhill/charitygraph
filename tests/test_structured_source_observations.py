from datetime import datetime, timezone

from charitygraph.structured_source_observations import deterministic_structured_observations


def test_structured_projection_is_deterministic_and_preserves_source_date():
    payload = {"data": {"Abn": "123", "DateEstablished": "2021-03-30T13:00:00Z", "Status": "Registered"}}
    kwargs = dict(subject_id="subject:abc", source_record_id="srcrec:def", evidence_locator_ids=("evloc:1",), observed_at=datetime(2026, 9, 2, tzinfo=timezone.utc))
    first = deterministic_structured_observations(payload, **kwargs)
    second = deterministic_structured_observations(payload, **kwargs)
    assert first == second
    established = next(x for x in first if x["predicate"] == "established_at")
    assert established["effective_date"] == "2021-03-30"
    assert established["source_record_ids"] == ("srcrec:def",)
