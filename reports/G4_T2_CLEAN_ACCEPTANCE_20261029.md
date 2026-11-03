# Gate 4 T2 clean factory supervisory acceptance

Date: 2026-10-29 (Australia/Sydney)
Decision: **ACCEPT — bounded T2 control-plane evidence only**
Target: `cef0e792d8826697db735216be9b3f918c7e44ff`
Fence: v44

## Commit and boundary

Independent Git inspection confirms that HEAD is a single direct child of
`700cfe1f4e576e00471155a6bfedbcc40fc36cab`. The parent-to-HEAD diff is exactly
these three added paths, 703 lines total:

- `reports/G4_T2_CLEAN_RECONSTRUCTION_20261029.md`
- `src/charitygraph/phase5_governed_cohort_rehearsal.py`
- `tests/test_phase5_governed_cohort_rehearsal.py`

HEAD tree: `856954af6ecd36a3a96ba65b053bbe808de5a558`.
The three Git blob identities are
`54e081d39d52e52d0eb001a33fd59def1cc09217`,
`093164a8ce2015052e1744adbdfaa04cd26ffb1c`, and
`f99d004fbb6bcc48b798f002e1dcd1ab55415a35`, respectively. No dirty or
quarantined path is in the bridge commit. The
checkout's pre-existing modified and untracked paths, including the dirty
`artifact_rights_*` prototype seam, remained outside this diff and were not
staged, committed, copied, or used as authority.

The reconstruction report's statement that the worker could not create
`.git/index.lock` is historical evidence from the parent checkout. It is
consistent with the current bridge-owned result: the later bridge commit is
the exact-path direct child above, with the bridge commit message and reflog
entry, and is the authority for the completed commit attestation. This review
does not treat the worker's failed staging attempt as evidence that the
commit was absent.

## Independent clean replay

An exact read-only `git archive` of HEAD was extracted to an OS temporary
directory and run from that archive root with:

```text
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src
python -m pytest -p no:cacheprovider -o addopts= --basetemp <OS-temp> -ra tests/test_phase5_governed_cohort_rehearsal.py
```

Result: **6 passed, 0 skipped, 0 xfailed**. The accepted run's root directory
was the archive, so no dirty checkout import was involved. The six tests
independently cover deterministic task/request identity, T1B/v29 authority
lowering, denial and projection mismatch with zero runtime side effects,
item-failure isolation, batch planning with zero batch sends, ambiguous-send
holding and reconciliation without resend, replay with no new fake send and
stable diagnostic SHA, and reservation/actual/release accounting.

The fixture is explicitly TEST-labelled and uses only synthetic
`example.invalid` material. It creates no external calls, acquisition,
provider request, model request, spend, publication, or network activity.
The fake provider is an observable wrapper around the existing clean fake
receipt seam; it does not add a second Factory or rights authority.

The fresh successful replay independently observed these identities:

- model task: `modeltask:4bd41da86ad2abe400acc5a7b787c24b154dce4c77fc211c5c19e443efc83793`
- task run: `taskrun:be9ecf1fba874d2f93f9c71a8f087c2fec3acd1c33565bb9b32f1c795be5ae30`
- physical attempt: `physical:fb35da8de397cbb23642aec10bdd5f7b11cf705d6b4fc6db42ca811a131f38bc`
- provider receipt: `fake-receipt:99d81e641b31cf613acfac6457a8211337cec6a0caa6afe664a6354d807926af`
- reservation: `reservation:133291d28e270ba78015b4b28ec29062e0ec354959f58375fc2fb21926d3d398`
- cost keys: `actual:<reservation>` and `release:<reservation>`; actual AUD `0.002000`
- fresh diagnostic SHA: `26d2636fe6c965bb0c27890b9730edb148cc12dadfdd1d1c0d2d795f8fc568ad`

The diagnostic SHA is stable on replay within the same run/state, as asserted
by the focused test. Its serialized provenance includes the temporary
catalog path, so a different temporary root can legitimately produce a
different cross-run SHA; the prior report's SHA is therefore not treated as
a required byte identity for this independent run.

The clean import probe found no `rights_decision_ids` field, no
`get_artifact_rights_decisions` catalog method, v29
`rights_projection_current`, and no `artifact_rights_*` SQLite tables. This
matches the accepted T1B governed-rights seam and excludes the dirty
side-installed rights prototype.

## Findings and limits

`git diff --check` on the bridge commit reports three pre-existing trailing
spaces in the committed reconstruction report and one final blank-line
warning in the committed test. This is a minor commit-hygiene finding, not a
failed focused behavioural test; no repair was made because this task is
report-only.

This is synthetic T2 control-plane evidence. It does not establish T3 real
rights determinations, real subject/source eligibility or binding, provider
readiness or provider-side exactly-once behaviour, semantic quality,
monitoring/SLOs, publication, release, or Gate 4 closure.

## Risk-limited next step

Under the Product Owner default-approve-authorised-sources policy, retain this
as bounded T2 evidence only. The next permissible step is a separately
authorised, no-send T3 binding review over one immutable governed cohort and
its exact rights/source/receipt lineage. Any provider crossing remains blocked
until Product Owner/Data authority supplies the exact source-owned provider
policy identity/version and per-run budget reservation; no discovery,
acquisition, spending, publication, release, watcher, GitHub, or follow-on
dispatch is authorised by this report.
