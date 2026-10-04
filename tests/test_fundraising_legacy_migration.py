from datetime import date

from charitygraph.fundraising_legacy_migration import migrate_legacy_fundraising_method
from charitygraph.change_detection import build_change_profile
from charitygraph.models import FundraisingMethodObservation, FundraisingObservationScope


SCOPE = FundraisingObservationScope(
    scope_kind="subject", scope_subject_causebase_id="cb_example", observed_at=date(2026, 10, 4)
)


def migrate(method, *, status="unknown", evidence_ids=("ev_legacy",)):
    return migrate_legacy_fundraising_method(
        FundraisingMethodObservation(method=method, status=status, evidence_ids=list(evidence_ids)),
        observation_id=f"fp_legacy_{method}", scope=SCOPE,
    )


def test_supported_legacy_label_migrates_deterministically_without_extra_axes_or_currentness():
    result = migrate("face_to_face", status="current")

    assert result.disposition == "migrated"
    assert result.practice.canonical_facets == ("fundraising.face_to_face",)
    assert result.practice.lifecycle == "unknown"
    assert result.practice.source_role == "unknown"
    assert result.practice.production_method == "deterministic_derivation"
    assert result.practice.evidence_ids == ["ev_legacy"]
    assert "setting" in result.practice.uncertainty_note


def test_historical_legacy_label_preserves_only_supported_historical_lifecycle():
    result = migrate("direct_mail", status="historical")
    assert result.practice.lifecycle == "historical"
    assert result.practice.canonical_facets == ("fundraising.direct_mail",)


def test_ambiguous_and_evidence_free_legacy_inputs_stay_explicitly_legacy_unknown():
    appeal = migrate("appeals")
    event = migrate("fundraising_events")
    evidence_free = migrate("telephone", evidence_ids=())

    assert appeal.practice is None and appeal.disposition == "retained_legacy_unknown"
    assert "campaign" in appeal.reason
    assert event.practice is None and event.disposition == "retained_legacy_unknown"
    assert evidence_free.practice is None and "no evidence binding" in evidence_free.reason


def test_legacy_list_cannot_drive_the_active_fundraising_change_projection():
    profile = build_change_profile(
        {"fundraising_methods": [{"method": "face_to_face"}]},
        {"fundraising_methods": [{"method": "telephone"}]},
    )
    assert "fundraising" not in profile.changed_dimensions

    typed = build_change_profile(
        {"fundraising_practice_observed": []},
        {"fundraising_practice_observed": [{"observation_id": "fp_legacy_face_to_face"}]},
    )
    assert "fundraising" in typed.changed_dimensions
