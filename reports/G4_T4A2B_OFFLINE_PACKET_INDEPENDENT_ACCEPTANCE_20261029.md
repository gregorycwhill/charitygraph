# G4 T4A2B offline packet — independent acceptance

Date: 2026-10-29 (Australia/Sydney)  
Reviewed HEAD: `1d23ff731f768414c3936494727c92a450167907`  
Parent: `372ca4183ee9511d99e3c06bab1a5c17bf0aa4b5`  
Fence: `v52`  
Disposition: **ACCEPT — provider-free internal offline packet only.** Gate 4 remains open; this is not real-send authorization or Gate 4 closure.

## Commit and exact files

The direct-child diff is exactly three added paths, `411` insertions, with no
deletions. `git diff --check` is clean. Git blob SHA-1, exact-content SHA-256,
and line counts are:

| path | Git blob | SHA-256 | lines |
|---|---|---|---:|
| `reports/G4_T4A2B_SINGLE_SUBJECT_OFFLINE_PACKET_20261029.md` | `c39520e0a5be191337b50b25ebc851d2f42a16e4` | `a1b64667af14ce5de426e3c131dfbc95acf22e1b6d424447e3826363a0287709` | 70 |
| `src/charitygraph/phase5_t4a_single_subject_offline_packet.py` | `9a4db5d99d731833a0d3ef0e8f272c7b81e9539a` | `2bfe994fb7f04916eed4a97863761916e8bf32ffa2b2f4eb2e3af2893d3b53b3` | 250 |
| `tests/test_phase5_t4a_single_subject_offline_packet.py` | `e9967185947a5a4c48a81a370f4860b0c3e70603` | `d25c28fff11e307df13c565fbdcb79271990ce02e31832aa70dd1c15d34feae2` | 91 |

The pre-existing checkout baseline was 10 modified and 91 untracked status
entries. None changed during this review; the required report is the only new
repository path. Candidate source/test paths remain clean against HEAD.

## Product acceptance findings

The packet selects the one retained governed subject
`subject:02649cdcb42049bb8dedd30f2333e150` and its registered-entity scope,
with exactly two distinct retained ACNC records: register record
`srcrec:4978c7ff7f9694d9d9d6db9ad871a8048cde5940c6e699a2dd4bd15360bcd28d`
and AIS record
`srcrec:554fa9df1414f0096b9035fea5ac5eee7ffb59e46eb767d6306d40d8f326f08a`.
The source identity includes acquisition receipts, source artifacts, source
hashes, distinct derived representation artifacts/hashes, evidence locators and
rights records (`phase5_t4a_single_subject_offline_packet.py:97-114`). The
retained T3 manifest and source-evidence provenance are checked before packet
construction (`:171-194`); no source body is emitted.

The semantic contract is selected from the current registry entry and resolved
with that entry’s declared schema/planner/prompt versions, so the current
`1.2` / `1.2-section-discriminated` contract is not carried as a stale literal
(`phase5_t4a_single_subject_offline_packet.py:57-79`, registry
`phase5_semantic_contracts.py:400-417`). Deterministic IDs and canonical SHA-256
content addressing cover the packet identity (`:208-248`). Source, schema,
subject, representation and rights inconsistencies produce typed diagnostics;
the tests cover deterministic replay, schema mismatch, subject/representation
drift and zero catalogue side effects (`tests/test_phase5_t4a_single_subject_offline_packet.py:41-91`). No natural-language Python heuristic or synthetic source provenance was added.

Offline readiness is correctly separated from send authority: the packet records
provider contract `unbound`, `send_authorization: not_authorized_for_send`,
semantic output `not_attempted`, public redistribution `not_assessed`, and
zero provider calls, transport requests, reservations, costs, acquisitions and
publications (`phase5_t4a_single_subject_offline_packet.py:241-245`). This
matches the T3/T4A authority: source-owned provider-contract identity/version
remains missing, and the prior builder report’s `4 passed/1 failed` pre-correction
run was not treated as acceptance.

## Verification and boundary

One focused invocation was run exactly as requested, with `-B`,
`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, empty `addopts`, and an
external basetemp:

`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_phase5_t4a_single_subject_offline_packet.py -p no:cacheprovider -o addopts= --basetemp C:\CharityGraph-runtime\g4-t4a2b-independent-acceptance-20261029 -ra`

Result: **5 passed, 0 failed.** No provider, transport, credential, budget,
network, source acquisition, publication, Drive/GitHub, watcher, staging,
commit, release or gate operation occurred. The report contains no private
source body or runtime payload.
