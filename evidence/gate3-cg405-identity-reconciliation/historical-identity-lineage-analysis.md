# CG405 identity-lineage reconciliation

## Method

This reconciliation used only identity provenance: the frozen CG405 benchmark identifier set, CG405's exact-ABN ACNC register bindings, the frozen CG405 manifest, the current governed 100-subject identity map, and the prior question-first universe manifest. No model responses, adjudications, oracle workspaces, source-content bodies, source-availability state, or question-designer output was read.

CG405 legacy IDs are static opaque `subject:` identifiers from `scoped_benchmark_v2.SUBJECT_IDS`. Their original identity binding is the documented CG405 rule: one ACNC search result whose ABN exactly equals the requested ABN and whose returned entity repeats that ABN. The ACNC entity UUID captured in that register event is retained in the crosswalk. Resolution joins legacy and current records only when their ABNs are exactly equal. Names never participate in matching.

## Result

Five legacy identities resolve one-to-one to current governed subjects and become new CG405 subject-exposure exclusions. They do not overlap the predecessor's 49 exclusions. Two legacy identities retain `UNKNOWN_EXPOSURE`: their historical ABNs have no exact current-pool match, and no permitted historical migration/crosswalk records establish a successor identity. The absence of an exact match is not treated as proof of no prior exposure. Consequently the 46 remaining candidates cannot be certified for independent selection, and no successor universe or external handoff is released.

## Inputs

The input hashes, exact crosswalk rows, and verification results are in the accompanying JSON artefacts. The frozen predecessor universe is not altered.
