# Fundraising cleanroom rebuild record — 5 October 2026

**Status:** Local engineering verification record. It creates no acquisition,
production-ingestion, public-release, public-contract, or Viewer authority.

## Result

The fundraising query projection at `ecc9dff` was not clean-worktree
buildable: it imported `fundraising_joint_coverage`, while both that module and
its deterministic fixture existed only as untracked files in the shared
checkout. The projection also required the governed fundraising observation
models that were uncommitted in that checkout. A cleanworktree recovery commits
those already-authored governed inputs rather than introducing new semantics.

The focused provider-free fundraising suite was run twice with
`PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`: **56 passed** on both runs, with no
worktree changes between runs. The full provider-free suite was then run with
an isolated pytest base directory: **519 passed, 1 skipped** in 27.92 seconds.

## Cache and performance disposition

`28c0ef4` contains the approved, integrity-checked source-acquisition cache,
but it is not an ancestor of `ecc9dff`; it was therefore deliberately not
silently combined with this cleanroom repair. Integrating that cache remains a
separate, explicit ancestry/review step. This verification made no network or
provider calls, so it does not claim a source-cache hit-rate benchmark.

The observed rebuild blocker was accidental omission of required tracked
projection inputs, now fixed. The relevant deterministic regression exercises
the bounded query projection and its non-attribution state, rather than
benchmarking or expanding source acquisition.
