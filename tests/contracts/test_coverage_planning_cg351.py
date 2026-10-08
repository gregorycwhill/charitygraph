from charitygraph.coverage_planning import CoverageAssessment, route_coverage_gap


def test_gap_states_remain_distinct_and_opportunity_dedupes():
    common = dict(subject_id="subject:1", section_id=15, claim_family="ethos", reason="central assessment")
    first = CoverageAssessment(**common, state="not_found_in_assessed_captures", assessed_source_scope=("retained:v1",))
    second = CoverageAssessment(**common, state="source_family_not_captured", assessed_source_scope=("retained:v1",))
    one = route_coverage_gap(first, desired_source_family="organisation_self_report")
    two = route_coverage_gap(second, desired_source_family="organisation_self_report")
    assert first.state != second.state
    assert one.opportunity_id == two.opportunity_id
    assert "url" not in one.model_dump()


def test_notability_empty_path_does_not_call_provider():
    from charitygraph.ethos_notability_extraction import run_notable_history_extraction
    from charitygraph.retained_capture import RetainedCaptureUniverse

    class FailingProvider:
        def extract(self, **kwargs):
            raise AssertionError("provider must not be called")

    result = run_notable_history_extraction(RetainedCaptureUniverse(subject_id="subject:1", permitted_scope_ids=("scope:1",)), FailingProvider())
    assert result["handoff"]["coverage_assessment"]["state"] == "not_found_in_assessed_captures"
    assert result["handoff"]["source_opportunity"]["section_id"] == 17
