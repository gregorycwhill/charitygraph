# Gate 4 G4-O1C — P3b1 acceptance / P3b2 policy archaeology

## STOP — control precondition mismatch

This was a report-only stop. No tests, code, test files, providers, watchers,
processes, Git operations, or follow-on work were run or changed.

The required report path was absent before start. Branch and HEAD matched:

- branch: `gate3-cg406-remediation`
- HEAD: `1a11cef17c8577ccc5b49f86d0d4866ce57d9785`
- actual and supplied tree: `f1a61cfbe7d200eb6b432773de22e5000444cf54`

The required active v27 fence was not present in the repository or configured
runtime locations. The local fence inventory stopped at v6:

| fence | SHA-256 | fenced HEAD |
|---|---|---|
| `...-v4.json` | `f1e057ea390522efa835dd60154ed2ffe482583a58a99074e401ce62c44793ee` | `068561551a43bbeaa0e8347e4ddff1a5caa8044d` |
| `...-v5.json` | `edf1c6ed08d509cf09f92e4e596cd06d8b7f061c2bd9f5ad91d56eb82584f0d3` | `b14e377bdb2681f9257e0591561b648f0c334a7a` |
| `...-v6.json` | `57b40d6d7a6bc9c58c9b9a83a4029a4b194974c6c1b0d44ff2b73cd5cfe52a37` | `6c8901222726e985c71e2ee94404cadbbecddbcd` |

Expected active fence SHA-256: `19527b9c06d13b7b6508a7e2c99205eed7df45336117f3f7ee4d4a57dc14ea8b`.
The watcher count could not be independently confirmed: the read-only Windows
process query returned `Access denied`. No watcher was started or stopped.

The specified current-file hashes were verified before stopping:

- `src/charitygraph/phase5_governed_factory_integration.py`: `7140efddfbea3077ab74b715bf1cbee8454b928d1e3d984da8bca4811eb9ba8d`
- `tests/test_phase5_source_subject_provenance_p3b1.py`: `41bb23e49f22e63b0f5fc6fd0b69babf508389292e2b9469f2992e43f0866cae`
- pre-existing untracked `tests/test_phase5_governed_factory_rights.py`: `dce27d7f5334c9073d8118ab935c1c8063597ac70e28b8a0b43584cd34954281`

The pre-existing worktree baseline was preserved: 277 status entries (10
modified, 267 untracked) were observed before this report was created.

Per the task control rule, P3b1 acceptance and P3b2 policy archaeology are
not assessed. Re-run only after the exact active v27 fence and one-watcher
control facts are independently available in the permitted local control
surface.
