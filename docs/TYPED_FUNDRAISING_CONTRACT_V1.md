# Typed fundraising contract v1

`CauseBaseCard` now has three canonical, versioned assertion collections:

- `fundraising_practice_observed: list[FundraisingPracticeObservation]` for a standing practice;
- `fundraising_campaign_observed: list[FundraisingCampaignObservation]` for a named, bounded appeal or campaign; and
- `fundraising_provider_relationships: list[FundraisingProviderRelationship]` for a directed relationship to an existing `provider_causebase_id`.

Funding source remains `funding_sources`, and aggregate fundraising expenditure remains
`fundraising_expenditure`. Neither is adapted into a practice or campaign, and no
method/campaign expenditure attribution is represented by this contract.

Every typed assertion carries its schema version, source-native phrase (where relevant),
candidate vocabulary facets, scope/geography, valid and observed time, lifecycle,
source role, production method, confidence/uncertainty, coverage status, and evidence IDs.
`fundraising-practice-v1` permits multiple facets only across different axes. For
example, F2F solicitation, a regular-giving programme, private-site placement,
recurrence, direct debit and acquisition can coexist; F2F and telephone cannot be
asserted in the same practice observation because they occupy the same axis.

Representative payload:

```json
{
  "schema_version": "fundraising-practice-v1",
  "observation_id": "fp_f2f_regular",
  "source_native_phrase": "F2F regular giving recruitment",
  "canonical_facets": ["fundraising.face_to_face", "fundraising.regular_giving"],
  "scope": {"scope_kind": "subject", "scope_subject_causebase_id": "cb_example", "geography": ["AU"], "observed_at": "2026-02-01"},
  "lifecycle": "current",
  "source_role": "direct_assertion",
  "production_method": "direct_extract",
  "coverage_status": "observed",
  "evidence_ids": ["ev_fundraising"]
}
```

`FundraisingProviderRelationship` requires explicit subject and provider roles and wraps
the common `SubjectRelationship` (including its resolved target CauseBase ID); no agency
relationship is inferred from F2F evidence. Its scope must bind to the containing charity,
and the embedded relationship evidence must be retained by the wrapper. `subject_role` is
the containing charity's role, while `provider_role` is the resolved target's role; this is
a directed relationship, not an organisation-wide practice assertion.

The containing card rejects repeated provider assignments with the same resolved target,
provider role and scope, even if supplied with different IDs or client/commissioner roles.
Repeated observations at different `observed_at` times are still the same assignment for
this check. A campaign and provider case may coexist with zero standing-practice
observations; no round-trip projection promotes either into a practice.
It also validates evidence IDs in both the fundraising wrapper and the embedded common
relationship. This fails closed rather than choosing between contradictory role assertions.

## Compatibility

`FundraisingMethodObservation` and `CauseBaseCard.fundraising_methods` remain readable
for historical payloads, but the field is marked deprecated in JSON Schema. There is no
lossy automatic migration: its flat values mix axes and cannot safely become typed
assertions. `project_fundraising` projects only the three typed collections, preserving
their lifecycle and coverage/missingness states unchanged.
