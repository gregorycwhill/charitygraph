# G4 T4E host recovery integration design

Date: 2026-10-31 (Australia/Sydney)
Target: `gate3-cg406-remediation@354619c30b5fe85c2a4d513b111315c432524fc6`, fence `v73`
Worker: bounded G4-O1C, read-only architecture review

## Decision

**GO for a dormant, host-owned dry-run design only. NO-GO for live adoption or
branch CAS in the current checkout.** No bridge, watcher, Git metadata, source,
provider, Drive or process action was performed.

The supplied candidate bytes are present as the two tracked dirty paths and
match the independent pins:

| path | SHA-256 |
|---|---|
| `src/charitygraph/phase5_t4d_e3_factory_handoff.py` | `e243efc54186a61f47ed092a4c1b7de43586f8459f17561961a1a99f028f67c8` |
| `tests/test_phase5_t4d_e3_factory_handoff.py` | `38f8f4871b317b76a0ca9d4aa7f55900431a16ba812cc6d3775c304176fb81c7` |

The dormant helper and validator have independently accepted focused tests
(9 and 28 respectively). The independent reconciliation records the final
clean-overlay result as 32 focused and 50 regression tests, while preserving
the source execution as `CODEX_EXECUTION_TIMEOUT`; it does not upgrade that
timeout to success. Exact current T3 rights authority remains blocked.

## What the current code proves

The existing bridge has one managed launcher, one adapter ledger and one claim
path. Ingress is restricted to `cg-g4-o1b-instruction-*.json`; engineering
admission requires the exact `charitygraph.autonomous-instruction/v1` envelope,
ChatGPT authority object, target repository/workspace/branch/HEAD, and a fresh
report path (`bridge/bridge.py:609-730`; `src/charitygraph/autonomous_loop.py:72-168`).
The launcher and watcher require an active fence whose workspace, branch and
HEAD exactly match the live checkout (`bridge/managed_launcher.py:51-80`;
`bridge/bridge.py:488-500`). Claims, leases and expired-lease ambiguity remain
in the durable local ledger; the watchdog refuses recovery when a claim or
ledger uncertainty exists (`bridge/managed_watchdog.py:24-49`).

Ordinary bounded commits reject a pre-dirty or staged allowlisted path. The
adoption route is narrower still: it only accepts a newly created untracked
file from a completed, verified, non-quarantined bridge result on an ancestor
of the current HEAD (`src/charitygraph/bounded_authority.py:278-335`;
`bridge/bridge.py:732-845`). It cannot adopt either tracked T4E path. The
bridge-owned commit also requires exact paths, one direct child and no
pre-existing dirty path (`bridge/bridge.py:847-942`;
`src/charitygraph/bounded_authority.py:461-511`).

`g4_clean_target_commit.py` is correctly dormant and defaults to
`dry_run=True`. It validates a canonical manifest, separate source anchor and
candidate bytes, then builds and byte-checks one direct child in a disposable
clone (`:254-303`, `:375-399`). Its repaired non-dry-run path accounts for
imported objects, avoids `FETCH_HEAD` writes, uses expected-old ref CAS and
never unlinks objects after CAS failure (`:400-468`). The helper accepts a
separate clean target, so it does not need to read candidate bytes from the
live worktree.

That is not sufficient for live adoption. With `isolated_target` supplied,
the helper still CASes the branch ref in `repository` (`:364-373`, `:432-452`)
without updating that repository's checked-out worktree or index. The accepted
dirty-main test proves preservation of existing bytes and staged entries; it
does not prove checkout/index coherence after HEAD moves
(`tests/test_g4_clean_target_commit.py:122-149`). Therefore:

- a CAS in the current dirty repository would move the branch while leaving
  the live checkout/index at the old tree;
- a CAS in a separate clean clone can be internally safe, but the clone's
  checkout/index also needs host re-materialisation before it is a coherent
  working target; and
- a CAS in that clone does not adopt the live repository. Transferring the
  result to the live branch would recreate the same incoherence and is not
  authorised by the current bridge.

The structural validator is intentionally non-actionable. Its dynamic
context/policy epoch and exact artifact allowlist are useful checks, but
`TrustedRecoveryPins` is caller-constructible and `RecoveryHostReadback` is
explicitly rejected until an authenticated host integration exists
(`src/charitygraph/g4_clean_target_recovery_authority.py:80-185`, `:327-363`).
The current independent acceptance therefore accepts the dormant validator,
not bridge authority.

## Required host-authenticated provenance chain

The future host route must construct this chain from host-read bytes, never
from caller-supplied hashes or a public URL:

1. The supervisor creates one new immutable ingress instruction using the
   existing canonical envelope and exact authority object. The bridge records
   the raw instruction bytes and SHA-256, claims it once, and binds its
   `instruction_id`/`content_sha256` to the target HEAD and fence `v73`.
2. The host reads the prior result by exact immutable artifact identity and
   recomputes its bytes/hash. It must be terminal
   `CODEX_EXECUTION_TIMEOUT`, with zero provider calls, no source acquisition,
   `publication=false`, `semantic_product_work=NOT_PERFORMED`, and no commit.
   It must never be treated as a successful worker result or replayed.
3. The host reads a separate independent reconciliation report and separate
   reconciliation result, recomputes both hashes, and requires their identity
   to differ from the timeout result. The report may explain the 32/50
   clean-overlay evidence, but its prose is not authority.
4. The host reads the exact v73 fence bytes and current status/ledger bytes,
   verifies their local hashes and exact repository/workspace/branch/HEAD
   identity, and rejects an active claim, stale lease, ledger-unavailable
   state, stale fence or alternate workspace.
5. The host obtains an immutable candidate-byte package containing exactly the
   two files, plus canonical manifest and source-anchor bytes. It recomputes
   every byte hash, checks the independently pinned values above, and passes
   those bytes to the helper. Reading or staging the ordinary dirty paths is
   not a substitute for this package.
6. The host verifies the helper result: exact two-path allowlist, source HEAD
   as parent, one non-merge direct child, proposed-tree bytes equal to the
   independently anchored bytes, and `dry_run=True` with no object import or
   ref update in the first tranche.

The Drive-synced file or public Drive URL is only a transport locator. It is
not an authority root. The current envelope's `source=chatgpt` field and a
caller-created frozen pins object are also declarations, not signatures. The
irreducible missing trust root is a bridge-owned, immutable provenance record
that authenticates the raw instruction/result/fence/reconciliation/test and
candidate-byte reads as one host observation. Without that record, matching
hash strings can be self-attested and the validator must remain blocked.

## Smallest bounded tranche

The smallest feasible tranche is a new host-only dormant route, not a worker
route and not `provenance_bound_adoption`:

- proposed ingress operation: `g4_t4e_clean_target_recovery_dry_run`;
- transport: the existing `charitygraph.autonomous-instruction/v1` immutable
  instruction and one-claim ledger, with canonical content schema
  `charitygraph.g4-t4e-recovery-request/v1`;
- proposed bridge entrypoint: a host method such as
  `CutoverWatcher._process_t4e_clean_target_recovery_dry_run`, dispatched from
  `_process_candidate` only after exact admission. It must call the structural
  validator and `create_clean_target_commit(..., dry_run=True)` directly; it
  must never launch Codex or write `.git` metadata from the worker sandbox;
- repository commit allowlist for any later separately authorised commit:
  exactly the two candidate paths above. No report, evidence directory,
  unrelated dirty path or index entry is allowlisted. Dry-run diagnostics and
  provenance belong in private runtime/artifact result surfaces, not Git;
- first-tranche result: `DRY_RUN_ONLY`, with `action=NONE`, no ref update, no
  fence creation, no watcher restoration and no live adoption.

The bounded code tranche would be limited to the bridge host adapter and its
tests; the already accepted dormant helper/validator need not be changed.
Tests must cover exact ingress/claim identity, authenticated-byte binding,
timeout non-upgrade, v73/workspace/HEAD mismatch, public-URL rejection as
authority, forged pins/readback, dirty or ignored clean-target rejection,
manifest/anchor/candidate tampering, zero dry-run Git mutations, and
preservation of a synthetic unrelated dirty/index baseline. A second test
must prove that a non-dry-run CAS cannot be reported as complete while its
checked-out worktree/index is stale.

## Rollout and failure policy

1. Implement and independently accept the host readback/provenance record and
   dormant dry-run route.
2. Run it once against a supervisor-provisioned clean target and inspect the
   private result. Any missing byte, mismatched identity, dirty target, active
   claim, stale fence, timeout-state mismatch, or helper validation failure is
   terminal `BLOCKED`; do not retry or replay automatically.
3. A later tranche may materialise the proposed commit in a new clean
   canonical workspace and create a new exact fence, but only after separate
   independent acceptance. It must leave the current dirty checkout and index
   untouched. There is **NO LIVE ADOPTION without separate independent
   acceptance** and an explicit worktree/index-coherence design.

If object import succeeds but CAS fails, retain the helper's object-import
attestation and do not unlink or run GC/prune. If CAS succeeds but the target
checkout is not re-materialised, treat the result as incomplete and do not
create a fence. No failure mode authorises reset, overwrite, ordinary dirty
path adoption, provider work, publication, release or gate closure.

## Final disposition

The minimum safe action today is to keep both dormant surfaces dormant and
prepare only the host-owned dry-run tranche described above. A separately
provisioned clean target can safely construct and inspect a proposed commit;
the current helper cannot safely make that commit the live branch while
preserving a dirty checkout/index. The missing authenticated host provenance
record and the live checkout-coherence step make non-dry-run integration
**not ready**.

Reviewed authority set included `ARCHITECTURE.md`, `BUILDER_MACHINERY.md`, the
sibling Data repository's `DOCUMENT_AUTHORITY.md`, `CURRENT_STATE.md`,
`IMPLEMENTATION_PLAN.md`, coverage/economics, integrated product/data, source
evidence/publication, taxonomy and test-plan documents, plus the bridge,
launcher/watchdog, bounded-authority, schema, helper, validator, tests and
T4E timeout/overlay and independent-acceptance reports. No private raw
material, credentials, runtime state, cache, prompt or model output was added
to Git; this report is the only file written by this task.
