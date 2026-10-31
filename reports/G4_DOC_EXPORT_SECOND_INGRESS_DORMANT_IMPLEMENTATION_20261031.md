# G4-O1C dormant second-ingress implementation

Date: 2026-10-31 (Australia/Sydney)  
Baseline HEAD: `50a9bd1a9e6450a8cdc26a12acd4cef21f67964`  
Immutable v82 fence SHA-256: `b21f8fad1beb77073b116cd05b84014374b9d67c3699b5dbd442046aa974639e`

## Disposition

**Implemented locally; DORMANT, not ACTIVE.** This is a pure decoder and
validation seam. The live watcher still scans only the existing raw
`cg-g4-o1b-instruction-*.json` prefix. No watcher, launcher, Drive sync,
credential, provider, external-source, GitHub, publication, release or gate
operation was performed.

The available local Data authority checkout did not contain the specifically
named `BUILDER_TO_65K_PLAN.md`; no external fetch was made. The Builder-to-65k
state remains Gate 1 `CLOSED`, Gate 2 `ACTIVE`, 12% earned. This reliability
task is not Gate 4 progress.

## Bounded implementation

- `bridge/g4_doc_export_ingress.py` accepts only a direct child of a caller-
  supplied trusted artifacts directory whose name matches
  `cg-g4-o1b-doc-export-*.txt`.
- It accepts exactly one ASCII `CGDOC1:<unpadded-base64url>:<lowercase-sha256>`
  line, with either no BOM or exactly one UTF-8 BOM and no final newline.
- It decodes the exact embedded bytes, checks the full SHA-256, rejects an
  embedded BOM, and requires UTF-8 sorted-key compact canonical JSON with
  exactly one trailing LF.
- Duplicate keys, non-standard JSON constants, pretty JSON, CRLF or newline
  tampering, malformed wrappers, bad hashes, unsafe names, path traversal and
  external paths fail closed.
- `InstructionEnvelope.from_dict` remains the existing envelope validator.
  The adapter then requires the exact ChatGPT engineering authority, schema,
  operation, `luna-high` model, current repository/workspace/branch/HEAD,
  active fence identity and exact bounded allowlist. Existing
  `content_sha256` validation is therefore retained rather than replaced.
- `scan_doc_exports()` returns no paths by default and remains empty even when
  asked to scan while the module activation constant is false. `bridge.py`
  records the inert prefix and explicit inactive state; its live candidate
  method is unchanged. `managed_launcher.py` is unchanged.

## Tests

Cache-free, bytecode-free commands:

```text
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-o1c-doc-export-pytest-final tests/test_bridge_doc_export_ingress.py
16 passed in 3.85s

PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -p no:cacheprovider --basetemp C:\CharityGraph-runtime\cg-g4-o1c-bridge-pytest-final2 tests/test_bridge_doc_export_ingress.py tests/test_bridge_cutover.py
37 passed, 1 skipped in 48.53s
```

The tests cover BOM/no-BOM exact round trips, wrapper and embedded SHA/
identity, authority/schema/operation/model, current branch/HEAD/fence,
allowlist and report path, malformed/pretty/CRLF/newline-tampered/duplicate
JSON, payload tampering, path traversal and unsafe filenames, conflicting
instruction identity, existing single-claim ledger behaviour, dormant scanning,
and unchanged raw JSON candidate bytes. The one skipped existing test is the
explicit real Codex CLI rehearsal, which was not enabled.

## Code hashes

SHA-256 after the local implementation:

| Path | SHA-256 |
|---|---|
| `bridge/bridge.py` | `d087e171a0b5c5987dd666b6a3ac166241d971957fbad2840d372b950c9f4de0` |
| `bridge/g4_doc_export_ingress.py` | `70099b22642bc7c6cfc4aed161d0d3124d7e664384205732c18693d78c05b3a1` |
| `tests/test_bridge_doc_export_ingress.py` | `643a61e83b949fd83a2a3014e99c206df61e593952341006a72d55c029b7c5af` |

The report itself is private project documentation and contains no raw
instruction, prompt, model response, credential, runtime state or cache.
No local commit was created; the pinned HEAD and all pre-existing unrelated
dirty paths remain unchanged.

## Exact separate activation / end-to-end acceptance step

This implementation does **not** prove end-to-end pickup. Separate Product
Owner activation must first authorize a bridge integration that, on every
poll, obtains the current exact fence/branch/HEAD/dirty baseline through the
existing machinery, explicitly enables the scanner, reads only direct-child
`.txt` exports, passes the verified context to this decoder, and submits the
returned `InstructionEnvelope` through the existing `LocalAutonomousBridge`
ledger and claim path. That integration must retain the raw `.json` path and
must not add launcher/process control, URLs, credentials or external paths.

Then an independent host acceptance must materialise one native connected Doc
export in the existing private artifacts folder, run the already managed
launcher without manual intervention, verify one immutable ledger claim and
result, replay the same export as a no-op, and verify conflicting identity,
wrong fence/HEAD, dirty-baseline and non-allowlisted-path rejection. Until
that separately authorised integration and host acceptance occur, the second
ingress is DORMANT and no end-to-end claim is made.

