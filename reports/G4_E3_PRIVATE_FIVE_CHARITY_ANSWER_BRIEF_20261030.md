# Gate 4 E3 independent technical and semantic product acceptance

Date: 2026-10-30 (Australia/Sydney)
Disposition: **PARTIAL — not Gate 4 closure**

## Scope and identity

Reviewed local branch `gate3-cg406-remediation` at exact HEAD
`beb2765e2136e9b11bd0610767e4f9ee6ac4b735`, whose direct parent is
`6442e9abdc39d40d55b1653a1b98b24dfa78821b`. The supplied supervisor fence is
`v64`, SHA-256
`5c69de1c6eb282f239e8e84dba835ffcbe3f59fa19f22ac6597aac1e73e504a6`;
that fence value was not found in local repository evidence, so its external
provenance is not independently reproducible here.

The exact parent-to-HEAD diff is the requested three paths only:

- `src/charitygraph/phase5_t4c_private_answer_brief.py`
- `tests/test_phase5_t4c_private_answer_brief.py`
- this E3 report

`git diff --check` for that direct-child diff is clean. The worktree was already
dirty before this review: 11 tracked status entries and 112 untracked entries.
They were preserved; no code, test, source/rights, manifest, Git, watcher or
host-process state was changed other than this report.

## Verification result

Focused local command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m pytest -p no:cacheprovider -o addopts= tests/test_phase5_t4c_private_answer_brief.py tests/test_phase5_t4b_source_answer_projection.py -q
19 passed in 0.77s
```

The actual local composition produced 5 subjects, 15 answer slots, 10 unique
representation hashes, 20 North Star coverage entries, five source-native
activity/scale pairs, and five unanswered currentness slots. Reporting periods
and field-basis locators are retained in citation-bearing values. Replay was
deterministic and all declared side-effect counters were zero.

The implementation is mechanically bounded: E3 composes only accepted E2B
records (`phase5_t4c_private_answer_brief.py:231-262, 344-409`), and E2B reads
only the supplied manifest and ten exact content-addressed JSON files, checking
the bytes, ABN and source type (`phase5_t4b_source_answer_projection.py:350-383`).
No provider/model/network, acquisition, SQLite/WAL, budget, publication,
release, GitHub or watcher effect was observed. No unrestricted prose heuristic
or discovery path is introduced.

## Semantic and product acceptance

PASS for the core private answer boundary:

- Supported values are selected from explicit source-native structured fields,
  marked `fact`, and retain subject, scope, source family, source record, exact
  representation SHA, reporting period/date and field basis
  (`phase5_t4b_source_answer_projection.py:423-531`;
  `phase5_t4c_private_answer_brief.py:28-70`).
- The comparison is mechanical and explicitly non-ranking. The two ACNC
  representations are kept as separate source-family records; their agreement
  is not treated as independent corroboration.
- The output carries all 20 coverage sections with per-subject status and
  explicit boundaries (`phase5_t4c_private_answer_brief.py:207-227, 315-341`).
  The coverage is honest partial/unassessed coverage, not North Star completion.
- No current giving, capacity, effectiveness, governance or conduct/adverse
  conclusion is fabricated.

Currentness missingness is substantively correct: each slot is
`answer_state="unanswered"`, `answer=None`, `missingness.status="not_established"`,
and `source_silence_is_not_absence=True`
(`phase5_t4b_source_answer_projection.py:387-418`). The value
`fact_vs_source_statement_vs_inference="not_applicable"` is only the epistemic
basis label for a slot with no answer, not the serialized missingness status.
This does not currently assert substantive inapplicability, but the terminology
is easy to misread and must remain distinct from true `not_applicable` coverage
under `ARCHITECTURE.md:216` and `BUILDER_MACHINERY.md:30`.

## Acceptance defect: source-role and rights metadata drift

The requested output does **not** contain explicit `source_role` values. E2B's
`SourceCitation` and `AnswerRecord` expose `source_family` but no role field
(`phase5_t4b_source_answer_projection.py:158-199`), and E3 copies that reduced
envelope (`phase5_t4c_private_answer_brief.py:28-70`). The governed T3 manifest
does contain `register_identity` and `annual_information_statement` roles
(`evidence/gate4-t3-five-subject-v1/selected-binding-manifest.json:38,66`).

An independent in-memory tamper probe changed one row at a time, recomputed the
manifest self-hash, and observed that `_validate_rows()` accepted changes to
`source_role`, `rights_policy_id`, `rights_policy_version`, and
`provider_processing_status`. The validator enforces the source-record,
subject/scope, representation-hash and rights-record tuple
(`phase5_t4b_source_answer_projection.py:293-347`), but not those additional
rights/role fields. This is a real fail-closed identity/rights drift gap, not a
test-environment limitation.

## Prioritised next bounded product-value task

Harden the same provider-free five-subject path by reloading or hash-anchoring
the governed T3 row authority, carrying explicit `source_role`, rights policy
ID/version and relevant processing/publication statuses into E2B/E3, and
rejecting tampering of each field. Add focused negative tests for those four
drifts, plus an explicit North Star v0.3 contract/version identifier in the
coverage document. Keep the currentness state as `unanswered`/
`not_established`; reserve substantive `not_applicable` for genuine scoped
non-applicability and test that distinction.

Until that bounded repair is complete, the private five-charity answer brief is
technically useful and reproducible but not independently acceptable as a
fully role- and rights-bound product answer. No Gate 4 closure, publication,
release, provider spend or follow-on dispatch is claimed.
