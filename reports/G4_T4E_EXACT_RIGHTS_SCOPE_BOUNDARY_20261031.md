# Gate 4 T4E exact-rights and scope-boundary follow-up

Date: 2026-10-31 (Australia/Sydney)  
Worker: bounded G4-O1C, provider-free  
Branch/HEAD: `gate3-cg406-remediation` / `d41fd766e8e5d9c1f9e63d17b30350c956bbcfc2`  
Fence: v68 / `e06d652988383909e72cf59367c8d4e290c9a9778407e72c644bae4a8c103ea3`

## Result

**PARTIAL follow-up.** The scope and coverage gaps are closed in the bounded
T4D adapter/test seam. Exact committed T3 rights authority remains explicitly
blocked because no independently inspectable current rights store/projection
for the ten committed rights IDs was available. No rights ID, policy, version,
representation hash, or eligibility state was rewritten.

## Implemented boundary

- `phase5_t4d_e3_factory_handoff.py` now rejects a physical package that has
  missing or mixed `scope_id` values before the returned plan can be seeded.
  The diagnostic retains the distinct source-record/representation identities.
- The handoff summary carries all 20 E3 North Star entries and the five
  `source_silent` currentness records unchanged. It does not upgrade coverage
  or missingness.
- The synthetic authorized internal-policy fixture is explicitly separate from
  the exact T3 authority test.
- The exact T3 test reads
  `evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json` unchanged:
  ten rows, five subjects, policy
  `CG_PUBLIC_SOURCE_PRIVATE_PROVIDER_TRANSMISSION_V1` v1.0.0,
  `bound_not_task_eligible`, and
  `blocked_provider_contract_not_bound`. With an empty rights store, all ten
  rows produce bounded `blocked` diagnostics and zero tasks; no synthetic
  authorization is substituted.

## Verification

Tests ran from a `git archive` of the exact HEAD with only the two allowed
source/test files overlaid, using `python -B` and `-p no:cacheprovider`:

- focused T4D: **31 passed** in 126.86s;
- clean relevant regression set (T4B/T4C/Factory/governed Factory/governed
  rights): **50 passed** in 20.37s.

The focused run covers synthetic zero-work/replay, exact-rights unavailable
diagnostics, all 20 coverage statuses and five source-silent records, mixed
scope rejection, same-scope distinct-source acceptance, and existing zero
provider/reservation/cost assertions.

## Authority, hashes and side effects

- committed T3 selected manifest identity:
  `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9`;
- exact T3 authority status remains ineligible; the available
  `evidence/cg406-rights-catalog-resolution` material is a different CG406
  corpus and was not used as T3 authority;
- source `phase5_t4d_e3_factory_handoff.py` SHA-256:
  `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8`;
- test `test_phase5_t4d_e3_factory_handoff.py` SHA-256:
  `f0a0ca3d0f18d6817c37d64f02edadfdfbf467ededc74d409a7e450d4e50a0bc`.

No provider/model call, network access, source acquisition, spend, reservation,
publication, release, watcher/process action, Drive operation, GitHub mutation,
or public/private raw-material addition occurred. The pre-existing dirty
Factory, governed-Factory, rights, T4A2 and other paths were preserved.

T4D may advance only as a **partial/conditional** acceptance: scope-boundary
and E3-carriage evidence is stronger, but full exact-rights acceptance and any
Gate 4 closure remain blocked until the ten current T3 rights records and
projection are independently inspectable. This worker did not operate the
bridge or create a commit; supervisor-owned direct-child adoption is required.
