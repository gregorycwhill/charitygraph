# CharityGraph archaeology summary (Tranche 2)

This is a metadata-only, read-only inventory at Builder `main` commit `42370a4e1978e2f0dadb9085cfe69536d6fb07d6`. Raw source, record, document, website, prompt, response, credential and absolute-private-path values are intentionally excluded.

## Configured roots

| Alias | Exists | Classification |
|---|---:|---|
| `archive:` | yes | private archive |
| `runtime:` | no | runtime/cache/staging |
| `data:` | yes | Data repository |

## Aggregate totals

- Files: **3,977**
- Bytes: **1,435,924,310**
- Unreadable/skipped files: **0**
- Symlink/reparse entries skipped: **0**
- Root handling: `archive:` and `data:` inspected; configured `runtime:` was absent and skipped without substitution.

## Counts by root, stage, source family, extension and sensitivity

### Root

| Key | Files | Bytes |
|---|---:|---:|
| `data` | 2,546 | 87,321,252 |
| `archive` | 1,431 | 1,348,603,058 |

### Historical stage

| Key | Files | Bytes |
|---|---:|---:|
| `phase2a` | 1,283 | 37,449,838 |
| `phase2b` | 1,055 | 39,400,339 |
| `unclassified` | 766 | 1,210,956,494 |
| `rc4` | 487 | 31,950,617 |
| `v0.5.0` | 350 | 6,682,017 |
| `reality-spike` | 23 | 543,807 |
| `golden` | 7 | 17,644 |
| `national-backbone` | 4 | 108,887,732 |
| `semantic` | 1 | 33,424 |
| `taxonomy` | 1 | 2,398 |

### Source family

| Key | Files | Bytes |
|---|---:|---:|
| `unknown` | 1,552 | 75,234,435 |
| `phase2a` | 1,283 | 37,449,838 |
| `acnc-public-profile` | 360 | 8,725,481 |
| `acnc-register` | 240 | 262,616 |
| `acnc-ais-detail` | 202 | 2,784,102 |
| `acnc-ais` | 172 | 149,110 |
| `web` | 95 | 17,378,985 |
| `reality-spike` | 17 | 530,113 |
| `report-extract` | 14 | 151,814 |
| `phase2b` | 13 | 2,009,636 |
| `regulator` | 9 | 1,050,745,163 |
| `reports` | 7 | 76,796,484 |
| `governed-inputs` | 6 | 13,694 |
| `national-backbone` | 4 | 108,887,732 |
| `annual-reports` | 3 | 54,805,107 |

### Extension

| Key | Files | Bytes |
|---|---:|---:|
| `.json` | 2,536 | 102,925,027 |
| `.md` | 694 | 3,062,428 |
| `[none]` | 579 | 2,421,378 |
| `.html` | 96 | 17,632,808 |
| `.parquet` | 21 | 3,271,226 |
| `.sample` | 14 | 26,788 |
| `.pdf` | 10 | 131,601,591 |
| `.csv` | 9 | 53,767,735 |
| `.jsonl` | 9 | 121,866,492 |
| `.idx` | 2 | 58,732 |
| `.pack` | 2 | 7,917,670 |
| `.rev` | 2 | 8,188 |
| `.zip` | 2 | 991,358,759 |
| `.mjs` | 1 | 5,488 |

### Sensitivity

| Key | Files | Bytes |
|---|---:|---:|
| `processed evidence` | 1,741 | 151,669,936 |
| `unknown` | 993 | 12,274,483 |
| `cache/runtime` | 560 | 8,711,242 |
| `public-safe metadata` | 543 | 62,894,142 |
| `private source` | 114 | 1,199,725,739 |
| `human decision` | 26 | 648,768 |

## Duplicate-content groups

9 groups have repeated SHA-256 content; exact groups and potential byte savings are in the machine inventory.

## Structured artefacts

2575 structured files were inspected for shape only. The machine inventory contains key unions, headers, counts, schema metadata and parse status, never record values.

## Model/LLM artefacts

259 files were identified by path or explicit metadata keys. Only metadata-field names are reported; prompts, evidence excerpts, responses and generated prose were not emitted.

## Human-decision/governed-input artefacts

26 files matched governed/review/decision/correction path signals; classification is path/metadata-only.

## References, orphan signals and recoverability

- Existing concrete code references: **7**
- Missing code references: **7**
- Apparently unreferenced directories: **275**; each is reported mechanically in `directory_inventory` and is not a deletion recommendation.
- Candidate irreplaceable evidence: `archive:sources/**`, `archive:governed-inputs/**`, `data:releases/**/source-records/**`.
- Candidate reproducible intermediates: `archive:processed/**`, `runtime:cache/**`, `runtime:staging/**`, `runtime:state/**`.
- Largest files/directories are included by alias, relative path, size and hash.

## Parse errors and limitations

No parse errors were recorded.

## Privacy check

- Reports contain no document/website body text, record values, prompt/response bodies, credentials, tokens, authorization headers, cookies, URL query strings, copied source files, or private absolute paths.
- Reports use only neutral aliases (`archive:`, `runtime:`, `data:`) and relative paths.
- No external service, model/API job, repository write, filesystem move, rename or deletion was performed.

## Uncertainties requiring design review

- Metadata and direct code references establish storage and path relationships, not semantic lineage beyond those references.
- Runtime may contain historical runs no longer referenced by current code.
- A path can be an active evidence store even when current code does not reference it.
- Values were intentionally not inspected where metadata/content boundaries were uncertain.

## Workspace rename and legacy separation

This section is classification-only. No rename, move, archive, or path rewrite was performed. Absolute private paths are deliberately redacted in these reports; file/line roles and neutral aliases identify the affected configuration.

### Active CharityGraph repositories and working directories

- `charitygraph/` - Builder; clean `main` at `42370a4e1978e2f0dadb9085cfe69536d6fb07d6`; remote `https://github.com/gregorycwhill/charitygraph.git`.
- `charitygraph-data/` - Data; branch `charitygraph-data-cutover-docs` at `00079d069f1ab92d31ebb9acab398d59c9a362d0`; remote `https://github.com/gregorycwhill/charitygraph-data.git`.
- `charitygraph-viewer/` - Viewer; branch `charitygraph-branding-followup` at `5f15be61296c1ece3730004e2693617b8b683f0d`; remote `https://github.com/gregorycwhill/charitygraph-viewer.git`; contains an untracked `debug.log`, intentionally preserved and not inventoried as source content.
- Each repository reports one current worktree; no workspace-level Git repository was used for this inventory.

### Configured absolute paths containing `CauseBase`

- The outer working directory itself is still the `CauseBase` directory and is the parent of all three active repositories.
- `src/charitygraph/config.py` derives the default archive and Data-repository paths from the workspace location, so both defaults contain the outer directory name.
- `charitygraph/.venv/pyvenv.cfg` embeds the former Builder path/name in its creation command, and the editable-install `.pth` embeds the former `causebase-builder` source path. This environment is therefore not safely portable across a rename.
- `charitygraph/.vscode/tasks.json` retains `CauseBase` task labels, a `causebase` CLI command, and a relative `../../work/staging` output convention. These are stale identifiers; the relative path is also not equivalent to the proposed `local-data` layout.
- The active configured runtime is `runtime:` at an external absolute location and does not contain `CauseBase`; it is currently absent. Moving it under the provisional target would be a separate configuration decision.
- The clean temporary test environment is outside the workspace and its editable `.pth` points at the current Builder directory; it would also need recreation or repair after a move.

### Evidence, superseded material, and retained legacy

- Active evidence stores by direct configuration/path signals: `archive:sources/**` (private source), `archive:processed/**` (processed evidence), `archive:governed-inputs/**` (governed inputs), and `data:releases/**/source-records/**` (release-bound processed evidence). `runtime:` is configured for cache/state/staging but does not exist at scan time.
- Directly outside the active repositories, `CauseBase_v01/`, `CauseBase_v02/`, and the two `CauseBase_*.zip` bundles appear superseded or historical by naming and age; their contents were not traversed for this task. The outer `CauseBase/` directory itself is current workspace infrastructure, not classified as superseded.
- `CauseBase` remains intentionally in immutable/provenance and compatibility material: `causebase_id`, the `causebase_builder` import/CLI compatibility surface, `CAUSEBASE_*` environment aliases, immutable v0.5 release/source identifiers, and explicit historical taxonomy/documentation references. These are not candidates for blind casing changes.

### Provisional old-path -> new-path mapping (not approved)

| Current classification | Provisional target | Conflict/status |
|---|---|---|
| outer workspace `CauseBase/` | `CharityGraph/` | Requires an explicit workspace move and all dependent-path updates. |
| `CauseBase/charitygraph/` | `CharityGraph/charitygraph/` | Repository move; `.venv`, VS Code tasks and editable installs require repair/recreation. |
| `CauseBase/charitygraph-data/` | `CharityGraph/charitygraph-data/` | Repository move; shared-document links and tools must be checked. |
| `CauseBase/charitygraph-viewer/` | `CharityGraph/charitygraph-viewer/` | Repository move; preserve untracked `debug.log` deliberately. |
| `CauseBase/archive/` | `CharityGraph/local-data/archive/` | Private evidence move; archive locators and any external tooling must be validated. |
| external `runtime:` | `CharityGraph/local-data/runtime/` | Not a mechanical rename: current configured root is absent and external; changing it alters runtime/state policy. |
| historical `CauseBase_v01/`, `CauseBase_v02/`, bundles | `CharityGraph/legacy/causebase-v0/` | Classification only; provenance and recoverability must be checked before any move. |

### Safe sequencing constraints surfaced by metadata

If the provisional target is later approved, the minimum safe sequence is: freeze and record all repository/worktree states; preserve the immutable release and private archive hashes; decide whether the external runtime remains external; update config defaults, editable environments, VS Code tasks and any external automation; move the three repositories and private roots as one planned operation; then run path resolution, tests, and metadata/hash checks before removing any old-path compatibility. No such operation was performed here.

