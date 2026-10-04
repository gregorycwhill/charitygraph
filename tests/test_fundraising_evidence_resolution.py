from datetime import date

from charitygraph.fundraising_evidence_resolution import (
    FundraisingResolutionClaim, resolve_fundraising_evidence,
)
from charitygraph.fundraising_evidence_roles import FundraisingEvidence


def claim(claim_id, source_id, value="current", *, role="first_party_practice_page", valid_from="2026-01-01", scope="organisation", review="reviewed", wording="We fundraise face-to-face"):
    return FundraisingResolutionClaim(
        claim_id=claim_id, subject_causebase_id="cb_example", claim_kind="practice",
        semantic_key=("fundraising.face_to_face", "lifecycle"), claim_value=value,
        evidence=FundraisingEvidence(
            evidence_id=f"ev_{claim_id}", source_id=source_id, source_role=role,
            locator=f"https://example.test/{source_id}#f2f", source_wording=wording,
            subject_binding="confirmed", binding_basis="named organisation", observed_at=date(2026, 2, 1),
            valid_from=date.fromisoformat(valid_from), scope={"kind": scope},
            production_method="direct_extract", review_status=review, asserted_facets=("practice",),
        ),
    )


def test_duplicate_extractions_are_one_canonical_claim_but_keep_all_evidence_ids():
    result = resolve_fundraising_evidence((claim("one", "page"), claim("two", "page")))
    assert result.duplicate_groups[0].canonical_claim_id == "one"
    assert result.duplicate_groups[0].evidence_ids == ("ev_one", "ev_two")
    assert result.corroborated_claim_ids == ()


def test_independent_sources_corroborate_without_becoming_duplicates():
    result = resolve_fundraising_evidence((claim("one", "page"), claim("two", "report", role="annual_report_statement")))
    assert result.duplicate_groups == ()
    assert result.corroborated_claim_ids == (("one", "two"),)


def test_temporal_and_scope_differences_are_not_presented_as_conflicts():
    temporal = resolve_fundraising_evidence((claim("old", "archive", value="ended", valid_from="2024-01-01"), claim("new", "page")))
    scoped = resolve_fundraising_evidence((claim("org", "page"), claim("program", "report", scope="program")))
    assert temporal.temporal_successor_claim_ids == (("old", "new"),)
    assert temporal.conflicts == ()
    assert scoped.scope_distinct_claim_ids == (("org", "program"),)


def test_same_time_same_scope_conflict_is_inspectable_and_only_reviewed_role_precedence_can_select():
    result = resolve_fundraising_evidence((claim("first_party", "page", value="current"), claim("agency", "case", value="ended", role="agency_provider_case_evidence")))
    conflict = result.conflicts[0]
    assert conflict.resolution == "source_role_precedence"
    assert conflict.preferred_claim_id == "first_party"

    unreviewed = resolve_fundraising_evidence((claim("first_party", "page", value="current", review="not_reviewed"), claim("agency", "case", value="ended", role="agency_provider_case_evidence", review="not_reviewed")))
    assert unreviewed.conflicts[0].resolution == "inspectable_conflict"
    assert unreviewed.conflicts[0].preferred_claim_id is None
