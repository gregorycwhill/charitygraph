"""Fail-closed compatibility adapter for deprecated flat fundraising inputs.

This adapter is deliberately not a prose classifier.  It only carries across
one-to-one legacy labels whose meaning is a standing-practice facet.  Campaign
and mixed-axis labels remain in the legacy quarantine with a machine-readable
reason for review.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import (
    FundraisingMethodObservation,
    FundraisingObservationScope,
    FundraisingPracticeObservation,
)


_ONE_TO_ONE_PRACTICE_FACETS = {
    "regular_giving": "fundraising.regular_giving",
    "face_to_face": "fundraising.face_to_face",
    "direct_mail": "fundraising.direct_mail",
    "telephone": "fundraising.telephone",
    "digital_advertising": "fundraising.digital",
    "major_donor_program": "fundraising.major_gifts",
    "bequest_program": "fundraising.bequests",
    "community_fundraising": "fundraising.community",
    "workplace_giving": "fundraising.workplace_giving",
    "peer_to_peer": "fundraising.peer_to_peer",
    "corporate_partnerships": "fundraising.corporate_partnerships",
    "raffles_or_lotteries": "fundraising.raffles_lotteries",
}

_AMBIGUOUS = {
    "appeals": "may denote a bounded campaign or a standing practice",
    "fundraising_events": "may denote a bounded event/campaign or a standing practice",
    "other": "has no controlled semantic target",
}


@dataclass(frozen=True)
class LegacyFundraisingMigration:
    """One input's outcome; callers must retain every refused legacy input."""

    legacy: FundraisingMethodObservation
    practice: FundraisingPracticeObservation | None
    disposition: str
    reason: str | None = None


def migrate_legacy_fundraising_method(
    legacy: FundraisingMethodObservation,
    *,
    observation_id: str,
    scope: FundraisingObservationScope,
) -> LegacyFundraisingMigration:
    """Make a deterministic, evidence-bounded migration decision.

    A legacy ``current`` label is not copied into typed lifecycle: it lacks the
    source wording and currentness basis required by the F2F/currentness policy.
    It is retained as ``unknown`` with an explicit uncertainty note.  This is a
    compatibility conversion, not new evidence.
    """
    if legacy.method in _AMBIGUOUS:
        return LegacyFundraisingMigration(
            legacy, None, "retained_legacy_unknown", _AMBIGUOUS[legacy.method]
        )
    if not legacy.evidence_ids:
        return LegacyFundraisingMigration(
            legacy, None, "retained_legacy_unknown", "legacy observation has no evidence binding"
        )

    facet = _ONE_TO_ONE_PRACTICE_FACETS.get(legacy.method)
    if facet is None:  # Defensive if the legacy enum expands before this adapter does.
        return LegacyFundraisingMigration(
            legacy, None, "retained_legacy_unknown", "legacy label has no approved deterministic migration"
        )
    lifecycle = "historical" if legacy.status in {"historical", "stale"} else "unknown"
    practice = FundraisingPracticeObservation(
        observation_id=observation_id,
        source_native_phrase=f"Legacy flat fundraising label: {legacy.method}",
        canonical_facets=(facet,),
        scope=scope,
        lifecycle=lifecycle,
        source_role="unknown",
        production_method="deterministic_derivation",
        confidence="low",
        coverage_status="observed",
        uncertainty_note=(
            "Migrated from deprecated flat input; source wording, setting, delivery party, "
            "commitment pattern and currentness remain unasserted."
        ),
        evidence_ids=legacy.evidence_ids,
    )
    return LegacyFundraisingMigration(legacy, practice, "migrated")
