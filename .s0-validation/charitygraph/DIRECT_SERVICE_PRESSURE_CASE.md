# Phase 3 direct-service pressure case

**Status:** Bounded implementation tranche; no provider execution
**Case:** Australian Red Cross Society (ABN 50 169 561 394)

This first case was selected from the existing development corpus. It combines
first-party service and participation material, the 2025 ACNC filing/report
bundle, a large official website, and an exact PFRA-linked membership record.
It therefore exercises organisation, service/program and relationship scope
without consuming an untouched holdout. The case is a pressure test, not a
claim that sections 6, 11 or 13 are complete.

## Evidence inventory

The inventory records what the frozen corpus can support before semantic
interpretation. No private source body, prompt or model output is copied here.

| Candidate proposition | North Star section | Scope to preserve | Evidence/source role | Existing Builder primitive | Method | Distinction that must survive |
| --- | --- | --- | --- | --- | --- | --- |
| Volunteer/member opportunity or role | 6 Participation | Organisation or named program/service | Official website; annual report | Observation, scope, evidence locator | Model-assisted interpretation after deterministic packet assembly | Advertised opportunity is not an actual participation measure |
| Participation aggregate, where explicitly reported | 6 Participation | Organisation/reporting period | Annual report | Observation with value/unit/time | Structured extraction or model validation | Measure is distinct from opportunity or enduring role |
| Service offer, eligibility and access pathway | 11 Capability, capacity, access & availability | Named service/program/site | Official website; annual report | Observation, scope, evidence locator | Model-assisted interpretation | Service existence does not establish current availability |
| Location, catchment, opening or fee condition | 11 Capability, capacity, access & availability | Service/site | Official website | Observation, scope, temporal fields | Model-assisted interpretation | Access conditions are not capacity or delivered output |
| Capacity or constraint measure, if explicitly reported | 11 Capability, capacity, access & availability | Organisation, service or reporting period | Annual report | Observation with value/unit/time | Structured extraction or model validation | Capacity is not activity, output or outcome |
| PFRA membership or scheme status | 13 Memberships, schemes, registrations & accreditations | Organisation | PFRA directory | Relationship/observation, source lineage | Deterministic source-native preservation | Membership does not prove capability, compliance or quality |
| Program/service accreditation or registration, if explicitly evidenced | 13 Memberships, schemes, registrations & accreditations | Program/service or organisation as evidenced | Official site; filing/report | Observation, scope, evidence locator | Model-assisted interpretation with source-native scheme fields | Program scope must not become organisation scope |
| Partner, funder, sponsor, auspice or network relationship | Cross-domain graph substrate | Lowest evidenced subject/scope | Official site; report; PFRA | RelationshipStatement with PR #36 role | Model-assisted interpretation, structural validation | Role direction and ownership are not propagated |

Sparse or unavailable propositions remain explicit coverage states; no value is
invented to fill a North Star field. The semantic task may be added after the
deterministic fixtures and review gate are complete. This tranche does not run
Luna, Terra or Sol and does not acquire or publish new source material.
