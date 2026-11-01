# CGDOC1 clean-head self-contained repair

Target: `gate3-cg406-remediation` at `396d4cd0470a843bb6aa42d9bf8aba9a4ab11cee`; fence v99 SHA256 `8a5e594fdef3210a4ceb4aaf7012915b372d6b9265ee1e73f7ecc0c7d1578190`.

## Direct diff

- `bridge/g4_doc_export_clean_adoption.py`: removed the imports of ingress-private `_has_reparse_attribute` and `_read_regular_file_no_follow`. Kept only committed public `DocExportError` and `FENCE_SCHEMA` imports. Added self-contained regular-file/reparse checks, descriptor identity checks, POSIX `O_NOFOLLOW`, and Windows `CreateFileW(...FILE_FLAG_OPEN_REPARSE_POINT...)` fail-closed opening. Existing parent-chain, traversal, dirty-baseline, manifest, canonical JSON, no-side-effect, and trust-boundary checks remain unchanged.
- `tests/test_bridge_doc_export_clean_adoption.py`: added a focused import probe that removes both private ingress names, imports the helper from a fresh module, and validates the existing synthetic clean target.
- `bridge/g4_doc_export_ingress.py` and all other pre-existing dirty/untracked paths were not edited, staged, or absorbed.

## Evidence and tests

- Before repair, importing the helper from a binary-safe archive of exact `HEAD` failed with `ImportError: cannot import name '_has_reparse_attribute'` from committed ingress.
- After repair, the helper imported successfully against the untouched committed ingress, and the clean-head regression passed.
- Focused command: `python -m pytest -q -p no:cacheprovider tests/test_bridge_doc_export_clean_adoption.py --basetemp <external C:\CharityGraph-runtime basetemp>` - 23 passed, 1 skipped (platform-dependent symlink creation); no pytest cache provider.
- `git diff --check` passed. No local commit was made.

## Remaining limitations

The Windows-positive reparse/junction path was not exercised on Windows by this run; the implementation is fail-closed but still needs native Windows-positive coverage. The helper does not prove trusted-host identity, operator authority, authenticated fence origin, or authenticated Google-Doc provenance. It remains a read-only attestation and does not adopt, activate, publish, or perform native Doc export integration.

No private evidence, source acquisition, provider/model/Drive access, credentials, publication, release, watcher/fence/ledger operation, or GitHub mutation was used.
